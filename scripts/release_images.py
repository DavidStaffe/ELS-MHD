"""Manual GHCR publication helpers. Never connect to or configure an installation."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

REPOSITORY = "DavidStaffe/ELS-MHD"
IMAGE_ROOT = "ghcr.io/davidstaffe/els-mhd-"
WORKFLOWS = ("update-tests.yaml", "onboarding-tests.yml", "installation.yml")


def validate_inputs(version, revision, actual_sha, ref, repository):
    if repository != REPOSITORY or ref != "refs/heads/main":
        raise ValueError("Release publication is restricted to this repository's main.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version):
        raise ValueError(
            "Version must contain 1-64 letters, digits, dots, underscores or hyphens."
        )
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or revision != actual_sha:
        raise ValueError(
            "Expected full revision must equal the dispatched main commit."
        )


def successful_run(runs, revision, workflow):
    matches = [
        r
        for r in runs
        if r["head_sha"] == revision
        and r["event"] == "push"
        and r["head_branch"] == "main"
        and r["path"] == f".github/workflows/{workflow}"
        and r["head_repository"]["full_name"] == REPOSITORY
    ]
    if not matches:
        raise ValueError(f"No main push verification for {workflow}.")
    latest = max(matches, key=lambda r: r["id"])
    if latest["status"] != "completed" or latest["conclusion"] != "success":
        raise ValueError(f"Latest verification is not successful: {workflow}.")
    return latest["id"]


def github(path):
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}{path}",
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
            "User-Agent": "ELS-MHD-release",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def verify_ci():
    revision = os.environ["REVISION"]
    validate_inputs(
        os.environ["VERSION"],
        revision,
        os.environ["GITHUB_SHA"],
        os.environ["GITHUB_REF"],
        os.environ["GITHUB_REPOSITORY"],
    )
    if os.environ.get("SCHEMA2_CONFIRMED") != "true":
        raise ValueError("Explicit schema-2 compatibility confirmation is required.")
    installation = None
    for workflow in WORKFLOWS:
        runs = github(
            f"/actions/workflows/{workflow}/runs?event=push&branch=main&head_sha={revision}&per_page=100"
        )
        run_id = successful_run(runs["workflow_runs"], revision, workflow)
        if workflow == "installation.yml":
            installation = run_id
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"installation_run={installation}\n")


def verify_archive(directory):
    directory = Path(directory)
    checksum = (directory / "els-mhd-arm64.sha256").read_text().strip()
    match = re.fullmatch(r"([0-9a-f]{64})  els-mhd-arm64.tar.gz", checksum)
    if not match:
        raise ValueError("Unexpected archive checksum format.")
    with (directory / "els-mhd-arm64.tar.gz").open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != match[1]:
        raise ValueError("ARM64 archive checksum mismatch.")


def docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout


def verify_image(image, revision):
    if (image.get("Os"), image.get("Architecture")) != ("linux", "arm64"):
        raise ValueError("Release image must be linux/arm64.")
    if (
        image.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.revision")
        != revision
    ):
        raise ValueError("Image revision differs from the approved main commit.")
    return image["Id"]


def manifest(version, revision, digests):
    if set(digests) != {"api", "web"}:
        raise ValueError("Exactly API and web images are required.")
    for digest in digests.values():
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("Invalid registry digest.")
    return {
        "version": version,
        "schema": 2,
        **{
            service: IMAGE_ROOT + service + "@" + digest
            for service, digest in digests.items()
        },
        "notes": "Reviewed schema-2 release from main " + revision,
    }


def publish():
    version, revision = os.environ["VERSION"], os.environ["REVISION"]
    validate_inputs(
        version,
        revision,
        os.environ["GITHUB_SHA"],
        os.environ["GITHUB_REF"],
        os.environ["GITHUB_REPOSITORY"],
    )
    # Verify BOTH loaded images before publishing either of them.
    images = {
        s: json.loads(docker("image", "inspect", f"els-mhd-{s}:arm64-test"))[0]
        for s in ("api", "web")
    }
    ids = {s: verify_image(image, revision) for s, image in images.items()}
    digests = {}
    for service in ("api", "web"):
        # No mutable latest/version tag: each workflow attempt has a unique tag.
        tag = f"{IMAGE_ROOT}{service}:{version}-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
        docker("tag", ids[service], tag)
        docker("push", tag)
        refs = json.loads(docker("image", "inspect", tag))[0].get("RepoDigests", [])
        prefix = IMAGE_ROOT + service + "@"
        candidates = [r.removeprefix(prefix) for r in refs if r.startswith(prefix)]
        if len(set(candidates)) != 1:
            raise ValueError("Registry digest is missing or ambiguous.")
        digest = candidates[0]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("Invalid published digest.")
        pinned = prefix + digest
        docker("pull", "--platform", "linux/arm64", pinned)
        remote = json.loads(docker("image", "inspect", pinned))[0]
        if verify_image(remote, revision) != ids[service]:
            raise ValueError("Published image differs from the tested image.")
        digests[service] = digest
    output = Path("release-output")
    output.mkdir()
    (output / "approved-release.json").write_text(
        json.dumps(manifest(version, revision, digests), indent=2) + "\n"
    )
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "commit": revision,
                "image_ids": ids,
                "installation_run": os.environ["INSTALLATION_RUN"],
                "publication_run": os.environ["GITHUB_SERVER_URL"]
                + "/"
                + REPOSITORY
                + "/actions/runs/"
                + os.environ["GITHUB_RUN_ID"],
            },
            indent=2,
        )
        + "\n"
    )
    with (output / "SHA256SUMS").open("w") as checksums:
        for name in ("approved-release.json", "provenance.json"):
            checksums.write(
                hashlib.sha256((output / name).read_bytes()).hexdigest()
                + "  "
                + name
                + "\n"
            )


if __name__ == "__main__":
    if sys.argv[1:] == ["verify-ci"]:
        verify_ci()
    elif sys.argv[1:] == ["verify-archive"]:
        verify_archive("release-input")
    elif sys.argv[1:] == ["publish"]:
        publish()
    else:
        raise SystemExit("Use verify-ci, verify-archive or publish.")

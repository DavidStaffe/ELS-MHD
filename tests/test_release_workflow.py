"""Release gates and publication roundtrip without registry, Docker or secrets."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_images", Path(__file__).resolve().parents[1] / "scripts/release_images.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = "a" * 40


class ReleaseTests(unittest.TestCase):
    def test_schema_confirmation_and_all_ci_runs_required_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "outputs"
            env = {
                "VERSION": "v2",
                "REVISION": SHA,
                "GITHUB_SHA": SHA,
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_REPOSITORY": release.REPOSITORY,
                "SCHEMA2_CONFIRMED": "false",
                "GITHUB_OUTPUT": str(output),
            }
            with patch.dict(os.environ, env), patch.object(release, "github") as api:
                with self.assertRaises(ValueError):
                    release.verify_ci()
                api.assert_not_called()
                self.assertFalse(output.exists())

            def response(path):
                workflow = path.split("/workflows/")[1].split("/")[0]
                return {
                    "workflow_runs": [
                        self.run_record(path=f".github/workflows/{workflow}")
                    ]
                }

            env["SCHEMA2_CONFIRMED"] = "true"
            with patch.dict(os.environ, env), patch.object(
                release, "github", side_effect=response
            ) as api:
                release.verify_ci()
                self.assertEqual(api.call_count, 3)
                self.assertEqual(output.read_text(), "installation_run=1\n")
            output.unlink()
            with patch.dict(os.environ, env), patch.object(
                release, "github", return_value={"workflow_runs": []}
            ):
                with self.assertRaises(ValueError):
                    release.verify_ci()
                self.assertFalse(output.exists())

    def test_inputs_reject_wrong_repository_branch_revision_and_injection(self):
        valid = [
            "v2026.10.29-incident.1",
            SHA,
            SHA,
            "refs/heads/main",
            release.REPOSITORY,
        ]
        release.validate_inputs(*valid)
        for index, value in [
            (0, "x;echo hacked"),
            (0, "x" * 65),
            (1, "a" * 12),
            (2, "b" * 40),
            (3, "refs/heads/feature"),
            (4, "fork/ELS-MHD"),
        ]:
            args = valid.copy()
            args[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                release.validate_inputs(*args)

    def run_record(self, **changes):
        return {
            "id": 1,
            "head_sha": SHA,
            "event": "push",
            "head_branch": "main",
            "path": ".github/workflows/installation.yml",
            "head_repository": {"full_name": release.REPOSITORY},
            "status": "completed",
            "conclusion": "success",
            **changes,
        }

    def test_only_latest_successful_main_push_counts(self):
        good = self.run_record()
        self.assertEqual(release.successful_run([good], SHA, "installation.yml"), 1)
        for changed in [
            {"event": "pull_request"},
            {"head_sha": "b" * 40},
            {"path": ".github/workflows/other.yml"},
            {"head_branch": "other"},
            {"head_repository": {"full_name": "fork/ELS-MHD"}},
            {"status": "in_progress"},
            {"conclusion": "failure"},
        ]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                release.successful_run(
                    [self.run_record(**changed)], SHA, "installation.yml"
                )
        with self.assertRaises(ValueError):
            release.successful_run(
                [good, self.run_record(id=2, status="in_progress")],
                SHA,
                "installation.yml",
            )

    def test_archive_checksum_and_filename_are_strict(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "els-mhd-arm64.tar.gz").write_bytes(b"synthetic")
            digest = hashlib.sha256(b"synthetic").hexdigest()
            checksum = root / "els-mhd-arm64.sha256"
            checksum.write_text(digest + "  els-mhd-arm64.tar.gz\n")
            release.verify_archive(root)
            for text in [
                digest + "  ../elsewhere",
                "0" * 64 + "  els-mhd-arm64.tar.gz",
            ]:
                checksum.write_text(text)
                with self.assertRaises(ValueError):
                    release.verify_archive(root)

    def test_image_architecture_and_revision_are_checked(self):
        good = {
            "Id": "image",
            "Os": "linux",
            "Architecture": "arm64",
            "Config": {"Labels": {"org.opencontainers.image.revision": SHA}},
        }
        self.assertEqual(release.verify_image(good, SHA), "image")
        for key, value in [
            ("Architecture", "amd64"),
            ("Os", "windows"),
            ("Config", {}),
        ]:
            image = copy.deepcopy(good)
            image[key] = value
            with self.assertRaises(ValueError):
                release.verify_image(image, SHA)

    def test_manifest_matches_agent_schema_and_never_uses_tags(self):
        digests = {"api": "sha256:" + "1" * 64, "web": "sha256:" + "2" * 64}
        result = release.manifest("v2", SHA, digests)
        self.assertEqual(set(result), {"version", "api", "web", "schema", "notes"})
        self.assertEqual(result["schema"], 2)
        self.assertEqual(result["api"], release.IMAGE_ROOT + "api@" + digests["api"])
        with self.assertRaises(ValueError):
            release.manifest("v2", SHA, {"api": "latest", "web": digests["web"]})

    def test_publish_writes_manifest_only_after_both_digest_roundtrips(self):
        images = {
            s: {
                "Id": s,
                "Os": "linux",
                "Architecture": "arm64",
                "Config": {"Labels": {"org.opencontainers.image.revision": SHA}},
                "RepoDigests": [release.IMAGE_ROOT + s + "@sha256:" + str(i) * 64],
            }
            for i, s in enumerate(("api", "web"), start=1)
        }
        commands = []

        def docker(*args):
            commands.append(args)
            if args[:2] == ("image", "inspect"):
                service = "api" if "api" in args[2] else "web"
                return json.dumps([images[service]])
            return ""

        env = {
            "VERSION": "v2",
            "REVISION": SHA,
            "GITHUB_SHA": SHA,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": release.REPOSITORY,
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
            "INSTALLATION_RUN": "456",
            "GITHUB_SERVER_URL": "https://github.com",
        }
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, env
        ), patch.object(release, "docker", docker):
            try:
                os.chdir(folder)
                release.publish()
                result = json.loads(
                    Path("release-output/approved-release.json").read_text()
                )
                self.assertEqual(result["schema"], 2)
                self.assertEqual(len([c for c in commands if c[0] == "push"]), 2)
                self.assertEqual(len([c for c in commands if c[0] == "pull"]), 2)
                self.assertTrue(Path("release-output/SHA256SUMS").exists())
                # A failed web push must leave no approval candidate, even if
                # the API image was already published successfully.
                for file in Path("release-output").iterdir():
                    file.unlink()
                Path("release-output").rmdir()

                def failed_push(*args):
                    if args[0] == "push" and "web" in args[1]:
                        raise RuntimeError("Simulated registry failure")
                    return docker(*args)

                with patch.object(release, "docker", failed_push), self.assertRaises(
                    RuntimeError
                ):
                    release.publish()
                self.assertFalse(Path("release-output").exists())

                # A pinned pull must resolve to exactly the tested image ID.
                def changed_pull(*args):
                    result = docker(*args)
                    if args[:2] == ("image", "inspect") and "@" in args[2]:
                        image = json.loads(result)[0]
                        image["Id"] = "unexpected-image"
                        return json.dumps([image])
                    return result

                with patch.object(release, "docker", changed_pull), self.assertRaises(
                    ValueError
                ):
                    release.publish()
                self.assertFalse(Path("release-output").exists())
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()

"""Synthetic fault injection; no Docker, network, patient records or secrets."""

import hashlib
import importlib.util
import json
from pathlib import Path
import threading
from unittest.mock import Mock

import pytest


def test_identity_floor_refuses_legacy_install_even_offline(engine):
    obj = engine
    (obj.root / "config/identity-required").write_text("2")
    with pytest.raises(agent.Refused):
        agent.Engine.install(obj)


def test_identity_floor_requires_explicit_migrated_release_schema(engine):
    obj = engine
    (obj.root / "config/identity-required").write_text("2")
    with pytest.raises(agent.Refused):
        obj.approved()
    release = agent.read(obj.root / "config/approved-release.json")
    release["schema"] = 2
    agent.atomic(obj.root / "config/approved-release.json", release)
    assert obj.approved()["schema"] == 2

spec = importlib.util.spec_from_file_location(
    "host_agent", Path(__file__).resolve().parents[2] / "deploy/agent/agent.py"
)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    for directory in ("config", "runtime", "update-public", "backups"):
        (tmp_path / directory).mkdir()
    obj = agent.Engine(tmp_path)
    current = {
        "version": "v1",
        "api": "sha256:" + "1" * 64,
        "web": "sha256:" + "2" * 64,
        "schema": 1,
        "notes": "",
    }
    target = {
        "version": "v2",
        "api": "ghcr.io/davidstaffe/els-mhd-api@sha256:" + "3" * 64,
        "web": "ghcr.io/davidstaffe/els-mhd-web@sha256:" + "4" * 64,
        "schema": 1,
        "notes": "Synthetic test release",
    }
    agent.atomic(obj.state_dir / "active.json", current)
    agent.atomic(tmp_path / "config/approved-release.json", target)
    (tmp_path / "runtime/compose.yaml").write_text("services: {}")
    agent.atomic(
        obj.state_dir / "bundle.json",
        {"sha256": hashlib.sha256(b"services: {}").hexdigest()},
    )
    salt = b"test-only-salt"
    encoded = hashlib.scrypt(b"test-password", salt=salt, n=16384, r=8, p=1).hex()
    (tmp_path / "config/update-password-hash").write_text(
        f"scrypt${salt.hex()}${encoded}"
    )
    monkeypatch.setattr(obj, "health", Mock())
    monkeypatch.setattr(obj, "safe", Mock())
    monkeypatch.setattr(obj, "backup", Mock())
    monkeypatch.setattr(obj, "install", Mock())
    monkeypatch.setattr(obj, "compose", Mock(return_value=b"container"))
    monkeypatch.setattr(obj, "run", Mock(return_value=b"image-id"))
    return obj


def prepare(obj, phase="queued"):
    obj.state = {
        "id": "synthetic",
        "state": phase,
        "before": obj.active(),
        "started_at": 0,
    }
    obj.save(phase)
    obj.gate(True)


def execute(obj):
    obj.mutex.acquire()
    obj.execute(obj.approved())


def test_only_exact_approved_repository_digests(engine):
    release = engine.approved()
    for field, value in [
        ("api", "ghcr.io/attacker/api:latest"),
        ("web", "$(id)"),
        ("schema", 2),
        ("version", "../../file"),
    ]:
        bad = {**release, field: value}
        agent.atomic(engine.root / "config/approved-release.json", bad)
        with pytest.raises(agent.Refused):
            engine.approved()
    agent.atomic(
        engine.root / "config/approved-release.json", {**release, "command": "id"}
    )
    with pytest.raises(agent.Refused):
        engine.approved()


def test_password_limit_persists_restart_and_no_secret_in_audit(engine):
    for _ in range(5):
        with pytest.raises(agent.Refused, match="ungültig"):
            engine.authenticate("wrong-secret")
    restarted = agent.Engine(engine.root)
    with pytest.raises(agent.Refused, match="viele"):
        restarted.authenticate("test-password")
    assert "wrong-secret" not in (engine.state_dir / "audit.jsonl").read_text()


def test_unknown_action_and_parallel_operations_refused(engine):
    with pytest.raises(agent.Refused):
        dispatch(engine, {"action": "shell", "command": "id"})
    engine.mutex.acquire()
    with pytest.raises(agent.Refused, match="läuft"):
        dispatch(
            engine, {"action": "apply", "password": "test-password", "version": "v2"}
        )
    engine.mutex.release()


def test_release_confirmation_must_match(engine):
    with pytest.raises(agent.Refused, match="geändert"):
        dispatch(
            engine,
            {"action": "apply", "password": "test-password", "version": "old-approval"},
        )
    assert not engine.mutex.locked()


def test_success_persists_checkpoint_and_reboot_state(engine):
    prepare(engine)
    before = engine.active()
    execute(engine)
    assert engine.state["state"] == "complete"
    assert engine.active()["version"] == "v2"
    assert agent.read(engine.state_dir / "previous.json") == before
    assert agent.Engine(engine.root).active() == engine.active()
    assert agent.read(engine.root / "update-public/status.json") == {
        "maintenance": False
    }
    engine.compose.assert_any_call("stop", "-t", "60", "web", "api")
    assert engine.safe.call_count == 2
    engine.backup.assert_called_once()


@pytest.mark.parametrize("fault", ["safe", "network", "backup", "health"])
def test_failures_restore_previous_state(engine, fault):
    prepare(engine)
    before = engine.active()
    if fault == "safe":
        engine.safe.side_effect = agent.Refused("Aktive Einsätze")
    elif fault == "network":
        engine.run.side_effect = agent.Refused("network")
    elif fault == "backup":
        engine.backup.side_effect = agent.Refused("missing USB or invalid backup")
    else:
        engine.health.side_effect = [None, agent.Refused("bad health"), None]
    execute(engine)
    assert engine.active() == before
    assert engine.state["state"] == "failed"
    assert engine.state["error"]
    assert not engine.mutex.locked()
    if fault in ("safe", "network"):
        engine.install.assert_not_called()  # Do not disrupt active incidents!
        engine.backup.assert_not_called()


@pytest.mark.parametrize(
    "phase", ["queued", "verify", "backup", "deploy", "health", "recover"]
)
def test_power_loss_recovers_before_new_requests(engine, phase):
    prepare(engine, phase)
    before = engine.state["before"]
    agent.atomic(engine.state_dir / "active.json", engine.approved())
    # queued/verify cannot yet have changed images, model only reachable states.
    if phase in ("queued", "verify"):
        agent.atomic(engine.state_dir / "active.json", before)
    engine.recover()
    assert engine.state["state"] == "failed"
    assert engine.active() == before


def test_failed_recovery_stays_locked_for_ssh(engine):
    prepare(engine, "deploy")
    engine.install.side_effect = agent.Refused("failed recovery")
    engine.recover()
    assert engine.state["state"] == "recovery_required"
    assert agent.read(engine.root / "update-public/status.json")["maintenance"]
    assert not engine.status()["can_install"]


def test_missing_checkpoint_refuses_rollback(engine):
    with pytest.raises(FileNotFoundError):
        dispatch(
            engine, {"action": "rollback", "password": "test-password", "version": "v0"}
        )
    assert not engine.mutex.locked()


def test_compose_drift_fails_before_container_changes(engine):
    prepare(engine)
    (engine.root / "runtime/compose.yaml").write_text("changed")
    execute(engine)
    engine.compose.assert_not_called()
    engine.install.assert_not_called()


def test_compose_pins_images_and_never_builds_or_recreates_db(engine, monkeypatch):
    monkeypatch.setattr(engine, "compose", agent.Engine.compose.__get__(engine))
    monkeypatch.setattr(engine, "install", agent.Engine.install.__get__(engine))
    engine.install()
    command = engine.run.call_args.args[0]
    assert command[-2:] == ["api", "web"]
    assert "--no-deps" in command and "--no-build" in command
    assert command[command.index("--pull") + 1] == "never"
    pinned = agent.read(engine.state_dir / "images.json")
    assert pinned["services"]["api"]["image"] == engine.active()["api"]


def test_backup_failure_and_stale_archives_fail_closed(engine, monkeypatch):
    prepare(engine)
    monkeypatch.setattr(engine, "backup", agent.Engine.backup.__get__(engine))
    with pytest.raises(agent.Refused, match="frisches"):
        engine.backup()
    engine.run.assert_called_once()


def test_failed_update_retains_existing_rollback_target(engine):
    previous = {**engine.active(), "version": "v0"}
    agent.atomic(engine.state_dir / "previous.json", previous)
    prepare(engine)
    engine.state["before_previous"] = previous
    engine.health.side_effect = [None, agent.Refused("candidate failed"), None]
    execute(engine)
    assert agent.read(engine.state_dir / "previous.json") == previous
    assert engine.active()["version"] == "v1"


def test_rollback_uses_same_backup_and_verification_path(engine):
    previous = {**engine.active(), "version": "v0"}
    agent.atomic(engine.state_dir / "previous.json", previous)
    prepare(engine)
    engine.state["before_previous"] = previous
    engine.mutex.acquire()
    engine.execute(previous)
    assert engine.active()["version"] == "v0"
    assert agent.read(engine.state_dir / "previous.json")["version"] == "v1"
    engine.backup.assert_called_once()
    assert engine.safe.call_count == 2


def test_real_backup_path_requires_test_restore_and_external_verification(
    engine, monkeypatch
):
    prepare(engine)
    archive = engine.root / "backups/els-mhd-20260101-000000.archive.gz"
    archive.write_bytes(b"synthetic-archive-placeholder")
    monkeypatch.setattr(engine, "backup", agent.Engine.backup.__get__(engine))
    monkeypatch.setattr(engine, "db", Mock(return_value=b"true"))
    engine.backup()
    commands = [call.args[0] for call in engine.run.call_args_list]
    assert any("--dryRun" in " ".join(cmd) for cmd in commands)
    assert any("--nsTo=" in " ".join(cmd) for cmd in commands)
    assert commands[-1] == ["/usr/local/lib/els-mhd/backup-external.sh"]
    assert (
        agent.read(engine.state_dir / "backup-synthetic.json")["sha256"]
        == hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    assert "dropDatabase" in engine.db.call_args.args[0]


def test_invalid_backup_never_reaches_external_step(engine, monkeypatch):
    prepare(engine)
    (engine.root / "backups/els-mhd-20260101-000000.archive.gz").write_bytes(b"broken")
    monkeypatch.setattr(engine, "backup", agent.Engine.backup.__get__(engine))
    engine.run.side_effect = [b"", agent.Refused("invalid archive")]
    with pytest.raises(agent.Refused):
        engine.backup()
    assert engine.run.call_count == 2


def dispatch(obj, request):
    if request.get("action") in ("apply", "rollback"):
        path = obj.state_dir / "previous.json"
        target = (
            obj.approved()
            if request["action"] == "apply"
            else (agent.read(path) if path.exists() else {})
        )
        request.setdefault("release_id", agent.release_id(target))
    return obj.dispatch(request)


def test_release_fingerprint_binds_same_version_to_exact_images(engine):
    original = engine.approved()
    changed = {**original, "notes": "changed after check"}
    agent.atomic(engine.root / "config/approved-release.json", changed)
    with pytest.raises(agent.Refused, match="geändert"):
        dispatch(
            engine,
            {
                "action": "apply",
                "password": "test-password",
                "version": original["version"],
                "release_id": agent.release_id(original),
            },
        )


def test_rollback_never_pulls_local_checkpoint_from_registry(engine):
    previous = {**engine.active(), "version": "v0"}
    prepare(engine)
    engine.state["action"] = "rollback"
    engine.mutex.acquire()
    engine.execute(previous)
    assert engine.state["state"] == "complete"
    assert not any(
        call.args[0][:2] == ["docker", "pull"] for call in engine.run.call_args_list
    )
    engine.run.assert_any_call(["docker", "image", "inspect", previous["api"]])


def test_missing_release_approval_is_normal_and_keeps_rollback_available(engine):
    (engine.root / "config/approved-release.json").unlink()
    agent.atomic(
        engine.state_dir / "previous.json", {**engine.active(), "version": "v0"}
    )
    for check in (False, True):
        result = engine.status(check=check)
        assert result["configured"] is True
        assert result["update_available"] is False
        assert result["can_install"] is False
        assert result["can_rollback"] is True
    assert "kein Release" in engine.status(check=True)["message"]
    with pytest.raises(agent.Refused, match="kein Release"):
        engine.approved()


def test_polling_retains_approved_update_availability(engine):
    assert engine.status(check=True)["can_install"] is True
    assert engine.status(check=False)["can_install"] is True
    assert engine.status()["available_version"] == "v2"

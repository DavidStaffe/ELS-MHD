"""Installer planning contracts; never operate a host or a database."""

import copy
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

agent_dir = Path(__file__).resolve().parents[2] / "deploy/agent"
sys.path.insert(0, str(agent_dir))
import migrate_identity as migration
import bootstrap

sys.path.remove(str(agent_dir))


@pytest.fixture
def frozen():
    return {
        "services": {
            "db": {
                "image": "mongo:7",
                "volumes": [{"source": "db", "target": "/data/db"}],
                "environment": {"MONGO_INITDB_ROOT_PASSWORD": "synthetic-only"},
            },
            "api": {
                "image": "old-api",
                "environment": {
                    "MONGO_URL": "mongodb://synthetic@db",
                    "DB_NAME": "els_mhd",
                    "ELS_SETTINGS_ENCRYPTION_KEY": "synthetic-legacy-key",
                    "DIVERA_API_KEY": "synthetic-key",
                    "ELS_ADMIN_PASSWORD": "obsolete",
                },
                "volumes": [],
            },
            "web": {
                "image": "old-web",
                "ports": [{"published": "8080", "target": 80, "host_ip": "127.0.0.1"}],
            },
        },
        "volumes": {"db": {"name": "els-mhd_mongodb_data"}},
    }


def test_upgrade_preserves_db_and_legacy_keys_and_input(frozen, tmp_path):
    original = copy.deepcopy(frozen)
    new = migration.bundle(
        frozen, tmp_path, "10.0.0.1", {"api": "new-api", "web": "new-web"}
    )
    assert frozen == original
    assert new["services"]["db"] == original["services"]["db"]
    assert new["volumes"]["db"] == original["volumes"]["db"]
    env = new["services"]["api"]["environment"]
    assert env["MONGO_URL"] == "mongodb://synthetic@db"
    assert env["ELS_SETTINGS_ENCRYPTION_KEY"] == "synthetic-legacy-key"
    assert env["DIVERA_API_KEY"] == "synthetic-key"
    assert "ELS_ADMIN_PASSWORD" not in env
    assert env["CORS_ORIGINS"] == "https://10.0.0.1"
    assert new["volumes"]["identity_state"]["name"] == "els-mhd_identity_state"
    assert new["services"]["web"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert new["services"]["web"]["ports"][1]["published"] == "443"
    mounts = new["services"]["web"]["volumes"]
    assert all(
        "ca.key" not in m["source"] and not m["source"].endswith("/tls") for m in mounts
    )
    assert any(m["target"] == "/run/tls/server.key" for m in mounts)


def test_existing_identity_volume_is_not_replaced(frozen, tmp_path):
    frozen["services"]["api"]["volumes"] = [
        {"type": "volume", "source": "preserve", "target": "/var/lib/els"}
    ]
    frozen["volumes"]["preserve"] = {"external": True, "name": "existing-identity"}
    new = migration.bundle(frozen, tmp_path, "10.0.0.1", {"api": "a", "web": "b"})
    assert "identity_state" not in new["volumes"]
    assert new["volumes"]["preserve"] == frozen["volumes"]["preserve"]


def test_rejects_readonly_identity_state(frozen, tmp_path):
    frozen["services"]["api"]["volumes"] = [
        {
            "type": "volume",
            "source": "state",
            "target": "/var/lib/els",
            "read_only": True,
        }
    ]
    with pytest.raises(ValueError, match="persistentes"):
        migration.bundle(frozen, tmp_path, "10.0.0.1", {"api": "a", "web": "b"})


@pytest.mark.parametrize(
    "value",
    ["https://10.0.0.1", "x\nsubjectAltName=DNS:evil", "x;touch bad", "../../bad"],
)
def test_hostname_rejects_config_and_command_injection(value):
    with pytest.raises(ValueError):
        migration.hostname(value)


def test_legacy_bootstrap_refuses_identity_source_before_touching_runtime(
    tmp_path, monkeypatch
):
    (tmp_path / "backend/core").mkdir(parents=True)
    (tmp_path / "backend/core/identity.py").write_text("")
    monkeypatch.setattr(bootstrap, "SOURCE", tmp_path)
    monkeypatch.setattr(bootstrap, "check_source", Mock())
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(bootstrap.sys, "argv", ["bootstrap.py"])
    engine = Mock()
    monkeypatch.setattr(bootstrap, "Engine", engine)
    with pytest.raises(RuntimeError, match="migrate_identity"):
        bootstrap.main()
    engine.assert_not_called()

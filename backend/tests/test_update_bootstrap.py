"""Bootstrap smoke isolation checks; no Pi, Docker or real credentials."""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock
import pytest

agent_dir = Path(__file__).resolve().parents[2] / "deploy/agent"
sys.path.insert(0, str(agent_dir))
import bootstrap

sys.path.remove(str(agent_dir))


class Response:
    status = 200

    def __init__(self, value):
        import json

        self.value = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.value


def test_smoke_stack_is_independent_and_cleaned_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    engine = Mock()
    engine.run.side_effect = [b"", b"0.0.0.0:12345", b""]
    with pytest.raises(RuntimeError, match="endpoint"):
        bootstrap.smoke(engine, {"api": "sha256:a", "web": "sha256:b"}, "mongo:test")
    cleanup = engine.run.call_args.args[0]
    assert cleanup[3].startswith("els-mhd-smoke-")
    assert cleanup[-2:] == ["down", "--volumes"]
    assert cleanup[3] != "els-mhd"
    assert list(tmp_path.iterdir()) == []


def test_generated_admin_hash_is_memory_hard_and_salted():
    first = bootstrap.password_hash("synthetic-only-password")
    second = bootstrap.password_hash("synthetic-only-password")
    assert first.startswith("scrypt$") and first != second
    assert "synthetic-only-password" not in first


def test_smoke_accepts_only_local_random_port(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    engine = Mock()
    captured = {}

    def run(command, **kwargs):
        if "up" in command:
            captured.update(json.loads(Path(command[5]).read_text()))
        return b"127.0.0.1:54321" if "port" in command else b""

    engine.run.side_effect = run
    monkeypatch.setattr(
        bootstrap,
        "urlopen",
        Mock(
            side_effect=[
                Response({"app": "ELS MHD"}),
                Response({"configured": False}),
                bootstrap.HTTPError("http://local", 401, "", {}, None),
                bootstrap.HTTPError("http://local", 401, "", {}, None),
                bootstrap.HTTPError("http://local", 401, "", {}, None),
                Response({"token": "synthetic-token"}),
                bootstrap.HTTPError("http://local", 503, "", {}, None),
            ]
        ),
    )
    bootstrap.smoke(
        engine, {"api": "synthetic-api", "web": "synthetic-web"}, "mongo:test"
    )
    assert captured["services"]["api"]["environment"]["DB_NAME"] == "synthetic_only"
    assert "ELS_UPDATE_SOCKET" not in captured["services"]["api"]["environment"]
    assert captured["services"]["web"]["ports"] == ["127.0.0.1::80"]
    assert list(tmp_path.iterdir()) == []

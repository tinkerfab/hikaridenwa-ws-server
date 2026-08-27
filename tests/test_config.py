import os

import pytest

from app.config import build_config, load_external_env_file

REQUIRED_ENV = {
    "HGW_HOST": "192.168.1.1",
    "SIP_EXTENSION": "2",
    "SIP_AUTH_USER": "2",
    "SIP_PASSWORD": "secret",
}


def test_build_config_applies_defaults():
    config = build_config(REQUIRED_ENV)

    assert config.hgw_host == "192.168.1.1"
    assert config.hgw_port == 5060
    assert config.sip_register_expires == 600
    assert config.local_bind_ip == "0.0.0.0"
    assert config.ring_timeout_s == 30
    assert config.http_port == 8080
    assert config.data_dir == "./data"


def test_build_config_overrides_defaults():
    env = {
        **REQUIRED_ENV,
        "HGW_PORT": "5061",
        "RING_TIMEOUT_S": "45",
        "HTTP_PORT": "9000",
        "DATA_DIR": "/var/lib/hikaridenwa-ws-server",
    }

    config = build_config(env)

    assert config.hgw_port == 5061
    assert config.ring_timeout_s == 45
    assert config.data_dir == "/var/lib/hikaridenwa-ws-server"
    assert config.http_port == 9000


@pytest.mark.parametrize("missing_key", list(REQUIRED_ENV.keys()))
def test_build_config_raises_on_missing_required_key(missing_key):
    env = {k: v for k, v in REQUIRED_ENV.items() if k != missing_key}

    with pytest.raises(RuntimeError, match=missing_key):
        build_config(env)


def test_build_config_reports_all_missing_keys_at_once():
    with pytest.raises(RuntimeError) as exc_info:
        build_config({})

    message = str(exc_info.value)
    for key in REQUIRED_ENV:
        assert key in message


def test_load_external_env_file_raises_helpful_error_when_missing(tmp_path):
    missing_path = tmp_path / "does-not-exist.env"

    with pytest.raises(RuntimeError, match="app.env.example"):
        load_external_env_file(str(missing_path))


def test_load_external_env_file_populates_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("HGW_HOST", raising=False)
    env_file = tmp_path / "app.env"
    env_file.write_text("HGW_HOST=10.0.0.1\n")

    load_external_env_file(str(env_file))

    assert os.environ["HGW_HOST"] == "10.0.0.1"


def test_load_external_env_file_does_not_override_existing_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("HGW_HOST", "already-set")
    env_file = tmp_path / "app.env"
    env_file.write_text("HGW_HOST=from-file\n")

    load_external_env_file(str(env_file))

    assert os.environ["HGW_HOST"] == "already-set"

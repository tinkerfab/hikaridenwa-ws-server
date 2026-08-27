from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

REQUIRED_KEYS = ("HGW_HOST", "SIP_EXTENSION", "SIP_AUTH_USER", "SIP_PASSWORD")

_DEFAULTS = {
    "HGW_PORT": "5060",
    "SIP_REGISTER_EXPIRES": "600",
    "LOCAL_BIND_IP": "0.0.0.0",
    "RING_TIMEOUT_S": "30",
    "HTTP_PORT": "8080",
    "DATA_DIR": "./data",
}


@dataclass(frozen=True)
class Config:
    hgw_host: str
    hgw_port: int
    sip_extension: str
    sip_auth_user: str
    sip_password: str
    sip_register_expires: int
    local_bind_ip: str
    ring_timeout_s: int
    http_port: int
    data_dir: str


def load_external_env_file(path: str) -> None:
    """Load SIP credentials from an operator-supplied file outside the repo/image.

    Never overrides variables already present in the environment (e.g. docker-compose's
    `environment:` block), matching python-dotenv's default `override=False` behavior.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise RuntimeError(
            f"Config file not found at {path}. Copy secrets/app.env.example to "
            "that path and fill in your HGW credentials (see README)."
        )
    load_dotenv(file_path, override=False)


def build_config(env: Mapping[str, str]) -> Config:
    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    if missing:
        raise RuntimeError(
            "Missing required config keys: " + ", ".join(missing) + ". "
            "Set them in secrets/app.env (see secrets/app.env.example)."
        )

    def get(key: str) -> str:
        return env.get(key) or _DEFAULTS[key]

    return Config(
        hgw_host=env["HGW_HOST"],
        hgw_port=int(get("HGW_PORT")),
        sip_extension=env["SIP_EXTENSION"],
        sip_auth_user=env["SIP_AUTH_USER"],
        sip_password=env["SIP_PASSWORD"],
        sip_register_expires=int(get("SIP_REGISTER_EXPIRES")),
        local_bind_ip=get("LOCAL_BIND_IP"),
        ring_timeout_s=int(get("RING_TIMEOUT_S")),
        http_port=int(get("HTTP_PORT")),
        data_dir=get("DATA_DIR"),
    )

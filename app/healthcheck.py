from __future__ import annotations

import os
import re
import sys
import urllib.request

DEFAULT_PORT = "8080"
DEFAULT_CONFIG_FILE = "/app/config/app.env"

_HTTP_PORT_LINE = re.compile(r"^\s*HTTP_PORT\s*=\s*(\S+)\s*$")


def resolve_http_port(env: dict | None = None) -> str:
    """Find the port the app is actually listening on.

    Mirrors app/config.py's own precedence: an OS-level HTTP_PORT (e.g. set
    via docker-compose's `environment:` block) wins; otherwise fall back to
    reading it out of the mounted secrets file directly, since this
    healthcheck runs as a separate shell-level process that — unlike the
    Python app itself — never calls load_dotenv() on it.
    """
    env = env if env is not None else os.environ
    port = env.get("HTTP_PORT")
    if port:
        return port

    config_path = env.get("CONFIG_FILE", DEFAULT_CONFIG_FILE)
    try:
        with open(config_path, encoding="utf-8") as f:
            for line in f:
                match = _HTTP_PORT_LINE.match(line)
                if match:
                    return match.group(1)
    except OSError:
        pass

    return DEFAULT_PORT


def main() -> int:
    port = resolve_http_port()
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2).read()
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

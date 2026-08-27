from app.healthcheck import resolve_http_port


def test_resolve_http_port_uses_os_env_when_set():
    assert resolve_http_port({"HTTP_PORT": "9000"}) == "9000"


def test_resolve_http_port_falls_back_to_config_file(tmp_path):
    config_file = tmp_path / "app.env"
    config_file.write_text("HGW_HOST=192.168.1.1\nHTTP_PORT=8090\n")

    port = resolve_http_port({"CONFIG_FILE": str(config_file)})

    assert port == "8090"


def test_resolve_http_port_defaults_when_nothing_found(tmp_path):
    config_file = tmp_path / "app.env"
    config_file.write_text("HGW_HOST=192.168.1.1\n")

    port = resolve_http_port({"CONFIG_FILE": str(config_file)})

    assert port == "8080"


def test_resolve_http_port_defaults_when_config_file_missing(tmp_path):
    missing = tmp_path / "does-not-exist.env"

    port = resolve_http_port({"CONFIG_FILE": str(missing)})

    assert port == "8080"


def test_resolve_http_port_os_env_wins_over_config_file(tmp_path):
    config_file = tmp_path / "app.env"
    config_file.write_text("HTTP_PORT=8090\n")

    port = resolve_http_port({"HTTP_PORT": "9999", "CONFIG_FILE": str(config_file)})

    assert port == "9999"

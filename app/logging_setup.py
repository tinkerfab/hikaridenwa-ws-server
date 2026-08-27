from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

APP_LOG_MAX_BYTES = 10_000_000
APP_LOG_BACKUP_COUNT = 5


def setup_logging(data_dir: str) -> None:
    """Configure application-wide logging to a rotating file under data_dir,
    in addition to the existing console output (so `docker logs` keeps
    working as before).

    Unlike the dashboard-server variant this project split off from, there
    is no dedicated call-history log here — clients own call history now
    (see README's "アーキテクチャ" section), so the server only keeps
    operational logs for its own troubleshooting.
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    app_handler = logging.handlers.RotatingFileHandler(
        data_path / "app.log",
        maxBytes=APP_LOG_MAX_BYTES,
        backupCount=APP_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root_logger.addHandler(app_handler)

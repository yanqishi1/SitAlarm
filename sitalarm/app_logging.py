from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_path = path / ".sitalarm_write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        return True
    except Exception:
        return False


def get_preferred_log_dir(app_name: str = "SitAlarm") -> Path:
    """
    Prefer writing logs next to the executable (install directory).
    If not writable (common inside a signed .app bundle), fall back to user dirs.
    """
    candidates: list[Path] = []

    try:
        candidates.append(Path(sys.argv[0]).resolve().parent)
    except Exception:
        pass

    candidates.extend(
        [
            Path.home() / ".sitalarm",
            Path.home() / "Library" / "Logs" / app_name,
        ]
    )

    for d in candidates:
        if _is_writable_dir(d):
            return d

    return Path.cwd()


def configure_logging(app_name: str = "SitAlarm") -> Path:
    """
    Configure root logger with a rotating file handler.
    Returns the log file path.
    """
    log_dir = get_preferred_log_dir(app_name)
    log_path = log_dir / f"{app_name.lower()}.log"

    if getattr(configure_logging, "_configured", False):
        return log_path

    level_name = os.environ.get("SITALARM_LOG_LEVEL", "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # When running from a terminal, also log to stderr for convenience.
    try:
        if sys.stderr is not None and getattr(sys.stderr, "isatty", lambda: False)():
            console = logging.StreamHandler()
            console.setLevel(level)
            console.setFormatter(fmt)
            root.addHandler(console)
    except Exception:
        pass

    configure_logging._configured = True  # type: ignore[attr-defined]
    logging.getLogger(__name__).info("日志已初始化，路径：%s", log_path)
    return log_path


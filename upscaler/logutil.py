"""Zero-config structured logging to JSONL file.

Bypasses Python's logging module and gunicorn entirely — just
appends one JSON line per call. Safe to use before/during
any logging setup or from within gunicorn workers.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_log_lock = threading.Lock()

_LOG_PATH = os.environ.get("LOG_DIR")
if not _LOG_PATH:
    _LOG_PATH = os.path.join(os.getcwd(), "logs")

_APP_LOG = Path(_LOG_PATH) / "app.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_log(level: str, msg: str, **extra) -> None:
    """Write one structured log line to LOG_DIR/app.jsonl.

    Example:
        app_log("INFO", "Upscaling", in_w=800, in_h=1200, size_mb=1.5)
    """
    record = {
        "ts": _now_iso(),
        "level": level,
        "app": "upscaler",
        "msg": msg,
    }
    record.update(extra)

    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))

    try:
        _APP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _log_lock:
            with open(_APP_LOG, "a") as f:
                f.write(line + "\n")
    except Exception:
        pass  # never crash on logging

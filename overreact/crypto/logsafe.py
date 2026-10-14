"""Logging that cannot leak secrets: values of KEY/SECRET/TOKEN/SESSION/HASH env vars and signature= are redacted."""
import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from overreact.env import load_env

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SECRET_NAME = re.compile(r"KEY|SECRET|TOKEN|SESSION|HASH|PASSWORD", re.I)
SIGNATURE = re.compile(r"(signature=)[^&\s]+", re.I)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clip(text: str, n: int = 200) -> str:
    """Untrusted text for logs: control chars removed, truncated."""
    return CONTROL.sub(" ", text)[:n]


class Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if record.exc_info:  # tracebacks are formatted after filters run: fold them in here so they get redacted too
            msg += "\n" + logging.Formatter().formatException(record.exc_info)
            record.exc_info, record.exc_text = None, None
        msg = SIGNATURE.sub(r"\1***", msg)
        for name, value in os.environ.items():
            if SECRET_NAME.search(name) and len(value) >= 6:
                msg = msg.replace(value, "***")
        record.msg, record.args = msg, None
        return True


def setup(name: str, log_dir: Path = LOG_DIR) -> logging.Logger:
    """File log data/crypto_<name>.log (rotated); also stdout when there is one (pythonw has none)."""
    load_env()
    log = logging.getLogger(f"crypto.{name}")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_dir / f"crypto_{name}.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    for h in handlers:
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        h.addFilter(Redact())
        log.addHandler(h)
    return log

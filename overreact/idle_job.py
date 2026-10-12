"""Heavy batch work for when the PC is idle (Windows task `overreact-idle`).

Order: SEC filing list -> 8-K texts -> LLM over filings -> LLM over new news. Every step skips work
already done, so the task can be killed when the user comes back and resumes on the next idle.
While running, Windows is asked not to sleep; the request ends with the process.
Usage: python -m overreact.idle_job
"""
import ctypes
import sys
from datetime import datetime

from overreact import edgar, extract
from overreact.db import DB_PATH

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def keep_awake() -> None:
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def main() -> None:
    if sys.stdout is None:  # started by pythonw from Task Scheduler: log to file
        sys.stdout = sys.stderr = open(DB_PATH.parent / "idle_job.log", "a", buffering=1, encoding="utf-8")
    keep_awake()
    print(f"{datetime.now():%Y-%m-%d %H:%M} idle job start")
    edgar.update()
    edgar.fetch_texts()
    extract.run_filings(share_gpu=True)
    extract.run(limit=2000)
    print(f"{datetime.now():%Y-%m-%d %H:%M} idle job done")


if __name__ == "__main__":
    main()

"""崩溃日志：捕获未处理的主线程 / 子线程异常，写入 crash.log 便于排查。"""

import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path


def install_crash_handler(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    crash_file = log_dir / "crash.log"

    def _write(tag: str, exc_type, exc_value, exc_tb) -> None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        trace = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )
        try:
            with crash_file.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[{timestamp}] {tag}\n{trace}\n")
        except OSError:
            pass

    def _sys_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _write("uncaught", exc_type, exc_value, exc_tb)

    def _thread_hook(args):
        _write("thread", args.exc_type, args.exc_value, args.exc_tb)

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook

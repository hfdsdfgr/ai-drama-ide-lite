"""崩溃日志测试。"""

import sys

from app.core.crash_log import install_crash_handler


def test_crash_handler_writes_log(tmp_path):
    install_crash_handler(tmp_path)
    try:
        raise ValueError("boom-crash")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    crash = tmp_path / "crash.log"
    assert crash.exists()
    content = crash.read_text(encoding="utf-8")
    assert "ValueError" in content
    assert "boom-crash" in content


def test_crash_handler_thread(tmp_path):
    import threading
    from types import SimpleNamespace

    install_crash_handler(tmp_path)
    errors = []

    def work():
        try:
            raise RuntimeError("thread-crash")
        except RuntimeError:
            errors.append(sys.exc_info())

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    args = SimpleNamespace(
        exc_type=errors[0][0],
        exc_value=errors[0][1],
        exc_tb=errors[0][2],
        thread=thread,
    )
    threading.excepthook(args)

    crash = tmp_path / "crash.log"
    assert crash.exists()
    assert "thread-crash" in crash.read_text(encoding="utf-8")

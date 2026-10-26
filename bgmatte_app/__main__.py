"""python -m bgmatte_app 으로 실행합니다 (.app 런처도 같은 명령을 사용)."""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

log = logging.getLogger("bgmatte_app")


def _set_mac_app_name(name: str) -> None:
    """macOS 메뉴 막대에 'python' 대신 앱 이름이 보이도록 번들 이름을 지정합니다 (pyobjc가 있을 때만)."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle  # type: ignore

        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = name
    except Exception:
        pass


def fatal_box(title: str, text: str) -> None:
    """콘솔 창이 없는 실행(pythonw)에서도 사용자가 볼 수 있게 오류 창을 띄웁니다. 윈도우 외에는 stderr에 씁니다."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # MB_ICONERROR
            return
        except Exception:
            pass
    print(f"[{title}] {text}", file=sys.stderr)


def setup_logging(path: Optional[Path] = None) -> Optional[Path]:
    """로그 설정. 윈도우에서는 콘솔 창 없이(pythonw) 실행하므로 stdout/stderr가 없습니다 —
    로그 파일에 쓰도록 연결해, 라이브러리가 print/경고를 내도 죽지 않고 기록이 남게 합니다.
    다른 OS(맥 .app 런처)는 런처가 출력을 같은 로그 파일로 모아 주므로 건드리지 않습니다."""
    handlers = []
    log_file: Optional[Path] = None
    if sys.platform == "win32" or path is not None:
        from .config import log_path

        log_file = path or log_path()
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(
                logging.handlers.RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            )
            if sys.stderr is None or sys.stdout is None:  # 콘솔 없음
                stream = open(log_file, "a", encoding="utf-8", buffering=1)
                if sys.stdout is None:
                    sys.stdout = stream
                if sys.stderr is None:
                    sys.stderr = stream
        except OSError:
            log_file = None
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers or [logging.NullHandler()],
        force=True,
    )
    try:
        if sys.stderr is not None:
            faulthandler.enable(file=sys.stderr)  # 네이티브 크래시도 로그에 남김
    except Exception:
        pass
    return log_file


def main() -> int:
    log_file = setup_logging()
    log.info("BG Matte 시작 (python %s)", sys.version.split()[0])

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        fatal_box(
            "BG Matte",
            "PySide6를 불러올 수 없습니다.\n\n"
            "install_windows.bat 을 다시 실행해 설치를 마쳐 주세요.\n"
            f"원본 오류: {exc}" + (f"\n\n로그: {log_file}" if log_file else ""),
        )
        return 1

    from .config import APP_NAME, load_config, log_path
    from .ui.main_window import MainWindow
    from .ui import theme

    _set_mac_app_name(APP_NAME)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(theme.build_style())
    from .ui.widgets import app_icon

    app.setWindowIcon(app_icon())  # Dock/창 아이콘

    shown = {"done": False}

    def excepthook(exc_type, exc, tb):
        log.error("처리되지 않은 예외", exc_info=(exc_type, exc, tb))
        if shown["done"]:
            return
        shown["done"] = True
        QMessageBox.critical(
            None,
            APP_NAME,
            f"예기치 않은 오류가 발생했습니다.\n\n{exc}\n\n로그: {log_path()}",
        )

    sys.excepthook = excepthook

    cfg, warning = load_config()
    window = MainWindow(cfg, startup_warning=warning)
    window.show()
    return app.exec()


def _run() -> int:
    try:
        return main()
    except Exception as exc:  # 창이 뜨기 전의 오류: 콘솔이 없어도 보이게 합니다
        log.exception("시작 중 오류")
        from .config import log_path

        fatal_box("BG Matte", f"시작하지 못했습니다.\n\n{exc}\n\n로그: {log_path()}")
        return 1


if __name__ == "__main__":
    sys.exit(_run())

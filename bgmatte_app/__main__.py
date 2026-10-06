"""python -m bgmatte_app 으로 실행합니다 (.app 런처도 같은 명령을 사용)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

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


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        print(
            "[오류] PySide6를 불러올 수 없습니다. 아래 명령으로 설치한 뒤 다시 실행해 주세요.\n"
            "  pip install -r requirements-app.txt\n"
            f"  원본 오류: {exc}",
            file=sys.stderr,
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


if __name__ == "__main__":
    sys.exit(main())

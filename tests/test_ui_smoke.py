"""메인 창 동작 확인 (오프스크린 Qt + 가짜 카메라/모델). 실제 키 입력과 버튼 클릭을 흉내 냅니다.

주의: 이벤트 대기에는 QTest.qWait 대신 processEvents + sleep을 씁니다. qWait는 대기 중
파이썬 GIL을 놓지 않아 워커 스레드가 멈춘 것처럼 보이는 문제가 있습니다 (앱 본체의
app.exec()에는 해당하지 않음).
"""

import time

import cv2
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from bgmatte_app import messages  # noqa: E402
from bgmatte_app.config import Config  # noqa: E402
from bgmatte_app.ui import main_window as mw  # noqa: E402
from bgmatte_app.ui.dialogs import IntroDialog, SettingsDialog  # noqa: E402
from bgmatte_app.ui import theme  # noqa: E402
from bgmatte_app.ui.widgets import NoticeBanner  # noqa: E402
from bgmatte_app.worker import PipelineWorker  # noqa: E402
from fakes import FakeCamera, FakeMatter, synthetic_frame  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.build_style())
    return app


def pump(qapp, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def wait_until(qapp, predicate, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return False


class Harness:
    def __init__(self, qapp, tmp_path, n_bg=3, with_bgr=True, auth="authorized", camera_kwargs=None, theme_name="dark"):
        self.qapp = qapp
        self.tmp = tmp_path
        self.folder = tmp_path / "backgrounds"
        self.folder.mkdir()
        for i in range(1, n_bg + 1):
            cv2.imwrite(str(self.folder / f"{i:02d}_bg.png"), synthetic_frame(64, 48))
        self.bgr = tmp_path / "bgr.png"
        if with_bgr:
            cv2.imwrite(str(self.bgr), synthetic_frame(64, 48))
        self.cfg = Config(
            bgr=str(self.bgr),
            backgrounds_dir=str(self.folder),
            legacy_background=str(tmp_path / "none.png"),
            countdown_seconds=1,
            average_frames=3,
            seen_intro=True,
            theme=theme_name,
        )
        self.saved = []
        self.opened = []
        self.matters = []
        self.auth = auth
        self.auth_requests = []
        self.camera_kwargs = camera_kwargs or {}
        self.window = mw.MainWindow(
            self.cfg,
            worker_factory=self._factory,
            auth_status=lambda: self.auth,
            auth_request=self.auth_requests.append,
            save=lambda c: self.saved.append(c.last_background),
            open_url=self.opened.append,
            auto_start=False,
        )
        self.window.show()
        self.window.activateWindow()
        pump(qapp, 50)

    def _factory(self, cfg, backgrounds):
        matter = FakeMatter()
        self.matters.append(matter)
        return PipelineWorker(
            cfg, backgrounds, matter_factory=lambda _c: matter,
            camera_factory=lambda _i: FakeCamera(**self.camera_kwargs),
        )

    # -- 조작 -----------------------------------------------------------------
    def key(self, key):
        QTest.keyClick(self.window, key)
        pump(self.qapp, 30)

    def until(self, predicate, timeout=6.0):
        return wait_until(self.qapp, predicate, timeout)

    def start_running(self):
        self.window.start_pipeline()
        assert self.until(lambda: self.window._state == "running" and self.window.preview.has_frame())

    def banner_buttons(self):
        return {
            b.text(): b
            for b in self.window.banner.findChildren(QPushButton)
            if b.text() not in ("✕",) and b.isVisibleTo(self.window.banner)
        }

    def history_titles(self):
        w = self.window.history
        return [w.item(i).text() for i in range(w.count())]

    def close(self):
        self.window.close()
        pump(self.qapp, 30)


@pytest.fixture
def harness(qapp, tmp_path):
    made = []

    def make(**kwargs):
        h = Harness(qapp, tmp_path, **kwargs)
        made.append(h)
        return h

    yield make
    for h in made:
        h.close()
    theme.set_theme("dark")  # 테마는 전역 상태라서 다음 테스트에 새지 않게 되돌림
    qapp.setStyleSheet(theme.build_style())


# ---------------------------------------------------------------- 시작
def test_starts_and_shows_running_state(harness):
    h = harness()
    h.start_running()
    w = h.window
    assert w.status_label.text() == "실행 중"
    assert [w.steps._labels[i].property("step") for i in range(4)] == ["done"] * 4
    assert [b.isEnabled() for b in w.bus._buttons] == [True] * 3 + [False] * 6
    assert w.bus._buttons[0].property("current") is True
    assert w.val_device.text() == "CPU" and w.val_resolution.text() == "64×48"
    assert w.btn_toggle.text() == "정지" and w.btn_capture.isEnabled()
    assert w.bg_count.text() == "3개 중 1번"


def test_shortcut_list_is_shown_in_panel(harness):
    h = harness()
    texts = {label.text() for label in h.window.side.findChildren(type(h.window.bg_name)) if label.text()}
    for needle in ("배경 번호로 바로 전환", "빈 배경 촬영 (촬영 중에는 취소)",
                   "알파 매트 함께 보기", "전체 화면", "사용 안내"):
        assert needle in texts, needle
    assert "이전 / 다음 배경" not in texts, "방향키 안내는 없어졌습니다"
    caps = {label.text() for label in h.window.side.findChildren(type(h.window.bg_name))}
    assert "Space" in caps and "B" not in caps and "←" not in caps


# ---------------------------------------------------------------- 배경 번호
def test_number_keys_switch_background_and_arrows_do_nothing(harness):
    h = harness()
    h.start_running()
    h.key(Qt.Key.Key_3)
    assert h.until(lambda: h.window._current_bg == 3)
    assert h.window.bus._buttons[2].property("current") is True
    assert h.window.bus._buttons[0].property("current") is False
    h.key(Qt.Key.Key_Left)  # 방향키는 더 이상 배경을 바꾸지 않음
    h.key(Qt.Key.Key_Right)
    pump(h.qapp, 150)
    assert h.window._current_bg == 3
    h.key(Qt.Key.Key_1)
    assert h.until(lambda: h.window._current_bg == 1)
    assert h.window.bg_name.text() == "01_bg.png"
    assert h.matters[0].bg_calls[-1].name == "01_bg.png"


def test_clicking_a_bus_button_switches_background(harness):
    h = harness()
    h.start_running()
    h.window.bus._buttons[1].click()
    assert h.until(lambda: h.window._current_bg == 2)
    assert h.window.bg_count.text() == "3개 중 2번"


def test_pressing_a_number_with_no_such_background_explains(harness):
    h = harness()
    h.start_running()
    h.key(Qt.Key.Key_7)
    assert any("7번 배경이 없습니다" in t for t in h.history_titles())
    assert h.window.banner.code == "bg_invalid"
    assert h.window._current_bg == 1


def test_number_before_ready_says_so(harness):
    h = harness()
    h.key(Qt.Key.Key_2)
    assert any("실행 중에만" in t for t in h.history_titles())


def test_last_background_is_remembered_on_close(harness):
    h = harness()
    h.start_running()
    h.key(Qt.Key.Key_2)
    assert h.until(lambda: h.window._current_bg == 2)
    h.close()
    assert h.saved and h.saved[-1] == 2


def test_alpha_key_toggles_status_text(harness):
    h = harness()
    h.start_running()
    h.key(Qt.Key.Key_A)
    assert h.until(lambda: h.window.val_alpha.text().startswith("켜짐"))
    h.key(Qt.Key.Key_A)
    assert h.until(lambda: h.window.val_alpha.text() == "꺼짐")


# ---------------------------------------------------------------- 빈 배경 촬영
def test_missing_bgr_guides_then_space_key_captures(harness):
    h = harness(with_bgr=False)
    w = h.window
    w.start_pipeline()
    assert h.until(lambda: w._state == "waiting_bg")
    assert w.status_label.text() == "배경 촬영 필요"
    assert w.banner.code == "bgr_missing" and "배경 촬영 (스페이스)" in h.banner_buttons()
    assert w.preview._title == "", "배너가 같은 안내를 하는 동안 카드로 반복하면 안 됩니다"
    assert w.btn_capture.property("emphasis") is True and w.btn_toggle.property("demoted") is True

    h.key(Qt.Key.Key_Space)
    assert h.until(lambda: w._state == "capturing")
    assert w.banner.code is None, "촬영이 시작되면 이전 안내는 걷어야 합니다"
    assert w.btn_capture.text() == "촬영 취소"
    assert h.until(lambda: w.preview._countdown is not None)
    assert h.until(lambda: w._state == "running", timeout=10)
    assert h.bgr.exists()
    assert w.banner.code == "capture_saved"
    assert w.preview._countdown is None
    assert w.btn_capture.property("emphasis") is False


def test_banner_capture_button_starts_capture(harness):
    h = harness(with_bgr=False)
    h.window.start_pipeline()
    assert h.until(lambda: h.window._state == "waiting_bg")
    h.banner_buttons()["배경 촬영 (스페이스)"].click()
    assert h.until(lambda: h.window._state == "capturing")


def test_escape_cancels_capture_without_closing(harness):
    h = harness()
    h.cfg.countdown_seconds = 10
    h.start_running()
    h.key(Qt.Key.Key_Space)
    assert h.until(lambda: h.window._state == "capturing")
    h.key(Qt.Key.Key_Escape)
    assert h.until(lambda: h.window._state == "running")
    assert h.window.isVisible(), "촬영 취소 Esc가 앱을 닫으면 안 됩니다"
    assert any("취소" in t for t in h.history_titles())


def test_capture_button_not_available_before_camera_is_ready(harness):
    h = harness()
    h.key(Qt.Key.Key_Space)
    assert any("지금은 배경을 촬영할 수 없습니다" in t for t in h.history_titles())
    assert not h.window.btn_capture.isEnabled()


# ---------------------------------------------------------------- 오류 안내와 조치 버튼
def test_no_background_images_offers_open_folder_then_restart(harness):
    h = harness(n_bg=0)
    w = h.window
    w.start_pipeline()
    assert h.until(lambda: w._state == "error")
    assert w.banner.code == "bg_none" and w.banner.level == messages.Level.ERROR
    buttons = h.banner_buttons()
    assert set(buttons) == {"배경 폴더 열기", "다시 시작"}
    assert w.bg_name.text() == "배경 이미지가 없습니다"
    assert w.btn_toggle.text() == "다시 시작"
    assert not any(b.isEnabled() for b in w.bus._buttons)

    buttons["배경 폴더 열기"].click()
    assert h.opened and h.opened[-1] == QUrl.fromLocalFile(str(h.folder))

    cv2.imwrite(str(h.folder / "01_new.png"), synthetic_frame(64, 48))
    h.banner_buttons()["다시 시작"].click()
    assert h.until(lambda: w._state == "running")
    assert w.banner.code is None
    assert w.bg_count.text() == "1개 중 1번"


def test_camera_permission_denied_points_to_system_settings(harness):
    h = harness(auth="denied")
    w = h.window
    w.start_pipeline()
    assert w._state == "error" and w._worker is None
    assert w.banner.code == "camera_permission_denied"
    assert w.steps._labels[0].property("step") == "error"
    h.banner_buttons()["시스템 설정 열기"].click()
    assert h.opened[-1].toString().endswith("Privacy_Camera")


def test_camera_permission_prompt_then_granted(harness):
    h = harness(auth="not_determined")
    w = h.window
    w.start_pipeline()
    assert w._worker is None and w.btn_toggle.text() == "정지"
    assert w.banner.code == "camera_permission_pending"
    assert len(h.auth_requests) == 1
    h.auth_requests[0](True)  # 사용자가 '허용'을 누른 상황
    assert h.until(lambda: w._state == "running")


def test_camera_permission_prompt_then_denied(harness):
    h = harness(auth="not_determined")
    w = h.window
    w.start_pipeline()
    h.auth_requests[0](False)
    assert h.until(lambda: w._state == "error")
    assert w.banner.code == "camera_permission_denied"


def test_stop_while_waiting_for_permission_ignores_late_answer(harness):
    h = harness(auth="not_determined")
    w = h.window
    w.start_pipeline()
    w.btn_toggle.click()  # 팝업 응답 전에 정지
    assert w._state == "stopped" and w.banner.code is None and w.btn_toggle.text() == "시작"
    h.auth_requests[0](True)  # 뒤늦게 허용이 와도 시작하면 안 됨
    pump(h.qapp, 200)
    assert w._state == "stopped" and w._worker is None


def test_camera_open_failure_shows_settings_action(harness):
    h = harness(camera_kwargs={"opened": False})
    h.window.start_pipeline()
    assert h.until(lambda: h.window._state == "error")
    assert h.window.banner.code == "camera_open_failed"
    assert "설정 열기" in h.banner_buttons()


# ---------------------------------------------------------------- 시작/정지/재시작
def test_stop_and_start_buttons(harness):
    h = harness()
    h.start_running()
    w = h.window
    w.btn_toggle.click()
    assert w._state == "stopped" and w._worker is None
    assert w.btn_toggle.text() == "시작" and not w.btn_capture.isEnabled()
    assert not w.preview.has_frame()
    w.btn_toggle.click()
    assert h.until(lambda: w._state == "running")


def test_restart_ignores_late_events_from_old_worker(harness):
    h = harness()
    h.start_running()
    first = h.window._worker
    h.window.restart_pipeline()
    assert h.window._worker is not first
    assert h.until(lambda: h.window._state == "running")
    pump(h.qapp, 400)
    assert h.window._state == "running", "이전 워커의 'stopped' 이벤트가 새 상태를 덮어쓰면 안 됩니다"
    assert not first.isRunning()


def test_close_stops_the_worker(harness):
    h = harness()
    h.start_running()
    worker = h.window._worker
    h.close()
    assert not worker.isRunning()


# ---------------------------------------------------------------- 설정
def test_settings_save_restarts_pipeline_with_new_values(harness, monkeypatch):
    h = harness()
    h.start_running()
    first = h.window._worker

    class StubDialog:
        def __init__(self, cfg, parent=None, camera_probe=None):
            self.cfg = cfg

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_config(self):
            from dataclasses import replace

            return replace(self.cfg, camera_index=2, countdown_seconds=3)

    monkeypatch.setattr(mw, "SettingsDialog", StubDialog)
    h.window.open_settings()
    assert h.window.cfg.camera_index == 2 and h.window.cfg.countdown_seconds == 3
    assert h.saved, "저장되어야 합니다"
    assert h.window._worker is not first
    assert h.until(lambda: h.window._state == "running")


def test_settings_cancel_restarts_only_if_it_was_running(harness, monkeypatch):
    h = harness()
    h.start_running()

    class CancelDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(mw, "SettingsDialog", CancelDialog)
    h.window.open_settings()
    assert h.until(lambda: h.window._state == "running"), "돌고 있었다면 취소해도 다시 돌아야 합니다"
    h.window.stop_pipeline()
    h.window.open_settings()
    assert h.window._state == "stopped", "사용자가 정지해 둔 상태는 그대로 두어야 합니다"


def test_settings_dialog_roundtrip_and_custom_values(qapp):
    cfg = Config(camera_index=3, camera_width=1600, camera_height=900, countdown_seconds=7)
    dialog = SettingsDialog(cfg, camera_probe=lambda: [(0, False, ""), (1, True, "1920×1080")])
    assert dialog.camera_index.currentData() == 3
    assert "1600 × 900" in dialog.resolution.currentText()
    assert dialog.countdown.currentText() == "7초"
    out = dialog.result_config()
    assert (out.camera_index, out.camera_width, out.camera_height, out.countdown_seconds) == (3, 1600, 900, 7)

    dialog.resolution.setCurrentIndex(dialog.resolution.findData("1920x1080"))
    dialog.countdown.setCurrentIndex(dialog.countdown.findData(10))
    out = dialog.result_config()
    assert (out.camera_width, out.camera_height, out.countdown_seconds) == (1920, 1080, 10)


def test_find_cameras_selects_first_working_one(qapp):
    dialog = SettingsDialog(Config(camera_index=0), camera_probe=lambda: [(0, False, ""), (1, True, "1280×720")])
    dialog._find_cameras()
    assert dialog.camera_index.currentData() == 1
    assert "0번  열 수 없음" in dialog.camera_result.text() and "1번  열림 1280×720" in dialog.camera_result.text()


def test_intro_dialog_checkbox_only_when_requested(qapp):
    assert IntroDialog(show_checkbox=False).dont_show.isHidden()
    assert not IntroDialog(show_checkbox=True).dont_show.isHidden()


# ---------------------------------------------------------------- 배너 규칙
def test_error_banner_is_not_replaced_by_milder_notices(qapp):
    banner = NoticeBanner({})
    banner.show_notice(messages.camera_lost())
    assert not banner.show_notice(messages.bg_invalid(7, 3))
    assert banner.code == "camera_lost"
    assert banner.show_notice(messages.camera_open_failed(1))  # 오류끼리는 최신이 이김
    assert banner.code == "camera_open_failed"


def test_sticky_banner_has_no_auto_hide_but_others_do(qapp):
    banner = NoticeBanner({})
    banner.show_notice(messages.bgr_missing(__import__("pathlib").Path("bgr.png")))
    assert not banner._timer.isActive()
    banner.show_notice(messages.bg_invalid(7, 3))
    assert banner._timer.isActive()
    banner.clear()
    banner.show_notice(messages.camera_lost())
    assert not banner._timer.isActive(), "오류는 사용자가 닫을 때까지 유지"


def test_history_is_capped_and_newest_first(harness):
    h = harness()
    for i in range(70):
        h.window._add_notice(messages.bg_invalid(i + 1, 3))
    assert h.window.history.count() == mw.HISTORY_LIMIT
    assert "70번" in h.history_titles()[0]


# ---------------------------------------------------------------- 레이아웃 / 테마
def test_control_buttons_sit_below_the_preview(harness):
    h = harness()
    w = h.window
    w.show()
    h.qapp.processEvents()
    top = lambda widget: widget.mapTo(w, widget.rect().topLeft()).y()  # noqa: E731
    assert top(w.btn_toggle) >= w.preview.mapTo(w, w.preview.rect().bottomLeft()).y()
    assert top(w.btn_capture) == top(w.btn_toggle) == top(w.btn_settings)
    assert not w.side.isAncestorOf(w.btn_toggle), "오른쪽 패널에는 더 이상 버튼이 없어야 합니다"


def test_info_sections_use_smaller_text_than_the_background_section(harness):
    h = harness()
    w = h.window
    w.show()
    h.qapp.processEvents()
    assert w.val_fps.font().pixelSize() in (-1, 11) or w.val_fps.fontInfo().pixelSize() <= 11
    assert w.bg_name.fontInfo().pixelSize() > w.val_fps.fontInfo().pixelSize()


def test_theme_switch_applies_saves_and_recolors(harness):
    h = harness()
    w = h.window
    assert theme.current().name == "dark"
    h.notices_before = w.history.count()
    w._add_notice(messages.bg_invalid(7, 3))
    saved = []
    w._save = lambda cfg: saved.append(cfg.theme)
    w._theme_buttons["light"].click()
    assert theme.current().name == "light" and w.cfg.theme == "light" and saved == ["light"]
    assert w._theme_buttons["light"].isChecked() and not w._theme_buttons["dark"].isChecked()
    assert theme.current().CONSOLE in h.qapp.styleSheet()
    key = w.history.item(0).data(Qt.ItemDataRole.UserRole)
    assert w.history.item(0).foreground().color().name() == theme.color(key).lower()
    w._theme_buttons["dark"].click()
    assert theme.current().name == "dark" and saved == ["light", "dark"]


def test_saved_theme_is_used_at_startup(harness):
    h = harness(theme_name="light")
    assert theme.current().name == "light" and h.window._theme_buttons["light"].isChecked()

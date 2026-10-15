"""모니터 창: 메인 창과 별개로 카메라 한 대의 실시간 합성 영상을 보여주는 보조 창.

창마다 자기 워커(카메라 → 매팅 → 합성)를 돌리므로 카메라 2대를 동시에 볼 수 있습니다.
한 카메라는 한 창에서만 열 수 있어서, 번호를 고를 때 다른 창이 쓰는 번호는 거절합니다.
불러온 모델은 창끼리 공유합니다 (메모리는 한 벌, 연산은 창 수만큼).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .. import messages
from ..backgrounds import BackgroundItem, scan_backgrounds
from ..config import APP_NAME, Config
from ..messages import Level, Notice
from ..worker import PipelineWorker
from . import theme
from .main_window import LEVEL_COLOR, STATE_VIEW, STEP_HINT, TALLY, _Bridge
from .widgets import BusRow, CamRow, PreviewView, repolish

log = logging.getLogger(__name__)


class MonitorWindow(QMainWindow):
    """카메라 하나를 보는 보조 창. 메인 창의 설정을 복사해서 쓰며, 이 창의 카메라 번호는 저장하지 않습니다."""

    def __init__(
        self,
        cfg: Config,
        worker_factory: Callable[[Config, Sequence[BackgroundItem]], PipelineWorker],
        camera_in_use: Callable[[int, object], bool],
        on_closed: Callable[["MonitorWindow"], None],
        *,
        title_no: int = 2,
        auto_start: bool = True,
    ):
        super().__init__()
        self.cfg = replace(cfg)  # 메인 창 설정의 복사본 (카메라 번호만 따로 바뀜)
        self._worker_factory = worker_factory
        self._camera_in_use = camera_in_use
        self._on_closed = on_closed
        self._title_no = title_no

        self._worker: Optional[PipelineWorker] = None
        self._retiring: List[PipelineWorker] = []
        self._state = "idle"
        self._step_text = ""
        self._backgrounds: List[BackgroundItem] = []
        self._current_bg = 0
        self._fps = 0.0

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(960, 620)
        self.setMinimumSize(640, 420)
        self._build_ui()
        self._install_shortcuts()
        self._scan_backgrounds()
        self._set_state("idle")
        self._refresh_title()
        if auto_start:
            QTimer.singleShot(0, self.start_pipeline)

    # ================================================================ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("console")
        self.setCentralWidget(central)
        col = QVBoxLayout(central)
        col.setContentsMargins(14, 12, 14, 12)
        col.setSpacing(8)

        self.preview = PreviewView()
        col.addWidget(self.preview, 1)

        self.controls = QWidget()
        self.controls.setObjectName("console")
        rows = QVBoxLayout(self.controls)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)

        sel = QHBoxLayout()
        sel.setSpacing(14)
        self.cam_row = CamRow()
        self.cam_row.set_current(self.cfg.camera_index)
        self.cam_row.chosen.connect(self.select_camera)
        sel.addWidget(self.cam_row)
        bg_label = QLabel("배경")
        bg_label.setObjectName("muted")
        sel.addWidget(bg_label)
        self.bus = BusRow()
        self.bus.chosen.connect(self.select_background)
        sel.addWidget(self.bus)
        sel.addStretch(1)
        rows.addLayout(sel)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_toggle = QPushButton("시작")
        self.btn_toggle.setObjectName("primary")
        self.btn_capture = QPushButton("배경 촬영")
        self.btn_capture.setObjectName("capture")
        for b in (self.btn_toggle, self.btn_capture):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setMinimumWidth(92)
            bar.addWidget(b)
        self.btn_toggle.clicked.connect(self.toggle_pipeline)
        self.btn_capture.clicked.connect(self.toggle_capture)
        bar.addStretch(1)
        self.note = QLabel("")
        self.note.setObjectName("faint")
        bar.addWidget(self.note)
        self.status_label = QLabel("")
        self.fps_label = QLabel("")
        bar.addWidget(self.status_label)
        bar.addWidget(self.fps_label)
        rows.addLayout(bar)
        col.addWidget(self.controls)

    def _install_shortcuts(self) -> None:
        self._shortcuts: List[QShortcut] = []

        def add(sequence, handler) -> None:
            sc = QShortcut(QKeySequence(sequence), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(handler)
            self._shortcuts.append(sc)

        for n in range(1, 10):
            add(str(n), lambda n=n: self.select_background(n))
        add("Space", self.toggle_capture)
        add("F", self.toggle_fullscreen)
        add("Esc", self.on_escape)

    def _refresh_title(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — 모니터 {self._title_no} (카메라 {self.cfg.camera_index}번)")

    # ================================================================ 외부에서 보는 상태
    def uses_camera(self, index: int) -> bool:
        """이 창이 지금 그 번호의 카메라를 열고 있는지 (정지해 있으면 카메라를 놓은 상태)."""
        return self._worker is not None and self.cfg.camera_index == index

    # ================================================================ 시작/정지
    def start_pipeline(self) -> None:
        if self._worker is not None:
            return
        if self._camera_in_use(self.cfg.camera_index, self):
            self._set_note(messages.camera_in_use(self.cfg.camera_index))
            self._set_state("error")
            self.preview.set_overlay(
                f"카메라 {self.cfg.camera_index}번을 쓸 수 없습니다",
                "다른 창에서 같은 카메라를 쓰고 있습니다. 아래 카메라 번호를 바꿔 주세요.",
            )
            return
        self._scan_backgrounds()
        self._set_state("starting")
        self._step_text = STEP_HINT[0]
        self._refresh_overlay()
        worker = self._worker_factory(self.cfg, self._backgrounds)
        self._worker = worker
        _Bridge(self, worker)
        worker.start()

    def stop_pipeline(self) -> None:
        worker = self._worker
        if worker is None:
            return
        self._worker = None  # 이후 이 워커의 이벤트는 무시됨
        worker.request_stop()
        if not worker.wait(5000):
            self._retiring.append(worker)
        self._set_state("stopped")

    def toggle_pipeline(self) -> None:
        if self._worker is not None:
            self.stop_pipeline()
        else:
            self.start_pipeline()

    def _on_worker_finished(self, worker: PipelineWorker) -> None:
        worker.wait(2000)
        if self._worker is worker:
            self._worker = None
            self._refresh_buttons()
        if worker in self._retiring:
            self._retiring.remove(worker)

    # ================================================================ 조작
    def select_camera(self, index: int) -> None:
        if index == self.cfg.camera_index and self._worker is not None:
            return
        if self._camera_in_use(index, self):
            self._set_note(messages.camera_in_use(index))
            return
        was_running = self._worker is not None
        self.stop_pipeline()
        self.cfg.camera_index = index
        self.cam_row.set_current(index)
        self._refresh_title()
        if was_running:
            self.start_pipeline()

    def select_background(self, number: int) -> None:
        if self._worker is None or self._state not in ("running", "capturing"):
            self._set_note(messages.bg_not_ready())
            return
        count = len(self._backgrounds)
        if not 1 <= number <= count:
            self._set_note(messages.bg_invalid(number, count))
            return
        self._worker.select_background(number)

    def toggle_capture(self) -> None:
        if self._worker is None:
            self._set_note(messages.capture_unavailable())
        elif self._state == "capturing":
            self._worker.cancel_capture()
        elif not self.cfg.needs_bgr:
            self._set_note(messages.capture_not_needed(self.cfg.engine))
        elif self._state in ("waiting_bg", "running"):
            self._worker.start_capture()
        else:
            self._set_note(messages.capture_unavailable())

    def toggle_fullscreen(self) -> None:
        full = not self.isFullScreen()
        if full:
            self.showFullScreen()
        else:
            self.showNormal()
        self.controls.setVisible(not full)
        self._update_hud()

    def on_escape(self) -> None:
        if self._state == "capturing" and self._worker is not None:
            self._worker.cancel_capture()
        elif self.isFullScreen():
            self.toggle_fullscreen()
        else:
            self.close()

    # ================================================================ 워커 이벤트 (메인 창의 _Bridge 가 호출)
    def _set_state(self, state: str) -> None:
        self._state = state
        text, color_key = STATE_VIEW[state]
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {theme.color(color_key)};")
        if state in ("idle", "starting", "stopped", "error"):
            self.preview.clear_frame()
            self.preview.set_countdown(None)
            self._fps = 0.0
            self.fps_label.setText("")
        if state == "capturing":
            self.note.setText("")
        self.preview.set_tally(TALLY.get(state))
        self._refresh_overlay()
        self._refresh_buttons()
        self._update_hud()

    def _on_step(self, index: int, status: str) -> None:
        if status == "active":
            self._step_text = STEP_HINT[index]
            self._refresh_overlay()

    def _on_background(self, number: int, count: int, name: str) -> None:
        self._current_bg = number
        self.bus.set_current(number)
        self._update_hud()

    def _on_fps(self, fps: float) -> None:
        self._fps = fps
        self.fps_label.setText(f"{fps:.1f} FPS")
        self._update_hud()

    def _on_info(self, device: str, resolution: str) -> None:
        pass  # 메인 창 '상태' 패널의 정보는 메인 창 기준입니다

    def _on_tick(self, value: int) -> None:
        self.preview.set_countdown(None if value < 0 else value, self.cfg.countdown_seconds)

    def _on_alpha(self, enabled: bool) -> None:
        pass

    def _add_notice(self, notice: Notice) -> None:
        self._set_note(notice)
        if notice.level == Level.ERROR:
            self.preview.set_overlay(notice.title, notice.hint or notice.detail)

    # ================================================================ 화면 갱신
    def _set_note(self, notice: Notice) -> None:
        text = notice.title if not notice.hint else f"{notice.title} — {notice.hint}"
        self.note.setText(text)
        self.note.setStyleSheet(f"color: {theme.color(LEVEL_COLOR[notice.level])};")
        self.note.setToolTip("\n".join(p for p in (notice.detail, notice.hint) if p))

    def _refresh_overlay(self) -> None:
        s = self._state
        if s == "starting":
            self.preview.set_overlay("준비하는 중", self._step_text)
        elif s == "waiting_bg":
            self.preview.set_overlay(
                f"카메라 {self.cfg.camera_index}번의 빈 배경을 촬영해 주세요",
                "피사체를 화면 밖으로 옮긴 뒤 '배경 촬영' 또는 스페이스바를 누르세요.",
            )
        elif s == "stopped":
            self.preview.set_overlay("정지됨", "'시작' 버튼으로 다시 실행합니다.")
        elif s == "error":
            pass  # 오류 안내는 _add_notice / start_pipeline 이 직접 띄웁니다
        else:
            self.preview.clear_overlay()

    def _refresh_buttons(self) -> None:
        active = self._worker is not None
        if self.btn_toggle.property("running") != active:
            self.btn_toggle.setProperty("running", active)
            repolish(self.btn_toggle)
        self.btn_toggle.setText("정지" if active else ("다시 시작" if self._state == "error" else "시작"))
        self.btn_capture.setEnabled(
            self.cfg.needs_bgr and active and self._state in ("waiting_bg", "running", "capturing")
        )
        self.btn_capture.setText("촬영 취소" if self._state == "capturing" else "배경 촬영")

    def _update_hud(self) -> None:
        if self.isFullScreen() and self._state in ("running", "capturing") and self._current_bg:
            self.preview.set_hud(f"카메라 {self.cfg.camera_index}번  배경 {self._current_bg}번   {self._fps:.1f} FPS")
        else:
            self.preview.set_hud("")

    def _scan_backgrounds(self) -> None:
        self._backgrounds = scan_backgrounds(
            self.cfg.resolve(self.cfg.backgrounds_dir), self.cfg.resolve(self.cfg.legacy_background)
        )
        self.bus.set_count(len(self._backgrounds))
        count = len(self._backgrounds)
        number = min(max(self.cfg.last_background, 1), count) if count else 0
        self._current_bg = number
        self.bus.set_current(number)

    # ================================================================ 종료
    def closeEvent(self, event: QCloseEvent) -> None:
        workers = list(self._retiring)
        if self._worker is not None:
            workers.append(self._worker)
            self._worker = None
        for worker in workers:
            worker.request_stop()
        for worker in workers:
            if not worker.wait(4000):
                log.warning("모니터 창 워커가 제때 끝나지 않아 강제 종료합니다")
                worker.terminate()
                worker.wait(1000)
        self._on_closed(self)
        event.accept()

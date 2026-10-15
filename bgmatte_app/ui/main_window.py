"""메인 창: 미리보기 + 단계 표시 + 알림 배너 + 오른쪽 콘솔(배경 번호·상태·단축키·알림 기록)."""

from __future__ import annotations

import logging
import sys
from dataclasses import replace
from datetime import datetime
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import camera_auth, messages
from ..backgrounds import BackgroundItem, scan_backgrounds
from ..config import APP_NAME, Config, save_config
from ..messages import Level, Notice
from ..worker import PipelineWorker
from . import theme
from .dialogs import IntroDialog, SettingsDialog, probe_cameras
from .widgets import (
    BusRow, CamRow, NoticeBanner, PreviewView, StepBar, TallyDot, app_icon_pixmap, keycaps, repolish, section_header,
)

log = logging.getLogger(__name__)

ACTION_LABELS = {
    "open_settings": "설정 열기",
    "open_camera_privacy": "시스템 설정 열기",
    "open_backgrounds": "배경 폴더 열기",
    "restart": "다시 시작",
    "capture": "배경 촬영 (스페이스)",
}

STATE_VIEW = {
    "idle": ("대기", "FAINT"),
    "starting": ("준비 중", "INFO"),
    "waiting_bg": ("배경 촬영 필요", "WAIT"),
    "running": ("실행 중", "LIVE"),
    "capturing": ("촬영 중", "STOP"),
    "stopped": ("정지됨", "FAINT"),
    "error": ("오류", "STOP"),
}

# 영상 테두리 불빛: 카메라의 탤리 램프처럼 현재 상태를 알려줍니다
TALLY = {"starting": "INFO", "waiting_bg": "WAIT", "running": "LIVE", "capturing": "STOP", "error": "STOP"}

STEP_HINT = (
    "카메라에 연결하는 중입니다.",
    "배경 이미지를 확인하는 중입니다.",
    "모델을 불러오는 중입니다. 처음에는 몇 초 걸릴 수 있습니다.",
    "합성을 시작하는 중입니다.",
)

LEVEL_COLOR = {
    Level.INFO: "MUTED",
    Level.SUCCESS: "LIVE",
    Level.WARN: "WAIT",
    Level.ERROR: "STOP",
}

_PREFS_KEYS = ("⌘", ",") if sys.platform == "darwin" else ("Ctrl", ",")
SHORTCUTS = (
    (("1", "–", "9"), "배경 번호로 바로 전환", "brand"),
    (("Space",), "빈 배경 촬영 (촬영 중에는 취소)", "pink"),
    (("A",), "알파 매트 함께 보기", "cyan"),
    (("F",), "전체 화면", "cyan"),
    (("M",), "모니터 창 추가 (카메라 2대 동시 보기)", "cyan"),
    (("H",), "사용 안내", "cyan"),
    (("Esc",), "촬영 취소 · 전체 화면 해제 · 종료", "amber"),
    (_PREFS_KEYS, "설정", ""),
)

HISTORY_LIMIT = 50
# 배너가 '빈 배경을 촬영하세요'를 안내하는 동안에는 미리보기 카드로 같은 말을 반복하지 않는다
WAITING_PROMPTS = {"bgr_missing", "bgr_unreadable"}
# 촬영이 시작되면 더는 필요 없는 안내
CAPTURE_PROMPTS = WAITING_PROMPTS | {"bgr_size_mismatch"}


def _default_worker_factory(cfg: Config, backgrounds: Sequence[BackgroundItem]) -> PipelineWorker:
    return PipelineWorker(cfg, backgrounds)


class _Bridge(QObject):
    """워커 하나와 창 사이의 연결. 재시작 뒤에 늦게 도착한 이전 워커의 이벤트를 걸러냅니다."""

    def __init__(self, window: "MainWindow", worker: PipelineWorker):
        super().__init__(window)
        self._w = window
        self._worker = worker
        worker.state_changed.connect(self.on_state)
        worker.step_changed.connect(self.on_step)
        worker.frame_ready.connect(self.on_frame)
        worker.notify.connect(self.on_notify)
        worker.background_changed.connect(self.on_background)
        worker.fps_updated.connect(self.on_fps)
        worker.stream_info.connect(self.on_info)
        worker.capture_tick.connect(self.on_tick)
        worker.alpha_changed.connect(self.on_alpha)
        worker.finished.connect(self.on_finished)

    def _live(self) -> bool:
        return self._w._worker is self._worker

    def on_state(self, state):
        if self._live():
            self._w._set_state(state)

    def on_step(self, index, status):
        if self._live():
            self._w._on_step(index, status)

    def on_frame(self, image):
        if self._live():
            self._w.preview.set_frame(image)
            self._worker.ack_frame()

    def on_notify(self, notice):
        if self._live():
            self._w._add_notice(notice)

    def on_background(self, number, count, name):
        if self._live():
            self._w._on_background(number, count, name)

    def on_fps(self, fps):
        if self._live():
            self._w._on_fps(fps)

    def on_info(self, device, resolution):
        if self._live():
            self._w._on_info(device, resolution)

    def on_tick(self, value):
        if self._live():
            self._w._on_tick(value)

    def on_alpha(self, enabled):
        if self._live():
            self._w._on_alpha(enabled)

    def on_finished(self):
        self._w._on_worker_finished(self._worker)
        self.deleteLater()  # 재시작할 때마다 브리지가 쌓이지 않도록 정리


class MainWindow(QMainWindow):
    permission_answered = Signal(bool)

    def __init__(
        self,
        cfg: Config,
        startup_warning: Optional[str] = None,
        *,
        worker_factory: Callable[[Config, Sequence[BackgroundItem]], PipelineWorker] = _default_worker_factory,
        auth_status: Callable[[], str] = camera_auth.authorization_status,
        auth_request: Callable[[Callable[[bool], None]], None] = camera_auth.request_access,
        camera_probe: Callable[[], list] = probe_cameras,
        save: Callable[[Config], None] = save_config,
        open_url: Callable[[QUrl], object] = QDesktopServices.openUrl,
        auto_start: bool = True,
    ):
        super().__init__()
        self.cfg = cfg
        self._startup_warning = startup_warning
        self._worker_factory = worker_factory
        self._auth_status = auth_status
        self._auth_request = auth_request
        self._camera_probe = camera_probe
        self._save = save
        self._open_url = open_url

        self._worker: Optional[PipelineWorker] = None
        self._retiring: List[PipelineWorker] = []
        self._monitors: list = []  # 열려 있는 모니터 창 (MonitorWindow)
        self._awaiting_permission = False
        self._state = "idle"
        self._step_text = ""
        self._backgrounds: List[BackgroundItem] = []
        self._current_bg = 0
        self._fps = 0.0
        self._alpha = False

        self.setWindowTitle(APP_NAME)
        self.resize(1240, 820)
        self.setMinimumSize(1000, 660)
        theme.set_theme(self.cfg.theme)
        self._build_ui()
        self._apply_theme()
        self._install_shortcuts()
        self.permission_answered.connect(self._on_permission_answered)
        self._set_state("idle")
        self._scan_backgrounds()
        self._refresh_engine_view()

        if auto_start:
            QTimer.singleShot(0, self._startup)

    # ================================================================ UI 구성
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("console")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(20)

        # ---- 왼쪽: 단계 / 배너 / 미리보기
        left = QVBoxLayout()
        left.setSpacing(10)
        self.steps = StepBar()
        self.banner = NoticeBanner(ACTION_LABELS)
        self.banner.action_requested.connect(self._on_action)
        self.banner.cleared.connect(self._refresh_overlay)
        self.preview = PreviewView()
        left.addWidget(self.steps)
        left.addWidget(self.banner)
        left.addWidget(self.preview, 1)

        # 미리보기 바로 아래: 카메라 번호 버튼과 모니터 창 추가 버튼
        self.camera_bar = QWidget()
        self.camera_bar.setObjectName("console")
        cam_line = QHBoxLayout(self.camera_bar)
        cam_line.setContentsMargins(0, 0, 0, 0)
        cam_line.setSpacing(10)
        self.cam_row = CamRow()
        self.cam_row.set_current(self.cfg.camera_index)
        self.cam_row.chosen.connect(self.select_camera)
        cam_line.addWidget(self.cam_row)
        cam_line.addStretch(1)
        self.btn_monitor = QPushButton("＋ 모니터 창")
        self.btn_monitor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_monitor.setToolTip("다른 카메라의 실시간 합성 영상을 별도 창으로 띄웁니다 (M)")
        self.btn_monitor.clicked.connect(self.open_monitor)
        cam_line.addWidget(self.btn_monitor)
        left.addWidget(self.camera_bar)

        # 그 아래: 시작/정지, 배경 촬영, 설정 버튼과 안내 한 줄
        self.controls = QWidget()
        self.controls.setObjectName("console")
        bar = QHBoxLayout(self.controls)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)
        self.btn_toggle = QPushButton("시작")
        self.btn_toggle.setObjectName("primary")
        self.btn_capture = QPushButton("배경 촬영")
        self.btn_capture.setObjectName("capture")
        self.btn_settings = QPushButton("설정")
        for b in (self.btn_toggle, self.btn_capture, self.btn_settings):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 단축키(스페이스 등)가 버튼에 먹히지 않도록
            b.setMinimumWidth(92)
            bar.addWidget(b)
        self.btn_toggle.clicked.connect(self.toggle_pipeline)
        self.btn_capture.clicked.connect(self.toggle_capture)
        self.btn_settings.clicked.connect(self.open_settings)
        bar.addStretch(1)
        self.footnote = QLabel("카메라는 빈 배경을 촬영한 뒤 움직이지 마세요.")
        self.footnote.setObjectName("faint")
        bar.addWidget(self.footnote)
        left.addWidget(self.controls)
        root.addLayout(left, 1)

        # ---- 오른쪽: 콘솔
        self.side = QWidget()
        self.side.setFixedWidth(350)
        side = QVBoxLayout(self.side)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(app_icon_pixmap(28))
        logo.setFixedSize(28, 28)
        header.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        header.addWidget(title)
        header.addStretch(1)
        header.addLayout(self._build_theme_switch())
        header.addSpacing(6)
        self.tally = TallyDot()
        self.status_label = QLabel()
        header.addWidget(self.tally)
        header.addWidget(self.status_label)
        side.addLayout(header)
        accent = QFrame()
        accent.setObjectName("accentLine")
        side.addWidget(accent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("console")
        body_col = QVBoxLayout(body)
        body_col.setContentsMargins(0, 4, 8, 0)
        body_col.setSpacing(10)

        def make_panel(title_text: str, tone: str, compact: bool):
            frame = QFrame()
            frame.setObjectName("panel")
            outer = QVBoxLayout(frame)
            outer.setContentsMargins(0, 0, 0, 0)
            inner = QWidget()
            if compact:  # 상태 · 단축키 · 알림 기록은 보조 정보라서 작은 글씨로 표시합니다.
                inner.setObjectName("compact")
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(12, 10, 12, 12)
            lay.setSpacing(8)
            head = section_header(title_text, tone)
            lay.addLayout(head)
            outer.addWidget(inner)
            body_col.addWidget(frame)
            return lay, head

        # 합성 배경
        col, head = make_panel("합성 배경", "brand", compact=False)
        self.bg_count = QLabel("")
        self.bg_count.setObjectName("muted")
        head.addWidget(self.bg_count)
        head.addStretch(1)
        self.btn_folder = QPushButton("폴더 열기")
        self.btn_folder.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_folder.setStyleSheet("padding: 3px 10px; font-size: 12px;")
        self.btn_folder.clicked.connect(lambda: self._on_action("open_backgrounds"))
        head.addWidget(self.btn_folder)
        self.bus = BusRow()
        self.bus.chosen.connect(self.select_background)
        col.addWidget(self.bus)
        self.bg_name = QLabel("")
        self.bg_name.setObjectName("bgName")
        self.bg_note = QLabel("")
        self.bg_note.setObjectName("faint")
        self.bg_note.setWordWrap(True)
        col.addWidget(self.bg_name)
        col.addWidget(self.bg_note)

        # 상태
        col, _ = make_panel("상태", "cyan", compact=True)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        self.val_engine = QLabel("—")
        self.val_device = QLabel("—")
        self.val_resolution = QLabel("—")
        self.val_fps = QLabel("—")
        self.val_fps.setObjectName("fpsValue")
        self.val_alpha = QLabel("꺼짐")
        for r, (name, value) in enumerate(
            (("엔진", self.val_engine), ("처리 장치", self.val_device), ("해상도", self.val_resolution),
             ("속도", self.val_fps), ("알파 보기", self.val_alpha))
        ):
            label = QLabel(name)
            label.setObjectName("muted")
            grid.addWidget(label, r, 0)
            grid.addWidget(value, r, 1)
        grid.setColumnStretch(1, 1)
        col.addLayout(grid)

        # 단축키 (키 역할별로 색을 나눔: 배경 번호=보라, 촬영=분홍, 보기=청록, 종료=노랑)
        col, _ = make_panel("단축키", "amber", compact=True)
        keys = QGridLayout()
        keys.setHorizontalSpacing(12)
        keys.setVerticalSpacing(4)
        for r, (caps, text, tone) in enumerate(SHORTCUTS):
            keys.addWidget(keycaps(*caps, height=18, tone=tone), r, 0, Qt.AlignmentFlag.AlignVCenter)
            label = QLabel(text)
            label.setWordWrap(True)
            keys.addWidget(label, r, 1, Qt.AlignmentFlag.AlignVCenter)
        keys.setColumnMinimumWidth(0, 78)
        keys.setColumnStretch(1, 1)
        col.addLayout(keys)

        # 알림 기록
        col, _ = make_panel("알림 기록", "pink", compact=True)
        self.history = QListWidget()
        self.history.setObjectName("history")
        self.history.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history.setMinimumHeight(84)
        self.history.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        col.addWidget(self.history)
        body_col.addStretch(1)

        scroll.setWidget(body)
        side.addWidget(scroll, 1)
        root.addWidget(self.side)

    def _build_theme_switch(self) -> QHBoxLayout:
        """헤더의 '어둡게 | 밝게' 선택 버튼."""
        box = QHBoxLayout()
        box.setSpacing(0)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_buttons = {}
        for name, pos in (("dark", "left"), ("light", "right")):
            button = QPushButton(theme.THEME_LABELS[name])
            button.setObjectName("seg")
            button.setProperty("pos", pos)
            button.setCheckable(True)
            button.setChecked(name == theme.current().name)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setToolTip("화면 색상을 바꿉니다")
            button.clicked.connect(lambda _=False, n=name: self.set_theme(n))
            self._theme_group.addButton(button)
            self._theme_buttons[name] = button
            box.addWidget(button)
        return box

    def set_theme(self, name: str) -> None:
        """사용자가 테마를 고른 경우: 적용하고 다음 실행에도 쓰도록 저장합니다."""
        if name not in theme.THEMES:
            return
        theme.set_theme(name)
        self.cfg.theme = name
        self._apply_theme()
        self._persist()

    def _apply_theme(self) -> None:
        palette = theme.current()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.build_style(palette))
        for name, button in self._theme_buttons.items():
            button.setChecked(name == palette.name)
        for i in range(self.history.count()):  # 이미 쌓인 알림 글자색도 새 테마에 맞춤
            item = self.history.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key:
                item.setForeground(QColor(theme.color(key)))
        self.tally.update()
        self.preview.update()

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
        add("A", self.toggle_alpha)
        add("F", self.toggle_fullscreen)
        add("M", self.open_monitor)
        add("H", self.show_intro)
        add("Esc", self.on_escape)
        add(QKeySequence.StandardKey.Preferences, self.open_settings)

    # ================================================================ 시작/정지
    def _startup(self) -> None:
        if self._startup_warning:
            self._add_notice(messages.config_corrupt(self._startup_warning))
        if not self.cfg.seen_intro:
            dialog = IntroDialog(self, show_checkbox=True)
            dialog.exec()
            if dialog.dont_show.isChecked():
                self.cfg.seen_intro = True
                self._persist()
        self.start_pipeline()

    def start_pipeline(self) -> None:
        if self._worker is not None or self._awaiting_permission:
            return
        self.banner.clear()
        self.steps.reset()
        if any(m.uses_camera(self.cfg.camera_index) for m in self._monitors):
            self._fail_with(replace(messages.camera_in_use(self.cfg.camera_index), banner=True))
            return
        self._set_state("starting")
        self._step_text = STEP_HINT[0]
        self._refresh_overlay()

        status = self._auth_status()
        if status == "denied":
            self._fail_with(messages.camera_permission_denied())
            return
        if status == "restricted":
            self._fail_with(messages.camera_restricted())
            return
        if status == "not_determined":
            self._awaiting_permission = True
            self._refresh_buttons()  # 권한 팝업을 기다리는 동안에도 버튼은 '정지'
            self._add_notice(messages.camera_permission_pending())
            self._auth_request(self.permission_answered.emit)
            return
        self._launch_worker()

    def _on_permission_answered(self, granted: bool) -> None:
        if not self._awaiting_permission:
            return
        self._awaiting_permission = False
        if granted:
            self.banner.clear()
            self._launch_worker()
        else:
            self._fail_with(messages.camera_permission_denied())

    def _launch_worker(self) -> None:
        self._scan_backgrounds()
        worker = self._worker_factory(self.cfg, self._backgrounds)
        self._worker = worker
        _Bridge(self, worker)
        worker.start()

    def stop_pipeline(self) -> None:
        was_waiting = self._awaiting_permission
        self._awaiting_permission = False
        worker = self._worker
        if worker is None:
            if was_waiting:  # 권한 팝업 응답을 기다리던 중에 정지
                self.banner.clear()
                self._set_state("stopped")
                self.steps.reset()
            return
        self._worker = None  # 이후 이 워커가 보내는 이벤트는 무시됨
        worker.request_stop()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            finished = worker.wait(5000)
        finally:
            QApplication.restoreOverrideCursor()
        if not finished:
            self._retiring.append(worker)
        self._set_state("stopped")
        self.steps.reset()

    def restart_pipeline(self) -> None:
        self.stop_pipeline()
        self.start_pipeline()

    def toggle_pipeline(self) -> None:
        if self._worker is not None or self._awaiting_permission:
            self.stop_pipeline()
        else:
            self.start_pipeline()

    def _on_worker_finished(self, worker: PipelineWorker) -> None:
        # finished 시그널은 스레드가 끝나기 직전에 나갑니다. 완전히 끝난 것을 확인한 뒤에야
        # 참조를 놓아야 'QThread: Destroyed while thread is still running' 오류가 나지 않습니다.
        worker.wait(2000)
        if self._worker is worker:
            self._worker = None
            self._refresh_buttons()
        if worker in self._retiring:
            self._retiring.remove(worker)

    def _fail_with(self, notice: Notice) -> None:
        self.steps.set_status(0, "error")
        self._set_state("error")
        self._add_notice(notice)

    # ================================================================ 사용자 조작
    def select_background(self, number: int) -> None:
        if self._worker is None or self._state not in ("running", "capturing"):
            self._add_notice(messages.bg_not_ready())
            return
        count = len(self._backgrounds)
        if not 1 <= number <= count:
            self._add_notice(messages.bg_invalid(number, count))
            return
        self._worker.select_background(number)

    def camera_in_use(self, index: int, exclude: object = None) -> bool:
        """그 번호의 카메라를 (exclude 창을 뺀) 다른 창이 열고 있는지."""
        if exclude is not self and self.cfg.camera_index == index and (
            self._worker is not None or self._awaiting_permission
        ):
            return True
        return any(m is not exclude and m.uses_camera(index) for m in self._monitors)

    def select_camera(self, index: int) -> None:
        """미리보기 아래 번호 버튼: 이 창이 쓰는 카메라를 바꿉니다 (실행 중이면 새 카메라로 다시 시작)."""
        if index == self.cfg.camera_index:
            return
        if self.camera_in_use(index, self):
            self._add_notice(messages.camera_in_use(index))
            return
        self.cfg.camera_index = index
        self.cam_row.set_current(index)
        self._persist()
        if self._worker is not None or self._awaiting_permission:
            self.restart_pipeline()

    def open_monitor(self) -> None:
        """메인 창과 별개로, 다른 카메라의 실시간 합성 영상을 보는 창을 하나 더 엽니다."""
        from .monitor_window import MonitorWindow

        free = [
            i for i in range(CamRow.SLOTS) if i != self.cfg.camera_index and not self.camera_in_use(i, None)
        ]
        if not free:
            self._add_notice(messages.no_free_camera(CamRow.SLOTS))
            return
        cfg = replace(self.cfg, camera_index=free[0])
        taken = {m._title_no for m in self._monitors}
        number = next(n for n in range(2, 99) if n not in taken)
        window = MonitorWindow(
            cfg, self._worker_factory, self.camera_in_use, self._on_monitor_closed,
            title_no=number, auto_start=False,
        )
        self._monitors.append(window)
        window.show()
        window.start_pipeline()  # 바로 시작해야 곧이어 여는 창이 같은 카메라 번호를 고르지 않습니다

    def _on_monitor_closed(self, window) -> None:
        if window in self._monitors:
            self._monitors.remove(window)

    def toggle_alpha(self) -> None:
        if self._worker is not None and self._state in ("running", "capturing"):
            self._worker.toggle_alpha()

    def toggle_capture(self) -> None:
        if self._worker is None:
            self._add_notice(messages.capture_unavailable())
        elif self._state == "capturing":
            self._worker.cancel_capture()
        elif not self.cfg.needs_bgr:
            self._add_notice(messages.capture_not_needed(self.cfg.engine))
        elif self._state in ("waiting_bg", "running"):
            self._worker.start_capture()
        else:
            self._add_notice(messages.capture_unavailable())

    def toggle_fullscreen(self) -> None:
        full = not self.isFullScreen()
        if full:
            self.showFullScreen()
        else:
            self.showNormal()
        for w in (self.side, self.steps, self.controls, self.camera_bar):
            w.setVisible(not full)
        self._update_hud()

    def on_escape(self) -> None:
        if self._state == "capturing" and self._worker is not None:
            self._worker.cancel_capture()
        elif self.isFullScreen():
            self.toggle_fullscreen()
        else:
            self.close()

    def show_intro(self) -> None:
        IntroDialog(self).exec()

    def open_settings(self) -> None:
        was_active = self._worker is not None or self._awaiting_permission
        self.stop_pipeline()  # 카메라를 놓아야 '카메라 찾기'가 동작합니다
        dialog = SettingsDialog(self.cfg, self, camera_probe=self._camera_probe)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            self.cfg = dialog.result_config()
            self._persist()
            self._scan_backgrounds()
            self._refresh_engine_view()
            self.cam_row.set_current(self.cfg.camera_index)
        if was_active or accepted:
            self.start_pipeline()

    def _on_action(self, action: str) -> None:
        if action == "open_settings":
            self.open_settings()
        elif action == "open_camera_privacy":
            self._open_url(QUrl(
                "ms-settings:privacy-webcam" if sys.platform == "win32"
                else "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"
            ))
        elif action == "open_backgrounds":
            folder = self.cfg.resolve(self.cfg.backgrounds_dir)
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                log.exception("배경 폴더를 만들지 못했습니다")
            self._open_url(QUrl.fromLocalFile(str(folder)))
        elif action == "restart":
            self.restart_pipeline()
        elif action == "capture":
            self.toggle_capture()

    # ================================================================ 워커 이벤트 처리
    def _set_state(self, state: str) -> None:
        self._state = state
        text, color_key = STATE_VIEW[state]
        self.status_label.setText(text)
        self.tally.set_color(color_key)
        if state in ("idle", "starting", "stopped", "error"):
            self.preview.clear_frame()
            self.preview.set_countdown(None)
            self._fps = 0.0
            self.val_fps.setText("—")
        if state in ("starting", "stopped", "error") and self._alpha:
            self._on_alpha(False)
        if state == "capturing" and self.banner.code in CAPTURE_PROMPTS:
            self.banner.clear()
        self.preview.set_tally(TALLY.get(state))
        self._refresh_overlay()
        self._refresh_buttons()
        self._update_hud()

    def _on_step(self, index: int, status: str) -> None:
        self.steps.set_status(index, status)
        if status == "active":
            self._step_text = STEP_HINT[index]
            self._refresh_overlay()

    def _on_background(self, number: int, count: int, name: str) -> None:
        self._current_bg = number
        self.cfg.last_background = number
        self._show_current_background(number, count, name)
        self._update_hud()

    def _on_fps(self, fps: float) -> None:
        self._fps = fps
        self.val_fps.setText(f"{fps:.1f} FPS")
        self._update_hud()

    def _on_info(self, device: str, resolution: str) -> None:
        if device:
            self.val_device.setText(device)
            self.val_device.setToolTip(
                "GPU를 쓸 수 없어 CPU로 처리합니다. 속도가 느릴 수 있습니다." if device.startswith("CPU") else ""
            )
        if resolution:
            self.val_resolution.setText(resolution)

    def _on_tick(self, value: int) -> None:
        self.preview.set_countdown(None if value < 0 else value, self.cfg.countdown_seconds)

    def _on_alpha(self, enabled: bool) -> None:
        self._alpha = enabled
        self.val_alpha.setText("켜짐 (오른쪽에 알파 매트 표시)" if enabled else "꺼짐")

    # ================================================================ 화면 갱신
    def _refresh_overlay(self) -> None:
        s = self._state
        if s == "starting":
            self.preview.set_overlay("준비하는 중", self._step_text)
        elif s == "waiting_bg":
            if self.banner.code in WAITING_PROMPTS:
                self.preview.clear_overlay()  # 배너가 같은 안내를 이미 보여주고 있음
            else:
                self.preview.set_overlay(
                    "빈 배경을 촬영해 주세요",
                    "피사체를 화면 밖으로 옮긴 뒤 스페이스바를 누르세요. 촬영한 뒤에는 카메라를 움직이지 마세요.",
                )
        elif s == "stopped":
            self.preview.set_overlay("정지됨", "'시작' 버튼으로 다시 실행합니다.")
        elif s == "error":
            self.preview.set_overlay("실행하지 못했습니다", "위의 안내를 확인한 뒤 '다시 시작'을 눌러 주세요.")
        else:
            self.preview.clear_overlay()

    def _refresh_engine_view(self) -> None:
        """선택한 엔진 이름과, 엔진에 따라 달라지는 안내 문구(빈 배경 촬영 필요 여부)를 갱신합니다."""
        name = messages.ENGINE_NAMES.get(self.cfg.engine, self.cfg.engine)
        if self.cfg.engine == "rvm":
            name += f" ({self.cfg.rvm_variant})"
        self.val_engine.setText(name)
        self.footnote.setText(
            "카메라는 빈 배경을 촬영한 뒤 움직이지 마세요." if self.cfg.needs_bgr
            else "이 엔진은 빈 배경 촬영 없이 바로 합성합니다."
        )
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        active = self._worker is not None or self._awaiting_permission
        if self.btn_toggle.property("running") != active:
            self.btn_toggle.setProperty("running", active)
            repolish(self.btn_toggle)
        if active:
            self.btn_toggle.setText("정지")
        else:
            self.btn_toggle.setText("다시 시작" if self._state == "error" else "시작")
        can_capture = (
            self.cfg.needs_bgr and self._worker is not None and self._state in ("waiting_bg", "running", "capturing")
        )
        self.btn_capture.setEnabled(can_capture)
        self.btn_capture.setText("촬영 취소" if self._state == "capturing" else "배경 촬영")
        need_capture = self._state == "waiting_bg"
        for button, name, value in ((self.btn_capture, "emphasis", need_capture), (self.btn_toggle, "demoted", need_capture)):
            if button.property(name) != value:
                button.setProperty(name, value)
                repolish(button)

    def _update_hud(self) -> None:
        if self.isFullScreen() and self._state in ("running", "capturing") and self._current_bg:
            self.preview.set_hud(f"배경 {self._current_bg}번   {self._fps:.1f} FPS")
        else:
            self.preview.set_hud("")

    def _scan_backgrounds(self) -> None:
        self._backgrounds = scan_backgrounds(
            self.cfg.resolve(self.cfg.backgrounds_dir), self.cfg.resolve(self.cfg.legacy_background)
        )
        count = len(self._backgrounds)
        self.bus.set_count(count)
        if count == 0:
            self._current_bg = 0
            self.bus.set_current(0)
            self.bg_count.setText("")
            self.bg_name.setText("배경 이미지가 없습니다")
            self.bg_note.setText("‘폴더 열기’로 backgrounds 폴더를 열고 PNG/JPG 파일을 넣어 주세요.")
            return
        number = min(max(self.cfg.last_background, 1), count)
        self._current_bg = number
        self._show_current_background(number, count, self._backgrounds[number - 1].name)

    def _show_current_background(self, number: int, count: int, name: str) -> None:
        self.bus.set_current(number)
        self.bg_count.setText(f"{count}개 중 {number}번")
        fm = QFontMetrics(self.bg_name.font())
        self.bg_name.setText(fm.elidedText(name, Qt.TextElideMode.ElideMiddle, 340))
        self.bg_name.setToolTip(name)
        notes = []
        if count > BusRow.SLOTS:
            notes.append(f"{BusRow.SLOTS}개까지만 선택할 수 있습니다. {BusRow.SLOTS + 1}번부터는 쓰이지 않습니다.")
        self.bg_note.setText(" ".join(notes))
        self.bg_note.setVisible(bool(notes))

    def _add_notice(self, notice: Notice) -> None:
        item = QListWidgetItem(f"{datetime.now():%H:%M:%S}   {notice.title}")
        item.setData(Qt.ItemDataRole.UserRole, LEVEL_COLOR[notice.level])
        item.setForeground(QColor(theme.color(LEVEL_COLOR[notice.level])))
        tip = "\n".join(part for part in (notice.detail, notice.hint) if part)
        if tip:
            item.setToolTip(tip)
        self.history.insertItem(0, item)
        while self.history.count() > HISTORY_LIMIT:
            self.history.takeItem(self.history.count() - 1)
        if notice.banner:
            self.banner.show_notice(notice)
            self._refresh_overlay()

    def _persist(self) -> None:
        try:
            self._save(self.cfg)
        except Exception:
            log.exception("설정을 저장하지 못했습니다")

    # ================================================================ 종료
    def closeEvent(self, event: QCloseEvent) -> None:
        for monitor in list(self._monitors):
            monitor.close()
        self._persist()
        self._awaiting_permission = False
        workers = list(self._retiring)
        if self._worker is not None:
            workers.append(self._worker)
            self._worker = None
        for worker in workers:
            worker.request_stop()
        for worker in workers:
            if not worker.wait(4000):
                log.warning("워커가 제때 끝나지 않아 강제 종료합니다")
                worker.terminate()
                worker.wait(1000)
        event.accept()

"""사용 안내 / 설정 다이얼로그."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import BACKBONES, DEVICES, MODEL_TYPES, Config, resolve_path
from . import theme
from .widgets import hairline, keycaps


# ---------------------------------------------------------------- 사용 안내
INTRO_STEPS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    (
        "카메라를 고정합니다",
        "배경을 촬영한 뒤 카메라가 조금이라도 움직이면 합성 품질이 크게 떨어집니다. 삼각대에 고정해 주세요.",
        (),
    ),
    (
        "빈 배경을 촬영합니다",
        "피사체(사람·물체)가 화면 밖에 있는 상태에서 스페이스바를 누르면, 카운트다운 뒤에 배경이 저장됩니다.",
        ("Space",),
    ),
    (
        "합성 배경을 고릅니다",
        "backgrounds 폴더의 이미지가 파일명 순서대로 1번, 2번… 이 됩니다. 숫자 키(1~9)로 바로 바꿀 수 있습니다.",
        ("1", "–", "9"),
    ),
    (
        "끝낼 때",
        "촬영 중에는 취소, 전체 화면에서는 해제, 그 외에는 앱을 종료합니다.",
        ("Esc",),
    ),
)


class IntroDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, show_checkbox: bool = False):
        super().__init__(parent)
        self.setWindowTitle("사용 안내")
        self.setFixedWidth(580)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        title = QLabel("합성을 시작하기 전에")
        title.setObjectName("appTitle")
        root.addWidget(title)

        for i, (head, body, keys) in enumerate(INTRO_STEPS):
            root.addWidget(hairline())
            row = QHBoxLayout()
            row.setSpacing(14)
            number = QLabel(str(i + 1))
            number.setObjectName("bgName")
            number.setFixedWidth(18)
            number.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            row.addWidget(number)
            col = QVBoxLayout()
            col.setSpacing(4)
            heading = QLabel(head)
            heading.setObjectName("sectionTitle")
            text = QLabel(body)
            text.setObjectName("muted")
            text.setWordWrap(True)
            col.addWidget(heading)
            col.addWidget(text)
            if keys:
                col.addWidget(keycaps(*keys))
            row.addLayout(col, 1)
            root.addLayout(row)

        root.addWidget(hairline())
        footer = QHBoxLayout()
        self.dont_show = QCheckBox("처음 실행 때만 보기")
        self.dont_show.setChecked(True)
        self.dont_show.setVisible(show_checkbox)
        footer.addWidget(self.dont_show)
        footer.addStretch(1)
        close = QPushButton("확인")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        footer.addWidget(close)
        root.addLayout(footer)
        root.activate()
        self.adjustSize()


# ---------------------------------------------------------------- 설정
class PathField(QWidget):
    """경로 입력 + 찾아보기 + 존재 여부 표시."""

    def __init__(self, value: str, kind: str, missing_text: str, caption: str = "", parent=None):
        super().__init__(parent)
        self._kind = kind  # 'dir' | 'file'
        self._missing_text = missing_text
        self._caption = caption
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.edit = QLineEdit(value)
        browse = QPushButton("찾아보기")
        browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse.clicked.connect(self._browse)
        row.addWidget(self.edit, 1)
        row.addWidget(browse)
        box.addLayout(row)
        self.status = QLabel()
        box.addWidget(self.status)
        self.edit.textChanged.connect(self._refresh)
        self._refresh()

    def text(self) -> str:
        return self.edit.text().strip()

    def _browse(self) -> None:
        start = str(resolve_path(self.text() or "."))
        if self._kind == "dir":
            chosen = QFileDialog.getExistingDirectory(self, self._caption or "폴더 선택", start)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, self._caption or "파일 선택", start)
        if chosen:
            self.edit.setText(chosen)

    def _refresh(self) -> None:
        text = self.text()
        path = resolve_path(text) if text else None
        ok = bool(path) and (path.is_dir() if self._kind == "dir" else path.is_file())
        if ok:
            self.status.setText("✓ 확인됨")
            color = theme.color("LIVE")
        else:
            self.status.setText(f"✕ {self._missing_text}")
            color = theme.color("WAIT")
        self.status.setStyleSheet(f"color: {color}; font-size: 12px;")


def _choice_combo(options, current, custom_label) -> QComboBox:
    """(표시 문구, 값) 목록으로 콤보박스를 만들고, 목록에 없는 현재 값은 '사용자 지정' 항목으로 추가합니다."""
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    index = combo.findData(current)
    if index < 0:
        combo.addItem(custom_label(current), current)
        index = combo.count() - 1
    combo.setCurrentIndex(index)
    return combo


RESOLUTIONS = (
    ("장치 기본값 (자동)", "0x0"),
    ("1280 × 720", "1280x720"),
    ("1920 × 1080", "1920x1080"),
    ("640 × 480", "640x480"),
    ("3840 × 2160", "3840x2160"),
)


def probe_cameras(max_index: int = 5) -> List[Tuple[int, bool, str]]:
    """카메라 번호 0..max_index-1을 열어 보고 (번호, 열림 여부, 해상도) 목록을 반환합니다."""
    import cv2

    found: List[Tuple[int, bool, str]] = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        try:
            if not cap.isOpened():
                found.append((index, False, ""))
                continue
            ok, frame = cap.read()
            size = f"{frame.shape[1]}×{frame.shape[0]}" if ok and frame is not None else "영상 없음"
            found.append((index, True, size))
        finally:
            cap.release()
    return found


class SettingsDialog(QDialog):
    def __init__(
        self,
        cfg: Config,
        parent: Optional[QWidget] = None,
        camera_probe: Callable[[], List[Tuple[int, bool, str]]] = probe_cameras,
    ):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumWidth(620)
        self._cfg = cfg
        self._probe = camera_probe

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        title = QLabel("설정")
        title.setObjectName("appTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # 카메라
        self.camera_index = _choice_combo([(f"{i}번", i) for i in range(10)], cfg.camera_index, lambda v: f"{v}번")
        find = QPushButton("카메라 찾기")
        find.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        find.clicked.connect(self._find_cameras)
        cam_row = QHBoxLayout()
        cam_row.addWidget(self.camera_index)
        cam_row.addWidget(find)
        cam_row.addStretch(1)
        self.camera_result = QLabel("")
        self.camera_result.setObjectName("muted")
        self.camera_result.setWordWrap(True)
        cam_box = QVBoxLayout()
        cam_box.setSpacing(4)
        cam_box.addLayout(cam_row)
        cam_box.addWidget(self.camera_result)
        form.addRow("카메라 번호", cam_box)

        self.resolution = _choice_combo(
            RESOLUTIONS,
            f"{cfg.camera_width}x{cfg.camera_height}",
            lambda key: key.replace("x", " × ") + " (현재 설정)",
        )
        form.addRow("해상도", self.resolution)

        # 이미지
        self.backgrounds = PathField(
            cfg.backgrounds_dir, "dir", "폴더가 없습니다 (만들거나 다른 폴더를 지정하세요)", "합성 배경 폴더"
        )
        form.addRow("합성 배경 폴더", self.backgrounds)
        self.bgr = PathField(
            cfg.bgr, "file", "아직 없음 (스페이스바로 촬영하면 만들어집니다)", "빈 배경 이미지"
        )
        form.addRow("빈 배경 이미지", self.bgr)
        self.countdown = _choice_combo(
            [(f"{n}초", n) for n in (3, 5, 8, 10, 15)], cfg.countdown_seconds, lambda v: f"{v}초"
        )
        form.addRow("촬영 카운트다운", self.countdown)

        # 모델
        self.repo = PathField(cfg.repo_path, "dir", "폴더를 찾을 수 없습니다", "BackgroundMattingV2 폴더")
        form.addRow("BackgroundMattingV2", self.repo)
        # 백본마다 가중치 파일이 따로 필요합니다. 아래 '백본'에서 고른 칸이 실제로 쓰입니다.
        self.checkpoints = {}
        for bb, value in (
            ("resnet50", cfg.checkpoint),
            ("resnet101", cfg.checkpoint_resnet101),
            ("mobilenetv2", cfg.checkpoint_mobilenetv2),
        ):
            field = PathField(value, "file", "파일 없음 (이 백본을 쓸 때만 필요합니다)", f"{bb} 가중치(.pth)")
            self.checkpoints[bb] = field
            form.addRow(f"가중치 · {bb}", field)
        self.backbone = QComboBox()
        self.backbone.addItems(BACKBONES)
        self.backbone.setCurrentText(cfg.backbone)
        self.model_type = QComboBox()
        self.model_type.addItems(MODEL_TYPES)
        self.model_type.setCurrentText(cfg.model_type)
        self.device = QComboBox()
        self.device.addItems(DEVICES)
        self.device.setCurrentText(cfg.device)
        combos = QHBoxLayout()
        for caption, combo in (("백본", self.backbone), ("종류", self.model_type), ("장치", self.device)):
            label = QLabel(caption)
            label.setObjectName("muted")
            combos.addWidget(label)
            combos.addWidget(combo)
        combos.addStretch(1)
        form.addRow("모델 옵션", combos)
        root.addLayout(form)

        note = QLabel("저장하면 실행 중인 합성이 다시 시작됩니다. 상대 경로는 저장소 폴더 기준입니다.")
        note.setObjectName("faint")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox()
        save = buttons.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("primary")
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _find_cameras(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            results = self._probe()
        finally:
            QApplication.restoreOverrideCursor()
        lines = []
        for index, opened, size in results:
            lines.append(f"{index}번  {'열림 ' + size if opened else '열 수 없음'}")
        self.camera_result.setText("  /  ".join(lines))
        current = self.camera_index.currentData()
        first_open = next((i for i, opened, _ in results if opened), None)
        if first_open is not None and not any(i == current and o for i, o, _ in results):
            self.camera_index.setCurrentIndex(max(self.camera_index.findData(first_open), 0))

    def result_config(self) -> Config:
        return replace(
            self._cfg,
            camera_index=int(self.camera_index.currentData()),
            camera_width=int(self.resolution.currentData().split("x")[0]),
            camera_height=int(self.resolution.currentData().split("x")[1]),
            backgrounds_dir=self.backgrounds.text(),
            bgr=self.bgr.text(),
            countdown_seconds=int(self.countdown.currentData()),
            repo_path=self.repo.text(),
            checkpoint=self.checkpoints["resnet50"].text(),
            checkpoint_resnet101=self.checkpoints["resnet101"].text(),
            checkpoint_mobilenetv2=self.checkpoints["mobilenetv2"].text(),
            backbone=self.backbone.currentText(),
            model_type=self.model_type.currentText(),
            device=self.device.currentText(),
        ).validated()

"""화면을 구성하는 작은 위젯들: 탤리 점, 단계 표시, 알림 배너, 배경 번호 버튼, 미리보기."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..messages import Level, Notice
from . import theme

_WRAP_LEFT = Qt.AlignmentFlag.AlignLeft.value | Qt.TextFlag.TextWordWrap.value
_CENTER = Qt.AlignmentFlag.AlignCenter.value


ASSETS = Path(__file__).resolve().parent.parent / "assets"


def app_icon() -> QIcon:
    """앱 아이콘 (assets/icon.png). 파일이 없으면 빈 아이콘."""
    path = ASSETS / "icon.png"
    return QIcon(str(path)) if path.is_file() else QIcon()


def app_icon_pixmap(size: int) -> QPixmap:
    icon = app_icon()
    return icon.pixmap(size, size) if not icon.isNull() else QPixmap(size, size)


def repolish(widget: QWidget) -> None:
    """동적 프로퍼티(property) 값을 바꾼 뒤 스타일시트를 다시 적용합니다."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def section_header(title: str, tone: str) -> QHBoxLayout:
    """색 막대 + 제목. tone: brand | cyan | amber | pink"""
    row = QHBoxLayout()
    row.setSpacing(8)
    marker = QFrame()
    marker.setObjectName("marker")
    marker.setProperty("tone", tone)
    label = QLabel(title)
    label.setObjectName("sectionTitle")
    row.addWidget(marker)
    row.addWidget(label)
    return row


def hairline() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def keycaps(*keys: str, height: int = 22, tone: str = "") -> QWidget:
    """키캡 모양 라벨 묶음 (예: keycaps('Space', tone='pink')). tone은 키의 역할별 색입니다."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    for key in keys:
        cap = QLabel(key)
        cap.setObjectName("keycap")
        if tone:
            cap.setProperty("tone", tone)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setFixedHeight(height)
        row.addWidget(cap)
    row.addStretch(1)
    return box


# ---------------------------------------------------------------- 탤리 점
class TallyDot(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._key = "FAINT"

    def set_color(self, key: str) -> None:
        """팔레트 색 이름(예: 'LIVE')으로 지정합니다. 테마를 바꾸면 자동으로 새 색을 따라갑니다."""
        self._key = key
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.color(self._key)))
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))


# ---------------------------------------------------------------- 준비 단계
class StepBar(QWidget):
    LABELS = ("카메라", "배경", "모델", "합성")
    GLYPH = {"pending": "○", "active": "●", "done": "✓", "error": "✕"}

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._labels: List[QLabel] = []
        for i, _ in enumerate(self.LABELS):
            if i:
                line = QFrame()
                line.setObjectName("stepLine")
                row.addWidget(line)
            label = QLabel()
            label.setObjectName("step")
            row.addWidget(label)
            self._labels.append(label)
        row.addStretch(1)
        self.reset()

    def reset(self) -> None:
        for i in range(len(self.LABELS)):
            self.set_status(i, "pending")

    def set_status(self, index: int, status: str) -> None:
        label = self._labels[index]
        label.setText(f"{self.GLYPH[status]}  {self.LABELS[index]}")
        label.setProperty("step", status)
        repolish(label)


# ---------------------------------------------------------------- 알림 배너
class NoticeBanner(QFrame):
    """제목/상황/해결 방법과 조치 버튼을 보여주는 알림 영역."""

    action_requested = Signal(str)
    cleared = Signal()

    AUTO_HIDE_MS = {Level.INFO: 6000, Level.SUCCESS: 6000, Level.WARN: 12000, Level.ERROR: 0}

    def __init__(self, action_labels: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("banner")
        self.setProperty("level", "info")
        self._action_labels = action_labels
        self._level: Optional[Level] = None
        self._code: Optional[str] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 8, 10)
        outer.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(3)
        self._title = QLabel()
        self._title.setObjectName("bannerTitle")
        self._title.setWordWrap(True)
        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._hint = QLabel()
        self._hint.setObjectName("muted")
        self._hint.setWordWrap(True)
        for w in (self._title, self._detail, self._hint):
            text.addWidget(w)
        outer.addLayout(text, 1)

        side = QVBoxLayout()
        side.setSpacing(6)
        side.setContentsMargins(0, 0, 0, 0)
        close = QPushButton("✕")
        close.setObjectName("bannerClose")
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip("닫기")
        close.clicked.connect(self.clear)
        side.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self._buttons_box = QVBoxLayout()
        self._buttons_box.setSpacing(6)
        side.addLayout(self._buttons_box)
        side.addStretch(1)
        outer.addLayout(side)
        self.setVisible(False)

    @property
    def level(self) -> Optional[Level]:
        return self._level if self.isVisible() else None

    @property
    def code(self) -> Optional[str]:
        return self._code if self.isVisible() else None

    def show_notice(self, notice: Notice) -> bool:
        """표시했으면 True. 오류 배너가 떠 있는 동안에는 덜 심각한 알림이 덮어쓰지 못합니다."""
        if self.level == Level.ERROR and notice.level != Level.ERROR:
            return False
        self._level = notice.level
        self._code = notice.code
        self.setProperty("level", notice.level.value)
        self._title.setText(notice.title)
        for label, text in ((self._detail, notice.detail), (self._hint, notice.hint)):
            label.setText(text)
            label.setVisible(bool(text))
        self._rebuild_actions(notice.actions)
        repolish(self)
        self.setVisible(True)
        self._timer.stop()
        delay = 0 if notice.sticky else self.AUTO_HIDE_MS[notice.level]
        if delay:
            self._timer.start(delay)
        return True

    def clear(self) -> None:
        was_visible = self.isVisible()
        self._timer.stop()
        self._level = None
        self._code = None
        self.setVisible(False)
        if was_visible:
            self.cleared.emit()

    def _rebuild_actions(self, actions: Sequence[str]) -> None:
        while self._buttons_box.count():
            item = self._buttons_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for action in actions:
            button = QPushButton(self._action_labels.get(action, action))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _=False, a=action: self.action_requested.emit(a))
            self._buttons_box.addWidget(button)


# ---------------------------------------------------------------- 배경 번호 버튼
class BusRow(QWidget):
    """영상 스위처의 번호 버튼처럼 1~9번 배경을 한 줄로 보여줍니다. 현재 배경만 초록으로 켜집니다."""

    chosen = Signal(int)
    SLOTS = 9
    HUES = ("brand", "cyan", "pink", "amber", "brand", "cyan", "pink", "amber", "brand")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        self._buttons: List[QPushButton] = []
        for i in range(self.SLOTS):
            button = QPushButton(str(i + 1))
            button.setObjectName("bus")
            button.setProperty("current", False)
            button.setProperty("hue", self.HUES[i])
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 숫자/방향 키 단축키를 가로채지 않도록
            button.clicked.connect(lambda _=False, n=i + 1: self.chosen.emit(n))
            row.addWidget(button)
            self._buttons.append(button)
        row.addStretch(1)
        self.set_count(0)

    def set_count(self, count: int) -> None:
        for i, button in enumerate(self._buttons):
            button.setEnabled(i < count)

    def set_current(self, number: int) -> None:
        for i, button in enumerate(self._buttons):
            button.setProperty("current", (i + 1) == number)
            repolish(button)


# ---------------------------------------------------------------- 미리보기
class PreviewView(QWidget):
    """카메라/합성 영상을 비율 유지로 그리고, 그 위에 안내 문구·카운트다운·HUD를 얹습니다."""

    FRAME = 4  # 테두리(탤리) 두께

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._frame: Optional[QImage] = None
        self._title = ""
        self._body = ""
        self._countdown: Optional[int] = None
        self._countdown_total = 1
        self._hud = ""
        self._tally: Optional[str] = None

    # -- 상태 ---------------------------------------------------------------
    def set_frame(self, image: QImage) -> None:
        self._frame = image
        self.update()

    def clear_frame(self) -> None:
        self._frame = None
        self.update()

    def has_frame(self) -> bool:
        return self._frame is not None

    def set_overlay(self, title: str, body: str = "") -> None:
        self._title, self._body = title, body
        self.update()

    def clear_overlay(self) -> None:
        self.set_overlay("", "")

    def set_countdown(self, value: Optional[int], total: int = 1) -> None:
        self._countdown = value
        self._countdown_total = max(total, 1)
        self.update()

    def set_tally(self, key: Optional[str]) -> None:
        """영상 테두리 색(팔레트 이름). 카메라의 탤리 램프처럼 현재 상태를 알려줍니다."""
        if key != self._tally:
            self._tally = key
            self.update()

    def set_hud(self, text: str) -> None:
        self._hud = text
        self.update()

    # -- 그리기 ---------------------------------------------------------------
    def _image_rect(self) -> QRect:
        box = self.rect().adjusted(self.FRAME, self.FRAME, -self.FRAME, -self.FRAME)
        if self._frame is None or self._frame.isNull():
            return box
        size = self._frame.size().scaled(box.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect(
            QPoint(box.x() + (box.width() - size.width()) // 2, box.y() + (box.height() - size.height()) // 2), size
        )

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.color("MONITOR")))
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        image_rect = self._image_rect()
        if self._frame is not None and not self._frame.isNull():
            p.drawImage(image_rect, self._frame)

        if self._countdown is not None:
            self._draw_countdown(p, image_rect)
        elif self._title:
            self._draw_card(p, image_rect, anchor_bottom=self._frame is not None)

        if self._hud:
            self._draw_hud(p, image_rect)

        if self._tally:
            half = self.FRAME / 2
            pen = QPen(QColor(theme.color(self._tally)), self.FRAME)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(half, half, -half, -half), 8, 8)

    def _draw_card(self, p: QPainter, area: QRect, anchor_bottom: bool) -> None:
        max_w = min(area.width() - 48, 480)
        if max_w < 160:
            return
        pad = 18
        inner_w = max_w - pad * 2
        title_font = QFont(self.font())
        title_font.setPixelSize(18)
        title_font.setWeight(QFont.Weight.DemiBold)
        body_font = QFont(self.font())
        body_font.setPixelSize(13)
        title_h = QFontMetrics(title_font).boundingRect(QRect(0, 0, inner_w, 2000), _WRAP_LEFT, self._title).height()
        body_h = 0
        if self._body:
            body_h = QFontMetrics(body_font).boundingRect(QRect(0, 0, inner_w, 4000), _WRAP_LEFT, self._body).height()
        height = pad * 2 + title_h + (8 + body_h if body_h else 0)
        x = area.x() + (area.width() - max_w) // 2
        y = area.bottom() - height - 28 if anchor_bottom else area.y() + (area.height() - height) // 2
        card = QRect(x, y, max_w, height)

        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.setBrush(QColor(30, 31, 34, 230))
        p.drawRoundedRect(QRectF(card), 6, 6)
        p.setFont(title_font)
        p.setPen(QColor(theme.ON_MONITOR_TEXT))
        p.drawText(QRect(x + pad, y + pad, inner_w, title_h), _WRAP_LEFT, self._title)
        if self._body:
            p.setFont(body_font)
            p.setPen(QColor(theme.ON_MONITOR_MUTED))
            p.drawText(QRect(x + pad, y + pad + title_h + 8, inner_w, body_h), _WRAP_LEFT, self._body)

    def _draw_countdown(self, p: QPainter, area: QRect) -> None:
        p.fillRect(area, QColor(0, 0, 0, 120))
        size = max(min(area.width(), area.height()) // 3, 96)
        ring = QRect(0, 0, size, size)
        ring.moveCenter(area.center() - QPoint(0, 16))
        value = self._countdown or 0

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 40), 6))
        p.drawEllipse(ring)
        if value > 0:
            fraction = min(value / self._countdown_total, 1.0)
            pen = QPen(QColor(theme.ON_MONITOR_STOP), 6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(ring, 90 * 16, int(-360 * 16 * fraction))

        font = QFont(self.font())
        font.setPixelSize(int(size * 0.5))
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(theme.ON_MONITOR_TEXT))
        p.drawText(ring, _CENTER, str(value) if value > 0 else "●")

        caption_font = QFont(self.font())
        caption_font.setPixelSize(15)
        p.setFont(caption_font)
        caption = "화면 밖으로 이동해 주세요" if value > 0 else "촬영 중… 움직이지 마세요"
        p.drawText(
            QRect(area.x(), ring.bottom() + 18, area.width(), 28), _CENTER, caption
        )

    def _draw_hud(self, p: QPainter, area: QRect) -> None:
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        w = QFontMetrics(font).horizontalAdvance(self._hud) + 20
        box = QRect(area.x() + 14, area.y() + 14, w, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(QRectF(box), 4, 4)
        p.setPen(QColor(theme.ON_MONITOR_TEXT))
        p.drawText(box, _CENTER, self._hud)

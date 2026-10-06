"""앱 아이콘 생성기: bgmatte_app/assets/icon.png 와 packaging/AppIcon.icns 를 만듭니다.

아이콘 디자인을 바꾸고 싶을 때만 실행하세요 (결과 파일은 저장소에 이미 들어 있습니다).
    python packaging/make_icon.py
의미: 보라→청록 배경 위에 인물 실루엣을 '오려내' 놓고(매팅), 오른쪽 아래의 분홍 면은 합성할 새 배경,
오른쪽 위의 초록 점은 방송 중(탤리) 표시입니다.
"""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024


def draw(size: int = SIZE) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = size / 1024

    # macOS 아이콘 격자: 824px 둥근 사각형을 가운데에
    tile = QRectF(100 * k, 100 * k, 824 * k, 824 * k)
    clip = QPainterPath()
    clip.addRoundedRect(tile, 186 * k, 186 * k)

    # 바닥 그림자
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(14):
        grow = (2 + i * 2) * k
        shadow = QPainterPath()
        shadow.addRoundedRect(tile.adjusted(-grow, -grow + 22 * k, grow, grow + 22 * k), (186 + i * 2) * k, (186 + i * 2) * k)
        p.fillPath(shadow, QColor(20, 10, 60, 7))

    p.setClipPath(clip)
    bg = QLinearGradient(tile.topLeft(), tile.bottomRight())
    bg.setColorAt(0.0, QColor("#5a46e6"))
    bg.setColorAt(0.55, QColor("#4f7cf0"))
    bg.setColorAt(1.0, QColor("#22bfd9"))
    p.fillRect(tile, QBrush(bg))

    # 오른쪽 아래: 합성할 새 배경 (분홍→노랑)
    plate = QPainterPath()
    plate.moveTo(tile.right() + 4 * k, tile.top() + 250 * k)
    plate.lineTo(tile.right() + 4 * k, tile.bottom() + 4 * k)
    plate.lineTo(tile.left() + 170 * k, tile.bottom() + 4 * k)
    plate.closeSubpath()
    pg = QLinearGradient(QPointF(tile.right(), tile.top() + 250 * k), QPointF(tile.left() + 170 * k, tile.bottom()))
    pg.setColorAt(0.0, QColor("#f4569f"))
    pg.setColorAt(1.0, QColor("#f7b53d"))
    p.fillPath(plate, QBrush(pg))

    # 위쪽 은은한 빛
    glow = QRadialGradient(QPointF(tile.left() + 250 * k, tile.top() + 160 * k), 520 * k)
    glow.setColorAt(0.0, QColor(255, 255, 255, 70))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(tile, QBrush(glow))

    # 인물 실루엣 (머리 + 어깨)
    cx = 500 * k
    person = QPainterPath()
    person.addEllipse(QPointF(cx, 400 * k), 118 * k, 126 * k)
    shoulders = QPainterPath()
    shoulders.moveTo(cx - 262 * k, tile.bottom() + 10 * k)
    shoulders.cubicTo(cx - 262 * k, 640 * k, cx - 170 * k, 560 * k, cx, 560 * k)
    shoulders.cubicTo(cx + 170 * k, 560 * k, cx + 262 * k, 640 * k, cx + 262 * k, tile.bottom() + 10 * k)
    shoulders.closeSubpath()
    person.addPath(shoulders)
    shade = QPainterPath(person)
    shade.translate(10 * k, 14 * k)
    p.fillPath(shade, QColor(25, 10, 90, 70))
    p.fillPath(person, QColor("#ffffff"))
    # 오려내기 선택 영역을 나타내는 점선 (매팅의 핵심 이미지)
    grown = QPainterPath()
    for stroker_width in (30 * k,):
        from PySide6.QtGui import QPainterPathStroker

        stroker = QPainterPathStroker()
        stroker.setWidth(stroker_width)
        grown = stroker.createStroke(person).united(person)
    outline = QPen(QColor("#ffffff"), 7 * k)
    outline.setStyle(Qt.PenStyle.CustomDashLine)
    outline.setDashPattern([2.2, 1.8])
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(outline)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(grown.simplified())

    # 방송 중 점 (오른쪽 위)
    p.setClipping(False)
    dot_c = QPointF(tile.right() - 150 * k, tile.top() + 150 * k)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(dot_c, 58 * k, 58 * k)
    p.setBrush(QColor("#2fd985"))
    p.drawEllipse(dot_c, 40 * k, 40 * k)
    p.end()
    return img


def png_bytes(img: QImage, px: int) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    scaled = img.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    scaled.save(buf, "PNG")
    return bytes(data)


def write_icns(img: QImage, path: Path) -> None:
    """PNG 조각을 이어 붙이는 .icns (macOS 10.7 이상이 읽는 형식)."""
    entries = [
        (b"icp4", 16), (b"icp5", 32), (b"icp6", 64), (b"ic07", 128), (b"ic08", 256),
        (b"ic09", 512), (b"ic10", 1024), (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512),
    ]
    chunks = b"".join(kind + struct.pack(">I", 8 + len(d)) + d for kind, px in entries for d in [png_bytes(img, px)])
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(chunks)) + chunks)


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    img = draw()
    (ROOT / "bgmatte_app" / "assets").mkdir(exist_ok=True)
    (ROOT / "bgmatte_app" / "assets" / "icon.png").write_bytes(png_bytes(img, 512))
    (ROOT / "packaging" / "AppIcon.png").write_bytes(png_bytes(img, 1024))
    write_icns(img, ROOT / "packaging" / "AppIcon.icns")
    print("아이콘을 만들었습니다: bgmatte_app/assets/icon.png, packaging/AppIcon.icns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

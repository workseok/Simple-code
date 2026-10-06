"""색상 팔레트(어둡게/밝게)와 전체 스타일시트.

방향: 영상 스위처/모니터 콘솔처럼 차분한 바탕에, 상태를 알려주는 불빛(탤리) 색만 쓴다.
  초록 = 현재 사용 중(실행 중, 선택된 배경) / 빨강 = 촬영 중·오류 / 호박색 = 사용자 조치 필요
카드·그림자 대신 가는 구분선으로 영역을 나누고, 강조는 번호 버튼(배경 버스) 한 곳에 모읍니다.

테마는 실행 중에 바꿀 수 있으므로 색을 모듈 상수로 굳히지 않고 `color("TEXT")`처럼 그때그때 읽습니다.
영상 미리보기 위에 얹는 글자는 테마와 무관하게 항상 밝은 색(ON_MONITOR_*)을 씁니다.
"""

from dataclasses import dataclass
from typing import Optional

THEMES = ("dark", "light")
THEME_LABELS = {"dark": "어둡게", "light": "밝게"}

FONT_STACK = '"Apple SD Gothic Neo", "Helvetica Neue", "Noto Sans CJK KR", "Malgun Gothic", sans-serif'

# 영상 위에 얹는 글자 (미리보기는 두 테마 모두 검은 모니터라서 고정)
ON_MONITOR_TEXT = "#e9e9ea"
ON_MONITOR_MUTED = "#9a9da5"
ON_MONITOR_STOP = "#e5483b"


@dataclass(frozen=True)
class Palette:
    name: str
    MONITOR: str          # 영상 모니터 주변 (두 테마 모두 검정)
    CONSOLE: str          # 창 바탕
    SURFACE: str          # 버튼/키캡
    SURFACE_HOVER: str
    SURFACE_PRESSED: str
    INSET: str            # 목록, 입력창, 비활성 버튼
    HAIRLINE: str
    BORDER_SOFT: str
    BORDER_STRONG: str
    TEXT: str
    MUTED: str
    FAINT: str
    LIVE: str             # 초록
    STOP: str             # 빨강
    WAIT: str             # 호박
    INFO: str
    ON_PRIMARY: str       # 진한 버튼 위 글자
    PRIMARY_HOVER: str
    PRIMARY_DISABLED_BG: str
    PRIMARY_DISABLED_TEXT: str
    BUS_BORDER: str
    BUS_TEXT: str
    BUS_HOVER: str
    BUS_DISABLED_TEXT: str
    BUS_DISABLED_BORDER: str
    BUS_CURRENT_TEXT: str
    BUS_CURRENT_BORDER: str
    BANNER_INFO: str
    BANNER_SUCCESS: str
    BANNER_WARN: str
    BANNER_ERROR: str
    SELECTION: str


DARK = Palette(
    name="dark",
    MONITOR="#000000",
    CONSOLE="#25272b",
    SURFACE="#2f3136",
    SURFACE_HOVER="#3a3d44",
    SURFACE_PRESSED="#292b30",
    INSET="#1e1f22",
    HAIRLINE="#3d4047",
    BORDER_SOFT="#34363b",
    BORDER_STRONG="#4a4d55",
    TEXT="#e9e9ea",
    MUTED="#9a9da5",
    FAINT="#6b6e76",
    LIVE="#3fb56b",
    STOP="#e5483b",
    WAIT="#e0a82e",
    INFO="#6aa4e8",
    ON_PRIMARY="#1b1c1f",
    PRIMARY_HOVER="#ffffff",
    PRIMARY_DISABLED_BG="#55575d",
    PRIMARY_DISABLED_TEXT="#2b2c30",
    BUS_BORDER="#484b53",
    BUS_TEXT="#c9cbd0",
    BUS_HOVER="#33363c",
    BUS_DISABLED_TEXT="#55575d",
    BUS_DISABLED_BORDER="#303338",
    BUS_CURRENT_TEXT="#0d1a11",
    BUS_CURRENT_BORDER="#66d28f",
    BANNER_INFO="#262f3a",
    BANNER_SUCCESS="#1f3126",
    BANNER_WARN="#393120",
    BANNER_ERROR="#3a2325",
    SELECTION="#4b5666",
)

LIGHT = Palette(
    name="light",
    MONITOR="#000000",
    CONSOLE="#f2f3f5",
    SURFACE="#ffffff",
    SURFACE_HOVER="#e9ebee",
    SURFACE_PRESSED="#dde0e5",
    INSET="#ffffff",
    HAIRLINE="#d2d5db",
    BORDER_SOFT="#dcdfe4",
    BORDER_STRONG="#b7bcc6",
    TEXT="#1d1f23",
    MUTED="#5b606a",
    FAINT="#868b96",
    LIVE="#1d9a52",
    STOP="#d33a2e",
    WAIT="#b36f0a",
    INFO="#2c6dc9",
    ON_PRIMARY="#ffffff",
    PRIMARY_HOVER="#000000",
    PRIMARY_DISABLED_BG="#c5c8cf",
    PRIMARY_DISABLED_TEXT="#f2f3f5",
    BUS_BORDER="#b7bcc6",
    BUS_TEXT="#33373e",
    BUS_HOVER="#e9ebee",
    BUS_DISABLED_TEXT="#b3b7c0",
    BUS_DISABLED_BORDER="#dcdfe4",
    BUS_CURRENT_TEXT="#ffffff",
    BUS_CURRENT_BORDER="#13763c",
    BANNER_INFO="#e5eefb",
    BANNER_SUCCESS="#e2f4e9",
    BANNER_WARN="#fbefd6",
    BANNER_ERROR="#fbe4e1",
    SELECTION="#cfe0fa",
)

PALETTES = {"dark": DARK, "light": LIGHT}

_current: Palette = DARK


def current() -> Palette:
    return _current


def set_theme(name: str) -> Palette:
    """알 수 없는 이름이면 어둡게로 되돌립니다."""
    global _current
    _current = PALETTES.get(name, DARK)
    return _current


def color(key: str) -> str:
    """현재 테마의 색 (예: color('LIVE'))."""
    return getattr(_current, key)


def build_style(p: Optional[Palette] = None) -> str:
    p = p or _current
    return f"""
* {{
    font-family: {FONT_STACK};
    font-size: 13px;
    color: {p.TEXT};
}}
QMainWindow, QDialog, QWidget#console {{ background: {p.CONSOLE}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {p.INSET}; color: {p.TEXT}; border: 1px solid {p.HAIRLINE}; padding: 6px 8px; }}

QLabel#muted {{ color: {p.MUTED}; }}
QLabel#faint {{ color: {p.FAINT}; }}
QLabel#sectionTitle {{ font-weight: 600; }}
QLabel#appTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#bgName {{ font-size: 15px; font-weight: 600; }}
QFrame#hairline {{ background: {p.HAIRLINE}; border: none; max-height: 1px; min-height: 1px; }}

QPushButton {{
    background: {p.SURFACE}; border: 1px solid {p.HAIRLINE}; border-radius: 4px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {p.SURFACE_HOVER}; }}
QPushButton:pressed {{ background: {p.SURFACE_PRESSED}; }}
QPushButton:disabled {{ color: {p.FAINT}; background: {p.INSET}; border-color: {p.BORDER_SOFT}; }}
QPushButton#primary {{ background: {p.TEXT}; color: {p.ON_PRIMARY}; border-color: {p.TEXT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {p.PRIMARY_HOVER}; }}
QPushButton#primary:disabled {{ background: {p.PRIMARY_DISABLED_BG}; color: {p.PRIMARY_DISABLED_TEXT}; border-color: {p.PRIMARY_DISABLED_BG}; }}
QPushButton#primary[demoted="true"] {{ background: {p.SURFACE}; color: {p.TEXT}; border-color: {p.HAIRLINE}; font-weight: 400; }}
QPushButton[emphasis="true"] {{ background: {p.TEXT}; color: {p.ON_PRIMARY}; border-color: {p.TEXT}; font-weight: 600; }}
QPushButton[emphasis="true"]:hover {{ background: {p.PRIMARY_HOVER}; }}

QPushButton#seg {{
    padding: 3px 10px; font-size: 12px; color: {p.MUTED};
    background: {p.SURFACE}; border: 1px solid {p.HAIRLINE};
}}
QPushButton#seg:checked {{ background: {p.TEXT}; color: {p.ON_PRIMARY}; border-color: {p.TEXT}; font-weight: 600; }}
QPushButton#seg[pos="left"] {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
QPushButton#seg[pos="right"] {{ border-top-left-radius: 0; border-bottom-left-radius: 0; }}

QPushButton#bus {{
    padding: 0; min-width: 31px; max-width: 31px; min-height: 36px; max-height: 36px;
    font-size: 15px; font-weight: 700; background: {p.INSET}; border: 1px solid {p.BUS_BORDER};
    border-radius: 3px; color: {p.BUS_TEXT};
}}
QPushButton#bus:hover {{ background: {p.BUS_HOVER}; }}
QPushButton#bus:disabled {{ color: {p.BUS_DISABLED_TEXT}; background: {p.INSET}; border-color: {p.BUS_DISABLED_BORDER}; }}
QPushButton#bus[current="true"] {{ background: {p.LIVE}; color: {p.BUS_CURRENT_TEXT}; border-color: {p.BUS_CURRENT_BORDER}; }}

QLabel#keycap {{
    background: {p.SURFACE}; border: 1px solid {p.BORDER_STRONG}; border-bottom: 2px solid {p.BORDER_STRONG};
    border-radius: 4px; padding: 0 6px; font-weight: 600; min-width: 14px;
}}

/* 상태 · 단축키 · 알림 기록은 보조 정보라서 한 단계 작게 표시 */
QWidget#compact QLabel {{ font-size: 11px; }}
QWidget#compact QLabel#sectionTitle {{ font-size: 12px; }}
QWidget#compact QLabel#keycap {{ font-size: 10px; padding: 0 4px; min-width: 10px; border-radius: 3px; }}

QLabel#step {{ color: {p.FAINT}; }}
QLabel#step[step="active"] {{ color: {p.TEXT}; font-weight: 600; }}
QLabel#step[step="done"] {{ color: {p.LIVE}; }}
QLabel#step[step="error"] {{ color: {p.STOP}; font-weight: 600; }}
QFrame#stepLine {{ background: {p.HAIRLINE}; min-height: 1px; max-height: 1px; min-width: 16px; max-width: 16px; }}

QFrame#banner {{ border-radius: 3px; border: none; border-left: 4px solid {p.INFO}; background: {p.BANNER_INFO}; }}
QFrame#banner[level="success"] {{ border-left-color: {p.LIVE}; background: {p.BANNER_SUCCESS}; }}
QFrame#banner[level="warn"] {{ border-left-color: {p.WAIT}; background: {p.BANNER_WARN}; }}
QFrame#banner[level="error"] {{ border-left-color: {p.STOP}; background: {p.BANNER_ERROR}; }}
QLabel#bannerTitle {{ font-weight: 700; font-size: 14px; }}
QPushButton#bannerClose {{
    background: transparent; border: none; color: {p.MUTED}; padding: 0 4px; font-size: 15px;
}}
QPushButton#bannerClose:hover {{ color: {p.TEXT}; }}

QListWidget#history {{
    background: {p.INSET}; border: 1px solid {p.BORDER_SOFT}; border-radius: 4px; outline: none;
    font-size: 11px;
}}
QListWidget#history::item {{ padding: 2px 6px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.BORDER_STRONG}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {p.INSET}; border: 1px solid {p.HAIRLINE}; border-radius: 4px; padding: 5px 8px;
    selection-background-color: {p.SELECTION};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {p.INFO}; }}
QComboBox QAbstractItemView {{ background: {p.INSET}; border: 1px solid {p.HAIRLINE}; selection-background-color: {p.SURFACE_HOVER}; }}
QCheckBox {{ spacing: 8px; }}
"""

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
    BRAND: str            # 브랜드 보라 (주 버튼, 선택 표시)
    BRAND_HOVER: str
    CYAN: str             # 수치/상태 값
    PINK: str             # 촬영 관련
    PANEL: str            # 패널 바탕
    PANEL_BORDER: str


DARK = Palette(
    name="dark",
    MONITOR="#000000",
    CONSOLE="#13141c",
    SURFACE="#232536",
    SURFACE_HOVER="#2d3047",
    SURFACE_PRESSED="#1b1d2b",
    INSET="#0f1018",
    HAIRLINE="#31354d",
    BORDER_SOFT="#292c41",
    BORDER_STRONG="#454a6b",
    TEXT="#eeeff7",
    MUTED="#9fa3c0",
    FAINT="#6e7290",
    LIVE="#3fd68b",
    STOP="#f2506a",
    WAIT="#f2b441",
    INFO="#6bb0ff",
    ON_PRIMARY="#ffffff",
    PRIMARY_HOVER="#9d90fa",
    PRIMARY_DISABLED_BG="#3a3d57",
    PRIMARY_DISABLED_TEXT="#7c80a0",
    BUS_BORDER="#3d4260",
    BUS_TEXT="#cdd0e8",
    BUS_HOVER="#2b2e45",
    BUS_DISABLED_TEXT="#575b78",
    BUS_DISABLED_BORDER="#2a2d42",
    BUS_CURRENT_TEXT="#06210f",
    BUS_CURRENT_BORDER="#7ae6ac",
    BANNER_INFO="#1c2a45",
    BANNER_SUCCESS="#143026",
    BANNER_WARN="#3a2d14",
    BANNER_ERROR="#3b1b28",
    SELECTION="#4b5090",
    BRAND="#8b7cf6",
    BRAND_HOVER="#a094fa",
    CYAN="#38c8e6",
    PINK="#f46aa9",
    PANEL="#1a1c2a",
    PANEL_BORDER="#2c3049",
)

LIGHT = Palette(
    name="light",
    MONITOR="#000000",
    CONSOLE="#f2f1fa",
    SURFACE="#ffffff",
    SURFACE_HOVER="#ebeaf7",
    SURFACE_PRESSED="#dedcef",
    INSET="#ffffff",
    HAIRLINE="#d8d6ea",
    BORDER_SOFT="#e3e1f1",
    BORDER_STRONG="#bcb9d8",
    TEXT="#1c1b2e",
    MUTED="#5d5b7b",
    FAINT="#8e8caa",
    LIVE="#11a35c",
    STOP="#d6324f",
    WAIT="#bb7803",
    INFO="#2c6fe0",
    ON_PRIMARY="#ffffff",
    PRIMARY_HOVER="#5b4bdc",
    PRIMARY_DISABLED_BG="#cfcde2",
    PRIMARY_DISABLED_TEXT="#f2f1fa",
    BUS_BORDER="#bcb9d8",
    BUS_TEXT="#34324d",
    BUS_HOVER="#ebeaf7",
    BUS_DISABLED_TEXT="#b4b2cc",
    BUS_DISABLED_BORDER="#e3e1f1",
    BUS_CURRENT_TEXT="#ffffff",
    BUS_CURRENT_BORDER="#0c7a43",
    BANNER_INFO="#e3ebfd",
    BANNER_SUCCESS="#dcf3e7",
    BANNER_WARN="#faedd0",
    BANNER_ERROR="#fbe0e6",
    SELECTION="#cfd0f7",
    BRAND="#6b5ce7",
    BRAND_HOVER="#5646d6",
    CYAN="#0d92b0",
    PINK="#d93a86",
    PANEL="#ffffff",
    PANEL_BORDER="#dedcee",
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
QLabel#sectionTitle {{ font-weight: 700; }}
QLabel#appTitle {{ font-size: 18px; font-weight: 800; }}
QLabel#bgName {{ font-size: 15px; font-weight: 600; }}
QLabel#fpsValue {{ color: {p.CYAN}; font-weight: 700; }}
QFrame#hairline {{ background: {p.HAIRLINE}; border: none; max-height: 1px; min-height: 1px; }}

/* 제목 아래 구분선 (색 없이 얇은 선 하나) */
QFrame#accentLine {{ border: none; min-height: 1px; max-height: 1px; background: {p.HAIRLINE}; }}

/* 오른쪽 패널의 영역 상자와 색 막대 */
QFrame#panel {{ background: {p.PANEL}; border: 1px solid {p.PANEL_BORDER}; border-radius: 10px; }}
QFrame#marker {{ border: none; border-radius: 2px; min-width: 4px; max-width: 4px; min-height: 14px; max-height: 14px; }}
QFrame#marker[tone="brand"] {{ background: {p.BRAND}; }}
QFrame#marker[tone="cyan"] {{ background: {p.CYAN}; }}
QFrame#marker[tone="amber"] {{ background: {p.WAIT}; }}
QFrame#marker[tone="pink"] {{ background: {p.PINK}; }}

QPushButton {{
    background: {p.SURFACE}; border: 1px solid {p.HAIRLINE}; border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {p.SURFACE_HOVER}; }}
QPushButton:pressed {{ background: {p.SURFACE_PRESSED}; }}
QPushButton:disabled {{ color: {p.FAINT}; background: {p.INSET}; border-color: {p.BORDER_SOFT}; }}

/* 시작/정지: 평소엔 보라, 실행 중에는 빨강(정지) */
QPushButton#primary {{ background: {p.BRAND}; color: {p.ON_PRIMARY}; border-color: {p.BRAND}; font-weight: 700; }}
QPushButton#primary:hover {{ background: {p.PRIMARY_HOVER}; border-color: {p.PRIMARY_HOVER}; }}
QPushButton#primary[running="true"] {{ background: {p.STOP}; border-color: {p.STOP}; }}
QPushButton#primary:disabled {{ background: {p.PRIMARY_DISABLED_BG}; color: {p.PRIMARY_DISABLED_TEXT}; border-color: {p.PRIMARY_DISABLED_BG}; }}
QPushButton#primary[demoted="true"] {{ background: {p.SURFACE}; color: {p.TEXT}; border-color: {p.HAIRLINE}; font-weight: 400; }}

/* 배경 촬영: 평소엔 다른 버튼과 같은 모양, 촬영이 필요할 때만 브랜드 색으로 강조 */
QPushButton#capture:disabled {{ color: {p.FAINT}; border-color: {p.BORDER_SOFT}; }}
QPushButton#capture[emphasis="true"], QPushButton[emphasis="true"] {{ background: {p.BRAND}; color: {p.ON_PRIMARY}; border-color: {p.BRAND}; font-weight: 700; }}
QPushButton#capture[emphasis="true"]:hover, QPushButton[emphasis="true"]:hover {{ background: {p.BRAND_HOVER}; }}

QPushButton#seg {{
    padding: 3px 10px; font-size: 12px; color: {p.MUTED};
    background: {p.SURFACE}; border: 1px solid {p.HAIRLINE};
}}
QPushButton#seg:checked {{ background: {p.SURFACE_PRESSED}; color: {p.TEXT}; border-color: {p.BORDER_STRONG}; font-weight: 700; }}
QPushButton#seg[pos="left"] {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
QPushButton#seg[pos="right"] {{ border-top-left-radius: 0; border-bottom-left-radius: 0; }}

/* 화면 아래의 작은 스위치/버튼. 켜짐은 색 대신 눌린 모양 + 진한 글씨로 표시 */
QPushButton#chip {{
    padding: 4px 11px; font-size: 12px; color: {p.MUTED};
    background: {p.SURFACE}; border: 1px solid {p.HAIRLINE}; border-radius: 12px;
}}
QPushButton#chip:hover {{ background: {p.SURFACE_HOVER}; color: {p.TEXT}; }}
QPushButton#chip:checked {{ background: {p.SURFACE_PRESSED}; color: {p.TEXT}; border-color: {p.BORDER_STRONG}; font-weight: 700; }}

/* 배경 번호 버튼: 스위처처럼 번호마다 아래쪽에 색이 칠해져 있고, 사용 중인 번호만 초록으로 켜집니다 */
QPushButton#bus {{
    padding: 0; min-width: 29px; max-width: 29px; min-height: 38px; max-height: 38px;
    font-size: 15px; font-weight: 700; background: {p.INSET}; border: 1px solid {p.BUS_BORDER};
    border-bottom: 3px solid {p.BUS_BORDER}; border-radius: 4px; color: {p.BUS_TEXT};
}}
QPushButton#bus[hue="brand"] {{ border-bottom-color: {p.BRAND}; }}
QPushButton#bus[hue="cyan"] {{ border-bottom-color: {p.CYAN}; }}
QPushButton#bus[hue="pink"] {{ border-bottom-color: {p.PINK}; }}
QPushButton#bus[hue="amber"] {{ border-bottom-color: {p.WAIT}; }}
QPushButton#bus:hover {{ background: {p.BUS_HOVER}; }}
QPushButton#bus:disabled {{ color: {p.BUS_DISABLED_TEXT}; background: {p.INSET}; border-color: {p.BUS_DISABLED_BORDER}; }}
QPushButton#bus[current="true"] {{ background: {p.LIVE}; color: {p.BUS_CURRENT_TEXT}; border-color: {p.BUS_CURRENT_BORDER}; }}

QLabel#keycap {{
    background: {p.SURFACE}; border: 1px solid {p.BORDER_STRONG}; border-bottom: 2px solid {p.BORDER_STRONG};
    border-radius: 4px; padding: 0 6px; font-weight: 700; min-width: 14px;
}}

/* 상태 · 단축키 · 알림 기록은 보조 정보라서 한 단계 작게 표시 */
QWidget#compact QLabel {{ font-size: 11px; }}
QWidget#compact QLabel#sectionTitle {{ font-size: 12px; }}
QWidget#compact QLabel#keycap {{ font-size: 10px; padding: 0 4px; min-width: 10px; border-radius: 3px; }}

QLabel#step {{ color: {p.FAINT}; }}
QLabel#step[step="active"] {{ color: {p.BRAND}; font-weight: 700; }}
QLabel#step[step="done"] {{ color: {p.LIVE}; }}
QLabel#step[step="error"] {{ color: {p.STOP}; font-weight: 700; }}
QFrame#stepLine {{ background: {p.HAIRLINE}; min-height: 1px; max-height: 1px; min-width: 16px; max-width: 16px; }}

QFrame#banner {{ border-radius: 6px; border: none; border-left: 4px solid {p.INFO}; background: {p.BANNER_INFO}; }}
QFrame#banner[level="success"] {{ border-left-color: {p.LIVE}; background: {p.BANNER_SUCCESS}; }}
QFrame#banner[level="warn"] {{ border-left-color: {p.WAIT}; background: {p.BANNER_WARN}; }}
QFrame#banner[level="error"] {{ border-left-color: {p.STOP}; background: {p.BANNER_ERROR}; }}
QLabel#bannerTitle {{ font-weight: 700; font-size: 14px; }}
QPushButton#bannerClose {{
    background: transparent; border: none; color: {p.MUTED}; padding: 0 4px; font-size: 15px;
}}
QPushButton#bannerClose:hover {{ color: {p.TEXT}; }}

QListWidget#history {{
    background: {p.INSET}; border: 1px solid {p.BORDER_SOFT}; border-radius: 6px; outline: none;
    font-size: 11px;
}}
QListWidget#history::item {{ padding: 2px 6px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.BORDER_STRONG}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {p.INSET}; border: 1px solid {p.HAIRLINE}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {p.SELECTION};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {p.BRAND}; }}
QComboBox QAbstractItemView {{ background: {p.INSET}; border: 1px solid {p.HAIRLINE}; selection-background-color: {p.SURFACE_HOVER}; }}
QCheckBox {{ spacing: 8px; }}
"""

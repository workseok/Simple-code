"""색상 토큰과 전체 스타일시트.

방향: 영상 스위처/모니터 콘솔처럼 차분한 회색 바탕에, 상태를 알려주는 불빛(탤리) 색만 쓴다.
  초록 = 현재 사용 중(실행 중, 선택된 배경) / 빨강 = 촬영 중·오류 / 호박색 = 사용자 조치 필요
카드·그림자 대신 가는 구분선으로 영역을 나누고, 강조는 번호 버튼(배경 버스) 한 곳에 모읍니다.
"""

# 색상 토큰
MONITOR = "#000000"      # 영상 모니터 주변 (진짜 검정)
CONSOLE = "#25272b"      # 창 바탕
SURFACE = "#2f3136"      # 버튼/키캡
INSET = "#1e1f22"        # 움푹 들어간 영역 (목록, 비활성 버튼)
HAIRLINE = "#3d4047"
TEXT = "#e9e9ea"
MUTED = "#9a9da5"
FAINT = "#6b6e76"

LIVE = "#3fb56b"         # 초록
STOP = "#e5483b"         # 빨강
WAIT = "#e0a82e"         # 호박
INFO = "#6aa4e8"

FONT_STACK = '"Apple SD Gothic Neo", "Helvetica Neue", "Noto Sans CJK KR", "Malgun Gothic", sans-serif'

STYLE = f"""
* {{
    font-family: {FONT_STACK};
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog, QWidget#console {{ background: {CONSOLE}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {INSET}; color: {TEXT}; border: 1px solid {HAIRLINE}; padding: 6px 8px; }}

QLabel#muted {{ color: {MUTED}; }}
QLabel#faint {{ color: {FAINT}; }}
QLabel#sectionTitle {{ font-weight: 600; }}
QLabel#appTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#bgName {{ font-size: 15px; font-weight: 600; }}
QFrame#hairline {{ background: {HAIRLINE}; border: none; max-height: 1px; min-height: 1px; }}

QPushButton {{
    background: {SURFACE}; border: 1px solid {HAIRLINE}; border-radius: 4px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: #3a3d44; }}
QPushButton:pressed {{ background: #292b30; }}
QPushButton:disabled {{ color: {FAINT}; background: {INSET}; border-color: #34363b; }}
QPushButton#primary {{ background: {TEXT}; color: #1b1c1f; border-color: {TEXT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: #ffffff; }}
QPushButton#primary:disabled {{ background: #55575d; color: #2b2c30; border-color: #55575d; }}
QPushButton#primary[demoted="true"] {{ background: {SURFACE}; color: {TEXT}; border-color: {HAIRLINE}; font-weight: 400; }}
QPushButton[emphasis="true"] {{ background: {TEXT}; color: #1b1c1f; border-color: {TEXT}; font-weight: 600; }}
QPushButton[emphasis="true"]:hover {{ background: #ffffff; }}

QPushButton#bus {{
    padding: 0; min-width: 31px; max-width: 31px; min-height: 36px; max-height: 36px;
    font-size: 15px; font-weight: 700; background: {INSET}; border: 1px solid #484b53;
    border-radius: 3px; color: #c9cbd0;
}}
QPushButton#bus:hover {{ background: #33363c; }}
QPushButton#bus:disabled {{ color: #55575d; background: {INSET}; border-color: #303338; }}
QPushButton#bus[current="true"] {{ background: {LIVE}; color: #0d1a11; border-color: #66d28f; }}

QLabel#keycap {{
    background: {SURFACE}; border: 1px solid #4a4d55; border-bottom: 2px solid #4a4d55;
    border-radius: 4px; padding: 0 6px; font-weight: 600; min-width: 14px;
}}

QLabel#step {{ color: {FAINT}; }}
QLabel#step[step="active"] {{ color: {TEXT}; font-weight: 600; }}
QLabel#step[step="done"] {{ color: {LIVE}; }}
QLabel#step[step="error"] {{ color: {STOP}; font-weight: 600; }}
QFrame#stepLine {{ background: {HAIRLINE}; min-height: 1px; max-height: 1px; min-width: 16px; max-width: 16px; }}

QFrame#banner {{ border-radius: 3px; border: none; border-left: 4px solid {INFO}; background: #262f3a; }}
QFrame#banner[level="success"] {{ border-left-color: {LIVE}; background: #1f3126; }}
QFrame#banner[level="warn"] {{ border-left-color: {WAIT}; background: #393120; }}
QFrame#banner[level="error"] {{ border-left-color: {STOP}; background: #3a2325; }}
QLabel#bannerTitle {{ font-weight: 700; font-size: 14px; }}
QPushButton#bannerClose {{
    background: transparent; border: none; color: {MUTED}; padding: 0 4px; font-size: 15px;
}}
QPushButton#bannerClose:hover {{ color: {TEXT}; }}

QListWidget#history {{
    background: {INSET}; border: 1px solid #34363b; border-radius: 4px; outline: none;
}}
QListWidget#history::item {{ padding: 4px 6px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #4a4d55; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {INSET}; border: 1px solid {HAIRLINE}; border-radius: 4px; padding: 5px 8px;
    selection-background-color: #4b5666;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {INFO}; }}
QComboBox QAbstractItemView {{ background: {INSET}; border: 1px solid {HAIRLINE}; selection-background-color: #3a3d44; }}
QCheckBox {{ spacing: 8px; }}
"""

"""BG Matte — 실시간 배경 매팅 GUI 앱.

기존 CLI(realtime_matte.py, capture_background.py)는 그대로 두고,
같은 utils.py / BackgroundMattingV2 모델을 GUI로 감싼 패키지입니다.

이 파일은 Qt/torch를 import하지 않습니다 (설정·메시지 로직을 가볍게 테스트하기 위함).
"""

__version__ = "1.0.0"

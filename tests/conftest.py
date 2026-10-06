import os
import sys
from pathlib import Path

# Qt를 화면 없이 돌리기 위한 설정 (CI/서버 환경용). 맥에서 직접 실행해도 무방합니다.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

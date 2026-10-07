"""한글·특수문자 경로에서도 동작하는 이미지 읽기/쓰기.

OpenCV의 imread/imwrite는 윈도우에서 경로에 한글 등 ASCII가 아닌 글자가 있으면 조용히 실패합니다
(예: C:\\Users\\김석\\... 또는 '01_스튜디오.png'). 파일을 직접 읽고 쓴 뒤 imdecode/imencode를 쓰면
모든 플랫폼에서 같게 동작합니다. torch를 가져오지 않는 가벼운 모듈입니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def imread(path, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """읽지 못하면 None (cv2.imread와 같은 규약)."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, flags)
    except OSError:
        return None


def imwrite(path, image: np.ndarray) -> bool:
    """확장자(.png/.jpg 등)에 맞춰 저장합니다. 실패하면 False."""
    path = Path(path)
    try:
        ok, encoded = cv2.imencode(path.suffix or ".png", image)
        if not ok:
            return False
        encoded.tofile(str(path))
        return True
    except (OSError, cv2.error):
        return False

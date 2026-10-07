"""카메라 열기 공통 코드 (맥/윈도우 차이를 한곳에서 처리).

- 윈도우: OpenCV 기본 백엔드(MSMF)는 해상도 지정이 잘 안 되고 시작이 느린 경우가 많아서
  DirectShow(CAP_DSHOW)로 엽니다. HDMI 캡처카드와 UVC 카메라 모두 이쪽이 안정적입니다.
- 맥/그 외: 기본 백엔드(AVFoundation 등)를 그대로 씁니다.
"""

from __future__ import annotations

import sys

import cv2


def open_capture(index: int):
    """플랫폼에 맞는 방식으로 VideoCapture를 엽니다 (열리지 않아도 객체는 돌려줍니다)."""
    if sys.platform == "win32":
        return cv2.VideoCapture(index, cv2.CAP_DSHOW)
    return cv2.VideoCapture(index)


def apply_format(cap, camera_format: str) -> None:
    """카메라 영상 형식을 요청합니다. 'mjpg'는 USB 대역폭이 모자란 캡처카드에서
    1080p/고프레임을 쓸 때 유리합니다 (장치가 지원하지 않으면 무시됩니다). 해상도 지정보다 먼저 호출해야 합니다."""
    if camera_format == "mjpg":
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

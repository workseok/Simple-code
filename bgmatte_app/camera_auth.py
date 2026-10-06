"""macOS 카메라 권한 확인/요청 (pyobjc가 있을 때만 동작, 없으면 'unknown').

OpenCV는 권한이 없으면 팝업 없이 검은 화면만 돌려주는 경우가 많아서, 가능하면 앱이
먼저 권한 상태를 직접 확인해 사용자에게 안내합니다. pyobjc가 없거나 mac이 아니면
'unknown'을 반환하고, 이 경우 앱은 영상이 안 들어올 때 안내하는 방식으로 대응합니다.
"""

from __future__ import annotations

import logging
import sys
from typing import Callable

log = logging.getLogger(__name__)

_STATUS = {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}


def authorization_status() -> str:
    """'authorized' | 'denied' | 'restricted' | 'not_determined' | 'unknown'"""
    if sys.platform != "darwin":
        return "unknown"
    try:
        import AVFoundation  # type: ignore

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeVideo
        )
        return _STATUS.get(int(status), "unknown")
    except Exception as exc:  # pyobjc 미설치 등
        log.info("카메라 권한 상태를 확인하지 못했습니다: %s", exc)
        return "unknown"


def request_access(callback: Callable[[bool], None]) -> None:
    """권한 팝업을 띄우고 응답이 오면 callback(granted)을 호출합니다 (임의의 스레드에서 호출될 수 있음)."""
    try:
        import AVFoundation  # type: ignore

        def handler(granted):
            callback(bool(granted))

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeVideo, handler
        )
    except Exception as exc:
        log.info("카메라 권한 요청을 건너뜁니다: %s", exc)
        callback(True)  # 판단 불가 → 일단 진행하고, 영상이 안 오면 그때 안내

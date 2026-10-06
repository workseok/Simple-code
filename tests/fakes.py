"""테스트용 가짜 카메라 / 가짜 매팅 모델 (torch·실제 카메라 없이 워커와 UI를 검증)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from bgmatte_app.messages import NoticeError


def synthetic_frame(width: int, height: int, tick: int = 0) -> np.ndarray:
    """보기 좋은 합성 프레임: 대각선 그라데이션 + 움직이는 원."""
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    base = np.stack([60 + 90 * x + 0 * y, 70 + 60 * y + 0 * x, 110 + 60 * (1 - x) * (1 - y)], axis=-1)
    frame = np.clip(base, 0, 255).astype(np.uint8)
    cx = int(width * (0.3 + 0.4 * ((tick % 60) / 60)))
    cv2.circle(frame, (cx, int(height * 0.55)), int(min(width, height) * 0.2), (200, 190, 230), -1)
    return frame


class FakeCamera:
    def __init__(
        self,
        size=(64, 48),
        opened: bool = True,
        no_frames: bool = False,
        black: bool = False,
        fail_after: Optional[int] = None,
        delay: float = 0.002,
    ):
        self.size = size
        self._opened = opened
        self.no_frames = no_frames
        self.black = black
        self.fail_after = fail_after
        self.delay = delay
        self.reads = 0
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def set(self, *_args) -> bool:
        return True

    def read(self):
        time.sleep(self.delay)
        self.reads += 1
        if self.no_frames or (self.fail_after is not None and self.reads > self.fail_after):
            return False, None
        w, h = self.size
        if self.black:
            return True, np.zeros((h, w, 3), np.uint8)
        return True, synthetic_frame(w, h, self.reads)

    def release(self) -> None:
        self.released = True


class FakeMatter:
    """Matter와 같은 인터페이스. 합성 결과는 입력을 그대로 돌려줍니다."""

    def __init__(self, gpu: bool = False, fail_first_process: bool = False, load_error: Optional[Exception] = None):
        self.gpu = gpu
        self.fail_first_process = fail_first_process
        self.load_error = load_error
        self.bgr_calls: List[Path] = []
        self.bg_calls: List[Path] = []
        self.processed = 0
        self.alpha_flags: List[bool] = []
        self.loaded = False

    def load(self) -> str:
        if self.load_error is not None:
            raise self.load_error
        self.loaded = True
        return "FAKE-GPU" if self.gpu else "CPU"

    def set_bgr(self, path: Path) -> None:
        self.bgr_calls.append(path)

    def set_background(self, path: Path) -> None:
        if path.name.startswith("bad"):
            raise FileNotFoundError(f"읽을 수 없음: {path}")
        self.bg_calls.append(path)

    def process(self, frame, show_alpha: bool = False):
        if self.gpu and self.fail_first_process and self.processed == 0:
            self.processed += 1
            raise RuntimeError("MPS backend out of memory")
        self.processed += 1
        self.alpha_flags.append(show_alpha)
        out = frame.copy()
        return np.hstack([out, out]) if show_alpha else out

    def is_gpu(self) -> bool:
        return self.gpu

    def fallback_to_cpu(self) -> str:
        self.gpu = False
        return "CPU (GPU 실패로 전환)"


def raising_matter(notice_error: NoticeError) -> FakeMatter:
    return FakeMatter(load_error=notice_error)

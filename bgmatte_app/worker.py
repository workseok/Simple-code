"""카메라 입력 → 매팅 → 합성을 돌리는 백그라운드 스레드.

GUI와는 시그널(이벤트)로만 소통합니다.

  state_changed(str)          starting | waiting_bg | running | capturing | stopped | error
  step_changed(int, str)      준비 단계 진행 (STEP_*, 'active' | 'done' | 'error')
  frame_ready(QImage)         미리보기 프레임 (GUI가 ack_frame()을 부를 때까지 다음 프레임은 보내지 않음)
  notify(Notice)              안내/경고/오류
  background_changed(n,c,nm)  현재 합성 배경 번호/전체 개수/파일명
  fps_updated(float)
  stream_info(str, str)       (처리 장치, 해상도)
  capture_tick(int)           배경 촬영 카운트다운 (남은 초, 0=촬영 중, -1=종료)
  alpha_changed(bool)

GUI → 워커 명령은 select_background / step_background / toggle_alpha / start_capture /
cancel_capture / request_stop 입니다 (스레드 안전한 큐를 거쳐 다음 프레임 사이에 처리).
"""

from __future__ import annotations

import logging
import math
import queue
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from . import messages
from .backgrounds import BackgroundItem
from .config import Config
from .messages import NoticeError

log = logging.getLogger(__name__)

STEP_CAMERA, STEP_BACKGROUND, STEP_MODEL, STEP_RUN = range(4)

WARMUP_ATTEMPTS = 60  # 카메라가 안정될 때까지 읽어볼 최대 횟수
WARMUP_GOOD_FRAMES = 10
BLACK_MEAN_THRESHOLD = 1.0
MAX_READ_FAILURES = 30  # 연속 실패가 이 횟수를 넘으면 카메라 연결 끊김으로 판단


def _default_matter_factory(cfg: Config):
    # torch는 무거우므로 '모델' 단계에서 처음 import합니다 (화면은 이미 떠 있음).
    from .matte_core import Matter

    return Matter(cfg)


def _default_camera_factory(index: int):
    if sys.platform == "win32":
        # 윈도우에서는 DirectShow가 해상도 지정과 시작 속도가 더 안정적입니다.
        return cv2.VideoCapture(index, cv2.CAP_DSHOW)
    return cv2.VideoCapture(index)


class PipelineWorker(QThread):
    state_changed = Signal(str)
    step_changed = Signal(int, str)
    frame_ready = Signal(QImage)
    notify = Signal(object)
    background_changed = Signal(int, int, str)
    fps_updated = Signal(float)
    stream_info = Signal(str, str)
    capture_tick = Signal(int)
    alpha_changed = Signal(bool)

    def __init__(
        self,
        cfg: Config,
        backgrounds: Sequence[BackgroundItem],
        matter_factory: Optional[Callable[[Config], object]] = None,
        camera_factory: Optional[Callable[[int], object]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._cfg = cfg
        self._backgrounds = list(backgrounds)
        self._matter_factory = matter_factory or _default_matter_factory
        self._camera_factory = camera_factory or _default_camera_factory

        self._cmds: "queue.SimpleQueue[tuple]" = queue.SimpleQueue()
        self._stop = threading.Event()
        self._frame_ack = threading.Event()
        self._frame_ack.set()

        self._state = "idle"
        self._active_step: Optional[int] = None
        self._show_alpha = False
        self._bg_index = 0
        if self._backgrounds:
            self._bg_index = min(max(cfg.last_background, 1), len(self._backgrounds)) - 1
        self._resolution = ""
        self._cam_wh: Tuple[int, int] = (0, 0)
        self._capture_end: Optional[float] = None
        self._capture_last_tick: Optional[int] = None
        self._capture_prev_state = "running"
        self._first_output = True

    # ------------------------------------------------------------ GUI 쪽 API
    @property
    def state(self) -> str:
        return self._state

    @property
    def current_background(self) -> int:
        return self._bg_index + 1

    def request_stop(self) -> None:
        self._stop.set()

    def ack_frame(self) -> None:
        self._frame_ack.set()

    def select_background(self, number: int) -> None:
        self._cmds.put(("bg", number))

    def step_background(self, delta: int) -> None:
        self._cmds.put(("bg_step", delta))

    def toggle_alpha(self) -> None:
        self._cmds.put(("alpha",))

    def start_capture(self) -> None:
        self._cmds.put(("capture",))

    def cancel_capture(self) -> None:
        self._cmds.put(("cancel",))

    # ------------------------------------------------------------ 스레드 본체
    def run(self) -> None:
        cap = None
        failed = False
        try:
            cap = self._open_camera()
            self._run_pipeline(cap)
        except NoticeError as err:
            failed = True
            self._fail(err.notice)
        except Exception as exc:  # 예상 밖 오류도 사용자에게 보여줍니다.
            failed = True
            log.exception("파이프라인 오류")
            self._fail(messages.unexpected(exc))
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    log.exception("카메라 해제 중 오류")
            if not failed:
                self._set_state("stopped")

    def _run_pipeline(self, cap) -> None:
        cfg = self._cfg

        # 2) 배경 확인: 합성 배경 이미지 (+ BackgroundMattingV2 엔진은 클린 배경(bgr)도 필요)
        self._step(STEP_BACKGROUND, "active")
        if not self._backgrounds:
            raise NoticeError(messages.bg_none(cfg.resolve(cfg.backgrounds_dir)))
        bgr_path = cfg.resolve(cfg.bgr)
        bgr_wh = self._read_image_size(bgr_path) if cfg.needs_bgr else None
        if cfg.needs_bgr and bgr_wh is None:
            if bgr_path.exists():
                self._notify(messages.bgr_unreadable(bgr_path))
            else:
                self._notify(messages.bgr_missing(bgr_path))
            self._set_state("waiting_bg")
            if not self._stream(cap, None, bgr_path):
                return  # 촬영 전에 정지됨
            bgr_wh = self._read_image_size(bgr_path)
        if bgr_wh is not None and self._cam_wh != (0, 0) and bgr_wh != self._cam_wh:
            self._notify(messages.bgr_size_mismatch(bgr_wh, self._cam_wh))
        self._step(STEP_BACKGROUND, "done")
        if self._stop.is_set():
            return

        # 3) 모델
        self._step(STEP_MODEL, "active")
        self._set_state("starting")
        matter = self._matter_factory(cfg)
        label = matter.load()
        self.stream_info.emit(label, self._resolution)
        if cfg.needs_bgr:
            matter.set_bgr(bgr_path)
        self._select_first_loadable_background(matter)
        self._step(STEP_MODEL, "done")
        if self._stop.is_set():
            return

        # 4) 실행
        self._step(STEP_RUN, "active")
        self._set_state("running")
        self._stream(cap, matter, bgr_path)

    # ------------------------------------------------------------ 1) 카메라
    def _open_camera(self):
        cfg = self._cfg
        self._set_state("starting")
        self._step(STEP_CAMERA, "active")
        cap = self._camera_factory(cfg.camera_index)
        try:
            if not cap.isOpened():
                raise NoticeError(messages.camera_open_failed(cfg.camera_index))
            if cfg.camera_width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
            if cfg.camera_height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)

            good = 0
            brightest = 0.0
            last = None
            for _ in range(WARMUP_ATTEMPTS):
                if self._stop.is_set():
                    break
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.03)
                    continue
                last = frame
                good += 1
                brightest = max(brightest, float(frame.mean()))
                if good >= WARMUP_GOOD_FRAMES:
                    break
            if last is None and not self._stop.is_set():
                raise NoticeError(messages.camera_no_frame(cfg.camera_index))
            if last is not None:
                h, w = last.shape[:2]
                self._cam_wh = (w, h)
                self._resolution = f"{w}×{h}"
                self.stream_info.emit("", self._resolution)
                if brightest < BLACK_MEAN_THRESHOLD:
                    self._notify(messages.camera_black())
            self._step(STEP_CAMERA, "done")
            return cap
        except BaseException:
            cap.release()
            raise

    # ------------------------------------------------------------ 메인 루프
    def _stream(self, cap, matter, bgr_path: Path) -> bool:
        """matter가 None이면 '배경 촬영 대기' 모드: 원본 영상을 보여주다가 촬영이 끝나면 True를 반환.
        matter가 있으면 정지될 때까지 합성을 계속합니다 (정지로 끝나면 False)."""
        failures = 0
        fps = 0.0
        last_t = time.monotonic()
        last_fps_emit = 0.0
        while not self._stop.is_set():
            self._drain_commands(matter)
            ok, frame = cap.read()
            if not ok or frame is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    raise NoticeError(messages.camera_lost())
                time.sleep(0.02)
                continue
            failures = 0

            if self._capture_end is not None:
                finished = self._capture_progress(cap, frame, bgr_path, matter)
                self._emit_frame(frame)
                if finished and matter is None:
                    return True
                continue

            if matter is None:
                self._emit_frame(frame)
                continue

            out = self._process(matter, frame)
            if out is None:
                continue
            self._emit_frame(out)
            if self._first_output:
                self._first_output = False
                self._step(STEP_RUN, "done")

            now = time.monotonic()
            inst = 1.0 / max(now - last_t, 1e-6)
            last_t = now
            fps = inst if fps == 0.0 else 0.9 * fps + 0.1 * inst
            if now - last_fps_emit >= 0.5:
                last_fps_emit = now
                self.fps_updated.emit(fps)
        return False

    def _process(self, matter, frame):
        try:
            return matter.process(frame, self._show_alpha)
        except Exception as exc:
            if matter.is_gpu():
                log.warning("GPU 추론 실패 → CPU 전환: %s", exc)
                label = matter.fallback_to_cpu()
                self.stream_info.emit(label, self._resolution)
                self._notify(messages.cpu_fallback(exc))
                return None  # 다음 프레임부터 CPU로 처리
            raise NoticeError(messages.inference_failed(exc)) from exc

    # ------------------------------------------------------------ 명령 처리
    def _drain_commands(self, matter) -> None:
        while True:
            try:
                cmd = self._cmds.get_nowait()
            except queue.Empty:
                return
            kind = cmd[0]
            if kind == "alpha":
                self._show_alpha = not self._show_alpha
                self.alpha_changed.emit(self._show_alpha)
            elif kind in ("bg", "bg_step"):
                if matter is None:
                    continue  # 모델 준비 전에는 전환할 수 없음 (GUI가 먼저 안내)
                self._handle_bg_command(matter, kind, cmd[1])
            elif kind == "capture":
                if not self._cfg.needs_bgr:
                    self._notify(messages.capture_not_needed(self._cfg.engine))
                    continue
                self._begin_capture()
            elif kind == "cancel":
                if self._capture_end is not None:
                    self._end_capture()
                    self._notify(messages.capture_cancelled())

    def _handle_bg_command(self, matter, kind: str, value: int) -> None:
        count = len(self._backgrounds)
        if kind == "bg":
            if not 1 <= value <= count:
                self._notify(messages.bg_invalid(value, count))
                return
            target = value - 1
        else:
            target = (self._bg_index + value) % count
        if target == self._bg_index:
            return
        self._apply_background(matter, target)

    def _apply_background(self, matter, index: int) -> bool:
        item = self._backgrounds[index]
        try:
            matter.set_background(item.path)
        except Exception as exc:
            self._notify(messages.bg_load_failed(item.name, exc))
            return False
        self._bg_index = index
        self.background_changed.emit(item.number, len(self._backgrounds), item.name)
        return True

    def _select_first_loadable_background(self, matter) -> None:
        count = len(self._backgrounds)
        for offset in range(count):
            index = (self._bg_index + offset) % count
            if self._apply_background(matter, index):
                return
        raise NoticeError(messages.bg_all_failed())

    # ------------------------------------------------------------ 배경(bgr) 촬영
    def _begin_capture(self) -> None:
        if self._capture_end is not None:
            return
        seconds = max(1, self._cfg.countdown_seconds)
        self._capture_prev_state = self._state
        self._capture_end = time.monotonic() + seconds
        self._capture_last_tick = None
        self._set_state("capturing")
        self._notify(messages.capture_started(seconds))

    def _end_capture(self) -> None:
        self._capture_end = None
        self._capture_last_tick = None
        self.capture_tick.emit(-1)
        self._set_state(self._capture_prev_state)

    def _capture_progress(self, cap, frame, bgr_path: Path, matter) -> bool:
        """카운트다운 진행. 촬영이 끝나 파일이 저장되면 True."""
        assert self._capture_end is not None
        left = self._capture_end - time.monotonic()
        if left > 0:
            sec = math.ceil(left)
            if sec != self._capture_last_tick:
                self._capture_last_tick = sec
                self.capture_tick.emit(sec)
            return False

        self.capture_tick.emit(0)
        saved = self._save_background(cap, frame, bgr_path)
        self._end_capture()
        if saved and matter is not None:
            try:
                matter.set_bgr(bgr_path)
            except Exception as exc:
                self._notify(messages.capture_failed(exc))
                return False
        return saved

    def _save_background(self, cap, first_frame, path: Path) -> bool:
        n = max(1, self._cfg.average_frames)
        acc = first_frame.astype(np.float32)
        count = 1
        attempts = 0
        while count < n and attempts < n * 5:
            attempts += 1
            ok, frame = cap.read()
            if ok and frame is not None and frame.shape == first_frame.shape:
                acc += frame
                count += 1
        averaged = np.clip(acc / count, 0, 255).astype(np.uint8)

        backup: Optional[Path] = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                backup = path.with_name(f"{path.stem}.prev{path.suffix}")
                shutil.copy2(path, backup)
            if not cv2.imwrite(str(path), averaged):
                raise OSError(f"{path} 에 이미지를 쓰지 못했습니다")
        except Exception as exc:
            log.exception("배경 저장 실패")
            self._notify(messages.capture_failed(exc))
            return False
        self._notify(messages.capture_saved(path, backup))
        return True

    # ------------------------------------------------------------ 유틸
    @staticmethod
    def _read_image_size(path: Path) -> Optional[Tuple[int, int]]:
        if not path.is_file():
            return None
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            return None
        h, w = image.shape[:2]
        return (w, h)

    def _emit_frame(self, bgr) -> None:
        if not self._frame_ack.is_set():
            return  # GUI가 아직 이전 프레임을 그리는 중 → 건너뜀
        self._frame_ack.clear()
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        h, w = rgb.shape[:2]
        self.frame_ready.emit(QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy())

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def _step(self, step: int, status: str) -> None:
        self._active_step = step if status == "active" else self._active_step
        self.step_changed.emit(step, status)

    def _notify(self, notice) -> None:
        self.notify.emit(notice)

    def _fail(self, notice) -> None:
        if self._active_step is not None:
            self.step_changed.emit(self._active_step, "error")
        self.notify.emit(notice)
        self._set_state("error")

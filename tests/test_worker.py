"""PipelineWorker의 상태 흐름을 가짜 카메라/가짜 모델로 확인합니다 (실제 스레드 사용)."""

import time

import cv2
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from bgmatte_app import messages  # noqa: E402
from bgmatte_app.backgrounds import scan_backgrounds  # noqa: E402
from bgmatte_app.config import Config  # noqa: E402
from bgmatte_app.messages import Level, NoticeError  # noqa: E402
from bgmatte_app.worker import PipelineWorker  # noqa: E402
from fakes import FakeCamera, FakeMatter, synthetic_frame  # noqa: E402

DIRECT = Qt.ConnectionType.DirectConnection


class Recorder:
    """워커 시그널을 시간 순서대로 기록합니다 (워커 스레드에서 직접 호출됨)."""

    def __init__(self, worker: PipelineWorker):
        self.events = []
        self.frames = 0
        self.w = worker
        worker.state_changed.connect(lambda s: self.events.append(("state", s)), DIRECT)
        worker.step_changed.connect(lambda i, s: self.events.append(("step", i, s)), DIRECT)
        worker.notify.connect(lambda n: self.events.append(("notice", n)), DIRECT)
        worker.background_changed.connect(lambda n, c, nm: self.events.append(("bg", n, c, nm)), DIRECT)
        worker.capture_tick.connect(lambda v: self.events.append(("tick", v)), DIRECT)
        worker.stream_info.connect(lambda d, r: self.events.append(("info", d, r)), DIRECT)
        worker.alpha_changed.connect(lambda a: self.events.append(("alpha", a)), DIRECT)
        worker.frame_ready.connect(self._frame, DIRECT)

    def _frame(self, _image):
        self.frames += 1
        self.w.ack_frame()

    def states(self):
        return [e[1] for e in self.events if e[0] == "state"]

    def notices(self):
        return [e[1] for e in self.events if e[0] == "notice"]

    def codes(self):
        return [n.code for n in self.notices()]

    def has_state(self, state):
        return state in self.states()

    def last_state(self):
        s = self.states()
        return s[-1] if s else None


def wait_for(predicate, timeout=6.0, interval=0.01):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def env(tmp_path):
    """bgr.png와 합성 배경 3개가 준비된 작업 폴더."""
    folder = tmp_path / "backgrounds"
    folder.mkdir()
    for name in ("01_studio.png", "02_office.png", "03_beach.png"):
        cv2.imwrite(str(folder / name), synthetic_frame(64, 48))
    bgr = tmp_path / "bgr.png"
    cv2.imwrite(str(bgr), synthetic_frame(64, 48))
    cfg = Config(
        bgr=str(bgr),
        backgrounds_dir=str(folder),
        legacy_background=str(tmp_path / "none.png"),
        countdown_seconds=1,
        average_frames=3,
    )
    return tmp_path, cfg, folder, bgr


def make_worker(cfg, folder, camera=None, matter=None):
    camera = camera or FakeCamera()
    matter = matter or FakeMatter()
    worker = PipelineWorker(
        cfg,
        scan_backgrounds(folder),
        matter_factory=lambda _cfg: matter,
        camera_factory=lambda _idx: camera,
    )
    return worker, camera, matter, Recorder(worker)


def stop(worker):
    worker.request_stop()
    assert worker.wait(5000), "워커가 정지 요청 뒤에도 끝나지 않았습니다"


# ---------------------------------------------------------------- 정상 경로
def test_happy_path_reaches_running_and_streams_frames(env):
    _, cfg, folder, _ = env
    worker, camera, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running") and rec.frames >= 3)
    steps = [e for e in rec.events if e[0] == "step"]
    assert ("step", 0, "done") in steps and ("step", 2, "done") in steps
    assert rec.states()[:2] == ["starting", "running"]
    assert ("info", "CPU", "64×48") in rec.events
    assert matter.loaded and len(matter.bgr_calls) == 1
    stop(worker)
    assert rec.last_state() == "stopped"
    assert camera.released, "정지 뒤에는 카메라를 놓아야 합니다"


def test_first_background_follows_last_background_setting(env):
    _, cfg, folder, _ = env
    cfg.last_background = 2
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    assert ("bg", 2, 3, "02_office.png") in rec.events
    assert matter.bg_calls[-1].name == "02_office.png"
    stop(worker)


def test_last_background_out_of_range_is_clamped(env):
    _, cfg, folder, _ = env
    cfg.last_background = 99
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    assert ("bg", 3, 3, "03_beach.png") in rec.events
    stop(worker)


# ---------------------------------------------------------------- 배경 번호 전환
def test_background_switching_by_number_and_arrows(env):
    _, cfg, folder, _ = env
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))

    worker.select_background(3)
    assert wait_for(lambda: ("bg", 3, 3, "03_beach.png") in rec.events)
    worker.step_background(+1)  # 3 → 1 (순환)
    assert wait_for(lambda: rec.events.count(("bg", 1, 3, "01_studio.png")) == 2)
    worker.step_background(-1)  # 1 → 3
    assert wait_for(lambda: rec.events.count(("bg", 3, 3, "03_beach.png")) == 2)
    stop(worker)


def test_invalid_number_is_reported_and_current_background_kept(env):
    _, cfg, folder, _ = env
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    before = [e for e in rec.events if e[0] == "bg"]
    worker.select_background(7)
    assert wait_for(lambda: "bg_invalid" in rec.codes())
    note = next(n for n in rec.notices() if n.code == "bg_invalid")
    assert "7번" in note.title and "3번" in note.detail
    assert [e for e in rec.events if e[0] == "bg"] == before
    stop(worker)


def test_background_that_fails_to_load_keeps_previous(env):
    _, cfg, folder, _ = env
    cv2.imwrite(str(folder / "bad_04.png"), synthetic_frame(64, 48))  # FakeMatter는 'bad'로 시작하면 로드 실패
    worker, _, _, rec = make_worker(cfg, folder)
    names = [b.name for b in worker._backgrounds]
    bad_number = names.index("bad_04.png") + 1
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    current = worker.current_background
    assert current != bad_number
    worker.select_background(bad_number)
    assert wait_for(lambda: "bg_load_failed" in rec.codes())
    note = next(n for n in rec.notices() if n.code == "bg_load_failed")
    assert "bad_04.png" in note.title
    assert worker.current_background == current, "실패하면 이전 배경을 유지해야 합니다"
    stop(worker)


def test_alpha_toggle_is_applied_to_processing(env):
    _, cfg, folder, _ = env
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    worker.toggle_alpha()
    assert wait_for(lambda: ("alpha", True) in rec.events and True in matter.alpha_flags)
    worker.toggle_alpha()
    assert wait_for(lambda: ("alpha", False) in rec.events)
    stop(worker)


# ---------------------------------------------------------------- 빈 배경(bgr) 촬영
def test_missing_bgr_waits_then_captures_then_runs(env):
    _, cfg, folder, bgr = env
    bgr.unlink()
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("waiting_bg"))
    assert "bgr_missing" in rec.codes()
    assert not matter.loaded, "촬영 전에는 모델을 불러오지 않아야 합니다"
    assert wait_for(lambda: rec.frames >= 2), "대기 중에도 카메라 영상은 보여야 합니다"

    worker.start_capture()
    assert wait_for(lambda: rec.has_state("running"), timeout=8)
    assert bgr.exists()
    assert "capture_saved" in rec.codes()
    ticks = [e[1] for e in rec.events if e[0] == "tick"]
    assert 1 in ticks and 0 in ticks and ticks[-1] == -1
    assert rec.states() == ["starting", "waiting_bg", "capturing", "waiting_bg", "starting", "running"]
    assert matter.bgr_calls == [bgr]
    image = cv2.imread(str(bgr))
    assert image is not None and image.shape == (48, 64, 3)
    stop(worker)


def test_capture_while_running_replaces_bgr_and_keeps_backup(env):
    _, cfg, folder, bgr = env
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    worker.start_capture()
    assert wait_for(lambda: "capture_saved" in rec.codes(), timeout=8)
    assert wait_for(lambda: rec.last_state() == "running")
    assert (bgr.parent / "bgr.prev.png").exists(), "이전 배경을 .prev로 보관해야 합니다"
    note = next(n for n in rec.notices() if n.code == "capture_saved")
    assert "bgr.prev.png" in note.detail
    assert matter.bgr_calls == [bgr, bgr], "촬영 뒤 모델이 새 배경을 다시 읽어야 합니다"
    assert rec.states()[-2:] == ["capturing", "running"]
    stop(worker)


def test_capture_can_be_cancelled(env):
    _, cfg, folder, bgr = env
    cfg.countdown_seconds = 5
    before = bgr.read_bytes()
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    worker.start_capture()
    assert wait_for(lambda: rec.last_state() == "capturing")
    worker.cancel_capture()
    assert wait_for(lambda: rec.last_state() == "running")
    assert "capture_cancelled" in rec.codes()
    assert bgr.read_bytes() == before, "취소하면 파일이 바뀌면 안 됩니다"
    assert not (bgr.parent / "bgr.prev.png").exists()
    assert [e[1] for e in rec.events if e[0] == "tick"][-1] == -1
    stop(worker)


def test_capture_failure_is_reported_and_pipeline_continues(env, monkeypatch):
    _, cfg, folder, _ = env
    monkeypatch.setattr("bgmatte_app.worker.imwrite", lambda *a, **k: False)
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    worker.start_capture()
    assert wait_for(lambda: "capture_failed" in rec.codes(), timeout=8)
    assert wait_for(lambda: rec.last_state() == "running")
    stop(worker)


def test_unreadable_bgr_is_treated_like_missing(env):
    _, cfg, folder, bgr = env
    bgr.write_bytes(b"not an image")
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("waiting_bg"))
    assert "bgr_unreadable" in rec.codes()
    stop(worker)


def test_bgr_resolution_mismatch_warns(env):
    _, cfg, folder, bgr = env
    cv2.imwrite(str(bgr), synthetic_frame(128, 96))
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    note = next(n for n in rec.notices() if n.code == "bgr_size_mismatch")
    assert "128×96" in note.detail and "64×48" in note.detail
    stop(worker)


# ---------------------------------------------------------------- 오류 경로
def run_to_error(worker):
    worker.start()
    assert worker.wait(8000), "오류 뒤 스레드가 끝나야 합니다"


def test_camera_cannot_open(env):
    _, cfg, folder, _ = env
    worker, camera, _, rec = make_worker(cfg, folder, camera=FakeCamera(opened=False))
    run_to_error(worker)
    assert rec.last_state() == "error"
    assert "camera_open_failed" in rec.codes()
    assert ("step", 0, "error") in rec.events
    assert camera.released


def test_camera_opens_but_no_frames(env):
    _, cfg, folder, _ = env
    worker, camera, _, rec = make_worker(cfg, folder, camera=FakeCamera(no_frames=True))
    run_to_error(worker)
    assert "camera_no_frame" in rec.codes()
    assert rec.last_state() == "error" and camera.released


def test_black_camera_warns_but_continues(env):
    _, cfg, folder, _ = env
    worker, _, _, rec = make_worker(cfg, folder, camera=FakeCamera(black=True))
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    assert "camera_black" in rec.codes()
    assert next(n for n in rec.notices() if n.code == "camera_black").level is Level.WARN
    stop(worker)


def test_camera_lost_during_run(env):
    _, cfg, folder, _ = env
    worker, camera, _, rec = make_worker(cfg, folder, camera=FakeCamera(fail_after=40))
    run_to_error(worker)
    assert "camera_lost" in rec.codes()
    assert rec.last_state() == "error" and camera.released


def test_no_backgrounds_is_an_error(env):
    _, cfg, folder, _ = env
    for f in folder.iterdir():
        f.unlink()
    worker, camera, matter, rec = make_worker(cfg, folder)
    run_to_error(worker)
    assert "bg_none" in rec.codes()
    assert ("step", 1, "error") in rec.events
    assert not matter.loaded and camera.released


def test_model_errors_are_shown_as_given(env):
    _, cfg, folder, _ = env
    from pathlib import Path

    err = NoticeError(messages.checkpoint_missing(Path("/no/model.pth")))
    worker, _, _, rec = make_worker(cfg, folder, matter=FakeMatter(load_error=err))
    run_to_error(worker)
    assert "checkpoint_missing" in rec.codes()
    assert ("step", 2, "error") in rec.events
    assert rec.last_state() == "error"


def test_unexpected_exception_is_reported_not_swallowed(env):
    _, cfg, folder, _ = env
    worker, camera, _, rec = make_worker(cfg, folder, matter=FakeMatter(load_error=RuntimeError("kaboom")))
    run_to_error(worker)
    note = next(n for n in rec.notices() if n.code == "unexpected")
    assert "kaboom" in note.detail
    assert rec.last_state() == "error" and camera.released


def test_gpu_failure_falls_back_to_cpu_and_keeps_running(env):
    _, cfg, folder, _ = env
    matter = FakeMatter(gpu=True, fail_first_process=True)
    worker, _, _, rec = make_worker(cfg, folder, matter=matter)
    worker.start()
    assert wait_for(lambda: "cpu_fallback" in rec.codes())
    assert wait_for(lambda: rec.frames >= 3)
    assert ("info", "CPU (GPU 실패로 전환)", "64×48") in rec.events
    assert not matter.is_gpu()
    stop(worker)


def test_inference_error_on_cpu_is_fatal_with_message(env):
    _, cfg, folder, _ = env

    class Broken(FakeMatter):
        def process(self, frame, show_alpha=False):
            raise ValueError("tensor shape mismatch")

    worker, _, _, rec = make_worker(cfg, folder, matter=Broken())
    run_to_error(worker)
    note = next(n for n in rec.notices() if n.code == "inference_failed")
    assert "tensor shape mismatch" in note.detail
    assert rec.last_state() == "error"


# ---------------------------------------------------------------- 정지
def test_stop_while_waiting_for_background_releases_camera(env):
    _, cfg, folder, bgr = env
    bgr.unlink()
    worker, camera, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("waiting_bg"))
    stop(worker)
    assert camera.released and rec.last_state() == "stopped"


def test_frames_are_throttled_until_acked(env):
    """GUI가 느릴 때(ack가 늦을 때) 프레임이 쌓이지 않고 건너뛰어야 합니다."""
    _, cfg, folder, _ = env
    matter = FakeMatter()
    worker = PipelineWorker(
        cfg,
        scan_backgrounds(folder),
        matter_factory=lambda _cfg: matter,
        camera_factory=lambda _idx: FakeCamera(),
    )
    delivered = []
    worker.frame_ready.connect(lambda img: delivered.append(img), DIRECT)  # 일부러 ack를 부르지 않음
    worker.start()
    assert wait_for(lambda: matter.processed >= 30)
    assert len(delivered) == 1, "승인(ack) 전에는 다음 프레임을 보내면 안 됩니다"
    worker.ack_frame()
    assert wait_for(lambda: len(delivered) == 2)
    stop(worker)


# ---------------------------------------------------------------- 빈 배경이 필요 없는 엔진 (modnet / rvm)
@pytest.mark.parametrize("engine", ["modnet", "rvm"])
def test_engines_without_bgr_run_immediately_even_if_bgr_is_missing(env, engine):
    _, cfg, folder, bgr = env
    bgr.unlink()
    cfg.engine = engine
    worker, _, matter, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running") and rec.frames >= 3)
    assert not rec.has_state("waiting_bg"), "빈 배경 촬영을 기다리면 안 됩니다"
    assert "bgr_missing" not in rec.codes()
    assert matter.loaded and matter.bgr_calls == [], "bgr를 모델에 넘기지 않아야 합니다"
    assert not bgr.exists()
    stop(worker)


def test_capture_command_is_declined_with_a_notice_when_engine_needs_no_bgr(env):
    _, cfg, folder, bgr = env
    bgr.unlink()
    cfg.engine = "rvm"
    worker, _, _, rec = make_worker(cfg, folder)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    worker.start_capture()
    assert wait_for(lambda: "capture_not_needed" in rec.codes())
    assert not rec.has_state("capturing") and not bgr.exists()
    stop(worker)


def test_mjpg_is_requested_before_resolution(env):
    _, cfg, folder, _ = env
    cfg.camera_format, cfg.camera_width, cfg.camera_height = "mjpg", 1280, 720

    class RecordingCamera(FakeCamera):
        def __init__(self):
            super().__init__()
            self.props = []

        def set(self, prop, value=None):
            self.props.append(prop)
            return True

    camera = RecordingCamera()
    worker, _, _, rec = make_worker(cfg, folder, camera=camera)
    worker.start()
    assert wait_for(lambda: rec.has_state("running"))
    stop(worker)
    assert camera.props[:3] == [cv2.CAP_PROP_FOURCC, cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT]

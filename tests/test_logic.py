"""Qt/torch 없이 확인할 수 있는 로직: 설정, 배경 번호, 안내 문구."""

import json
import inspect

import pytest

from bgmatte_app import messages
from bgmatte_app.backgrounds import scan_backgrounds
from bgmatte_app.config import Config, load_config, resolve_path, save_config
from bgmatte_app.messages import ACTIONS, Level, Notice


# ---------------------------------------------------------------- 설정
def test_load_missing_file_gives_defaults(tmp_path):
    cfg, warning = load_config(tmp_path / "nope.json")
    assert cfg == Config()
    assert warning is None


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(camera_index=2, countdown_seconds=8, last_background=4, seen_intro=True)
    save_config(cfg, path)
    loaded, warning = load_config(path)
    assert warning is None
    assert loaded == cfg


def test_corrupt_file_falls_back_with_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ 이건 json이 아님", encoding="utf-8")
    cfg, warning = load_config(path)
    assert cfg == Config()
    assert warning and "config.json" in warning


def test_non_object_json_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    _, warning = load_config(path)
    assert warning


def test_unknown_keys_ignored_and_values_clamped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "mystery": 1,
                "backbone": "vgg",  # 허용되지 않는 값 → 기본값
                "camera_index": "3",  # 문자열 → 정수
                "countdown_seconds": 999,  # 범위 초과 → 30
                "average_frames": -4,  # → 1
                "last_background": 0,  # → 1
                "bgr": "   ",  # 빈 값 → 기본값
            }
        ),
        encoding="utf-8",
    )
    cfg, warning = load_config(path)
    assert warning is None
    assert cfg.backbone == "resnet50"
    assert cfg.camera_index == 3
    assert cfg.countdown_seconds == 30
    assert cfg.average_frames == 1
    assert cfg.last_background == 1
    assert cfg.bgr == "bgr.png"


def test_save_is_atomic_and_leaves_no_tmp(tmp_path):
    path = tmp_path / "sub" / "config.json"
    save_config(Config(), path)
    assert path.exists()
    assert not list(path.parent.glob("*.tmp"))


def test_relative_paths_resolve_against_project_root():
    p = resolve_path("bgr.png")
    assert p.is_absolute() and p.name == "bgr.png"
    assert resolve_path("/abs/x.png").as_posix() == "/abs/x.png"


# ---------------------------------------------------------------- 배경 번호
def _touch(folder, *names):
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"x")


def test_numbering_is_natural_sorted(tmp_path):
    folder = tmp_path / "backgrounds"
    _touch(folder, "bg10.png", "bg2.png", "bg1.png", "notes.txt", ".hidden.png")
    items = scan_backgrounds(folder)
    assert [i.name for i in items] == ["bg1.png", "bg2.png", "bg10.png"]
    assert [i.number for i in items] == [1, 2, 3]


def test_numeric_prefix_controls_order(tmp_path):
    folder = tmp_path / "backgrounds"
    _touch(folder, "02_office.jpg", "01_studio.PNG", "03_beach.webp")
    assert [i.name for i in scan_backgrounds(folder)] == ["01_studio.PNG", "02_office.jpg", "03_beach.webp"]


def test_legacy_background_used_when_folder_missing_or_empty(tmp_path):
    legacy = tmp_path / "ai_background.png"
    legacy.write_bytes(b"x")
    assert [i.name for i in scan_backgrounds(tmp_path / "missing", legacy)] == ["ai_background.png"]
    empty = tmp_path / "backgrounds"
    empty.mkdir()
    assert [i.number for i in scan_backgrounds(empty, legacy)] == [1]


def test_folder_images_win_over_legacy(tmp_path):
    legacy = tmp_path / "ai_background.png"
    legacy.write_bytes(b"x")
    folder = tmp_path / "backgrounds"
    _touch(folder, "a.png")
    assert [i.name for i in scan_backgrounds(folder, legacy)] == ["a.png"]


def test_nothing_found_returns_empty(tmp_path):
    assert scan_backgrounds(tmp_path / "missing", tmp_path / "also-missing.png") == []


# ---------------------------------------------------------------- 안내 문구
def _all_notices():
    from pathlib import Path

    p = Path("/x/y.png")
    return [
        messages.camera_permission_pending(),
        messages.camera_permission_denied(),
        messages.camera_restricted(),
        messages.camera_open_failed(1),
        messages.camera_no_frame(0),
        messages.camera_black(),
        messages.camera_lost(),
        messages.bgr_missing(p),
        messages.bgr_unreadable(p),
        messages.bgr_size_mismatch((1920, 1080), (1280, 720)),
        messages.capture_unavailable(),
        messages.capture_started(5),
        messages.capture_saved(p, p),
        messages.capture_saved(p, None),
        messages.capture_cancelled(),
        messages.capture_failed(OSError("disk full")),
        messages.bg_none(p),
        messages.bg_all_failed(),
        messages.bg_invalid(7, 5),
        messages.bg_not_ready(),
        messages.camera_in_use(1),
        messages.no_free_camera(5),
        messages.bg_load_failed("a.png", "boom"),
        messages.repo_missing(p),
        messages.repo_bad(p, ImportError("no model")),
        messages.checkpoint_missing(p),
        messages.checkpoint_mismatch("mattingrefine", "resnet50", "size mismatch"),
        messages.engine_repo_missing("rvm", p),
        messages.engine_checkpoint_missing("rvm", p),
        messages.engine_load_failed("rvm", "size mismatch"),
        messages.capture_not_needed("rvm"),
        messages.inference_failed("oops"),
        messages.cpu_fallback("mps oom"),
        messages.config_corrupt("bad json"),
        messages.unexpected(RuntimeError("x")),
    ]


def test_every_notice_is_well_formed():
    codes = set()
    for n in _all_notices():
        assert isinstance(n, Notice)
        assert n.title.strip(), n.code
        assert isinstance(n.level, Level)
        assert set(n.actions) <= set(ACTIONS), (n.code, n.actions)
        codes.add(n.code)
    # 코드가 겹치면 안 됨 (capture_saved는 두 번 만들었으므로 제외하고 비교)
    assert len(codes) == len(_all_notices()) - 1


def test_errors_always_tell_the_user_what_to_do():
    for n in _all_notices():
        if n.level is Level.ERROR:
            assert n.hint, f"{n.code}: 오류에는 해결 방법(hint)이 있어야 합니다"
            assert n.actions or n.code in {"repo_bad"}, f"{n.code}: 조치 버튼이 필요합니다"


def test_invalid_number_message_mentions_range():
    n = messages.bg_invalid(7, 5)
    assert "7번" in n.title and "5번" in n.detail


def test_every_message_factory_is_covered_by_the_list_above():
    # 새 안내 문구를 추가하고 위 목록에 넣지 않으면 알려줍니다.
    factories = {
        name
        for name, fn in inspect.getmembers(messages, inspect.isfunction)
        if fn.__module__ == messages.__name__ and not name.startswith("_")
    }
    covered = {n.code for n in _all_notices()}
    missing = {name for name in factories if name not in covered}
    assert not missing, f"테스트 목록에 없는 안내 문구: {missing}"


def test_notice_error_carries_notice():
    n = messages.camera_lost()
    with pytest.raises(messages.NoticeError) as info:
        raise messages.NoticeError(n)
    assert info.value.notice is n


def test_theme_setting_is_validated():
    from bgmatte_app.config import Config

    assert Config(theme="light").validated().theme == "light"
    assert Config(theme="neon").validated().theme == "dark"
    assert Config().theme == "dark"


def test_checkpoint_is_chosen_per_backbone():
    cfg = Config(
        checkpoint="a50.pth", checkpoint_resnet101="b101.pth", checkpoint_mobilenetv2="c.pth",
        backbone="resnet101",
    )
    assert cfg.checkpoint_for() == "b101.pth"
    assert cfg.checkpoint_for("resnet50") == "a50.pth"
    assert cfg.checkpoint_for("mobilenetv2") == "c.pth"


def test_all_checkpoint_paths_survive_roundtrip_and_blank_falls_back(tmp_path):
    path = tmp_path / "config.json"
    save_config(Config(checkpoint_resnet101="models/my101.pth"), path)
    cfg, _ = load_config(path)
    assert cfg.checkpoint_resnet101 == "models/my101.pth"
    assert cfg.checkpoint == "models/pytorch_resnet50.pth"
    path.write_text(json.dumps({"checkpoint_mobilenetv2": "  "}), encoding="utf-8")
    cfg, _ = load_config(path)
    assert cfg.checkpoint_mobilenetv2 == "models/pytorch_mobilenetv2.pth"


def test_old_single_checkpoint_config_moves_to_its_backbone_slot(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"backbone": "resnet101", "checkpoint": "models/pytorch_resnet101.pth"}),
        encoding="utf-8",
    )
    cfg, _ = load_config(path)
    assert cfg.checkpoint_resnet101 == "models/pytorch_resnet101.pth"
    assert cfg.checkpoint == "models/pytorch_resnet50.pth"
    assert cfg.checkpoint_for() == "models/pytorch_resnet101.pth"


def test_engine_defaults_and_validation():
    cfg = Config()
    assert cfg.engine == "bmv2" and cfg.needs_bgr
    assert not Config(engine="rvm").needs_bgr
    bad = Config(engine="nope", rvm_variant="x", rvm_downsample=9).validated()
    assert (bad.engine, bad.rvm_variant) == ("bmv2", "mobilenetv3")
    assert bad.rvm_downsample == 1.0


def test_rvm_checkpoint_is_chosen_per_variant():
    cfg = Config(rvm_checkpoint="a.pth", rvm_checkpoint_resnet50="b.pth")
    assert cfg.rvm_checkpoint_for("mobilenetv3") == "a.pth"
    assert cfg.rvm_checkpoint_for("resnet50") == "b.pth"
    assert Config(rvm_variant="resnet50", rvm_checkpoint_resnet50="b.pth").rvm_checkpoint_for() == "b.pth"


def test_engine_settings_survive_roundtrip_and_old_config_defaults_to_bmv2(tmp_path):
    path = tmp_path / "config.json"
    save_config(Config(engine="rvm", rvm_variant="resnet50", rvm_downsample=0.5), path)
    loaded, warning = load_config(path)
    assert warning is None
    assert (loaded.engine, loaded.rvm_variant, loaded.rvm_downsample) == ("rvm", "resnet50", 0.5)
    path.write_text('{"backbone": "resnet50", "camera_index": 2}', encoding="utf-8")  # 엔진 도입 전 설정 파일
    old, _ = load_config(path)
    assert old.engine == "bmv2" and old.camera_index == 2


def test_windows_settings_and_log_live_under_appdata(monkeypatch, tmp_path):
    from bgmatte_app import config as cfgmod

    monkeypatch.setattr(cfgmod.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert cfgmod.config_path() == tmp_path / "Roaming" / "BGMatte" / "config.json"
    assert cfgmod.log_path() == tmp_path / "Local" / "BGMatte" / "app.log"


def test_open_capture_uses_directshow_only_on_windows(monkeypatch):
    from bgmatte_app import camera

    calls = []
    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda *a: calls.append(a) or object())
    monkeypatch.setattr(camera.sys, "platform", "win32")
    camera.open_capture(2)
    monkeypatch.setattr(camera.sys, "platform", "darwin")
    camera.open_capture(1)
    assert calls == [(2, camera.cv2.CAP_DSHOW), (1,)]


def test_camera_format_validation_and_mjpg_request():
    from bgmatte_app import camera

    assert Config(camera_format="x").validated().camera_format == "auto"
    assert Config(camera_format="mjpg").validated().camera_format == "mjpg"

    class Cap:
        def __init__(self):
            self.sets = []

        def set(self, prop, value):
            self.sets.append(prop)

    cap = Cap()
    camera.apply_format(cap, "auto")
    assert cap.sets == []
    camera.apply_format(cap, "mjpg")
    assert cap.sets == [camera.cv2.CAP_PROP_FOURCC]


def test_imageio_roundtrips_korean_file_names(tmp_path):
    import numpy as np

    from bgmatte_app.imageio import imread, imwrite

    image = (np.random.rand(20, 30, 3) * 255).astype("uint8")
    path = tmp_path / "한글 폴더" / "01_스튜디오.png"
    path.parent.mkdir()
    assert imwrite(path, image)
    back = imread(path)
    assert back is not None and back.shape == image.shape and (back == image).all()
    assert imread(tmp_path / "없는파일.png") is None
    (tmp_path / "빈파일.png").write_bytes(b"")
    assert imread(tmp_path / "빈파일.png") is None
    (tmp_path / "깨진.png").write_bytes(b"not an image")
    assert imread(tmp_path / "깨진.png") is None


def test_utils_loads_images_with_korean_names(tmp_path):
    torch = pytest.importorskip("torch")
    import numpy as np

    from bgmatte_app.imageio import imwrite
    from utils import load_image_as_tensor

    path = tmp_path / "배경.png"
    assert imwrite(path, np.zeros((8, 12, 3), "uint8"))
    assert tuple(load_image_as_tensor(str(path), torch.device("cpu")).shape) == (1, 3, 8, 12)
    with pytest.raises(FileNotFoundError):
        load_image_as_tensor(str(tmp_path / "없음.png"), torch.device("cpu"))


def test_config_saved_while_modnet_existed_still_loads_and_falls_back_to_bmv2(tmp_path):
    """MODNet 엔진을 뺀 뒤에도, 예전에 MODNet을 골라 저장한 설정 파일은 오류 없이 열려야 합니다."""
    path = tmp_path / "config.json"
    path.write_text(
        '{"engine": "modnet", "modnet_repo": "../MODNet", "modnet_ref_size": 384, "modnet_smooth": 0.3, "camera_index": 1}',
        encoding="utf-8",
    )
    cfg, warning = load_config(path)
    assert warning is None
    assert cfg.engine == "bmv2" and cfg.needs_bgr and cfg.camera_index == 1
    assert not hasattr(cfg, "modnet_repo")


def test_bgr_path_is_per_camera():
    from bgmatte_app.config import Config

    assert Config(camera_index=0, bgr="bgr.png").bgr_for_camera() == "bgr.png"
    assert Config(camera_index=2, bgr="bgr.png").bgr_for_camera().endswith("bgr_cam2.png")
    nested = Config(camera_index=1, bgr="shots/bg.jpg").bgr_for_camera().replace("\\", "/")
    assert nested == "shots/bg_cam1.jpg"

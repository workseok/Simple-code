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
        messages.bg_load_failed("a.png", "boom"),
        messages.repo_missing(p),
        messages.repo_bad(p, ImportError("no model")),
        messages.checkpoint_missing(p),
        messages.checkpoint_mismatch("mattingrefine", "resnet50", "size mismatch"),
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

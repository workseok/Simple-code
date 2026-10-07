"""매팅 엔진(BMV2 / MODNet / RVM) 연결을 가짜 저장소로 확인합니다.

실제 모델 대신, 각 저장소와 같은 모양(패키지 이름·클래스 이름·입출력)을 흉내 낸 아주 작은 코드를
tmp 폴더에 만듭니다. 세 저장소가 모두 'model'이라는 같은 이름의 패키지를 쓰기 때문에,
한 프로세스에서 엔진을 바꿔 써도 서로 섞이지 않는지가 가장 중요한 검증입니다.
"""

import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from bgmatte_app import matte_core  # noqa: E402
from bgmatte_app.config import Config  # noqa: E402
from bgmatte_app.messages import NoticeError  # noqa: E402
from fakes import synthetic_frame  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def make_bmv2_repo(root: Path) -> Path:
    repo = root / "BackgroundMattingV2"
    _write(repo / "model" / "__init__.py", """
        import torch
        from torch import nn
        MARK = "bmv2"
        class MattingBase(nn.Module):
            def __init__(self, backbone):
                super().__init__(); self.w = nn.Parameter(torch.zeros(1))
            def forward(self, src, bgr):
                return torch.full_like(src[:, :1], 1.0), src
        class MattingRefine(MattingBase):
            def __init__(self, backbone, backbone_scale=0.25, refine_mode="sampling", refine_sample_pixels=80000):
                super().__init__(backbone)
            def forward(self, src, bgr):
                pha, fgr = super().forward(src, bgr)
                return pha, fgr, None
    """)
    return repo


def make_rvm_repo(root: Path) -> Path:
    repo = root / "RobustVideoMatting"
    _write(repo / "model" / "__init__.py", """
        import torch
        from torch import nn
        MARK = "rvm"
        class MattingNetwork(nn.Module):
            calls = []
            def __init__(self, variant="mobilenetv3"):
                super().__init__(); self.variant = variant; self.w = nn.Parameter(torch.zeros(1))
            def forward(self, src, r1=None, r2=None, r3=None, r4=None, downsample_ratio=1, segmentation_pass=False):
                MattingNetwork.calls.append((r1 is not None, downsample_ratio))
                state = torch.ones(1, 1, 2, 2)
                return src, torch.full_like(src[:, :1], 0.5), state, state, state, state
    """)
    return repo


def make_modnet_repo(root: Path) -> Path:
    repo = root / "MODNet"
    _write(repo / "src" / "__init__.py", "")
    _write(repo / "src" / "models" / "__init__.py", "")
    _write(repo / "src" / "models" / "modnet.py", """
        import torch
        from torch import nn
        class MODNet(nn.Module):
            seen = []
            def __init__(self, backbone_pretrained=True):
                super().__init__(); self.w = nn.Parameter(torch.zeros(1))
            def forward(self, x, inference):
                MODNet.seen.append(tuple(x.shape[-2:]))
                n, _, h, w = x.shape
                return None, None, torch.full((n, 1, h, w), 0.8)
    """)
    return repo


@pytest.fixture
def world(tmp_path):
    """세 가짜 저장소 + 가중치 + 이미지가 준비된 폴더와 기본 설정."""
    bmv2, rvm, modnet = make_bmv2_repo(tmp_path), make_rvm_repo(tmp_path), make_modnet_repo(tmp_path)
    models = tmp_path / "models"
    models.mkdir()
    torch.save({"w": torch.zeros(1)}, models / "bmv2.pth")
    torch.save({"w": torch.zeros(1)}, models / "rvm.pth")
    torch.save({"w": torch.zeros(1)}, models / "rvm50.pth")
    # 공식 MODNet 가중치는 DataParallel로 저장되어 키 앞에 'module.'이 붙어 있음
    torch.save({"module.w": torch.zeros(1)}, models / "modnet.ckpt")
    cv2.imwrite(str(tmp_path / "bg.png"), synthetic_frame(64, 48))
    cv2.imwrite(str(tmp_path / "bgr.png"), synthetic_frame(64, 48))
    cfg = Config(
        device="cpu", repo_path=str(bmv2), checkpoint=str(models / "bmv2.pth"),
        modnet_repo=str(modnet), modnet_checkpoint=str(models / "modnet.ckpt"),
        rvm_repo=str(rvm), rvm_checkpoint=str(models / "rvm.pth"), rvm_checkpoint_resnet50=str(models / "rvm50.pth"),
    )
    matte_core._MODEL_CACHE.clear()
    yield tmp_path, cfg
    matte_core._MODEL_CACHE.clear()


def run(cfg, tmp_path, show_alpha=False, frames=1):
    matter = matte_core.Matter(cfg)
    matter.load()
    matter.set_bgr(tmp_path / "bgr.png")
    matter.set_background(tmp_path / "bg.png")
    frame = synthetic_frame(64, 48)
    out = None
    for _ in range(frames):
        out = matter.process(frame, show_alpha)
    return matter, out


@pytest.mark.parametrize("engine", ["bmv2", "modnet", "rvm"])
def test_every_engine_produces_a_composite_and_an_alpha_view(world, engine):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": engine}).validated()
    _, out = run(cfg, tmp_path)
    assert out.shape == (48, 64, 3) and out.dtype == np.uint8
    _, wide = run(cfg, tmp_path, show_alpha=True)
    assert wide.shape == (48, 128, 3), "알파 보기는 오른쪽에 매트를 붙입니다"


def test_engines_with_same_package_name_do_not_mix_in_one_process(world):
    tmp_path, cfg = world
    order = ["modnet", "rvm", "bmv2", "rvm", "modnet", "bmv2"]
    for engine in order:
        run(Config(**{**cfg.__dict__, "engine": engine}).validated(), tmp_path)
    # 엔진을 불러온 뒤에는 다른 저장소의 'model'/'src'가 모듈 캐시나 경로에 남아 있으면 안 됩니다.
    assert "model" not in sys.modules and "src" not in sys.modules
    assert not any(str(tmp_path) in p for p in sys.path)


def test_rvm_keeps_recurrent_state_between_frames_and_uses_downsample(world):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": "rvm", "rvm_downsample": 0.5}).validated()
    matter, _ = run(cfg, tmp_path, frames=3)
    from_repo = matter._engine.model
    assert from_repo.calls[-3:] == [(False, 0.5), (True, 0.5), (True, 0.5)], "첫 프레임 뒤에는 이전 상태를 넘겨야 합니다"


def test_rvm_variant_selects_its_own_weight_file(world):
    tmp_path, cfg = world
    (tmp_path / "models" / "rvm50.pth").unlink()
    cfg = Config(**{**cfg.__dict__, "engine": "rvm", "rvm_variant": "resnet50"}).validated()
    with pytest.raises(NoticeError) as err:
        matte_core.Matter(cfg).load()
    assert err.value.notice.code == "engine_checkpoint_missing"
    assert "rvm50.pth" in err.value.notice.detail


def test_modnet_resizes_to_multiple_of_32_and_returns_full_resolution_alpha(world):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": "modnet", "modnet_ref_size": 128, "modnet_smooth": 0.0}).validated()
    matter, out = run(cfg, tmp_path)
    h, w = matter._engine.model.seen[-1]
    assert h % 32 == 0 and w % 32 == 0 and min(h, w) >= 32
    assert out.shape == (48, 64, 3)


def test_modnet_smoothing_blends_with_previous_alpha(world):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": "modnet", "modnet_smooth": 0.5}).validated()
    matter, _ = run(cfg, tmp_path)
    prev = matter._engine._prev.clone()
    matter._engine.model.forward = lambda x, inf: (None, None, torch.zeros(x.shape[0], 1, *x.shape[-2:]))
    matter.process(synthetic_frame(64, 48))
    assert torch.allclose(matter._engine._prev, prev * 0.5, atol=1e-6)


@pytest.mark.parametrize("engine,code", [("modnet", "engine_repo_missing"), ("rvm", "engine_repo_missing"), ("bmv2", "repo_missing")])
def test_missing_repo_gives_a_notice_for_that_engine(world, engine, code):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": engine, "modnet_repo": str(tmp_path / "x"),
                    "rvm_repo": str(tmp_path / "x"), "repo_path": str(tmp_path / "x")}).validated()
    with pytest.raises(NoticeError) as err:
        matte_core.Matter(cfg).load()
    assert err.value.notice.code == code
    assert "open_settings" in err.value.notice.actions


def test_bad_weights_report_engine_load_failed(world):
    tmp_path, cfg = world
    torch.save({"unrelated": torch.zeros(3)}, tmp_path / "models" / "modnet.ckpt")
    cfg = Config(**{**cfg.__dict__, "engine": "modnet"}).validated()
    with pytest.raises(NoticeError) as err:
        matte_core.Matter(cfg).load()
    assert err.value.notice.code == "engine_load_failed"


def test_set_bgr_is_ignored_by_engines_that_do_not_need_it(world):
    tmp_path, cfg = world
    cfg = Config(**{**cfg.__dict__, "engine": "rvm"}).validated()
    matter = matte_core.Matter(cfg)
    matter.load()
    matter.set_bgr(tmp_path / "does_not_exist.png")  # 오류 없이 무시되어야 함

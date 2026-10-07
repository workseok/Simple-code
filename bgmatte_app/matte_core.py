"""torch를 쓰는 매팅 코어. 워커는 이 모듈을 Matter 클래스로만 사용합니다.

realtime_matte.py의 로직(장치 선택 → 모델 로드 → 추론 → 합성)을 GUI에서 쓰기 좋게
다시 묶은 것입니다. 전처리/후처리/합성은 저장소의 utils.py를 그대로 재사용하므로
CLI와 결과가 같습니다. 차이점은 오류를 sys.exit 대신 NoticeError로 던진다는 것,
로드한 모델을 재시작 사이에 캐시한다는 것, 그리고 GPU 추론 실패 시 CPU로 내려가는
기능(README의 'auto' 설명대로)이 실제 추론 단계까지 확장되어 있다는 것입니다.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

import cv2
import torch

from . import messages
from .config import PROJECT_ROOT, Config
from .messages import NoticeError

# 저장소 루트의 utils.py를 쓰기 위해 경로를 보장합니다 (BackgroundMattingV2 경로를
# sys.path 앞에 넣기 전에 먼저 import해 두어야 이름이 겹쳐도 우리 utils가 우선합니다).
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from utils import (  # noqa: E402
    composite,
    load_image_as_tensor,
    resize_to_match,
    tensor_to_frame,
    to_tensor,
)

log = logging.getLogger(__name__)

_MODEL_CACHE: Dict[tuple, object] = {}
_GPU_DISABLED = False  # GPU 추론이 한 번 실패하면 이번 실행에서는 다시 시도하지 않음


def _probe(device: torch.device) -> None:
    torch.zeros(1, device=device)  # 실제로 해당 장치에서 동작하는지 확인


def resolve_device(pref: str) -> Tuple[torch.device, str]:
    """(장치, 화면에 보여줄 이름). auto는 cuda → mps → cpu 순으로 시도합니다."""
    if pref != "auto":
        device = torch.device(pref)
        try:
            _probe(device)
            return device, _label(device)
        except Exception as exc:
            log.warning("%s 장치를 쓸 수 없어 CPU로 전환합니다: %s", pref, exc)
            return torch.device("cpu"), f"CPU ({pref.upper()} 사용 불가)"

    if not _GPU_DISABLED:
        candidates = (
            ("cuda", lambda: torch.cuda.is_available()),
            ("mps", lambda: getattr(torch.backends, "mps", None) is not None
             and torch.backends.mps.is_available()),
        )
        for name, available in candidates:
            try:
                if not available():
                    continue
                device = torch.device(name)
                _probe(device)
                return device, _label(device)
            except Exception as exc:
                log.warning("%s 장치 사용 실패(%s) — 다음 장치를 시도합니다.", name, exc)
    return torch.device("cpu"), "CPU"


def _label(device: torch.device) -> str:
    return {"cuda": "CUDA (NVIDIA GPU)", "mps": "MPS (Apple Silicon GPU)", "cpu": "CPU"}.get(
        device.type, device.type
    )


@contextlib.contextmanager
def _isolated_import(repo: Path, top_names: Tuple[str, ...]):
    """엔진마다 저장소 안에 같은 이름의 패키지('model')가 있어서, 한 프로세스에서 엔진을 바꿔 쓰면
    먼저 불러온 쪽이 계속 쓰이는 문제가 생깁니다. 해당 이름의 모듈 캐시를 잠시 치우고 이 저장소를
    맨 앞에 두어 불러온 뒤, 원래 상태로 되돌립니다. (이미 불러온 클래스는 그대로 동작합니다.)"""
    def clashing(name: str) -> bool:
        return any(name == top or name.startswith(top + ".") for top in top_names)

    saved = {k: v for k, v in sys.modules.items() if clashing(k)}
    for k in saved:
        del sys.modules[k]
    sys.path.insert(0, str(repo))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(repo))
        except ValueError:
            pass
        for k in [k for k in sys.modules if clashing(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


def _check_files(cfg: Config, engine: str, repo: Path, ckpt: Path) -> None:
    if not repo.is_dir():
        if engine == "bmv2":
            raise NoticeError(messages.repo_missing(repo))
        raise NoticeError(messages.engine_repo_missing(engine, repo))
    if not ckpt.is_file():
        if engine == "bmv2":
            raise NoticeError(messages.checkpoint_missing(ckpt, cfg.backbone))
        raise NoticeError(messages.engine_checkpoint_missing(engine, ckpt))


def _load_bmv2(cfg: Config, device: torch.device):
    repo = cfg.resolve(cfg.repo_path)
    ckpt = cfg.resolve(cfg.checkpoint_for(cfg.backbone))
    _check_files(cfg, "bmv2", repo, ckpt)

    key = (
        "bmv2", str(repo), str(ckpt), cfg.model_type, cfg.backbone, cfg.backbone_scale,
        cfg.refine_mode, cfg.refine_sample_pixels, device.type,
    )
    if key in _MODEL_CACHE:
        return key, _MODEL_CACHE[key]

    try:
        with _isolated_import(repo, ("model",)):
            from model import MattingBase, MattingRefine  # type: ignore  # noqa: E402
    except ImportError as exc:
        raise NoticeError(messages.repo_bad(repo, exc)) from exc

    try:
        if cfg.model_type == "mattingbase":
            model = MattingBase(cfg.backbone)
        else:
            model = MattingRefine(
                cfg.backbone,
                backbone_scale=cfg.backbone_scale,
                refine_mode=cfg.refine_mode,
                refine_sample_pixels=cfg.refine_sample_pixels,
            )
        state = torch.load(str(ckpt), map_location="cpu")
        model.load_state_dict(state, strict=True)
    except Exception as exc:
        raise NoticeError(messages.checkpoint_mismatch(cfg.model_type, cfg.backbone, exc)) from exc

    model = model.to(device).eval()
    _MODEL_CACHE[key] = model
    return key, model


def _load_modnet(cfg: Config, device: torch.device):
    repo = cfg.resolve(cfg.modnet_repo)
    ckpt = cfg.resolve(cfg.modnet_checkpoint)
    _check_files(cfg, "modnet", repo, ckpt)
    key = ("modnet", str(repo), str(ckpt), device.type)
    if key in _MODEL_CACHE:
        return key, _MODEL_CACHE[key]
    try:
        with _isolated_import(repo, ("src",)):
            from src.models.modnet import MODNet  # type: ignore  # noqa: E402
        model = MODNet(backbone_pretrained=False)
        state = torch.load(str(ckpt), map_location="cpu")
        # 공식 가중치는 DataParallel로 저장되어 키 앞에 'module.'이 붙어 있습니다.
        model.load_state_dict({k.replace("module.", "", 1): v for k, v in state.items()})
    except Exception as exc:
        raise NoticeError(messages.engine_load_failed("modnet", exc)) from exc
    model = model.to(device).eval()
    _MODEL_CACHE[key] = model
    return key, model


def _load_rvm(cfg: Config, device: torch.device):
    repo = cfg.resolve(cfg.rvm_repo)
    ckpt = cfg.resolve(cfg.rvm_checkpoint_for())
    _check_files(cfg, "rvm", repo, ckpt)
    key = ("rvm", str(repo), str(ckpt), cfg.rvm_variant, device.type)
    if key in _MODEL_CACHE:
        return key, _MODEL_CACHE[key]
    try:
        with _isolated_import(repo, ("model",)):
            from model import MattingNetwork  # type: ignore  # noqa: E402
        model = MattingNetwork(cfg.rvm_variant)
        model.load_state_dict(torch.load(str(ckpt), map_location="cpu"))
    except Exception as exc:
        raise NoticeError(messages.engine_load_failed("rvm", exc)) from exc
    model = model.to(device).eval()
    _MODEL_CACHE[key] = model
    return key, model


# ---------------------------------------------------------------- 엔진 (모델 한 장 추론)
# 엔진은 src(1,3,H,W, RGB, 0~1)를 받아 (알파, 전경색 또는 None)을 돌려줍니다.
# 전경색이 None이면 Matter가 원본 프레임을 전경으로 씁니다. 합성·배경·알파 보기는 엔진과 무관하게 공통입니다.
# 새 엔진(윈도우용 ONNX/TensorRT 등)은 이 인터페이스만 구현하면 됩니다.


class _BMV2Engine:
    name = "bmv2"
    needs_bgr = True

    def __init__(self, cfg: Config, model):
        self.cfg, self.model, self._bgr = cfg, model, None

    def set_bgr(self, tensor) -> None:
        self._bgr = tensor

    def infer(self, src):
        bgr = resize_to_match(self._bgr, src.shape[-2:])
        if self.cfg.model_type == "mattingbase":
            pha, fgr = self.model(src, bgr)
        else:
            pha, fgr, *_ = self.model(src, bgr)
        return pha, fgr

    def to(self, device) -> None:
        self.model = self.model.to(device)
        self._bgr = self._bgr.to(device) if self._bgr is not None else None


class _MODNetEngine:
    name = "modnet"
    needs_bgr = False

    def __init__(self, cfg: Config, model):
        self.cfg, self.model, self._prev = cfg, model, None

    def infer(self, src):
        h, w = src.shape[-2:]
        scale = self.cfg.modnet_ref_size / min(h, w)
        nh = max(32, int(round(h * scale / 32)) * 32)  # MODNet은 가로·세로가 32의 배수여야 합니다
        nw = max(32, int(round(w * scale / 32)) * 32)
        x = torch.nn.functional.interpolate(src, size=(nh, nw), mode="area" if scale < 1 else "bilinear",
                                            **({} if scale < 1 else {"align_corners": False}))
        x = (x - 0.5) / 0.5
        _, _, matte = self.model(x, True)
        smooth = self.cfg.modnet_smooth
        if smooth > 0 and self._prev is not None and self._prev.shape == matte.shape:
            matte = smooth * self._prev + (1 - smooth) * matte
        self._prev = matte
        pha = torch.nn.functional.interpolate(matte, size=(h, w), mode="bilinear", align_corners=False)
        return pha.clamp(0, 1), None

    def to(self, device) -> None:
        self.model = self.model.to(device)
        self._prev = None


class _RVMEngine:
    name = "rvm"
    needs_bgr = False

    def __init__(self, cfg: Config, model):
        self.cfg, self.model, self._rec = cfg, model, [None] * 4

    def infer(self, src):
        # 이전 프레임의 상태(rec)를 이어받는 것이 RVM의 핵심입니다. 화면 크기가 바뀌면 초기화합니다.
        if self._rec[0] is not None and self._rec[0].shape[0] != src.shape[0]:
            self._rec = [None] * 4
        fgr, pha, *self._rec = self.model(src, *self._rec, self.cfg.rvm_downsample)
        return pha, fgr

    def to(self, device) -> None:
        self.model = self.model.to(device)
        self._rec = [None] * 4


_LOADERS = {
    "bmv2": (_load_bmv2, _BMV2Engine),
    "modnet": (_load_modnet, _MODNetEngine),
    "rvm": (_load_rvm, _RVMEngine),
}


class Matter:
    """엔진 + 합성 배경을 들고 프레임 한 장을 처리합니다."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.device: torch.device = torch.device("cpu")
        self.device_label = ""
        self._engine = None
        self._cache_key = None
        self._bg = None
        self._bg_cache: Dict[Path, torch.Tensor] = {}

    # -- 준비 ---------------------------------------------------------------
    def load(self) -> str:
        """모델을 불러오고 장치 이름을 반환합니다. 실패하면 NoticeError."""
        self.device, self.device_label = resolve_device(self.cfg.device)
        loader, engine_cls = _LOADERS[self.cfg.engine]
        self._cache_key, model = loader(self.cfg, self.device)
        self._engine = engine_cls(self.cfg, model)
        return self.device_label

    def set_bgr(self, path: Path) -> None:
        """클린 배경(bgr.png) 로드. BackgroundMattingV2 전용이며 다른 엔진에서는 무시합니다."""
        if self._engine is not None and self._engine.needs_bgr:
            self._engine.set_bgr(load_image_as_tensor(str(path), self.device))

    def set_background(self, path: Path) -> None:
        """합성 배경 전환. 한 번 읽은 이미지는 캐시합니다. 실패하면 FileNotFoundError."""
        tensor = self._bg_cache.get(path)
        if tensor is None:
            tensor = load_image_as_tensor(str(path), self.device)
            self._bg_cache[path] = tensor
        self._bg = tensor

    # -- 처리 ---------------------------------------------------------------
    def process(self, frame_bgr, show_alpha: bool = False):
        """카메라 프레임(BGR uint8) → 합성 결과(BGR uint8). show_alpha면 오른쪽에 알파 매트를 붙입니다."""
        with torch.no_grad():
            src = to_tensor(frame_bgr, self.device)
            pha, fgr = self._engine.infer(src)
            out = tensor_to_frame(composite(src if fgr is None else fgr, pha, self._bg))
            if show_alpha:
                alpha = tensor_to_frame(pha.repeat(1, 3, 1, 1))
                out = cv2.hconcat([out, alpha])
        return out

    # -- GPU 실패 시 CPU 전환 -------------------------------------------------
    def is_gpu(self) -> bool:
        return self.device.type != "cpu"

    def fallback_to_cpu(self) -> str:
        global _GPU_DISABLED
        _GPU_DISABLED = True
        cpu = torch.device("cpu")
        self._engine.to(cpu)
        _MODEL_CACHE.pop(self._cache_key, None)  # GPU 키에 CPU 모델이 남지 않도록
        self._bg_cache = {p: t.to(cpu) for p, t in self._bg_cache.items()}
        self._bg = self._bg.to(cpu) if self._bg is not None else None
        self.device = cpu
        self.device_label = "CPU (GPU 실패로 전환)"
        return self.device_label

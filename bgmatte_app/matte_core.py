"""torch를 쓰는 매팅 코어. 워커는 이 모듈을 Matter 클래스로만 사용합니다.

realtime_matte.py의 로직(장치 선택 → 모델 로드 → 추론 → 합성)을 GUI에서 쓰기 좋게
다시 묶은 것입니다. 전처리/후처리/합성은 저장소의 utils.py를 그대로 재사용하므로
CLI와 결과가 같습니다. 차이점은 오류를 sys.exit 대신 NoticeError로 던진다는 것,
로드한 모델을 재시작 사이에 캐시한다는 것, 그리고 GPU 추론 실패 시 CPU로 내려가는
기능(README의 'auto' 설명대로)이 실제 추론 단계까지 확장되어 있다는 것입니다.
"""

from __future__ import annotations

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


def _load_model(cfg: Config, device: torch.device):
    repo = cfg.resolve(cfg.repo_path)
    ckpt = cfg.resolve(cfg.checkpoint)
    if not repo.is_dir():
        raise NoticeError(messages.repo_missing(repo))
    if not ckpt.is_file():
        raise NoticeError(messages.checkpoint_missing(ckpt))

    key = (
        str(repo), str(ckpt), cfg.model_type, cfg.backbone, cfg.backbone_scale,
        cfg.refine_mode, cfg.refine_sample_pixels, device.type,
    )
    if key in _MODEL_CACHE:
        return key, _MODEL_CACHE[key]

    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    try:
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


class Matter:
    """모델 + 배경(bgr) + 합성 배경을 들고 프레임 한 장을 처리합니다."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.device: torch.device = torch.device("cpu")
        self.device_label = ""
        self._model = None
        self._cache_key = None
        self._bgr = None
        self._bg = None
        self._bg_cache: Dict[Path, torch.Tensor] = {}

    # -- 준비 ---------------------------------------------------------------
    def load(self) -> str:
        """모델을 불러오고 장치 이름을 반환합니다. 실패하면 NoticeError."""
        self.device, self.device_label = resolve_device(self.cfg.device)
        self._cache_key, self._model = _load_model(self.cfg, self.device)
        return self.device_label

    def set_bgr(self, path: Path) -> None:
        """클린 배경(bgr.png) 로드. 해상도가 다른 경우는 처리 시 자동으로 맞춥니다."""
        self._bgr = load_image_as_tensor(str(path), self.device)

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
            bgr = resize_to_match(self._bgr, src.shape[-2:])
            if self.cfg.model_type == "mattingbase":
                pha, fgr = self._model(src, bgr)
            else:
                pha, fgr, *_ = self._model(src, bgr)
            out = tensor_to_frame(composite(fgr, pha, self._bg))
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
        self._model = self._model.to(cpu)
        _MODEL_CACHE.pop(self._cache_key, None)  # GPU 키에 CPU 모델이 남지 않도록
        self._bgr = self._bgr.to(cpu) if self._bgr is not None else None
        self._bg_cache = {p: t.to(cpu) for p, t in self._bg_cache.items()}
        self._bg = self._bg.to(cpu) if self._bg is not None else None
        self.device = cpu
        self.device_label = "CPU (GPU 실패로 전환)"
        return self.device_label

"""설정 저장/불러오기와 경로 해석.

상대 경로는 저장소 루트(PROJECT_ROOT) 기준으로 해석합니다. 기본값은
docs/SETUP_MAC.md의 폴더 구성(~/Simple-code, ~/BackgroundMattingV2)과 같습니다.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Optional, Tuple

log = logging.getLogger(__name__)

APP_NAME = "BG Matte"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_TYPES = ("mattingrefine", "mattingbase")
BACKBONES = ("resnet50", "resnet101", "mobilenetv2")
REFINE_MODES = ("full", "sampling", "thresholding")
DEVICES = ("auto", "mps", "cuda", "cpu")


def config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BGMatte"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "BGMatte"


def config_path() -> Path:
    return config_dir() / "config.json"


def log_path() -> Path:
    """런처(.app)가 stdout/stderr를 모으는 로그 파일 위치와 같습니다."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "BGMatte" / "app.log"
    return Path.home() / ".cache" / "BGMatte" / "app.log"


@dataclass
class Config:
    # 모델
    repo_path: str = "../BackgroundMattingV2"
    checkpoint: str = "models/pytorch_resnet50.pth"
    model_type: str = "mattingrefine"
    backbone: str = "resnet50"
    backbone_scale: float = 0.25
    refine_mode: str = "sampling"
    refine_sample_pixels: int = 80_000
    device: str = "auto"
    # 이미지
    bgr: str = "bgr.png"
    backgrounds_dir: str = "backgrounds"
    legacy_background: str = "ai_background.png"
    # 카메라 (width/height 0 = 장치 기본값)
    camera_index: int = 0
    camera_width: int = 0
    camera_height: int = 0
    # 배경 촬영
    countdown_seconds: int = 5
    average_frames: int = 10
    # 앱 상태
    last_background: int = 1
    seen_intro: bool = False

    def resolve(self, value: str) -> Path:
        return resolve_path(value)

    def validated(self) -> "Config":
        """타입/범위를 보정한 복사본을 반환합니다 (손으로 고친 config.json 방어)."""
        defaults = Config()
        values: dict[str, Any] = {}
        for f in fields(self):
            default = getattr(defaults, f.name)
            values[f.name] = _coerce(getattr(self, f.name), default)

        def pick(name: str, choices: Tuple[str, ...]) -> None:
            if values[name] not in choices:
                values[name] = getattr(defaults, name)

        pick("model_type", MODEL_TYPES)
        pick("backbone", BACKBONES)
        pick("refine_mode", REFINE_MODES)
        pick("device", DEVICES)

        values["backbone_scale"] = min(max(values["backbone_scale"], 0.1), 1.0)
        values["refine_sample_pixels"] = max(values["refine_sample_pixels"], 1_000)
        values["camera_index"] = min(max(values["camera_index"], 0), 20)
        values["camera_width"] = max(values["camera_width"], 0)
        values["camera_height"] = max(values["camera_height"], 0)
        values["countdown_seconds"] = min(max(values["countdown_seconds"], 1), 30)
        values["average_frames"] = min(max(values["average_frames"], 1), 60)
        values["last_background"] = max(values["last_background"], 1)
        for name in ("repo_path", "checkpoint", "bgr", "backgrounds_dir", "legacy_background"):
            if not values[name].strip():
                values[name] = getattr(defaults, name)
        return replace(self, **values)


def _coerce(value: Any, default: Any) -> Any:
    try:
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        return str(value)
    except (TypeError, ValueError):
        return default


def resolve_path(value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def load_config(path: Optional[Path] = None) -> Tuple[Config, Optional[str]]:
    """(설정, 경고 메시지)를 반환합니다. 파일이 없으면 기본값, 깨졌으면 기본값 + 경고."""
    path = path or config_path()
    if not path.exists():
        return Config(), None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("최상위 값이 객체가 아닙니다")
    except (OSError, ValueError) as exc:
        log.warning("설정 파일을 읽지 못했습니다: %s (%s)", path, exc)
        return Config(), f"{path} ({exc})"
    known = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in raw.items() if k in known})
    return cfg.validated(), None


def save_config(cfg: Config, path: Optional[Path] = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {f.name: getattr(cfg.validated(), f.name) for f in fields(Config)}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

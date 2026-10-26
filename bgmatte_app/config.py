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

# 매팅 엔진: bmv2 = BackgroundMattingV2(빈 배경 촬영 필요), rvm = 빈 배경 없이 사람만 분리
ENGINES = ("bmv2", "rvm")
RVM_VARIANTS = ("mobilenetv3", "resnet50")
MODEL_TYPES = ("mattingrefine", "mattingbase")
BACKBONES = ("resnet50", "resnet101", "mobilenetv2")
REFINE_MODES = ("full", "sampling", "thresholding")
DEVICES = ("auto", "mps", "cuda", "cpu")
THEMES = ("dark", "light")
CAMERA_FORMATS = ("auto", "mjpg")


def config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BGMatte"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "BGMatte"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "BGMatte"


def config_path() -> Path:
    return config_dir() / "config.json"


def log_path() -> Path:
    """런처(.app)가 stdout/stderr를 모으는 로그 파일 위치와 같습니다."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "BGMatte" / "app.log"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "BGMatte" / "app.log"
    return Path.home() / ".cache" / "BGMatte" / "app.log"


@dataclass
class Config:
    # 엔진 선택 (아래 '모델' 설정은 bmv2, 그 아래 rvm 설정은 각 엔진용)
    engine: str = "bmv2"
    # 모델
    repo_path: str = "../BackgroundMattingV2"
    # 백본마다 가중치 파일이 따로 필요합니다 (층 구조가 달라 서로 바꿔 쓸 수 없습니다).
    # checkpoint는 예전 설정 파일과의 호환을 위해 이름을 유지한 resnet50용 경로입니다.
    checkpoint: str = "models/pytorch_resnet50.pth"
    checkpoint_resnet101: str = "models/pytorch_resnet101.pth"
    checkpoint_mobilenetv2: str = "models/pytorch_mobilenetv2.pth"
    model_type: str = "mattingrefine"
    backbone: str = "resnet50"
    backbone_scale: float = 0.25
    refine_mode: str = "sampling"
    refine_sample_pixels: int = 80_000
    device: str = "auto"
    # RobustVideoMatting: 이전 프레임 상태를 이어받는 영상 매팅. downsample이 작을수록 빠름
    rvm_repo: str = "../RobustVideoMatting"
    rvm_variant: str = "mobilenetv3"
    rvm_checkpoint: str = "models/rvm_mobilenetv3.pth"
    rvm_checkpoint_resnet50: str = "models/rvm_resnet50.pth"
    rvm_downsample: float = 0.375
    # 이미지
    bgr: str = "bgr.png"
    backgrounds_dir: str = "backgrounds"
    legacy_background: str = "ai_background.png"
    # 카메라 (width/height 0 = 장치 기본값)
    camera_index: int = 0
    camera_width: int = 0
    camera_height: int = 0
    camera_format: str = "auto"  # auto = 장치 기본 | mjpg = 압축 영상 요청 (캡처카드 1080p/고프레임용)
    # 배경 촬영
    countdown_seconds: int = 5
    average_frames: int = 10
    # 앱 상태
    last_background: int = 1
    seen_intro: bool = False
    theme: str = "dark"  # 화면 테마: dark(어둡게) | light(밝게)
    # 오른쪽 콘솔의 보조 패널 표시 여부 (설정 → 화면 표시). 합성 배경 패널은 항상 보입니다.
    show_status: bool = True
    show_shortcuts: bool = True
    show_history: bool = True

    def resolve(self, value: str) -> Path:
        return resolve_path(value)

    def checkpoint_for(self, backbone: Optional[str] = None) -> str:
        """백본에 맞는 가중치 경로(설정 문자열)를 반환합니다. 기본은 현재 선택된 백본."""
        backbone = backbone or self.backbone
        return {
            "resnet101": self.checkpoint_resnet101,
            "mobilenetv2": self.checkpoint_mobilenetv2,
        }.get(backbone, self.checkpoint)

    def rvm_checkpoint_for(self, variant: Optional[str] = None) -> str:
        variant = variant or self.rvm_variant
        return self.rvm_checkpoint_resnet50 if variant == "resnet50" else self.rvm_checkpoint

    def bgr_for_camera(self) -> str:
        """현재 카메라 번호에 맞는 빈 배경 이미지 경로(설정 문자열).

        빈 배경은 카메라마다 다르므로 0번은 설정값(bgr.png) 그대로, 1번 이상은 bgr_cam1.png 처럼
        번호를 붙인 파일을 씁니다. 카메라를 2대 이상 쓸 때 서로 덮어쓰지 않게 하기 위해서입니다."""
        if self.camera_index == 0:
            return self.bgr
        p = Path(self.bgr)
        return str(p.with_name(f"{p.stem}_cam{self.camera_index}{p.suffix}"))

    @property
    def needs_bgr(self) -> bool:
        """빈 배경(bgr.png) 촬영이 필요한 엔진인지. rvm은 필요 없습니다."""
        return self.engine == "bmv2"

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

        pick("engine", ENGINES)
        pick("rvm_variant", RVM_VARIANTS)
        pick("model_type", MODEL_TYPES)
        pick("backbone", BACKBONES)
        pick("refine_mode", REFINE_MODES)
        pick("device", DEVICES)
        pick("theme", THEMES)
        pick("camera_format", CAMERA_FORMATS)

        values["rvm_downsample"] = min(max(values["rvm_downsample"], 0.1), 1.0)
        values["backbone_scale"] = min(max(values["backbone_scale"], 0.1), 1.0)
        values["refine_sample_pixels"] = max(values["refine_sample_pixels"], 1_000)
        values["camera_index"] = min(max(values["camera_index"], 0), 20)
        values["camera_width"] = max(values["camera_width"], 0)
        values["camera_height"] = max(values["camera_height"], 0)
        values["countdown_seconds"] = min(max(values["countdown_seconds"], 1), 30)
        values["average_frames"] = min(max(values["average_frames"], 1), 60)
        values["last_background"] = max(values["last_background"], 1)
        for name in ("repo_path", "checkpoint", "checkpoint_resnet101", "checkpoint_mobilenetv2", "bgr", "backgrounds_dir", "legacy_background",
                     "rvm_repo", "rvm_checkpoint", "rvm_checkpoint_resnet50"):
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
    raw = {k: v for k, v in raw.items() if k in known}
    # 예전 설정(가중치 경로 1개): resnet50이 아닌 백본이 선택돼 있었다면 그 백본의 칸으로 옮깁니다.
    legacy_backbone = raw.get("backbone")
    if legacy_backbone in ("resnet101", "mobilenetv2") and "checkpoint" in raw:
        slot = f"checkpoint_{legacy_backbone}"
        if slot not in raw:
            raw[slot] = raw.pop("checkpoint")
    cfg = Config(**raw)
    return cfg.validated(), None


def save_config(cfg: Config, path: Optional[Path] = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {f.name: getattr(cfg.validated(), f.name) for f in fields(Config)}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

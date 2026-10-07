"""사용자에게 보이는 안내/오류 문구 모음.

화면에 나오는 한국어 문구는 모두 이 파일에서 관리합니다. 각 Notice는
  - title : 한 줄 요약
  - detail: 무슨 일이 있었는지
  - hint  : 어떻게 하면 되는지
  - actions: 배너에 붙을 버튼 (open_settings / open_camera_privacy / open_backgrounds /
             restart / capture)
로 구성됩니다. Qt/torch에 의존하지 않으므로 단독으로 테스트할 수 있습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

from .config import log_path

ACTIONS = ("open_settings", "open_camera_privacy", "open_backgrounds", "restart", "capture")


class Level(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class Notice:
    code: str
    level: Level
    title: str
    detail: str = ""
    hint: str = ""
    actions: Tuple[str, ...] = ()
    banner: bool = True  # False면 알림 기록에만 남기고 배너는 띄우지 않음
    sticky: bool = False  # True면 자동으로 사라지지 않고, 사용자가 조치하거나 닫을 때까지 유지


class NoticeError(Exception):
    """워커/코어에서 '사용자에게 보여줄 오류'를 던질 때 사용합니다."""

    def __init__(self, notice: Notice):
        super().__init__(notice.title)
        self.notice = notice


def _short(err: object, limit: int = 180) -> str:
    text = " ".join(str(err).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------- 카메라


def camera_permission_pending() -> Notice:
    return Notice(
        "camera_permission_pending", Level.INFO, "카메라 권한을 요청하고 있습니다",
        "화면에 나타난 팝업에서 '허용'을 눌러 주세요.",
    )


def camera_permission_denied() -> Notice:
    return Notice(
        "camera_permission_denied", Level.ERROR, "카메라 권한이 꺼져 있습니다",
        "macOS가 이 앱의 카메라 사용을 막고 있습니다.",
        "시스템 설정 → 개인정보 보호 및 보안 → 카메라에서 'BG Matte'(터미널로 실행했다면 "
        "해당 터미널 앱)를 켠 뒤 '다시 시작'을 눌러 주세요.",
        ("open_camera_privacy", "restart"),
    )


def camera_restricted() -> Notice:
    return Notice(
        "camera_restricted", Level.ERROR, "이 Mac에서는 카메라 사용이 제한되어 있습니다",
        "화면 시간 또는 관리자 설정이 카메라 접근을 막고 있습니다.",
        "시스템 설정 → 개인정보 보호 및 보안 → 카메라 항목과 제한 설정을 확인해 주세요.",
        ("open_camera_privacy",),
    )


def camera_open_failed(index: int) -> Notice:
    return Notice(
        "camera_open_failed", Level.ERROR, "카메라를 열 수 없습니다",
        f"카메라 번호 {index}번에 연결하지 못했습니다.",
        "USB 연결을 확인하고, 설정에서 카메라 번호를 0 → 1 → 2 순으로 바꿔 보세요. "
        "Zoom·OBS 등 다른 앱이 카메라를 쓰고 있다면 종료해 주세요.",
        ("open_settings", "restart"),
    )


def camera_no_frame(index: int) -> Notice:
    return Notice(
        "camera_no_frame", Level.ERROR, "카메라 영상이 들어오지 않습니다",
        f"카메라 {index}번은 열렸지만 프레임을 받지 못했습니다.",
        "권한 팝업이 떠 있었다면 '허용' 후 다시 시작해 주세요. 캡처카드라면 HDMI 입력 신호"
        "(소스 장비의 전원·출력)를 확인해 주세요.",
        ("restart", "open_settings"),
    )


def camera_black() -> Notice:
    return Notice(
        "camera_black", Level.WARN, "영상이 검게 들어오고 있습니다",
        "카메라는 연결됐지만 화면이 거의 완전히 검습니다.",
        "카메라 번호나 캡처카드 입력 신호를 확인해 주세요. 권한이 막힌 경우에도 검은 화면이 나옵니다.",
        ("open_settings",),
    )


def camera_lost() -> Notice:
    return Notice(
        "camera_lost", Level.ERROR, "카메라 연결이 끊겼습니다",
        "영상을 계속 읽지 못해 실행을 멈췄습니다.",
        "케이블과 캡처카드를 다시 연결한 뒤 '다시 시작'을 눌러 주세요.",
        ("restart",),
    )


# ---------------------------------------------------------------- 배경(bgr) 촬영


def bgr_missing(path: Path) -> Notice:
    return Notice(
        "bgr_missing", Level.WARN, "먼저 빈 배경을 촬영해 주세요",
        f"저장된 배경 이미지({path.name})가 없습니다.",
        "피사체(사람·물체)를 화면 밖으로 옮기고 스페이스바를 누르세요. 촬영한 뒤에는 카메라를 움직이지 마세요.",
        ("capture",),
        sticky=True,
    )


def bgr_unreadable(path: Path) -> Notice:
    return Notice(
        "bgr_unreadable", Level.WARN, "저장된 배경 이미지를 읽을 수 없습니다",
        f"{path.name} 파일이 손상됐거나 이미지가 아닙니다.",
        "피사체를 화면 밖으로 옮기고 스페이스바로 다시 촬영해 주세요.",
        ("capture",),
        sticky=True,
    )


def bgr_size_mismatch(bgr_wh: Tuple[int, int], cam_wh: Tuple[int, int]) -> Notice:
    return Notice(
        "bgr_size_mismatch", Level.WARN, "배경 이미지와 카메라 해상도가 다릅니다",
        f"배경 {bgr_wh[0]}×{bgr_wh[1]} / 현재 카메라 {cam_wh[0]}×{cam_wh[1]}",
        "이대로도 동작하지만 합성 품질이 떨어질 수 있습니다. 같은 해상도에서 스페이스바로 다시 촬영하세요.",
        ("capture",),
    )


def capture_unavailable() -> Notice:
    return Notice(
        "capture_unavailable", Level.INFO, "지금은 배경을 촬영할 수 없습니다",
        "카메라 연결과 준비가 끝나 상태가 '실행 중' 또는 '배경 촬영 필요'가 되면 촬영할 수 있습니다.",
    )


def capture_started(seconds: int) -> Notice:
    return Notice(
        "capture_started", Level.INFO, "배경 촬영을 시작합니다",
        f"{seconds}초 뒤에 촬영합니다. 피사체는 화면 밖으로 이동해 주세요.",
        banner=False,
    )


def capture_saved(path: Path, backup: Optional[Path]) -> Notice:
    detail = f"{path.name} 저장 완료."
    if backup is not None:
        detail += f" 이전 배경은 {backup.name}로 보관했습니다."
    return Notice(
        "capture_saved", Level.SUCCESS, "배경을 저장했습니다", detail,
        "이제 촬영이 끝날 때까지 카메라를 움직이지 마세요.",
    )


def capture_cancelled() -> Notice:
    return Notice("capture_cancelled", Level.INFO, "배경 촬영을 취소했습니다", banner=False)


def capture_failed(err: object) -> Notice:
    return Notice(
        "capture_failed", Level.WARN, "배경을 저장하지 못했습니다", _short(err),
        "저장 위치의 쓰기 권한과 디스크 여유 공간을 확인한 뒤 다시 시도해 주세요.",
        ("capture",),
    )


# ---------------------------------------------------------------- 합성 배경(번호)


def bg_none(folder: Path) -> Notice:
    return Notice(
        "bg_none", Level.ERROR, "합성할 배경 이미지가 없습니다",
        f"'{folder.name}' 폴더에 이미지(PNG/JPG)가 없습니다.",
        "폴더에 이미지를 넣은 뒤 '다시 시작'을 눌러 주세요. 파일명 앞에 01_, 02_ 처럼 번호를 붙이면 "
        "그 순서대로 1번, 2번이 됩니다.",
        ("open_backgrounds", "restart"),
    )


def bg_all_failed() -> Notice:
    return Notice(
        "bg_all_failed", Level.ERROR, "배경 이미지를 하나도 불러오지 못했습니다",
        "backgrounds 폴더의 이미지가 모두 손상됐거나 지원하지 않는 형식입니다.",
        "PNG 또는 JPG 파일인지 확인한 뒤 '다시 시작'을 눌러 주세요.",
        ("open_backgrounds", "restart"),
    )


def bg_invalid(number: int, count: int) -> Notice:
    return Notice(
        "bg_invalid", Level.WARN, f"{number}번 배경이 없습니다",
        f"등록된 배경은 1번부터 {count}번까지입니다.",
        banner=True,
    )


def bg_not_ready() -> Notice:
    return Notice(
        "bg_not_ready", Level.INFO, "배경 전환은 실행 중에만 할 수 있습니다",
        "준비가 끝나면 숫자 키(1~9)로 배경을 바꿀 수 있습니다.",
    )


def bg_load_failed(name: str, err: object) -> Notice:
    return Notice(
        "bg_load_failed", Level.WARN, f"'{name}'을(를) 불러오지 못했습니다", _short(err),
        "이전 배경을 그대로 사용합니다. 파일이 손상되지 않았는지 확인해 주세요.",
    )


# ---------------------------------------------------------------- 모델


def repo_missing(path: Path) -> Notice:
    return Notice(
        "repo_missing", Level.ERROR, "BackgroundMattingV2 폴더를 찾을 수 없습니다",
        f"{path}",
        "git clone https://github.com/PeterL1n/BackgroundMattingV2.git 으로 내려받은 뒤, "
        "설정에서 그 폴더를 지정해 주세요.",
        ("open_settings",),
    )


def repo_bad(path: Path, err: object) -> Notice:
    return Notice(
        "repo_bad", Level.ERROR, "BackgroundMattingV2 폴더가 올바르지 않습니다",
        f"{path} 에서 model 모듈을 불러오지 못했습니다. ({_short(err, 120)})",
        "model 폴더가 바로 보이는 최상위 폴더를 지정했는지 확인해 주세요.",
        ("open_settings",),
    )


def checkpoint_missing(path: Path, backbone: str = "") -> Notice:
    which = f"{backbone} " if backbone else ""
    return Notice(
        "checkpoint_missing", Level.ERROR, f"{which}모델 가중치 파일(.pth)이 없습니다",
        f"{path}",
        f"BackgroundMattingV2 README의 Model/Checkpoints에서 {which}용 .pth 파일을 받아 위 위치에 두거나, "
        "설정의 모델 가중치 칸에서 파일 위치를 바꿔 주세요. 백본마다 파일이 따로 필요합니다.",
        ("open_settings",),
    )


def checkpoint_mismatch(model_type: str, backbone: str, err: object) -> Notice:
    return Notice(
        "checkpoint_mismatch", Level.ERROR, "가중치와 모델 설정이 맞지 않습니다",
        f"{model_type} / {backbone} 설정으로 불러오지 못했습니다. ({_short(err, 120)})",
        "설정의 백본 칸과 그 백본의 가중치 칸에 지정한 파일(예: resnet101은 pytorch_resnet101.pth)이 같은 종류인지 확인해 주세요.",
        ("open_settings",),
    )


def inference_failed(err: object) -> Notice:
    return Notice(
        "inference_failed", Level.ERROR, "합성 처리 중 오류가 발생했습니다", _short(err),
        "'다시 시작'으로도 반복되면 설정에서 장치를 CPU로 바꿔 보세요.",
        ("restart", "open_settings"),
    )


def cpu_fallback(err: object) -> Notice:
    return Notice(
        "cpu_fallback", Level.WARN, "GPU 처리에 실패해 CPU로 전환했습니다", _short(err),
        "계속 동작하지만 속도가 느려질 수 있습니다.",
    )


# ---------------------------------------------------------------- 기타


def config_corrupt(detail: str) -> Notice:
    return Notice(
        "config_corrupt", Level.WARN, "설정 파일을 읽지 못해 기본값으로 시작했습니다",
        _short(detail, 200),
        "설정 창에서 저장하면 새 설정 파일이 만들어집니다.",
        ("open_settings",),
    )


def unexpected(err: object) -> Notice:
    return Notice(
        "unexpected", Level.ERROR, "예기치 않은 오류가 발생했습니다", _short(err),
        f"자세한 내용은 로그를 확인해 주세요: {log_path()}",
        ("restart",),
    )

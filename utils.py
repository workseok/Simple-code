"""
utils.py

capture_background.py와는 무관하며, realtime_matte.py에서만 사용하는
텐서 변환 / 알파 합성 헬퍼 모음입니다.

BackgroundMattingV2 공식 레포(https://github.com/PeterL1n/BackgroundMattingV2)의
inference_speed_test.py에서 사용하는 전처리·후처리 방식을 참고해
동일한 입출력 규약(RGB, [0, 1] float, NCHW)을 따르도록 구현했습니다.
- 모델 입력(src, bgr)  : (N, 3, H, W), float32, RGB, 0.0~1.0
- 모델 출력(pha, fgr)  : pha = (N, 1, H, W) 알파 마스크, fgr = (N, 3, H, W) 전경색

이 파일은 realtime_matte.py와 (필요 시) capture_background.py 외의 다른
프로젝트와 공유하지 않습니다.
"""

from typing import Tuple

import cv2
import numpy as np
import torch


def to_tensor(frame_bgr: np.ndarray, device: torch.device) -> torch.Tensor:
    """cv2로 읽은 BGR uint8 HWC 프레임을 모델 입력 텐서로 변환합니다.

    반환 shape: (1, 3, H, W), dtype float32, 값 범위 [0, 1], 채널 순서 RGB.
    """
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    tensor = torch.from_numpy(frame_rgb).to(device)
    tensor = tensor.permute(2, 0, 1).contiguous()  # HWC -> CHW
    tensor = tensor.float().div(255.0)
    return tensor.unsqueeze(0)  # CHW -> NCHW


def load_image_as_tensor(path: str, device: torch.device) -> torch.Tensor:
    """이미지 파일(bgr.png, ai_background.png 등)을 모델 입력 텐서로 로드합니다."""
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {path}")
    return to_tensor(image, device)


def tensor_to_frame(tensor: torch.Tensor) -> np.ndarray:
    """모델 출력/합성 결과 텐서를 cv2로 표시 가능한 BGR uint8 HWC 배열로 변환합니다.

    입력 shape: (1, 3, H, W) 또는 (3, H, W), 값 범위 [0, 1], 채널 순서 RGB.
    """
    if tensor.dim() == 4:
        tensor = tensor[0]
    frame_rgb = tensor.clamp(0, 1).mul(255.0).byte()
    frame_rgb = frame_rgb.permute(1, 2, 0).contiguous().cpu().numpy()  # CHW -> HWC
    return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)


def resize_to_match(tensor: torch.Tensor, target_hw: Tuple[int, int]) -> torch.Tensor:
    """tensor의 공간 해상도를 target_hw = (H, W)에 맞춰 리사이즈합니다.

    src(실시간 입력), bgr(배경), ai_background 세 이미지의 해상도가
    서로 다를 수 있으므로, 합성 전 반드시 동일 해상도로 맞춰야 합니다.
    """
    if tensor.shape[-2:] == target_hw:
        return tensor
    return torch.nn.functional.interpolate(
        tensor, size=target_hw, mode="bilinear", align_corners=False
    )


def composite(fgr: torch.Tensor, pha: torch.Tensor, target_bgr: torch.Tensor) -> torch.Tensor:
    """알파 매트를 이용해 전경(fgr)을 새 배경(target_bgr) 위에 합성합니다.

    com = fgr * pha + target_bgr * (1 - pha)

    - fgr, target_bgr: (N, 3, H, W), RGB, [0, 1]
    - pha: (N, 1, H, W), [0, 1]
    모든 텐서는 동일 해상도여야 합니다 (필요 시 resize_to_match 사용).
    """
    target_bgr = resize_to_match(target_bgr, fgr.shape[-2:])
    return fgr * pha + target_bgr * (1 - pha)

"""
realtime_matte.py

capture_background.py로 미리 저장해 둔 bgr.png(클린 배경)를 기준으로,
실시간 카메라 입력과 비교해 BackgroundMattingV2 모델로 알파 매트를
추출하고, 추출된 알파로 전경을 AI 생성 배경 플레이트(ai_background.png)
위에 합성해 cv2.imshow로 미리보기 출력합니다.

전제:
- 카메라는 bgr.png를 캡처한 시점부터 완전 고정 상태여야 합니다.
  (팬/틸트/줌/흔들림 발생 시 배경과 실시간 프레임이 어긋나 매팅 품질 저하)
- 완전 오프라인으로 동작합니다 (클라우드 API 호출 없음).

모델 아키텍처(model.MattingBase / model.MattingRefine)는 이 저장소에
포함하지 않습니다. BackgroundMattingV2 공식 레포를 별도로 clone한 뒤
--repo-path로 경로를 지정하면 sys.path에 추가해 import합니다.

    git clone https://github.com/PeterL1n/BackgroundMattingV2.git

추론 로직(입력 전처리 -> 모델 forward -> 알파/전경 분리)은 공식 레포의
inference_speed_test.py 흐름을 참고해 구성했습니다.

사용 예:
    python realtime_matte.py \
        --repo-path ../BackgroundMattingV2 \
        --model-checkpoint models/pytorch_resnet50.pth \
        --model-backbone resnet50 \
        --bgr bgr.png \
        --ai-background ai_background.png
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import torch

from utils import composite, load_image_as_tensor, resize_to_match, tensor_to_frame, to_tensor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BackgroundMattingV2로 실시간 배경 매팅 및 합성 미리보기를 수행합니다.",
    )
    parser.add_argument(
        "--repo-path",
        type=str,
        required=True,
        help="clone해 둔 BackgroundMattingV2 공식 레포 경로 (model 패키지를 "
        "import하기 위해 sys.path에 추가됩니다)",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        choices=["mattingbase", "mattingrefine"],
        default="mattingrefine",
        help="사용할 모델 클래스 (기본값: mattingrefine)",
    )
    parser.add_argument(
        "--model-backbone",
        type=str,
        choices=["resnet50", "resnet101", "mobilenetv2"],
        default="resnet50",
        help="백본 네트워크 (기본값: resnet50)",
    )
    parser.add_argument(
        "--model-checkpoint",
        type=str,
        required=True,
        help="모델 가중치(.pth) 경로. README의 다운로드 안내를 참고해 "
        "models/ 디렉터리에 받아두세요 (git에는 커밋되지 않음)",
    )
    parser.add_argument(
        "--backbone-scale",
        type=float,
        default=0.25,
        help="mattingrefine에서 저해상도 백본 추론에 사용할 다운스케일 비율 "
        "(기본값: 0.25, 공식 레포 기본값과 동일)",
    )
    parser.add_argument(
        "--refine-mode",
        type=str,
        choices=["full", "sampling", "thresholding"],
        default="sampling",
        help="mattingrefine의 refine 모드 (기본값: sampling)",
    )
    parser.add_argument(
        "--refine-sample-pixels",
        type=int,
        default=80_000,
        help="refine-mode=sampling일 때 정제할 픽셀 수 (기본값: 80000)",
    )
    parser.add_argument(
        "--bgr",
        type=str,
        default="bgr.png",
        help="capture_background.py로 저장한 클린 배경 이미지 경로 (기본값: bgr.png)",
    )
    parser.add_argument(
        "--ai-background",
        type=str,
        default="ai_background.png",
        help="합성에 사용할 AI 생성 배경 플레이트 경로 (기본값: ai_background.png)",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="cv2.VideoCapture 장치 인덱스 (기본값: 0)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "mps", "cuda", "cpu"],
        help="추론 장치 (기본값: auto — mps를 먼저 시도하고, 사용할 수 없거나 "
        "런타임 오류가 나면 자동으로 cpu로 전환)",
    )
    parser.add_argument(
        "--show-alpha",
        action="store_true",
        help="합성 결과 옆에 알파 매트도 함께 표시합니다 (디버그용)",
    )
    return parser.parse_args()


def resolve_device(device_arg: str) -> torch.device:
    """추론 장치를 결정합니다.

    --device auto(기본값)일 때는 mps(Apple Silicon GPU)를 먼저 시도하고,
    이 시스템에서 지원하지 않거나 실제 연산 중 오류가 나면 자동으로
    cpu로 넘어갑니다. is_available() 체크만으로는 런타임 오류를 잡지
    못하므로, 실제로 작은 텐서 연산을 한 번 실행해 확인합니다.
    """
    if device_arg != "auto":
        return torch.device(device_arg)

    try:
        if not torch.backends.mps.is_available():
            raise RuntimeError("이 시스템에서 MPS 백엔드를 사용할 수 없습니다.")
        device = torch.device("mps")
        torch.zeros(1, device=device)  # 실제 동작 여부 확인
        print("[정보] mps(Apple Silicon GPU) 장치를 사용합니다.")
        return device
    except Exception as exc:
        print(f"[경고] mps 장치 사용 실패({exc}) — cpu로 전환합니다.")
        return torch.device("cpu")


def load_model(args: argparse.Namespace, device: torch.device):
    """BackgroundMattingV2 공식 레포에서 MattingBase/MattingRefine을 import해
    가중치를 로드한 뒤 eval 모드의 모델을 반환합니다."""
    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"[오류] --repo-path 경로가 존재하지 않습니다: {repo_path}", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, str(repo_path))

    try:
        from model import MattingBase, MattingRefine  # noqa: E402  (동적 경로 삽입 후 import)
    except ImportError as exc:
        print(
            "[오류] BackgroundMattingV2 레포에서 model 모듈을 import할 수 없습니다.\n"
            f"  --repo-path='{repo_path}' 가 공식 레포 루트를 가리키는지 확인하세요.\n"
            "  (git clone https://github.com/PeterL1n/BackgroundMattingV2.git)\n"
            f"  원본 오류: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.model_type == "mattingbase":
        model = MattingBase(args.model_backbone)
    else:
        model = MattingRefine(
            args.model_backbone,
            backbone_scale=args.backbone_scale,
            refine_mode=args.refine_mode,
            refine_sample_pixels=args.refine_sample_pixels,
        )

    checkpoint = torch.load(args.model_checkpoint, map_location=device)
    model.load_state_dict(checkpoint, strict=True)
    model = model.to(device).eval()
    return model


@torch.no_grad()
def run_inference(model, model_type: str, src: torch.Tensor, bgr: torch.Tensor):
    """전처리된 src(실시간 입력), bgr(배경) 텐서로 모델을 실행해 (pha, fgr)를 반환합니다."""
    if model_type == "mattingbase":
        pha, fgr = model(src, bgr)
    else:  # mattingrefine
        pha, fgr, *_ = model(src, bgr)
    return pha, fgr


def main() -> None:
    args = parse_args()
    device = resolve_device(args.device)
    print(f"[정보] 추론 장치: {device}")

    model = load_model(args, device)

    # 배경(bgr)과 AI 배경 플레이트는 촬영 내내 고정이므로 최초 1회만 로드합니다.
    bgr_tensor = load_image_as_tensor(args.bgr, device)
    ai_background_tensor = load_image_as_tensor(args.ai_background, device)

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"[오류] 카메라 인덱스 {args.camera_index}를 열 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    window_name = "realtime_matte - ESC: quit"
    prev_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[오류] 프레임을 읽을 수 없습니다.", file=sys.stderr)
                break

            src_tensor = to_tensor(frame, device)
            bgr_matched = resize_to_match(bgr_tensor, src_tensor.shape[-2:])

            pha, fgr = run_inference(model, args.model_type, src_tensor, bgr_matched)
            composited = composite(fgr, pha, ai_background_tensor)

            output_frame = tensor_to_frame(composited)

            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now
            cv2.putText(
                output_frame,
                f"FPS: {fps:.1f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            if args.show_alpha:
                alpha_frame = tensor_to_frame(pha.repeat(1, 3, 1, 1))
                output_frame = cv2.hconcat([output_frame, alpha_frame])

            cv2.imshow(window_name, output_frame)

            if (cv2.waitKey(1) & 0xFF) == 27:  # ESC
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

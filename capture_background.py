"""
capture_background.py

리허설 단계에서 수동으로 1회 실행하는 스크립트입니다.
피사체(사람/물체)가 전혀 없는 상태에서 카메라(HDMI 캡처카드 또는
노트북 내장캠, cv2.VideoCapture로 접근 가능한 모든 장치)가 보는
"깨끗한 배경" 프레임을 캡처해 bgr.png로 저장합니다.

이 파일은 realtime_matte.py, utils.py와 완전히 독립적으로 동작합니다.
(BackgroundMattingV2는 리허설 시점의 배경(bgr) 프레임과 실시간 입력(src)
프레임을 비교해 알파 매트를 추출하는데, 이 두 프레임의 카메라 자세가
1픽셀이라도 어긋나면 결과 품질이 크게 떨어지므로, 배경 캡처 이후
촬영이 끝날 때까지 카메라는 절대 움직이면 안 됩니다.)

사용 예:
    python capture_background.py
    python capture_background.py --camera-index 1 --output bgr.png
    python capture_background.py --width 1920 --height 1080 --warmup-frames 30
"""

import argparse
import sys
import time

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="피사체 없는 클린 배경 프레임을 캡처해 저장합니다.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="cv2.VideoCapture에 전달할 장치 인덱스 (기본값: 0). "
        "HDMI 캡처카드가 여러 개 장치로 잡히는 경우 값을 바꿔가며 확인하세요.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="bgr.png",
        help="저장할 배경 이미지 경로 (기본값: bgr.png)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="캡처 해상도 가로 (지정하지 않으면 장치 기본값 사용)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="캡처 해상도 세로 (지정하지 않으면 장치 기본값 사용)",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=30,
        help="캡처카드/카메라의 자동 노출·화이트밸런스가 안정되기까지 "
        "버리는 초기 프레임 수 (기본값: 30)",
    )
    parser.add_argument(
        "--average-frames",
        type=int,
        default=1,
        help="저장 직전 평균을 낼 프레임 수. 1보다 크면 노이즈를 줄이기 위해 "
        "여러 프레임을 평균 합성합니다 (기본값: 1, 평균 없이 단일 프레임 저장)",
    )
    return parser.parse_args()


def open_capture(camera_index: int, width: int, height: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[오류] 카메라 인덱스 {camera_index}를 열 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    return cap


def warmup(cap: cv2.VideoCapture, num_frames: int) -> None:
    """자동 노출/화이트밸런스가 안정될 때까지 초기 프레임을 버립니다."""
    for _ in range(max(num_frames, 0)):
        cap.read()


def capture_averaged_frame(cap: cv2.VideoCapture, num_frames: int) -> np.ndarray:
    """num_frames만큼 프레임을 읽어 평균을 낸 배경 프레임을 반환합니다."""
    num_frames = max(num_frames, 1)
    accumulator = None

    for i in range(num_frames):
        ok, frame = cap.read()
        if not ok:
            print(f"[오류] {i + 1}번째 프레임을 읽는 데 실패했습니다.", file=sys.stderr)
            sys.exit(1)

        if accumulator is None:
            accumulator = np.zeros_like(frame, dtype=np.float64)
        accumulator += frame.astype(np.float64)

    averaged = (accumulator / num_frames).clip(0, 255).astype(np.uint8)
    return averaged


def main() -> None:
    args = parse_args()

    cap = open_capture(args.camera_index, args.width, args.height)

    try:
        warmup(cap, args.warmup_frames)

        print("=" * 60)
        print("피사체(사람/물체)가 완전히 프레임 밖으로 나간 것을 확인한 뒤")
        print("[SPACE] 키로 배경을 캡처하세요. 취소하려면 [ESC]를 누르세요.")
        print(f"저장 경로: {args.output}")
        print("=" * 60)

        window_name = "capture_background - SPACE: capture / ESC: cancel"

        while True:
            ok, frame = cap.read()
            if not ok:
                print("[오류] 프레임을 읽을 수 없습니다.", file=sys.stderr)
                sys.exit(1)

            preview = frame.copy()
            cv2.putText(
                preview,
                "SPACE: capture background  /  ESC: cancel",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                print("취소되었습니다.")
                sys.exit(0)
            if key == 32:  # SPACE
                break

        background = capture_averaged_frame(cap, args.average_frames)

        saved = cv2.imwrite(args.output, background)
        if not saved:
            print(f"[오류] {args.output} 저장에 실패했습니다.", file=sys.stderr)
            sys.exit(1)

        print(f"[완료] 배경 프레임을 {args.output}에 저장했습니다.")
        print("주의: 이 시점 이후 촬영이 끝날 때까지 카메라를 절대 움직이지 마세요.")

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

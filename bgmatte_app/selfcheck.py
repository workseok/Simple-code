"""GUI·카메라 없이 설정/모델/추론 경로만 점검합니다.

    python -m bgmatte_app.selfcheck

앱이 실행되지 않거나 느릴 때 어느 단계가 문제인지 빠르게 확인하는 용도입니다.
(모델 로드 → 합성 배경 → 빈 배경 → 1프레임 추론 → 예상 FPS)
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from . import camera_auth
from .backgrounds import scan_backgrounds
from .config import config_path, load_config
from .messages import NoticeError


def _ok(text: str) -> None:
    print(f"  ✓ {text}")


def _bad(text: str, hint: str = "") -> None:
    print(f"  ✕ {text}")
    if hint:
        print(f"      → {hint}")


def main() -> int:
    cfg, warning = load_config()
    failed = False
    print("BG Matte 셀프체크")
    print(f"  설정 파일: {config_path()}" + (" (없음 → 기본값 사용)" if not config_path().exists() else ""))
    if warning:
        _bad("설정 파일을 읽지 못해 기본값을 씁니다", warning)

    print("\n[1] 카메라 권한")
    status = camera_auth.authorization_status()
    if status == "authorized":
        _ok("허용됨")
    elif status == "unknown":
        print("  - 확인할 수 없음 (macOS가 아니거나 pyobjc 미설치). 앱 실행 시 영상이 안 들어오면 안내합니다.")
    else:
        _bad(f"상태: {status}", "시스템 설정 → 개인정보 보호 및 보안 → 카메라에서 허용해 주세요.")

    print("\n[2] 합성 배경 / 빈 배경")
    backgrounds = scan_backgrounds(cfg.resolve(cfg.backgrounds_dir), cfg.resolve(cfg.legacy_background))
    if backgrounds:
        _ok(f"합성 배경 {len(backgrounds)}개: " + ", ".join(f"{b.number}={b.name}" for b in backgrounds[:9]))
    else:
        failed = True
        _bad(f"합성 배경이 없습니다 ({cfg.resolve(cfg.backgrounds_dir)})", "PNG/JPG 파일을 넣어 주세요.")
    bgr_path = cfg.resolve(cfg.bgr)
    if bgr_path.is_file():
        _ok(f"빈 배경 {bgr_path.name}")
    else:
        print(f"  - 빈 배경({bgr_path.name})이 아직 없습니다. 앱에서 스페이스바로 촬영하면 만들어집니다.")

    print("\n[3] 모델")
    try:
        import numpy as np

        from .matte_core import Matter
    except ImportError as exc:
        _bad(f"torch/opencv를 불러오지 못했습니다: {exc}", "conda 환경(bgmatte)을 활성화했는지 확인하세요.")
        return 1

    matter = Matter(cfg)
    try:
        t0 = time.perf_counter()
        label = matter.load()
        _ok(f"모델 로드 완료 ({time.perf_counter() - t0:.1f}초), 장치: {label}")
    except NoticeError as err:
        n = err.notice
        _bad(f"{n.title} — {n.detail}", n.hint)
        return 1

    print("\n[4] 1프레임 추론")
    if not backgrounds:
        _bad("합성 배경이 없어 추론을 건너뜁니다")
        return 1
    try:
        import cv2

        with tempfile.TemporaryDirectory() as tmpdir:
            if bgr_path.is_file():
                bgr_file = bgr_path
                bgr = cv2.imread(str(bgr_path), cv2.IMREAD_COLOR)
            else:  # 빈 배경이 아직 없으면 임의의 이미지로 속도만 측정합니다
                bgr = np.random.default_rng(0).integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
                bgr_file = Path(tmpdir) / "bgr.png"
                cv2.imwrite(str(bgr_file), bgr)
            matter.set_background(backgrounds[0].path)
            matter.set_bgr(bgr_file)

        frame = bgr.copy()
        half = frame.shape[1] // 2
        frame[:, :half] = (frame[:, :half] * 0.6).astype(np.uint8)  # 배경과 약간 다른 프레임
        times = []
        for _ in range(4):
            t0 = time.perf_counter()
            out = matter.process(frame)
            times.append(time.perf_counter() - t0)
        _ok(f"출력 {out.shape[1]}×{out.shape[0]}, 첫 프레임 {times[0] * 1000:.0f}ms")
        steady = sum(times[1:]) / len(times[1:])
        _ok(f"이후 평균 {steady * 1000:.0f}ms/프레임 ≈ {1 / steady:.1f} FPS (추론만, 화면 표시 제외)")
        if steady > 0.2:
            print("      참고: 5 FPS 미만이면 카메라 해상도를 1280×720 이하로 낮추거나,")
            print("      설정에서 백본을 mobilenetv2로 바꿔 보세요(해당 가중치 필요).")
    except Exception as exc:
        failed = True
        _bad(f"추론 중 오류: {exc}")

    print("\n" + ("문제가 있습니다. 위 ✕ 항목을 먼저 해결해 주세요." if failed else "모든 점검을 통과했습니다."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

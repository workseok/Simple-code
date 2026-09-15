# Simple-code — 오프라인 실시간 배경 매팅 파이프라인

그린스크린 없이, **완전 고정 카메라** 기준으로 실시간 배경 매팅을 수행하는
로컬 파이프라인입니다. [BackgroundMattingV2](https://github.com/PeterL1n/BackgroundMattingV2)
모델을 사용하며, 클라우드 API나 인터넷 연결 없이 완전 오프라인으로 동작합니다.

> ⚠️ 본 저장소는 `workseek/Part1_AI-test` (ComfyUI 클라우드 파이프라인)와
> 완전히 독립적인 코드베이스입니다. 공유 함수/모듈을 두지 않습니다.

## 전제 조건

- 카메라는 촬영 시작(배경 캡처 시점)부터 종료까지 **완전 고정**
  (팬/틸트/줌/흔들림 없음). 카메라가 조금이라도 움직이면 배경 프레임과
  실시간 프레임이 어긋나 매팅 품질이 크게 떨어집니다.
- 입력: HDMI 캡처카드 (OpenCV `VideoCapture`로 장치 인덱스 접근)
- 출력: 1차는 로컬 미리보기(`cv2.imshow`), 추후 NDI 출력으로 교체 예정

## 스크립트 구성

| 파일 | 역할 |
| --- | --- |
| `capture_background.py` | 리허설 단계에서 1회 실행. 피사체 없는 클린 배경 프레임을 캡처해 `bgr.png`로 저장 |
| `realtime_matte.py` | `bgr.png` 기준으로 실시간 입력과 비교해 알파 매트 추출 후 AI 배경(`ai_background.png`)과 합성 |
| `utils.py` | 두 스크립트가 공유하는 텐서 변환/합성 헬퍼 |

## 환경 설정

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 모델 가중치

BackgroundMattingV2 공식 레포에서 PyTorch 가중치(`.pth`)를 받아
저장소 루트의 `models/` 디렉터리에 배치하세요 (예: `models/pytorch_resnet50.pth`).

- 공식 레포: https://github.com/PeterL1n/BackgroundMattingV2
- 가중치 다운로드: 레포 README의 "Model / Checkpoints" 섹션 안내를 따르세요.

`*.pth` 파일은 `.gitignore`에 등록되어 있으며 커밋되지 않습니다.

## 사용 순서

1. **배경 캡처** (리허설, 피사체 없이 1회):
   ```bash
   python capture_background.py --camera-index 0 --output bgr.png
   ```
   `SPACE`로 캡처, `ESC`로 취소. 이 시점 이후 촬영이 끝날 때까지
   카메라를 움직이지 마세요.

2. **실시간 매팅** (추후 추가 예정):
   ```bash
   python realtime_matte.py --bgr bgr.png --ai-background ai_background.png
   ```

## 검증 순서

1. 노트북 내장캠으로 먼저 로직 검증 (캡처카드 연결 전 단계)
2. 캡처카드 연결 후 동일 로직으로 재검증
3. 실제 AI 배경 플레이트로 교체해 최종 합성 확인

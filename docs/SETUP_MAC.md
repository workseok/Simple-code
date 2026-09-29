# macOS 설치 및 실행 가이드

이 문서는 **macOS**에서 이 저장소(오프라인 실시간 배경 매팅 파이프라인)를
처음부터 끝까지 — 필수 프로그램 설치부터 실행까지 — 이 문서 하나만 보고
따라 할 수 있도록 정리한 가이드입니다. Windows 관련 내용은 다루지 않습니다.

## 0. 준비물

- macOS (Apple Silicon 권장 — M1/M2/M3 등. Intel Mac에서도 동작하지만
  GPU 가속(MPS)은 Apple Silicon에서만 사용 가능합니다.)
- HDMI 캡처카드 (USB로 Mac에 연결하는 타입)
- 터미널(Terminal.app) 사용 권한

---

## 1. Git 설치

macOS는 Xcode Command Line Tools를 설치하면 Git이 함께 설치됩니다.

1. **터미널**(Terminal.app, Spotlight에서 "터미널" 검색)을 엽니다.
2. 아래 명령을 입력합니다.
   ```bash
   xcode-select --install
   ```
3. 설치 안내 팝업이 뜨면 **설치**를 클릭하고 완료될 때까지 기다립니다.
   (이미 설치되어 있다면 "이미 설치되어 있습니다" 오류가 뜨는데, 이 경우
   그냥 다음 단계로 넘어가면 됩니다.)
4. 설치 확인:
   ```bash
   git --version
   ```
   버전 번호가 출력되면 정상입니다.

## 2. Miniforge(Python) 설치

이 프로젝트는 Python 패키지 관리와 가상환경 생성에 **Miniforge**(경량
conda 배포판)를 사용합니다. Apple Silicon에서는 Miniforge가 arm64 네이티브
패키지를 안정적으로 제공해 특히 권장됩니다.

1. Mac 칩 종류 확인 (Apple 메뉴 → 이 Mac에 관하여):
   - "Apple M1/M2/M3…" 라고 나오면 **Apple Silicon**
   - "Intel"이라고 나오면 **Intel Mac**
2. 터미널에서 칩 종류에 맞는 설치 스크립트를 다운로드해 실행합니다.

   **Apple Silicon (M1/M2/M3…)**
   ```bash
   curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
   bash Miniforge3-MacOSX-arm64.sh
   ```

   **Intel Mac**
   ```bash
   curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
   bash Miniforge3-MacOSX-x86_64.sh
   ```

3. 설치 스크립트가 라이선스 동의를 물으면 `Enter`를 눌러 읽어보고
   `yes`를 입력합니다. 설치 경로는 기본값(`~/miniforge3`)을 그대로
   사용하면 됩니다. 마지막에 "initialize Miniforge3" 여부를 물으면
   `yes`를 입력합니다 (셸 시작 시 자동으로 PATH에 잡히도록 해 줍니다).
4. 설치가 끝나면 **터미널을 완전히 종료했다가 다시 엽니다**.
5. 설치 확인:
   ```bash
   conda --version
   python --version
   ```

## 3. 저장소 clone

```bash
cd ~
git clone https://github.com/workseok/Simple-code.git
cd Simple-code
```

## 4. 가상환경 생성

```bash
conda create -n bgmatte python=3.10 -y
conda activate bgmatte
```

터미널을 새로 열 때마다(또는 프로젝트 작업을 재개할 때마다) 아래 명령으로
가상환경을 다시 활성화해야 합니다.

```bash
conda activate bgmatte
```

## 5. 의존성 설치

```bash
pip install -r requirements.txt
```

### GPU(MPS) 가속에 대해

Apple Silicon Mac에서는 PyTorch가 Apple의 **MPS**(Metal Performance
Shaders) 백엔드를 통해 GPU 가속을 지원합니다. `requirements.txt`로 설치되는
표준 PyTorch 패키지에 이미 MPS 지원이 포함되어 있으므로 별도 설치 단계는
필요 없습니다.

- `realtime_matte.py`의 `--device` 기본값은 `auto`이며, 이 경우 **MPS를
  먼저 시도**하고 사용할 수 없거나 오류가 나면 자동으로 CPU로 전환됩니다.
- MPS가 실제로 인식되는지 미리 확인하려면:
  ```bash
  python -c "import torch; print(torch.backends.mps.is_available())"
  ```
  `True`가 출력되면 정상입니다. Intel Mac이거나 macOS 버전이 오래된 경우
  `False`가 나올 수 있으며, 이 경우 자동으로 CPU로 동작합니다.
- 특정 장치를 강제하려면 `--device mps` 또는 `--device cpu`를 붙이세요.

## 6. BackgroundMattingV2 공식 레포 clone

`realtime_matte.py`는 모델 아키텍처 코드를 별도로 clone된 공식 레포에서
불러옵니다. 저장소 바로 바깥 위치에 clone하는 것을 권장합니다.

```bash
cd ~
git clone https://github.com/PeterL1n/BackgroundMattingV2.git
cd Simple-code
```

## 7. 모델 가중치 다운로드

1. https://github.com/PeterL1n/BackgroundMattingV2 접속 후 README의
   "Model / Checkpoints" 섹션 안내를 따라 `.pth` 가중치 파일을 다운로드합니다.
2. 저장소 루트에 `models` 폴더를 만들고 그 안에 저장합니다.
   ```bash
   mkdir -p models
   ```
   다운로드한 파일을 `models/pytorch_resnet50.pth`와 같이 옮겨두세요
   (Finder에서 직접 옮겨도 됩니다).
   - `.pth` 파일은 `.gitignore`에 등록되어 있어 커밋되지 않습니다.

## 8. HDMI 캡처카드 인식 및 카메라 권한 확인

1. HDMI 캡처카드를 USB로 Mac에 연결하고, HDMI 입력(카메라/소스 장비)도
   연결합니다.
2. **카메라 접근 권한**: macOS는 터미널 앱이 카메라를 사용하려면 명시적
   권한이 필요합니다. `capture_background.py`를 처음 실행하면 권한 요청
   팝업이 뜰 수 있습니다 — **허용**을 누르세요. 팝업이 뜨지 않고 화면이
   검게 나온다면 **시스템 설정 → 개인정보 보호 및 보안 → 카메라**에서
   사용 중인 터미널 앱(터미널.app 또는 iTerm 등)에 체크가 되어 있는지
   확인하세요.
3. OpenCV에서의 장치 인덱스(`--camera-index`)는 보통 0부터 시작해 연결
   순서대로 번호가 매겨지며, 내장 FaceTime 카메라가 있다면 그것이 0번을
   차지하는 경우가 많습니다. 아래 스크립트로 인덱스별 영상이 뜨는지
   확인해 보세요.
   ```bash
   python -c "
   import cv2
   for i in range(5):
       cap = cv2.VideoCapture(i)
       ok = cap.isOpened()
       print(f'index {i}: opened={ok}')
       cap.release()
   "
   ```
   `capture_background.py` 실행 시 미리보기 창이 뜨므로, 여러 인덱스를
   바꿔가며 실제로 캡처카드 화면이 보이는 번호를 찾으면 됩니다.

## 9. 실행

### 9-1. 배경 캡처 (리허설, 최초 1회)

피사체(사람/물체)가 화면에 전혀 없는 상태에서 실행합니다.

```bash
python capture_background.py --camera-index 0 --output bgr.png
```

- 미리보기 창에서 `SPACE`를 누르면 캡처, `ESC`를 누르면 취소됩니다.
- **이 시점 이후 촬영이 끝날 때까지 카메라를 절대 움직이지 마세요.**

### 9-2. AI 배경 플레이트 준비

합성에 사용할 AI 생성 배경 이미지를 `ai_background.png`라는 이름으로
저장소 루트에 준비해 둡니다. (별도 제작 과정은 이 문서의 범위 밖입니다.)

### 9-3. 실시간 매팅 실행

```bash
python realtime_matte.py \
    --repo-path ../BackgroundMattingV2 \
    --model-checkpoint models/pytorch_resnet50.pth \
    --model-backbone resnet50 \
    --bgr bgr.png \
    --ai-background ai_background.png \
    --camera-index 0
```

- 미리보기 창에서 `ESC`를 누르면 종료됩니다.
- `--show-alpha` 옵션을 추가하면 합성 결과 옆에 알파 매트도 함께
  표시됩니다 (디버그용).
- `--device` 옵션은 기본값이 `auto`이며, Apple Silicon Mac이라면 MPS를
  자동으로 시도하고 실패 시 CPU로 전환됩니다.

---

## 문제 해결

- **`conda: command not found` / `python: command not found`**
  터미널을 완전히 재시작했는지 확인하세요. 그래도 안 되면 Miniforge 설치
  스크립트를 다시 실행하면서 "initialize Miniforge3" 질문에 `yes`로
  답했는지 확인하세요.
- **카메라 미리보기 창이 뜨지 않거나 검은 화면**
  시스템 설정 → 개인정보 보호 및 보안 → 카메라 권한을 먼저 확인하고,
  `--camera-index` 값을 0, 1, 2 순서로 바꿔가며 시도하세요.
- **`torch.backends.mps.is_available()`가 `False`**
  Intel Mac이거나 macOS 버전이 오래된 경우 정상적인 결과이며, 이 경우
  `realtime_matte.py`는 자동으로 CPU로 동작합니다.
- **`pip install` 중 오류**
  `conda activate bgmatte`로 가상환경이 활성화된 상태인지 프롬프트 앞에
  `(bgmatte)`가 붙어 있는지 확인하세요.

# Windows 설치 및 실행 가이드

이 문서는 **Windows**에서 이 저장소(오프라인 실시간 배경 매팅 파이프라인)를
처음부터 끝까지 — 필수 프로그램 설치부터 실행까지 — 이 문서 하나만 보고
따라 할 수 있도록 정리한 가이드입니다. macOS 관련 내용은 다루지 않습니다.

## 0. 준비물

- Windows 10/11 (64비트)
- HDMI 캡처카드 (USB로 PC에 연결하는 타입)
- 관리자 권한으로 프로그램을 설치할 수 있는 계정

---

## 1. Git 설치

1. https://git-scm.com/download/win 접속 후 **64-bit Git for Windows Setup**을
   다운로드합니다.
2. 설치 프로그램을 실행합니다. 설치 옵션은 대부분 기본값을 그대로 두면 됩니다.
   - "Adjusting your PATH environment" 단계에서는 기본 선택된
     **"Git from the command line and also from 3rd-party software"**를 유지하세요.
3. 설치가 끝나면 시작 메뉴에서 **Git Bash**를 실행합니다. 이후 이 문서의
   모든 명령어는 **Git Bash**에서 입력합니다 (PowerShell/CMD가 아님).
4. 설치 확인:
   ```bash
   git --version
   ```
   버전 번호가 출력되면 정상입니다.

## 2. Miniforge(Python) 설치

이 프로젝트는 Python 패키지 관리와 가상환경 생성에 **Miniforge**(경량
conda 배포판)를 사용합니다.

1. https://github.com/conda-forge/miniforge#miniforge3 접속
2. **Windows** 섹션에서 `Miniforge3-Windows-x86_64.exe` 설치 파일을
   다운로드합니다.
3. 설치 프로그램을 실행합니다.
   - "Advanced Installation Options"에서 **"Add Miniforge3 to my PATH environment
     variable"**에 체크합니다. (기본값은 체크 해제이므로 직접 선택해야 합니다.)
   - 나머지 옵션은 기본값 그대로 진행합니다.
4. 설치가 끝나면 **Git Bash를 완전히 종료했다가 다시 실행**합니다 (PATH가
   갱신되려면 재시작이 필요합니다).
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

### GPU(CUDA) 가속을 사용하려면 (선택)

NVIDIA GPU가 있고 최신 드라이버가 설치되어 있다면, PyTorch를 CUDA 지원
빌드로 다시 설치하면 추론 속도가 크게 빨라집니다. (없어도 CPU로 동작은
합니다.)

1. GPU와 드라이버가 인식되는지 확인:
   ```bash
   nvidia-smi
   ```
   표 형태로 GPU 정보가 나오면 정상입니다. 이 명령이 실패하면 NVIDIA
   드라이버를 먼저 설치하세요 (https://www.nvidia.com/Download/index.aspx).
2. CUDA 지원 PyTorch 재설치 (아래는 CUDA 12.1 예시이며, 정확한 버전은
   https://pytorch.org/get-started/locally/ 에서 본인 환경에 맞게 확인하세요):
   ```bash
   pip uninstall torch torchvision -y
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```
3. 확인:
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```
   `True`가 출력되면 GPU를 사용할 준비가 된 것입니다.
4. **주의:** `realtime_matte.py`의 `--device` 기본값(`auto`)은 Windows에서
   CPU로 동작합니다. GPU를 쓰려면 실행 시 반드시 `--device cuda`를
   명시하세요 (9-3 단계 참고).

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
   다운로드한 파일을 `models\pytorch_resnet50.pth`와 같이 배치하세요
   (탐색기에서 직접 옮겨도 됩니다).
   - `.pth` 파일은 `.gitignore`에 등록되어 있어 커밋되지 않습니다.

## 8. HDMI 캡처카드 인식 확인

1. HDMI 캡처카드를 USB로 PC에 연결하고, HDMI 입력(카메라/소스 장비)도
   연결합니다.
2. Windows에서는 캡처카드가 보통 "카메라" 앱이나 장치 관리자에서
   비디오 입력 장치로 인식됩니다. 장치 관리자(`devmgmt.msc`)의
   **카메라** 또는 **이미징 장치** 항목에서 이름이 보이는지 확인하세요.
3. OpenCV에서의 장치 인덱스(`--camera-index`)는 보통 0부터 시작해 연결
   순서대로 번호가 매겨지며, 노트북 내장캠이 있다면 그것이 0번을 차지하는
   경우가 많습니다. 아래 스크립트로 인덱스별 영상이 뜨는지 확인해 보세요.
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
- `--device` 옵션을 생략하면(기본값 `auto`) CPU로 동작합니다.
  5단계에서 CUDA 지원 PyTorch를 설치했다면 명령 끝에 `--device cuda`를
  추가해 GPU로 실행하세요.

---

## 문제 해결

- **`conda: command not found` / `python: command not found`**
  Git Bash를 완전히 재시작했는지 확인하세요. 그래도 안 되면 Miniforge
  설치 시 PATH 추가 옵션을 체크했는지 다시 확인하고 재설치하세요.
- **카메라 미리보기 창이 검은 화면**
  `--camera-index` 값을 0, 1, 2 순서로 바꿔가며 시도하세요. 캡처카드
  드라이버(제조사 제공)가 별도로 필요한 경우가 있습니다.
- **`pip install` 중 오류**
  `conda activate bgmatte`로 가상환경이 활성화된 상태인지 프롬프트 앞에
  `(bgmatte)`가 붙어 있는지 확인하세요.

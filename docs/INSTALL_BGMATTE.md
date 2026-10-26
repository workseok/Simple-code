# BG Matte 앱 설치 가이드 (Windows / Mac 통합)

이 문서는 설치 **입구**입니다. 순서대로 따라 하면 되고, 자세한 사용법·문제 해결은 OS별 문서로 연결됩니다.

| 내 PC | 설치 방식 | 상세 문서 |
| --- | --- | --- |
| Windows 10/11 (64비트) | `packaging\install_windows.bat` 더블클릭 (자동 설치) | [APP_WINDOWS.md](APP_WINDOWS.md) |
| macOS | 터미널 명령 몇 줄 + `.app` 빌드 | [SETUP_MAC.md](SETUP_MAC.md), [APP_MAC.md](APP_MAC.md) |

> **상태 안내**: Windows 설치기는 맥 환경에서 만들었고 테스트(자동 테스트 115개)는 통과했지만,
> **실제 Windows PC에서의 설치는 아직 검증 전**입니다. 막히면 화면 메시지를 그대로 기록해 알려 주세요.

---

## 1. 파일 받기

저장소 주소: `https://github.com/workseok/simple-code`
현재 작업 브랜치(branch, 저장소의 작업 갈래): **`claude/determined-mccarthy-5aul8m`** (아직 `main`에 합쳐지지 않았습니다.)

**방법 A — ZIP (코드를 모르는 경우 권장)**
1. 위 저장소 페이지에서 왼쪽 위 브랜치 선택 칸을 눌러 `claude/determined-mccarthy-5aul8m` 선택
2. 초록색 **Code → Download ZIP**
3. 받은 ZIP을 `C:\bgmatte-app`(Windows) 또는 `~/bgmatte-app`(Mac)처럼 **짧고 단순한 경로**에 풀기 (한글·공백이 적을수록 안전)

**방법 B — git**
```bash
git clone -b claude/determined-mccarthy-5aul8m https://github.com/workseok/simple-code.git bgmatte-app
```

## 2. Windows 설치

1. 풀린 폴더의 `packaging` → **`install_windows.bat`** 더블클릭
   ("Windows가 PC를 보호했습니다"가 뜨면 **추가 정보 → 실행**)
2. 검은 창에서 10~30분 대기. 자동으로 하는 일: 파이썬 환경(`bgmatte`, Python 3.11) 생성 → PyTorch(NVIDIA GPU면 CUDA용 먼저 시도) → 라이브러리 → 엔진 코드 2종 + 가중치 5종 전부 다운로드 (약 540MB) → 바탕화면 바로가기 → 셀프체크
3. "설치가 끝났습니다"가 나오면 완료. 바탕화면 **BG Matte** 실행

중간에 끊기면 `install_windows.bat`을 다시 실행하세요. 받은 것은 건너뛰고 이어서 진행합니다.

### 2-1. "Miniforge를 찾지 못했습니다" 가 뜰 때

Miniforge는 파이썬 환경을 만들어 주는 도구(conda 배포판)입니다. 설치기는 이게 필요합니다.

- 창에서 **`Y`** 입력 → winget(윈도우 기본 설치 도구)으로 자동 설치. 끝나면 **창을 닫고 `install_windows.bat`을 다시 실행**
- `Y`가 실패하거나 winget이 없으면 수동 설치:
  1. https://github.com/conda-forge/miniforge/releases/latest 에서 **Miniforge3-Windows-x86_64.exe** 다운로드
  2. 설치 위치를 **`C:\miniforge3`** 로 지정 (사용자 이름이 한글이면 특히 중요. 설치기가 이 경로를 먼저 찾습니다)
  3. `install_windows.bat` 재실행

### 2-1-1. 설치가 끝나면 인터넷이 필요 없습니다

설치기는 마지막에 엔진 코드 2종과 가중치 5종이 모두 이 PC에 있는지 확인하고,
`엔진 코드 2종과 가중치 5종이 모두 이 PC에 있습니다. 이제 인터넷 연결 없이 사용할 수 있습니다.` 라고 알려 줍니다.
이 문구가 보이면 이후에는 오프라인 PC에서도 동작합니다 (앱은 실행 중 어디에도 접속하지 않습니다).
이 문구 대신 `빠진 파일이 있습니다`가 나오면 `install_windows.bat`을 다시 실행하세요.

### 2-2. 설치 옵션 (명령 프롬프트에서 `install_windows.bat` 뒤에 붙임)

| 옵션 | 효과 |
| --- | --- |
| `--minimal` | 꼭 필요한 가중치 2종만 받기 (기본은 가중치 5종 모두, 약 540MB) |
| `--all-weights` | 예전 옵션 (이제 기본 동작) |
| `--cpu` | GPU가 있어도 CPU용으로 설치 |
| `--skip-torch` | PyTorch 설치 건너뛰기 |

## 3. Mac 설치 (Intel / Apple Silicon)

1. Miniforge 설치: [SETUP_MAC.md](SETUP_MAC.md) 2장 (Intel은 x86_64, Apple Silicon은 arm64용)
2. 환경 만들기 (**Python 3.11** 사용. Intel Mac은 PyTorch 2.2.2가 마지막 지원 버전이라 3.12 이하·`numpy<2` 필수)
   ```bash
   conda create -n bgmatte python=3.11 -y
   conda activate bgmatte
   pip install -r requirements.txt -r requirements-app.txt
   ```
3. 엔진 코드·가중치: `bash packaging/install_engines.sh`
4. 사전 점검: `python -m bgmatte_app.selfcheck`
5. 앱 만들기: `bash packaging/build_app.sh --install` → `~/Applications/BG Matte.app`

처음 실행 시 카메라 권한 팝업에서 **허용**. 자세한 내용은 [APP_MAC.md](APP_MAC.md).

## 4. 설치 후 필수 설정

1. **합성 배경**: `backgrounds` 폴더에 `01_이름.png`처럼 번호로 시작하는 파일
2. **카메라**: 설정에서 카메라 번호·해상도 선택. 노트북 내장 카메라가 0번이면 캡처카드는 1번 이상
3. **엔진 선택** (비교 상세는 [ENGINES.md](ENGINES.md))

| 엔진 | 빈 배경 촬영 | 대상 | 라이선스 |
| --- | --- | --- | --- |
| RobustVideoMatting (RVM) | 불필요 | 사람만 | GPL-3.0 (배포 전 검토 필요) |
| BackgroundMattingV2 | 필요 (스페이스바, 이후 카메라 고정) | 의자·소품 포함 | MIT |

현장 모니터링은 지금까지의 테스트 기준으로 RVM이 가장 적합하다는 판단이지만, 윈도우·GPU에서의 FPS는 **실측 전**입니다.

- **Nikon ZR 등 HDMI 캡처카드**: 설정의 영상 형식을 `MJPG`로 바꾸면 1080p가 안 나오거나 프레임이 낮을 때 개선되는 경우가 있습니다 (품질은 약간 저하 가능). 다른 프로그램(OBS 등)이 카메라를 쓰고 있으면 열리지 않습니다.

## 5. 설치가 되었는지 확인

- 앱 상태 패널의 **처리 장치**가 NVIDIA 환경이면 `CUDA`, 아니면 `CPU`(Mac은 `MPS`)로 표시되는지 확인
- 로그: Windows `%LOCALAPPDATA%\BGMatte\app.log`, 설정: `%APPDATA%\BGMatte\config.json`
- 문제 해결 표: [APP_WINDOWS.md](APP_WINDOWS.md) 5장

## 6. 설치 파일 목록 (저장소 내 위치)

| 파일 | 역할 |
| --- | --- |
| `packaging/install_windows.bat` | 윈도우 원클릭 설치기 (conda 찾기/설치 → 환경 생성 → setup 실행) |
| `packaging/setup_windows.py` | torch·라이브러리·엔진·가중치·바로가기·셀프체크 |
| `packaging/BGMatte.bat` | 윈도우 실행 파일 |
| `packaging/AppIcon.ico` / `.icns` | 아이콘 |
| `packaging/build_app.sh`, `install_engines.sh` | Mac 앱 빌드·엔진 설치 |
| `requirements.txt`, `requirements-app.txt` | 파이썬 라이브러리 목록 |

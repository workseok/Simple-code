# BGMatte_Setup.exe 만들기 (윈도우에서)

`packaging/BGMatte_Setup.iss` 는 **설치 마법사 형태의 `.exe`** 를 만드는 스크립트입니다.
안에서는 검증된 `install_windows.bat` 을 그대로 실행하므로 설치 로직은 같습니다.

> 이 스크립트는 윈도우에서 아직 컴파일해 보지 않았습니다. 막히면 오류 문구를 그대로 알려 주세요.

## 1. 한 번만 준비

1. Inno Setup 6 설치 (무료): https://jrsoftware.org/isdl.php → `innosetup-6.x.x.exe`
2. 최신 코드 받기 (`C:\bgmatte-app` 에 이미 있다면 그 폴더 사용)

## 2. 빌드

1. `C:\bgmatte-app\packaging\BGMatte_Setup.iss` 를 더블클릭 (Inno Setup으로 열림)
2. 메뉴 **Build → Compile** (또는 `Ctrl+F9`)
3. 완료되면 `C:\bgmatte-app\packaging\Output\BGMatte_Setup.exe` 가 생깁니다 (수 MB).

## 3. 팀원이 쓰는 법

1. `BGMatte_Setup.exe` 더블클릭 → 설치 → 검은 창에서 10~30분 대기 (인터넷 필요)
2. 완료되면 바탕화면 **BG Matte** 실행

앱은 `C:\BGMatte\app` 에, 엔진 코드는 `C:\BGMatte\` 옆 폴더에 설치됩니다.
`models`, `backgrounds`, `bgr.png` 는 설치 중에 만들어지거나 팀원이 각자 설정합니다.

## 알아둘 점

- 서명하지 않은 `.exe` 라서 처음 실행하면 "Windows가 PC를 보호했습니다"(SmartScreen)가 뜹니다. **추가 정보 → 실행**.
  없애려면 코드 서명 인증서가 필요합니다 (팀 내부 배포에는 보통 불필요).
- 이 `.exe` 는 파이썬·PyTorch를 포함하지 않습니다. 설치 중 각 PC의 GPU에 맞춰 받기 때문에 NVIDIA PC는 CUDA용, 아닌 PC는 CPU용으로 자동 설치됩니다.
- 제거: 윈도우 설정 → 앱 → BG Matte 제거. 앱 폴더, 엔진 코드 폴더, 바로가기가 삭제됩니다. conda 환경(`bgmatte`)은 남으므로 필요하면 `conda env remove -n bgmatte` 로 지웁니다.

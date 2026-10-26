# 배포 가이드 (새 버전을 팀에 배포하기)

앱을 고칠 때마다 아래 순서로 새 설치 파일 `BGMatte_Setup_vX.Y.Z.exe` 를 만들어 팀에 나눕니다.
설치 파일은 **윈도우 서버(GitHub Actions)가 자동으로 만들어 줍니다.** 윈도우 PC에서 직접 빌드할 필요가 없습니다.

## 1. 새 버전 내기 (개발하는 쪽)

1. 코드 수정 → 테스트 통과 확인 (`python -m pytest`)
2. 버전 올리기 (`bgmatte_app/__init__.py` 의 `__version__` 한 곳만 바뀝니다)
   ```
   python packaging/bump_version.py patch     # 1.0.0 → 1.0.1  (버그 수정)
   python packaging/bump_version.py minor     # 1.0.0 → 1.1.0  (기능 추가)
   ```
3. 커밋하고 같은 번호로 태그를 붙여 올리기 (스크립트가 마지막 줄에 명령을 알려 줍니다)
   ```
   git commit -am "release: v1.0.1"
   git tag v1.0.1
   git push origin HEAD v1.0.1
   ```
4. GitHub 저장소의 **Actions** 탭에서 `release` 가 초록색으로 끝나면, **Releases** 에
   `BGMatte_Setup_v1.0.1.exe` 가 올라옵니다. 이 파일을 팀에 공유합니다.

태그 번호와 `__version__` 이 다르면 빌드가 일부러 실패합니다 (버전이 어긋난 설치 파일이 나가는 것을 막기 위함).
설치 파일만 시험 삼아 만들고 싶으면 Actions 탭 → `release` → **Run workflow** (릴리스는 만들지 않고, 결과 파일만 내려받을 수 있습니다).

### 윈도우 PC에서 직접 빌드하고 싶을 때

Inno Setup 6 을 설치한 PC(`https://jrsoftware.org/isdl.php`)에서 `packaging\build_release.bat` 을 더블클릭하면
`packaging\Output\BGMatte_Setup_vX.Y.Z.exe` 가 만들어집니다.

## 2. 팀원이 업데이트하는 법

- 새 `BGMatte_Setup_vX.Y.Z.exe` 를 **그냥 실행**합니다. 같은 위치(`C:\BGMatte\app`)에 새 파일을 덮어쓰고,
  이미 받은 가중치·엔진 코드는 건너뛰므로 처음 설치보다 훨씬 빠릅니다.
- 설정(`%APPDATA%\BGMatte\config.json`)과 `models`, `backgrounds`, 빈 배경 이미지는 그대로 남습니다.
- 앱을 켜 둔 채로 설치하지 말고, 먼저 종료해 주세요.
- 실행 중인 버전은 앱 창 제목(예: `BG Matte 1.0.1`)에서 확인합니다.

## 3. 알아둘 점

- 설치 파일은 서명되어 있지 않아서 처음 실행하면 "Windows가 PC를 보호했습니다"가 뜹니다. **추가 정보 → 실행**.
- 설치 중에는 인터넷이 필요합니다 (파이썬 환경, PyTorch, 가중치). 설치가 끝나면 인터넷 없이 쓸 수 있습니다.
- GitHub 저장소가 비공개이면 팀원이 Releases 에서 받으려면 저장소에 초대되어 있어야 합니다.
  초대하지 않을 거라면 Releases 의 `.exe` 를 내려받아 사내 드라이브로 공유하세요.
- 앱을 실행하면 검은 콘솔 창이 뜨지 않습니다. 문제가 생기면 `%LOCALAPPDATA%\BGMatte\app.log` 를 확인하세요.
  (예전 방식으로 검은 창을 보고 싶을 때는 `packaging\BGMatte.bat` 을 실행합니다.)

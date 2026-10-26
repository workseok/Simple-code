; BG Matte 설치 프로그램 (Inno Setup 6) — 윈도우에서 컴파일해 BGMatte_Setup.exe 를 만듭니다.
; 방법: docs/BUILD_SETUP_EXE.md
;
; 이 설치 프로그램은 앱 파일을 C:\BGMatte\app 에 복사한 뒤 packaging\install_windows.bat 을 실행합니다.
; (파이썬 환경, PyTorch, 엔진 코드, 가중치는 설치 중에 인터넷에서 받습니다.)
; 엔진 코드 폴더(..\BackgroundMattingV2, ..\RobustVideoMatting)가 앱 폴더 '옆'에 만들어져야 하므로
; 설치 위치는 C:\BGMatte\app 으로 고정합니다 (한글·공백이 없는 경로).

#define AppName "BG Matte"
; 버전은 bgmatte_app/__init__.py 의 __version__ 하나만 고치면 됩니다.
; build_release.bat / GitHub Actions 가 /DAppVersion=x.y.z 로 넘겨 줍니다 (직접 컴파일하면 0.0.0 으로 표시).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B6F1D6E0-5A41-4B7B-9C2E-6D1A0B6E7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Greenweb Service
DefaultDirName={sd}\BGMatte\app
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=BGMatte_Setup_v{#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=BG Matte 설치 프로그램
SetupIconFile=AppIcon.ico
UninstallDisplayIcon={app}\packaging\AppIcon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Korean.isl 이 들어 있는 Inno Setup 에서만 한국어 마법사를 씁니다 (없으면 영어로 컴파일되어 빌드가 실패하지 않습니다).
#if FileExists(AddBackslash(CompilerPath) + "Languages\Korean.isl")
[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#endif

[Files]
; 저장소 전체(.iss 가 packaging 안에 있으므로 상위 폴더 기준). 개발용 파일과 용량 큰 생성물은 제외.
Source: "..\*"; DestDir: "{app}"; Excludes: ".git\*,.github\*,.pytest_cache\*,__pycache__\*,*.pyc,dist\*,build\*,models\*,Output\*,tests\*,*.pth,bgr.png"; Flags: recursesubdirs createallsubdirs ignoreversion

[Run]
; 파이썬 환경 + 엔진 + 가중치 설치 (10~30분, 검은 창이 열립니다. 닫지 마세요)
Filename: "{cmd}"; Parameters: "/c ""{app}\packaging\install_windows.bat"""; WorkingDir: "{app}\packaging"; StatusMsg: "BG Matte 환경을 설치하는 중입니다 (10~30분 걸립니다. 검은 창을 닫지 마세요)..."; Flags: waitUntilTerminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{sd}\BGMatte\BackgroundMattingV2"
Type: filesandordirs; Name: "{sd}\BGMatte\RobustVideoMatting"
Type: filesandordirs; Name: "{userdesktop}\BG Matte.lnk"

; BG Matte 설치 프로그램 (Inno Setup 6) — 윈도우에서 컴파일해 BGMatte_Setup.exe 를 만듭니다.
; 방법: docs/BUILD_SETUP_EXE.md
;
; 이 설치 프로그램은 앱 파일을 C:\BGMatte\app 에 복사한 뒤 packaging\install_windows.bat 을 실행합니다.
; (파이썬 환경, PyTorch, 엔진 코드, 가중치는 설치 중에 인터넷에서 받습니다.)
; 엔진 코드 폴더(..\BackgroundMattingV2, ..\RobustVideoMatting)가 앱 폴더 '옆'에 만들어져야 하므로
; 설치 위치는 C:\BGMatte\app 으로 고정합니다 (한글·공백이 없는 경로).

#define AppName "BG Matte"
#define AppVersion "1.0"

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
OutputBaseFilename=BGMatte_Setup
SetupIconFile=AppIcon.ico
UninstallDisplayIcon={app}\packaging\AppIcon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
; 저장소 전체(.iss 가 packaging 안에 있으므로 상위 폴더 기준). 개발용 파일과 용량 큰 생성물은 제외.
Source: "..\*"; DestDir: "{app}"; Excludes: ".git\*,.github\*,__pycache__\*,*.pyc,dist\*,build\*,models\*,Output\*,tests\*,*.pth,bgr.png"; Flags: recursesubdirs createallsubdirs ignoreversion

[Run]
; 파이썬 환경 + 엔진 + 가중치 설치 (10~30분, 검은 창이 열립니다. 닫지 마세요)
Filename: "{cmd}"; Parameters: "/c ""{app}\packaging\install_windows.bat"""; WorkingDir: "{app}\packaging"; StatusMsg: "BG Matte 환경을 설치하는 중입니다 (10~30분 걸립니다. 검은 창을 닫지 마세요)..."; Flags: waitUntilTerminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{sd}\BGMatte\BackgroundMattingV2"
Type: filesandordirs; Name: "{sd}\BGMatte\RobustVideoMatting"
Type: filesandordirs; Name: "{userdesktop}\BG Matte.lnk"

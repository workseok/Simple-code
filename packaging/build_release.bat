@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title BG Matte 배포 파일 만들기
rem 윈도우에서 BGMatte_Setup_vX.Y.Z.exe 를 만듭니다. (Inno Setup 6 필요: https://jrsoftware.org/isdl.php)
rem 버전은 bgmatte_app\__init__.py 의 __version__ 에서 읽습니다.
cd /d "%~dp0.."

set "PY=python"
if exist "%~dp0python_path.txt" set /p PY=<"%~dp0python_path.txt"
set "VER="
for /f "delims=" %%v in ('"%PY%" -c "import bgmatte_app;print(bgmatte_app.__version__)" 2^>nul') do set "VER=%%v"
if "%VER%"=="" (
    echo 버전을 읽지 못했습니다. install_windows.bat 으로 파이썬 환경을 먼저 만들어 주세요.
    pause
    exit /b 1
)

set "ISCC="
for %%p in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
    if exist %%p set "ISCC=%%~p"
)
if "%ISCC%"=="" (
    echo Inno Setup 6 을 찾지 못했습니다. https://jrsoftware.org/isdl.php 에서 설치한 뒤 다시 실행해 주세요.
    pause
    exit /b 1
)

echo.
echo  버전 %VER% 으로 설치 파일을 만듭니다...
echo.
"%ISCC%" "/DAppVersion=%VER%" "packaging\BGMatte_Setup.iss"
if errorlevel 1 (
    echo.
    echo 빌드에 실패했습니다. 위의 오류 메시지를 확인해 주세요.
    pause
    exit /b 1
)

echo.
echo  완료: %CD%\packaging\Output\BGMatte_Setup_v%VER%.exe
echo  이 파일을 팀에 배포하세요.
explorer "%CD%\packaging\Output"
pause

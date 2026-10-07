@echo off
chcp 65001 >nul
rem BG Matte 실행 (install_windows.bat 으로 설치한 뒤 바탕화면 바로가기 또는 이 파일을 더블클릭)
cd /d "%~dp0.."
set PYTHONUTF8=1

set "PY=python"
if exist "%~dp0python_path.txt" set /p PY=<"%~dp0python_path.txt"
if not exist "%PY%" if /i not "%PY%"=="python" (
    echo 설치된 파이썬 환경을 찾지 못했습니다. install_windows.bat 을 먼저 실행해 주세요.
    pause
    exit /b 1
)

"%PY%" -m bgmatte_app
if errorlevel 1 (
    echo.
    echo 앱이 오류로 종료되었습니다. 위 메시지를 확인해 주세요.
    echo 로그: %LOCALAPPDATA%\BGMatte\app.log
    pause
)

@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title BG Matte 설치

rem 프로젝트 폴더(이 파일의 상위 폴더)에서 실행합니다.
cd /d "%~dp0.."

echo.
echo  ==============================================
echo    BG Matte 윈도우 설치
echo    (인터넷 연결 필요, 약 1~3GB 다운로드, 10~30분)
echo  ==============================================
echo.

rem ---- 1) conda(Miniforge) 찾기
set "CONDA="
where conda >nul 2>nul && set "CONDA=conda"
if not defined CONDA call :findconda

if not defined CONDA (
    echo  Miniforge ^(파이썬 설치 도구^) 가 필요한데 찾지 못했습니다.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo.
        echo  아래 주소에서 Miniforge3-Windows-x86_64.exe 를 받아 설치한 뒤,
        echo  이 파일을 다시 실행해 주세요. ^(설치 옵션은 기본값 그대로 두면 됩니다^)
        echo    https://github.com/conda-forge/miniforge/releases/latest
        goto :fail
    )
    set /p ANSWER="  Miniforge를 자동으로 설치할까요? (Y/N): "
    if /i not "!ANSWER!"=="Y" (
        echo  설치를 취소했습니다.
        goto :fail
    )
    winget install -e --id CondaForge.Miniforge3 --accept-package-agreements --accept-source-agreements
    call :findconda
    if not defined CONDA (
        echo  Miniforge 설치 뒤에도 찾지 못했습니다. 컴퓨터를 다시 시작하거나 창을 닫고 이 파일을 다시 실행해 보세요.
        goto :fail
    )
)
echo  ✓ conda 확인: !CONDA!

rem ---- 2) 환경 만들기 (이름: bgmatte)
for /f "delims=" %%i in ('"!CONDA!" info --base') do set "BASE=%%i"
set "PY=!BASE!\envs\bgmatte\python.exe"
if not exist "!PY!" (
    echo.
    echo  파이썬 환경 'bgmatte'를 만드는 중입니다...
    call "!CONDA!" create -n bgmatte python=3.11 -y
    if errorlevel 1 goto :fail
)
if not exist "!PY!" (
    echo  환경을 찾지 못했습니다: !PY!
    goto :fail
)
echo  ✓ 파이썬 환경: !PY!

rem ---- 3) 나머지는 python 설치 도우미가 처리
echo.
"!PY!" packaging\setup_windows.py %*
set RESULT=%ERRORLEVEL%
echo.
if "%RESULT%"=="0" (
    echo  ==============================================
    echo    설치가 끝났습니다. 바탕화면의 'BG Matte'를 실행하세요.
    echo  ==============================================
) else (
    echo  설치 중 문제가 있었습니다. 위 메시지를 확인해 주세요.
)
pause
exit /b %RESULT%

:findconda
for %%d in ("C:\miniforge3" "%USERPROFILE%\miniforge3" "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniforge3" "%ProgramData%\miniforge3" "%ProgramData%\miniconda3") do (
    if not defined CONDA if exist "%%~d\Scripts\conda.exe" set "CONDA=%%~d\Scripts\conda.exe"
)
exit /b 0

:fail
echo.
pause
exit /b 1

@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title BG Matte 오프라인 설치

rem 이 파일은 오프라인 팩의 맨 위 폴더에 있습니다. 인터넷에 접속하지 않습니다.
set "PACK=%~dp0"
set "DEST=C:\BGMatte"
set "PYDIR=%DEST%\python"
set "APP=%DEST%\app"

echo.
echo  ==============================================
echo    BG Matte 오프라인 설치 (인터넷 필요 없음)
echo    설치 위치: %DEST%   (약 10분)
echo  ==============================================
echo.

if not exist "%PACK%offline\wheels" (
    echo  offline 폴더를 찾지 못했습니다. zip 을 완전히 풀었는지 확인해 주세요.
    echo  ^(압축 파일 안에서 바로 실행하면 안 됩니다. 먼저 '모두 압축 풀기'를 하세요.^)
    goto :fail
)

rem ---- 1) 파이썬 3.11 (이미 있으면 건너뜀)
if not exist "%PYDIR%\python.exe" (
    echo  파이썬을 설치하는 중입니다...
    start /wait "" "%PACK%offline\python-installer.exe" /quiet InstallAllUsers=0 TargetDir="%PYDIR%" Include_launcher=0 Include_test=0 Include_doc=0 PrependPath=0 Shortcuts=0 AssociateFiles=0
)
if not exist "%PYDIR%\python.exe" (
    echo  파이썬 설치에 실패했습니다. 이 PC가 64비트 윈도우 10 이상인지 확인해 주세요.
    goto :fail
)
echo  ✓ 파이썬: %PYDIR%\python.exe

rem ---- 2) 앱 파일 복사 (다시 실행하면 새 버전으로 덮어씀. 설정·촬영한 배경은 유지)
echo.
echo  앱 파일을 복사하는 중입니다...
robocopy "%PACK%app" "%APP%" /E /NFL /NDL /NJH /NJS /NP /XF config.json bgr*.png python_path.txt
if %ERRORLEVEL% GEQ 8 (
    echo  앱 파일을 복사하지 못했습니다. ^(robocopy 코드 %ERRORLEVEL%^)
    goto :fail
)
echo  ✓ 앱: %APP%

rem ---- 3) 나머지는 설치 도우미가 처리 (팩 안의 파일만 사용)
echo.
"%PYDIR%\python.exe" "%APP%\packaging\setup_windows.py" --offline-dir "%PACK%offline" %*
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

:fail
echo.
pause
exit /b 1

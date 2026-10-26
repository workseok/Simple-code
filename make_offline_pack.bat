@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title BG Matte 오프라인 팩 만들기
rem 이 파일이 있는 폴더(packaging 폴더가 보이는 곳)에서 실행됩니다. 경로를 입력할 필요가 없습니다.
cd /d "%~dp0"

if not exist "packaging\build_offline_pack.py" (
    echo.
    echo  packaging\build_offline_pack.py 를 찾지 못했습니다.
    echo  이 파일을 'packaging' 폴더와 'requirements.txt' 가 함께 보이는 폴더 안으로 옮겨서 다시 실행해 주세요.
    echo  현재 위치: %CD%
    goto :end
)

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "C:\BGMatte\python\python.exe" set "PY=C:\BGMatte\python\python.exe"
if not defined PY (
    echo.
    echo  파이썬을 찾지 못했습니다. https://www.python.org/downloads/ 에서 파이썬을 설치한 뒤 다시 실행해 주세요.
    echo  ^(설치 화면 아래쪽 'Add python.exe to PATH'를 체크하세요^)
    goto :end
)

echo.
echo  오프라인 팩을 만듭니다. 인터넷이 필요하고 10~30분 걸립니다. 창을 닫지 마세요.
echo  사용 파이썬: %PY%
echo.
%PY% packaging\build_offline_pack.py %*
echo.
echo  결과는 이 폴더 안의 dist 폴더에 생깁니다: %CD%\dist

:end
echo.
pause

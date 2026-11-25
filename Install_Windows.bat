@echo off
chcp 65001 >nul
set PYTHONUTF8=1
rem  GW_CCT_AI Matte Live 윈도우 설치 - 이 파일을 더블클릭하면 설치가 시작됩니다.
rem  (실제 설치 내용은 packaging 폴더의 install_windows.bat 이 처리합니다)
call "%~dp0packaging\install_windows.bat"

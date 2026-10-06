#!/bin/bash
# 대체 실행 방법: .app 대신 이 파일을 더블클릭하면 터미널에서 GUI 앱을 실행합니다.
# (카메라 권한은 'BG Matte'가 아니라 터미널 앱에 붙습니다 — 기존 .command와 같은 방식)
# 처음 한 번만: chmod +x packaging/BGMatte.command

cd "$(dirname "$0")/.." || exit 1

# conda 환경 활성화 (환경 이름을 바꿨다면 BGMATTE_ENV=이름 으로 지정)
if ! command -v conda >/dev/null 2>&1; then
    for base in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3"; do
        [ -f "$base/etc/profile.d/conda.sh" ] && source "$base/etc/profile.d/conda.sh" && break
    done
fi
if command -v conda >/dev/null 2>&1; then
    eval "$(conda shell.bash hook)"
    conda activate "${BGMATTE_ENV:-bgmatte}" || { echo "conda 환경 '${BGMATTE_ENV:-bgmatte}'를 켜지 못했습니다."; read -r -p "Enter 키를 누르면 닫습니다."; exit 1; }
fi

python -m bgmatte_app
status=$?
if [ $status -ne 0 ]; then
    echo
    echo "앱이 오류로 종료되었습니다 (코드 $status). 위 메시지를 확인해 주세요."
    read -r -p "Enter 키를 누르면 닫습니다."
fi
exit $status

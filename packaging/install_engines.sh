#!/bin/bash
# RobustVideoMatting 엔진 설치 (코드 + 가중치). 맥과 윈도우(Git Bash) 공용입니다.
#
# 사용법 (앱을 쓰는 conda 환경을 켠 상태에서, 프로젝트 폴더 안에서 실행):
#   bash packaging/install_engines.sh            # RVM(mobilenetv3)
#   bash packaging/install_engines.sh rvm50      # RVM resnet50 가중치(108MB) 추가
#
# 결과 (설정 화면의 기본값과 같은 위치):
#   ../RobustVideoMatting/                                      (코드)
#   models/rvm_mobilenetv3.pth  models/rvm_resnet50.pth         (가중치)
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
WHAT="${1:-all}"
mkdir -p models

PY=python
command -v python >/dev/null 2>&1 || PY=python3

clone() {  # clone <url> <폴더>
    if [ -d "$2/.git" ] || [ -d "$2/src" ] || [ -d "$2/model" ]; then
        echo "  ✓ 이미 있음: $2"
    else
        git clone --depth 1 "$1" "$2" || { echo "  ✕ 코드 받기 실패: $1"; return 1; }
    fi
}

size_of() { wc -c < "$1" | tr -d ' '; }

fetch() {  # fetch <url> <저장경로> <기대 바이트>
    if [ -f "$2" ] && [ "$(size_of "$2")" = "$3" ]; then
        echo "  ✓ 이미 있음: $2"
        return 0
    fi
    curl -L --fail -o "$2" "$1" || { echo "  ✕ 다운로드 실패: $1"; rm -f "$2"; return 1; }
    if [ "$(size_of "$2")" != "$3" ]; then
        echo "  ✕ 파일 크기가 맞지 않습니다 ($(size_of "$2") / 기대 $3). 다시 실행해 주세요."
        rm -f "$2"; return 1
    fi
    echo "  ✓ 받음: $2"
}

install_rvm() {
    echo "[RobustVideoMatting]"
    clone https://github.com/PeterL1n/RobustVideoMatting.git ../RobustVideoMatting || return 1
    fetch https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3.pth \
        models/rvm_mobilenetv3.pth 15217721
}

install_rvm50() {
    echo "[RobustVideoMatting resnet50]"
    clone https://github.com/PeterL1n/RobustVideoMatting.git ../RobustVideoMatting || return 1
    fetch https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50.pth \
        models/rvm_resnet50.pth 107905875
}

fail=0
case "$WHAT" in
    all|rvm) install_rvm || fail=1 ;;
    rvm50)  install_rvm50 || fail=1 ;;
    *) echo "사용법: bash packaging/install_engines.sh [all|rvm|rvm50]"; exit 2 ;;
esac

echo
if [ "$fail" = 0 ]; then
    echo "완료. 앱 설정의 '매팅 엔진'에서 RobustVideoMatting을 고르세요."
else
    echo "일부 항목이 실패했습니다. 위 ✕ 표시를 확인해 주세요."
fi
exit "$fail"

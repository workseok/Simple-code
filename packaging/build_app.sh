#!/usr/bin/env bash
# BG Matte.app 만들기 (macOS 전용)
#
# 사용법 (bgmatte 환경을 켠 상태에서):
#   conda activate bgmatte
#   pip install -r requirements-app.txt      # 최초 1회
#   bash packaging/build_app.sh              # → dist/BG Matte.app
#   bash packaging/build_app.sh --install    # → 위 + ~/Applications 에 복사
#
# 만들어지는 앱은 파이썬과 라이브러리를 '복사하지 않습니다'. 지금 켜 둔 conda 환경의
# python과 이 저장소 폴더를 가리키는 가벼운 런처일 뿐이라서, 코드를 고치면 바로 반영되고
# (재빌드 불필요) 용량도 수십 KB입니다. 대신 저장소 폴더나 conda 환경을 옮기면 다시 빌드하세요.

set -euo pipefail

APP_NAME="BG Matte"
EXEC_NAME="BGMatte"
BUNDLE_ID="com.workseok.bgmatte"

fail() { echo "[오류] $*" >&2; exit 1; }
step() { echo; echo "[$1] $2"; }

[[ "$(uname)" == "Darwin" ]] || fail "macOS에서만 실행할 수 있습니다."

INSTALL=0
for arg in "$@"; do
    case "$arg" in
        --install) INSTALL=1 ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) fail "알 수 없는 옵션: $arg" ;;
    esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
APP="$ROOT/dist/$APP_NAME.app"

step "1/5" "파이썬 환경 확인"
PYTHON_BIN="${PYTHON:-$(command -v python || true)}"
[[ -n "$PYTHON_BIN" ]] || fail "python을 찾을 수 없습니다. 'conda activate bgmatte'를 먼저 실행해 주세요."
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
echo "    python: $PYTHON_BIN"

missing="$("$PYTHON_BIN" - <<'PY'
import importlib.util
needed = {"PySide6": "PySide6", "cv2": "opencv-python", "numpy": "numpy", "torch": "torch"}
print(" ".join(pip for mod, pip in needed.items() if importlib.util.find_spec(mod) is None))
PY
)"
if [[ -n "$missing" ]]; then
    echo "    없는 패키지: $missing" >&2
    if [[ "$missing" == *PySide6* ]]; then
        fail "'pip install -r requirements-app.txt' 로 설치한 뒤 다시 실행해 주세요."
    fi
    fail "'conda activate bgmatte' 상태에서 실행했는지 확인해 주세요. (필요: pip install -r requirements.txt)"
fi
echo "    PySide6, OpenCV, torch 확인됨"

step "2/5" "런처 컴파일"
CC_BIN="$(command -v clang || command -v cc || true)"
[[ -n "$CC_BIN" ]] || fail "C 컴파일러가 없습니다. 'xcode-select --install' 로 명령줄 도구를 설치해 주세요."
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/bgmatte_app/__init__.py")"
VERSION="${VERSION:-0.1.0}"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
"$CC_BIN" -O2 -Wall -o "$APP/Contents/MacOS/$EXEC_NAME" "$HERE/launcher.c"
echo "    $CC_BIN → Contents/MacOS/$EXEC_NAME"

step "3/5" "번들 구성 (Info.plist, launch.conf)"
ICON_KEY=""
if [[ -f "$HERE/AppIcon.icns" ]]; then
    cp "$HERE/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
    ICON_KEY="<key>CFBundleIconFile</key><string>AppIcon</string>"
fi
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$APP_NAME</string>
    <key>CFBundleDisplayName</key><string>$APP_NAME</string>
    <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
    <key>CFBundleExecutable</key><string>$EXEC_NAME</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>CFBundleVersion</key><string>$VERSION</string>
    <key>LSMinimumSystemVersion</key><string>10.15</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>LSUIElement</key><true/>
    <key>NSCameraUsageDescription</key><string>실시간 배경 합성을 위해 카메라(캡처카드) 영상을 사용합니다.</string>
    $ICON_KEY
</dict>
</plist>
PLIST
printf '%s\n%s\n' "$PYTHON_BIN" "$ROOT" > "$APP/Contents/Resources/launch.conf"
echo "    python 경로와 프로젝트 폴더를 launch.conf 에 기록했습니다."

step "4/5" "서명 (ad-hoc)"
if command -v codesign >/dev/null 2>&1; then
    codesign --force --deep --sign - "$APP" >/dev/null 2>&1 \
        && echo "    ad-hoc 서명 완료 (이 Mac에서 카메라 권한을 기억하기 위한 용도)" \
        || echo "    서명에 실패했습니다. 앱은 실행되지만 카메라 권한을 매번 물을 수 있습니다."
else
    echo "    codesign이 없어 건너뜁니다."
fi

step "5/5" "마무리"
if [[ "$INSTALL" -eq 1 ]]; then
    DEST="$HOME/Applications"
    mkdir -p "$DEST"
    rm -rf "$DEST/$APP_NAME.app"
    ditto "$APP" "$DEST/$APP_NAME.app"
    echo "    설치: $DEST/$APP_NAME.app"
fi

cat <<EOF

완료: $APP

처음 실행할 때
  1) '$APP_NAME.app'을 더블클릭하면 카메라 권한 팝업이 뜹니다 → '허용'
  2) 팝업이 안 뜨고 검은 화면이면: 시스템 설정 → 개인정보 보호 및 보안 → 카메라 → '$APP_NAME' 켜기
  3) 앱이 안 열리면 로그를 확인하세요: ~/Library/Logs/BGMatte/app.log
재빌드하면 권한 팝업이 다시 뜰 수 있습니다 (앱 서명이 바뀌기 때문).
EOF

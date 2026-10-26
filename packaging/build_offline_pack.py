"""BG Matte 오프라인 팩 만들기 — '인터넷이 되는' 윈도우 PC에서 한 번 실행합니다.

만들어지는 것: dist/BGMatte_Offline_v<버전>/  (그리고 같은 이름의 .zip)
  install_offline.bat      ← 설치할 PC에서 더블클릭하는 파일
  app/                     ← 앱 코드
  offline/python-installer.exe   파이썬 3.11 설치 파일
  offline/wheels/                PyTorch(CUDA) + 앱 라이브러리 wheel 파일들
  offline/repos/                 BackgroundMattingV2 / RobustVideoMatting 코드 zip
  offline/models/                가중치 5종
  offline/MANIFEST.txt           내용물과 SHA-256 (복사 중 깨졌는지 확인용)

설치 PC는 인터넷에 한 번도 접속하지 않습니다.

사용법:
  python packaging\\build_offline_pack.py                 (기본: CUDA 12.6 PyTorch)
  python packaging\\build_offline_pack.py --cuda cu128    (RTX 50 시리즈 등 최신 GPU용)
  python packaging\\build_offline_pack.py --cuda cu126 --cuda cu128   (여러 개 담기: 용량이 약 2배)
  python packaging\\build_offline_pack.py --no-zip        (폴더만 만들고 zip은 만들지 않기)
이 스크립트는 어느 파이썬(3.8 이상)에서든 실행됩니다. 담기는 wheel은 항상 '윈도우 64비트 + 파이썬 3.11'용입니다.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("setup_windows", HERE / "setup_windows.py")
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)

PYTHON_VERSION = "3.11.9"  # 3.11 계열의 마지막 윈도우 설치 파일 버전
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
PYPI = "https://pypi.org/simple"
DEFAULT_CUDA = "cu126"
TARGET = ("--platform", "win_amd64", "--python-version", "3.11", "--implementation", "cp", "--only-binary=:all:")
IGNORE = shutil.ignore_patterns(
    ".git", ".github", ".pytest_cache", "__pycache__", "*.pyc", "dist", "build", "models", "Output", "tests", "*.pth",
    "bgr*.png", "python_path.txt", "config.json",
)


def app_version() -> str:
    for line in (ROOT / "bgmatte_app" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pip_download(dest: Path, *args: str) -> bool:
    cmd = [sys.executable, "-m", "pip", "download", "--dest", str(dest), *TARGET, *args]
    # 한국어 윈도우(cp949)에서 UTF-8 텍스트를 읽다 멈추지 않도록 UTF-8 모드로 실행합니다.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, env=env).returncode == 0


def download_wheels(wheels: Path, cuda_tags: Sequence[str]) -> List[str]:
    """PyTorch(각 CUDA 태그) → 앱 라이브러리 순서로 받고, 마지막에 '인터넷 없이' 해석이 되는지 검증합니다."""
    problems: List[str] = []
    wheels.mkdir(parents=True, exist_ok=True)
    for tag in cuda_tags:
        sw.say(f"  PyTorch({tag}) wheel 받는 중... (수 GB, 시간이 걸립니다)")
        if not pip_download(wheels, "torch", "torchvision", "--index-url", f"https://download.pytorch.org/whl/{tag}",
                            "--extra-index-url", PYPI):
            problems.append(f"PyTorch {tag}")
    sw.say("  앱 라이브러리 wheel 받는 중...")
    if not pip_download(wheels, "-r", str(ROOT / "requirements.txt"), "-r", str(ROOT / "requirements-app.txt"),
                        "--find-links", str(wheels), "--index-url", PYPI):
        problems.append("앱 라이브러리")
    if not problems:
        sw.say("  검증: 받은 파일만으로 모두 설치 가능한지 확인...")
        scratch = wheels.parent / "_verify"
        ok = pip_download(scratch, "torch", "torchvision", "-r", str(ROOT / "requirements.txt"),
                          "-r", str(ROOT / "requirements-app.txt"), "--no-index", "--find-links", str(wheels))
        shutil.rmtree(scratch, ignore_errors=True)
        if not ok:
            problems.append("wheel 검증(빠진 의존 패키지가 있음)")
    return problems


def write_manifest(pack: Path) -> None:
    lines = [f"BG Matte 오프라인 팩 v{app_version()}  (python {PYTHON_VERSION}, win_amd64)", ""]
    for path in sorted((pack / "offline").rglob("*")):
        if path.is_file() and path.name != "MANIFEST.txt":
            lines.append(f"{sha256(path)}  {path.relative_to(pack / 'offline').as_posix()}  {path.stat().st_size}")
    (pack / "offline" / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_zip(pack: Path) -> Path:
    """wheel/가중치는 이미 압축된 파일이라 저장만 합니다(빠름). 4GB를 넘어도 되는 zip64 형식입니다."""
    out = pack.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                zf.write(path, Path(pack.name) / path.relative_to(pack))
    return out


def build(cuda_tags: Sequence[str], out_dir: Path, zip_it: bool = True) -> int:
    pack = out_dir / f"BGMatte_Offline_v{app_version()}"
    offline = pack / "offline"
    problems: List[str] = []
    for sub in ("wheels", "repos", "models"):
        (offline / sub).mkdir(parents=True, exist_ok=True)

    sw.say("[1/5] 앱 파일 복사")
    shutil.copytree(ROOT, pack / "app", ignore=IGNORE, dirs_exist_ok=True)
    shutil.copyfile(HERE / "install_offline.bat", pack / "install_offline.bat")

    sw.say("\n[2/5] 파이썬 설치 파일")
    if not sw.download(PYTHON_URL, offline / "python-installer.exe"):
        problems.append("python-installer.exe")

    sw.say("\n[3/5] PyTorch · 앱 라이브러리")
    problems += download_wheels(offline / "wheels", cuda_tags)

    sw.say("\n[4/5] 엔진 코드 · 가중치")
    for name, url in sw.REPOS.items():
        if not sw.download(url, offline / "repos" / f"{name}.zip"):
            problems.append(f"{name} 코드")
    for name, url, size, _core in sw.WEIGHTS:
        if not sw.download(url, offline / "models" / name, size):
            problems.append(name)

    if problems:
        sw.say("\n✕ 팩을 완성하지 못했습니다. 실패: " + ", ".join(problems))
        sw.say("  인터넷 연결을 확인하고 같은 명령을 다시 실행하면 받은 것은 건너뛰고 이어서 받습니다.")
        return 1

    sw.say("\n[5/5] 목록 기록" + (" · zip 만들기 (몇 분 걸립니다)" if zip_it else ""))
    write_manifest(pack)
    sw.say(f"\n✓ 폴더: {pack}")
    if zip_it:
        sw.say(f"✓ zip : {make_zip(pack)}")
    sw.say("USB나 사내 공유 폴더로 옮긴 뒤, 설치할 PC에서 install_offline.bat 을 실행하세요.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="BG Matte 오프라인 팩 만들기")
    parser.add_argument("--cuda", action="append", help=f"담을 CUDA 버전 (cu126, cu128 …). 여러 번 지정 가능. 기본 {DEFAULT_CUDA}")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="결과 폴더 (기본: dist)")
    parser.add_argument("--no-zip", action="store_true")
    args = parser.parse_args(argv)
    return build(args.cuda or [DEFAULT_CUDA], args.out, zip_it=not args.no_zip)


if __name__ == "__main__":
    sys.exit(main())

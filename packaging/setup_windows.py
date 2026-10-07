"""BG Matte 윈도우 설치 도우미 (install_windows.bat 이 conda 환경을 만든 뒤 이 파일을 실행합니다).

하는 일 (여러 번 실행해도 안전합니다 — 이미 있는 것은 건너뜁니다):
  1. PyTorch 설치: NVIDIA GPU가 있으면 CUDA 빌드를 시도하고, 안 되면 CPU 빌드로 내려갑니다.
  2. 앱 라이브러리 설치 (requirements.txt, requirements-app.txt)
  3. 매팅 엔진 코드 3종을 프로젝트 폴더 '옆'에 내려받기 (git 불필요, zip으로 받음)
       ../BackgroundMattingV2  ../RobustVideoMatting
  4. 가중치 내려받기 (파일 크기로 검증): models/ 아래
  5. 바탕화면 바로가기 만들기, 셀프체크 실행

옵션:
  --all-weights   BackgroundMattingV2 resnet101/mobilenetv2, RVM resnet50 가중치도 받기 (약 370MB 추가)
  --cpu           NVIDIA GPU가 있어도 CPU용 PyTorch로 설치
  --skip-torch    PyTorch 설치 단계를 건너뛰기
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent

CUDA_TAGS = ("cu128", "cu126", "cu124", "cu121")  # 최신 → 오래된 순으로 시도 (드라이버가 오래돼도 낮은 쪽은 동작)

REPOS = {
    "BackgroundMattingV2": "https://github.com/PeterL1n/BackgroundMattingV2/archive/refs/heads/master.zip",
    "RobustVideoMatting": "https://github.com/PeterL1n/RobustVideoMatting/archive/refs/heads/master.zip",
}

BMV2 = "https://github.com/PeterL1n/BackgroundMattingV2/releases/download/v1.0.0/"
RVM = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/"

# (저장 이름, URL, 정상 파일 크기(바이트), 기본 설치 여부)
WEIGHTS: Tuple[Tuple[str, str, int, bool], ...] = (
    ("pytorch_resnet50.pth", BMV2 + "pytorch_resnet50.pth", 161_356_827, True),
    ("rvm_mobilenetv3.pth", RVM + "rvm_mobilenetv3.pth", 15_217_721, True),
    ("pytorch_resnet101.pth", BMV2 + "pytorch_resnet101.pth", 237_643_033, False),
    ("pytorch_mobilenetv2.pth", BMV2 + "pytorch_mobilenetv2.pth", 20_307_935, False),
    ("rvm_resnet50.pth", RVM + "rvm_resnet50.pth", 107_905_875, False),
)


def say(text: str = "") -> None:
    print(text, flush=True)


# ------------------------------------------------------------------ 내려받기 도우미
def file_ok(path: Path, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size


def download(url: str, dest: Path, size: Optional[int] = None) -> bool:
    """url → dest. size가 주어지면 크기까지 맞아야 성공. 실패하면 부분 파일을 지우고 False."""
    if size is not None and file_ok(dest, size):
        say(f"  ✓ 이미 있음: {dest.name}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bgmatte-setup"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last = -1
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    if pct // 10 != last // 10:
                        last = pct
                        say(f"    {dest.name} {pct}%")
        if size is not None and part.stat().st_size != size:
            say(f"  ✕ 파일 크기가 맞지 않습니다: {dest.name} ({part.stat().st_size} / 기대 {size}). 다시 실행해 주세요.")
            part.unlink(missing_ok=True)
            return False
        part.replace(dest)
        say(f"  ✓ 받음: {dest.name}")
        return True
    except Exception as exc:  # 네트워크/방화벽/디스크
        say(f"  ✕ 받지 못했습니다: {dest.name} ({exc})")
        part.unlink(missing_ok=True)
        return False


def git_clone(name: str, zip_url: str, dest: Path) -> bool:
    """zip 받기가 막힌 환경(회사망 등)을 위한 대체 수단. git이 설치되어 있을 때만 시도합니다."""
    git = shutil.which("git")
    if not git:
        return False
    repo_url = zip_url.split("/archive/")[0] + ".git"
    say(f"  · zip을 받지 못해 git으로 시도합니다: {repo_url}")
    return subprocess.run([git, "clone", "--depth", "1", repo_url, str(dest)]).returncode == 0


def fetch_repo(name: str, url: str, parent: Path) -> bool:
    """GitHub zip을 받아 parent/name 폴더로 풀어 놓습니다 (git이 없어도 동작, zip이 막히면 git으로 대체)."""
    dest = parent / name
    if dest.is_dir() and any(dest.iterdir()):
        say(f"  ✓ 이미 있음: {dest}")
        return True
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{name}.zip"
        if download(url, archive):
            try:
                extract_single_root(archive, dest)
                say(f"  ✓ 코드 준비: {dest}")
                return True
            except Exception as exc:
                say(f"  ✕ 압축을 풀지 못했습니다: {name} ({exc})")
                shutil.rmtree(dest, ignore_errors=True)
    if git_clone(name, url, dest):
        say(f"  ✓ 코드 준비: {dest}")
        return True
    say(f"  ✕ {name} 코드를 받지 못했습니다. 인터넷/방화벽을 확인해 주세요.")
    shutil.rmtree(dest, ignore_errors=True)
    return False


def extract_single_root(archive: Path, dest: Path) -> None:
    """zip 안에 최상위 폴더 하나(예: RobustVideoMatting-master)가 있으면 그 안의 내용을 dest로 옮깁니다."""
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        entries = list(Path(tmp).iterdir())
        source = entries[0] if len(entries) == 1 and entries[0].is_dir() else Path(tmp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, dirs_exist_ok=True)


# ------------------------------------------------------------------ pip / torch
def pip(*args: str, check: bool = True) -> int:
    cmd = [sys.executable, "-m", "pip", *args]
    return subprocess.run(cmd, check=check).returncode


def has_nvidia_gpu() -> bool:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return False
    try:
        return subprocess.run([exe], capture_output=True, timeout=20).returncode == 0
    except Exception:
        return False


def cuda_works() -> bool:
    code = "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)"
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def torch_installed() -> bool:
    return subprocess.run([sys.executable, "-c", "import torch,torchvision"], capture_output=True).returncode == 0


def torch_plan(gpu: bool, force_cpu: bool) -> List[Optional[str]]:
    """설치를 시도할 순서. 값은 CUDA 태그이고 None은 기본(윈도우에서는 CPU) 빌드입니다."""
    if gpu and not force_cpu:
        return [*CUDA_TAGS, None]
    return [None]


def install_torch(force_cpu: bool) -> None:
    gpu = has_nvidia_gpu()
    say(f"  NVIDIA GPU: {'있음' if gpu else '없음 (CPU로 설치)'}" + (" — 단, --cpu 지정으로 CPU 설치" if gpu and force_cpu else ""))
    # 빌드 종류(CPU/CUDA)만 다른 같은 버전은 pip가 '이미 설치됨'으로 보므로 먼저 지웁니다.
    pip("uninstall", "-y", "torch", "torchvision", check=False)
    for tag in torch_plan(gpu, force_cpu):
        if tag is None:
            say("  CPU용 PyTorch를 설치합니다...")
            pip("install", "torch", "torchvision")
            return
        say(f"  GPU용 PyTorch({tag})를 시도합니다...")
        if pip("install", "torch", "torchvision", "--index-url", f"https://download.pytorch.org/whl/{tag}", check=False) == 0 and cuda_works():
            say(f"  ✓ GPU(CUDA) 사용 가능 ({tag})")
            return
        say(f"  · {tag} 로는 GPU를 쓸 수 없어 다음 후보를 시도합니다")
        pip("uninstall", "-y", "torch", "torchvision", check=False)
    # 위 루프의 마지막 후보(None)는 return 으로 끝나므로 여기에는 오지 않습니다.


# ------------------------------------------------------------------ 나머지 단계
def make_shortcut() -> None:
    """바탕화면에 'BG Matte' 바로가기를 만듭니다 (실패해도 설치는 계속)."""
    bat = ROOT / "packaging" / "BGMatte.bat"
    icon = ROOT / "packaging" / "AppIcon.ico"
    ps = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'BG Matte.lnk'));"
        f"$s.TargetPath='{bat}';$s.WorkingDirectory='{ROOT}';$s.IconLocation='{icon}';$s.Save();$d"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            say(f"  ✓ 바탕화면 바로가기를 만들었습니다: {out.stdout.strip()}\\BG Matte.lnk")
        else:
            say("  · 바로가기를 만들지 못했습니다. packaging\\BGMatte.bat 을 직접 실행하세요.")
    except Exception:
        say("  · 바로가기를 만들지 못했습니다. packaging\\BGMatte.bat 을 직접 실행하세요.")


def write_python_path() -> None:
    """런처(BGMatte.bat)가 이 환경의 python을 찾을 수 있도록 경로를 기록합니다."""
    (ROOT / "packaging" / "python_path.txt").write_text(sys.executable + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="BG Matte 윈도우 설치 도우미")
    parser.add_argument("--all-weights", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--skip-torch", action="store_true")
    args = parser.parse_args(argv)

    problems: List[str] = []
    models = ROOT / "models"
    models.mkdir(exist_ok=True)
    (ROOT / "backgrounds").mkdir(exist_ok=True)

    say("[1/5] PyTorch")
    if args.skip_torch or (torch_installed() and not args.cpu and cuda_works() == has_nvidia_gpu()):
        say("  ✓ 이미 설치되어 있어 건너뜁니다")
    else:
        install_torch(args.cpu)

    say("\n[2/5] 앱 라이브러리")
    pip("install", "-r", str(ROOT / "requirements.txt"), "-r", str(ROOT / "requirements-app.txt"))

    say("\n[3/5] 매팅 엔진 코드")
    for name, url in REPOS.items():
        if not fetch_repo(name, url, ROOT.parent):
            problems.append(f"{name} 코드")

    say("\n[4/5] 가중치")
    for name, url, size, default in WEIGHTS:
        if default or args.all_weights:
            if not download(url, models / name, size):
                problems.append(name)

    say("\n[5/5] 마무리")
    write_python_path()
    make_shortcut()
    say("\n셀프체크 (모델 불러오기·추론 점검)")
    say("  ※ '합성 배경이 없습니다' 표시는 처음에는 정상입니다. 이미지를 backgrounds 폴더에 넣으면 사라집니다.")
    subprocess.run([sys.executable, "-m", "bgmatte_app.selfcheck"], cwd=str(ROOT))

    say()
    if problems:
        say("일부 항목이 실패했습니다: " + ", ".join(problems))
        say("인터넷 연결을 확인하고 install_windows.bat 을 다시 실행하면 이어서 받습니다.")
        return 1
    say("설치가 끝났습니다. 바탕화면의 'BG Matte'를 실행하세요. (설정 → 매팅 엔진에서 엔진을 고릅니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

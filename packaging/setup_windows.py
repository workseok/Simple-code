"""BG Matte 윈도우 설치 도우미 (install_windows.bat 이 conda 환경을 만든 뒤 이 파일을 실행합니다).

하는 일 (여러 번 실행해도 안전합니다 — 이미 있는 것은 건너뜁니다):
  1. PyTorch 설치: NVIDIA GPU가 있으면 CUDA 빌드를 시도하고, 안 되면 CPU 빌드로 내려갑니다.
  2. 앱 라이브러리 설치 (requirements.txt, requirements-app.txt)
  3. 매팅 엔진 코드 3종을 프로젝트 폴더 '옆'에 내려받기 (git 불필요, zip으로 받음)
       ../BackgroundMattingV2  ../RobustVideoMatting
  4. 가중치 5종을 모두 내려받기 (파일 크기로 검증, 약 540MB): models/ 아래
  5. 바탕화면 바로가기 만들기, 셀프체크, '인터넷 없이 쓸 준비가 됐는지' 확인

설치가 끝나면 앱은 인터넷 없이 동작합니다 (엔진 코드·가중치가 모두 이 PC에 있고, 앱은 실행 중 어디에도 접속하지 않습니다).

옵션:
  --minimal       꼭 필요한 가중치 2종만 받기 (BackgroundMattingV2 resnet50, RVM mobilenetv3). 용량을 아끼고 싶을 때
  --all-weights   예전 옵션 (이제는 기본 동작이라 아무 일도 하지 않습니다)
  --cpu           NVIDIA GPU가 있어도 CPU용 PyTorch로 설치
  --skip-torch    PyTorch 설치 단계를 건너뛰기
  --offline-dir D 인터넷 없이 설치: D(오프라인 팩의 offline 폴더)의 wheels / repos / models 만 사용합니다.
                  (오프라인 팩은 packaging/build_offline_pack.py 로 인터넷 되는 PC에서 만듭니다. docs/OFFLINE_PACK.md)
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

# (저장 이름, URL, 정상 파일 크기(바이트), 최소 설치에 포함 여부). 기본 설치는 5종 모두 받습니다.
WEIGHTS: Tuple[Tuple[str, str, int, bool], ...] = (
    ("pytorch_resnet50.pth", BMV2 + "pytorch_resnet50.pth", 161_356_827, True),
    ("rvm_mobilenetv3.pth", RVM + "rvm_mobilenetv3.pth", 15_217_721, True),
    ("pytorch_resnet101.pth", BMV2 + "pytorch_resnet101.pth", 237_643_033, False),
    ("pytorch_mobilenetv2.pth", BMV2 + "pytorch_mobilenetv2.pth", 20_307_935, False),
    ("rvm_resnet50.pth", RVM + "rvm_resnet50.pth", 107_905_875, False),
)


def say(text: str = "") -> None:
    print(text, flush=True)


def offline_missing(root: Path = ROOT) -> List[str]:
    """인터넷 없이 모든 엔진·백본을 쓰기 위해 이 PC에 있어야 하는데 빠진 항목 이름 목록(비어 있으면 준비 완료)."""
    missing: List[str] = []
    for name in REPOS:
        folder = root.parent / name
        if not (folder / "model").is_dir():
            missing.append(f"{name} 코드")
    for name, _url, size, _core in WEIGHTS:
        if not file_ok(root / "models" / name, size):
            missing.append(name)
    return missing


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


# ------------------------------------------------------------------ 오프라인 팩에서 설치
def pack_problems(pack: Path) -> List[str]:
    """오프라인 팩(offline 폴더)에 빠진 것이 있으면 이름 목록을 돌려줍니다 (비어 있으면 설치 가능)."""
    missing: List[str] = []
    wheels = pack / "wheels"
    for prefix in ("torch-", "torchvision-"):
        if not any(wheels.glob(prefix + "*.whl")):
            missing.append(f"wheels/{prefix}*.whl")
    for name in REPOS:
        if not (pack / "repos" / f"{name}.zip").is_file():
            missing.append(f"repos/{name}.zip")
    for name, _url, size, _core in WEIGHTS:
        if not file_ok(pack / "models" / name, size):
            missing.append(f"models/{name}")
    return missing


def pip_offline(pack: Path, *args: str, check: bool = True) -> int:
    """인터넷에 접속하지 않고(--no-index) 팩의 wheels 폴더에서만 설치합니다."""
    return pip("install", "--no-index", "--find-links", str(pack / "wheels"), *args, check=check)


def install_torch_offline(pack: Path) -> bool:
    """팩에 든 PyTorch(CUDA 빌드)를 설치합니다. NVIDIA GPU가 없는 PC에서는 같은 빌드가 CPU로 동작합니다."""
    pip("uninstall", "-y", "torch", "torchvision", check=False)
    if pip_offline(pack, "torch", "torchvision", check=False) != 0:
        say("  ✕ 팩의 PyTorch 설치에 실패했습니다. 팩이 이 PC의 파이썬(3.11, 64비트)과 맞는지 확인해 주세요.")
        return False
    gpu = has_nvidia_gpu()
    ok = cuda_works()
    if gpu and not ok:
        say("  · NVIDIA GPU가 보이지만 이 팩의 CUDA 버전으로는 쓸 수 없습니다 (그래픽 드라이버가 오래되었을 수 있습니다).")
        say("    → NVIDIA 드라이버를 최신으로 올리면 GPU로 동작합니다. 그때까지는 CPU로 동작합니다.")
    else:
        say(f"  ✓ PyTorch 설치 완료 ({'GPU(CUDA) 사용 가능' if ok else 'CPU 사용'})")
    return True


def install_repos_offline(pack: Path, parent: Path) -> List[str]:
    failed: List[str] = []
    for name in REPOS:
        dest = parent / name
        if (dest / "model").is_dir():
            say(f"  ✓ 이미 있음: {dest}")
            continue
        try:
            extract_single_root(pack / "repos" / f"{name}.zip", dest)
            say(f"  ✓ 코드 준비: {dest}")
        except Exception as exc:
            say(f"  ✕ {name} 코드를 풀지 못했습니다 ({exc})")
            failed.append(f"{name} 코드")
    return failed


def copy_weights_offline(pack: Path, models: Path, minimal: bool = False) -> List[str]:
    failed: List[str] = []
    models.mkdir(parents=True, exist_ok=True)
    for name, _url, size, core in WEIGHTS:
        if not (core or not minimal):
            continue
        dest = models / name
        if file_ok(dest, size):
            say(f"  ✓ 이미 있음: {name}")
            continue
        src = pack / "models" / name
        if not file_ok(src, size):
            say(f"  ✕ 팩에 없거나 크기가 맞지 않습니다: {name}")
            failed.append(name)
            continue
        shutil.copyfile(src, dest)
        say(f"  ✓ 복사: {name}")
    return failed


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
def shortcut_command(python_exe: str = "", root: Path = ROOT) -> Tuple[str, str]:
    """바탕화면 바로가기가 실행할 (프로그램, 인자). 콘솔 창이 뜨지 않도록 pythonw.exe 로 앱을 직접 띄웁니다.
    pythonw.exe 가 없으면 예전 방식(BGMatte.bat, 검은 창이 함께 뜸)으로 대신합니다."""
    exe = Path(python_exe or sys.executable)
    windowless = exe.with_name("pythonw.exe")
    if windowless.is_file():
        return str(windowless), "-m bgmatte_app"
    return str(root / "packaging" / "BGMatte.bat"), ""


def make_shortcut() -> None:
    """바탕화면에 'BG Matte' 바로가기를 만듭니다 (실패해도 설치는 계속)."""
    target, arguments = shortcut_command()
    icon = ROOT / "packaging" / "AppIcon.ico"
    ps = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'BG Matte.lnk'));"
        f"$s.TargetPath='{target}';$s.Arguments='{arguments}';$s.WorkingDirectory='{ROOT}';"
        f"$s.IconLocation='{icon}';$s.Save();$d"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            say(f"  ✓ 바탕화면 바로가기를 만들었습니다: {out.stdout.strip()}\\BG Matte.lnk")
            if not arguments:
                say("  · pythonw.exe 를 찾지 못해 검은 창이 함께 뜨는 방식으로 만들었습니다.")
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
    parser.add_argument("--all-weights", action="store_true", help="(예전 옵션, 기본 동작과 같습니다)")
    parser.add_argument("--minimal", action="store_true", help="필수 가중치 2종만 받기")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--skip-torch", action="store_true")
    parser.add_argument("--offline-dir", type=Path, default=None, help="오프라인 팩의 offline 폴더 (인터넷 없이 설치)")
    args = parser.parse_args(argv)
    pack: Optional[Path] = args.offline_dir
    if pack is not None:
        absent = pack_problems(pack)
        if absent:
            say("오프라인 팩이 완전하지 않습니다. 빠진 항목: " + ", ".join(absent))
            say("팩을 만든 PC에서 build_offline_pack.py 를 다시 실행하거나, 복사 중 끊긴 파일이 없는지 확인해 주세요.")
            return 2

    problems: List[str] = []
    models = ROOT / "models"
    models.mkdir(exist_ok=True)
    (ROOT / "backgrounds").mkdir(exist_ok=True)

    say("[1/5] PyTorch" + (" (오프라인 팩)" if pack else ""))
    if pack is not None and not args.skip_torch:
        if not install_torch_offline(pack):
            problems.append("PyTorch")
    elif args.skip_torch or (torch_installed() and not args.cpu and cuda_works() == has_nvidia_gpu()):
        say("  ✓ 이미 설치되어 있어 건너뜁니다")
    else:
        install_torch(args.cpu)

    say("\n[2/5] 앱 라이브러리")
    requirements = ("-r", str(ROOT / "requirements.txt"), "-r", str(ROOT / "requirements-app.txt"))
    if pack is not None:
        if pip_offline(pack, *requirements, check=False) != 0:
            problems.append("앱 라이브러리")
    else:
        pip("install", *requirements)

    say("\n[3/5] 매팅 엔진 코드")
    if pack is not None:
        problems += install_repos_offline(pack, ROOT.parent)
    else:
        for name, url in REPOS.items():
            if not fetch_repo(name, url, ROOT.parent):
                problems.append(f"{name} 코드")

    say("\n[4/5] 가중치")
    if pack is not None:
        problems += copy_weights_offline(pack, models, args.minimal)
    else:
        for name, url, size, core in WEIGHTS:
            if core or not args.minimal:
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
        say("오프라인 팩 설치를 다시 실행해 주세요." if pack else "인터넷 연결을 확인하고 install_windows.bat 을 다시 실행하면 이어서 받습니다.")
        return 1
    missing = offline_missing()
    if missing and not args.minimal:
        say("설치는 끝났지만 아직 빠진 파일이 있습니다: " + ", ".join(missing))
        say("install_windows.bat 을 다시 실행해 주세요.")
        return 1
    say("설치가 끝났습니다. 바탕화면의 'BG Matte'를 실행하세요. (설정 → 매팅 엔진에서 엔진을 고릅니다)")
    if not missing:
        say("엔진 코드 2종과 가중치 5종이 모두 이 PC에 있습니다. 이제 인터넷 연결 없이 사용할 수 있습니다.")
    else:
        say("--minimal 로 설치해서 일부 가중치가 없습니다: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())

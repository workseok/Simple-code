"""오프라인 팩: 설치 쪽(setup_windows --offline-dir)과 팩 만들기(build_offline_pack)의 순수 로직."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "packaging"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sw = load("setup_windows")
bp = load("build_offline_pack")


def make_pack(root: Path, skip=()):
    (root / "wheels").mkdir(parents=True)
    (root / "repos").mkdir()
    (root / "models").mkdir()
    for f in ("torch-2.0-cp311-win_amd64.whl", "torchvision-0.15-cp311-win_amd64.whl"):
        (root / "wheels" / f).write_bytes(b"w")
    for name in sw.REPOS:
        with zipfile.ZipFile(root / "repos" / f"{name}.zip", "w") as zf:
            zf.writestr(f"{name}-master/model/__init__.py", "")
    for name, _u, size, _c in sw.WEIGHTS:
        (root / "models" / name).write_bytes(b"x" * size) if name not in skip else None
    return root


@pytest.fixture(autouse=True)
def small_weights(monkeypatch):
    # 수백 MB 파일을 만들지 않도록 크기를 작게 바꿔 둔다
    small = tuple((n, u, 10 + i, c) for i, (n, u, _s, c) in enumerate(sw.WEIGHTS))
    monkeypatch.setattr(sw, "WEIGHTS", small)


def test_complete_pack_has_no_problems(tmp_path):
    assert sw.pack_problems(make_pack(tmp_path / "offline")) == []


def test_pack_problems_lists_everything_missing(tmp_path):
    pack = make_pack(tmp_path / "offline", skip=("rvm_resnet50.pth",))
    (pack / "repos" / "RobustVideoMatting.zip").unlink()
    for w in (pack / "wheels").glob("torchvision*"):
        w.unlink()
    problems = sw.pack_problems(pack)
    assert "models/rvm_resnet50.pth" in problems
    assert "repos/RobustVideoMatting.zip" in problems
    assert "wheels/torchvision-*.whl" in problems and len(problems) == 3


def test_truncated_weight_is_reported(tmp_path):
    pack = make_pack(tmp_path / "offline")
    (pack / "models" / "pytorch_resnet50.pth").write_bytes(b"cut")
    assert sw.pack_problems(pack) == ["models/pytorch_resnet50.pth"]


def test_main_refuses_incomplete_pack_before_touching_anything(tmp_path, monkeypatch, capsys):
    pack = make_pack(tmp_path / "offline", skip=("rvm_resnet50.pth",))
    called = []
    monkeypatch.setattr(sw, "pip", lambda *a, **k: called.append(a) or 0)
    assert sw.main(["--offline-dir", str(pack)]) == 2
    assert not called, "팩이 불완전하면 아무것도 설치하지 않아야 합니다"
    assert "rvm_resnet50.pth" in capsys.readouterr().out


def test_offline_install_uses_no_index_and_pack_wheels(tmp_path, monkeypatch):
    pack = make_pack(tmp_path / "offline")
    calls = []
    monkeypatch.setattr(sw, "pip", lambda *a, **k: calls.append(a) or 0)
    monkeypatch.setattr(sw, "has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(sw, "cuda_works", lambda: False)
    assert sw.install_torch_offline(pack)
    install = [c for c in calls if c[0] == "install"]
    assert install and all("--no-index" in c and str(pack / "wheels") in c for c in install)
    assert not any("--index-url" in c or "--extra-index-url" in c for c in calls)


def test_offline_install_failure_is_reported(tmp_path, monkeypatch):
    pack = make_pack(tmp_path / "offline")
    monkeypatch.setattr(sw, "pip", lambda *a, **k: 1 if a[0] == "install" else 0)
    assert sw.install_torch_offline(pack) is False


def test_repos_and_weights_are_installed_from_pack_without_network(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("네트워크를 쓰면 안 됩니다")

    monkeypatch.setattr(sw.urllib.request, "urlopen", boom)
    pack = make_pack(tmp_path / "offline")
    parent = tmp_path / "BGMatte"
    assert sw.install_repos_offline(pack, parent) == []
    assert (parent / "BackgroundMattingV2" / "model" / "__init__.py").is_file()
    models = parent / "app" / "models"
    assert sw.copy_weights_offline(pack, models) == []
    assert sw.offline_missing(parent / "app") == []
    # 다시 실행해도 안전 (이미 있음)
    assert sw.install_repos_offline(pack, parent) == [] and sw.copy_weights_offline(pack, models) == []


def test_minimal_copies_only_core_weights(tmp_path):
    pack = make_pack(tmp_path / "offline")
    models = tmp_path / "m"
    assert sw.copy_weights_offline(pack, models, minimal=True) == []
    assert {p.name for p in models.iterdir()} == {n for n, _u, _s, core in sw.WEIGHTS if core}


def test_manifest_and_zip_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "app_version", lambda: "9.9.9")
    pack = make_pack(tmp_path / "BGMatte_Offline_v9.9.9" / "offline")
    root = pack.parent
    (root / "install_offline.bat").write_text("@echo off")
    bp.write_manifest(root)
    text = (pack / "MANIFEST.txt").read_text(encoding="utf-8")
    assert "9.9.9" in text and "models/pytorch_resnet50.pth" in text and "MANIFEST.txt" not in text.split("\n", 2)[2]
    out = bp.make_zip(root)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "BGMatte_Offline_v9.9.9/install_offline.bat" in names
    assert "BGMatte_Offline_v9.9.9/offline/models/pytorch_resnet50.pth" in names


def test_build_stops_and_reports_when_a_download_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bp, "ROOT", tmp_path / "src")
    (tmp_path / "src" / "bgmatte_app").mkdir(parents=True)
    (tmp_path / "src" / "bgmatte_app" / "__init__.py").write_text('__version__ = "1.2.3"\n')
    monkeypatch.setattr(bp.sw, "download", lambda *a, **k: False)
    monkeypatch.setattr(bp, "download_wheels", lambda *a, **k: [])
    rc = bp.build(["cu126"], tmp_path / "dist")
    assert rc == 1
    out = capsys.readouterr().out
    assert "python-installer.exe" in out and "완성하지 못했습니다" in out
    assert not list((tmp_path / "dist").glob("*.zip")), "실패하면 zip을 만들지 않습니다"


def test_wheel_download_targets_windows_python311(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bp.subprocess, "run", lambda cmd, **k: calls.append(cmd) or type("R", (), {"returncode": 0})())
    assert bp.download_wheels(tmp_path / "w", ["cu126", "cu128"]) == []
    torch_calls = [c for c in calls if "torch" in c and "--index-url" in c]
    assert len(torch_calls) == 2 and any("cu128" in " ".join(c) for c in torch_calls)
    for c in calls:
        assert "win_amd64" in c and "3.11" in c and "--only-binary=:all:" in c
    assert "--no-index" in calls[-1], "마지막은 인터넷 없이 설치 가능한지 검증하는 호출"


def test_batch_file_is_offline_only():
    text = (PKG / "install_offline.bat").read_text(encoding="utf-8")
    for bad in ("winget", "conda", "http://", "https://", "curl", "Invoke-WebRequest"):
        assert bad not in text, bad
    assert "--offline-dir" in text and "robocopy" in text
    assert 'TargetDir="%PYDIR%"' in text


def test_pack_excludes_user_data_when_copying_app(tmp_path):
    src = tmp_path / "src"
    for rel in ("models/a.pth", "bgr.png", "bgr_cam1.png", "tests/t.py", ".git/x", "bgmatte_app/a.py", "dist/z"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x")
    import shutil
    shutil.copytree(src, tmp_path / "out", ignore=bp.IGNORE)
    kept = {p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*") if p.is_file()}
    assert kept == {"bgmatte_app/a.py"}


def test_requirements_files_are_ascii_so_pip_works_on_korean_windows():
    # 한국어 윈도우의 pip는 기본으로 cp949로 읽으므로 한글(UTF-8) 주석이 있으면 설치가 멈춥니다.
    root = PKG.parent
    for name in ("requirements.txt", "requirements-app.txt"):
        (root / name).read_bytes().decode("ascii")


def test_batch_files_force_utf8_mode():
    for rel in ("make_offline_pack.bat", "packaging/install_offline.bat"):
        assert "PYTHONUTF8=1" in (PKG.parent / rel).read_text(encoding="utf-8"), rel

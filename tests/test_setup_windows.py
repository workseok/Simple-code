"""윈도우 설치 도우미(packaging/setup_windows.py)의 순수 로직을 확인합니다 (네트워크 없이 file:// 로 대체)."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "setup_windows", Path(__file__).resolve().parent.parent / "packaging" / "setup_windows.py"
)
sw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sw)


def make_zip(path: Path, files: dict) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return path


def test_download_verifies_size_and_skips_when_already_correct(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 1000)
    dest = tmp_path / "out" / "w.pth"
    assert sw.download(src.as_uri(), dest, 1000) and dest.stat().st_size == 1000
    src.write_bytes(b"changed but same name")  # 이미 맞는 파일이 있으면 다시 받지 않음
    assert sw.download(src.as_uri(), dest, 1000) and dest.read_bytes() == b"x" * 1000


def test_download_rejects_wrong_size_and_leaves_no_partial_file(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 10)
    dest = tmp_path / "w.pth"
    assert not sw.download(src.as_uri(), dest, 999)
    assert not dest.exists() and not list(tmp_path.glob("*.part"))


def test_download_failure_returns_false(tmp_path):
    assert not sw.download((tmp_path / "missing.bin").as_uri(), tmp_path / "w.pth", 1)


def test_repo_zip_with_single_top_folder_is_unwrapped(tmp_path):
    archive = make_zip(tmp_path / "r.zip", {"RobustVideoMatting-master/model/model.py": "x", "RobustVideoMatting-master/README.md": "r"})
    sw.extract_single_root(archive, tmp_path / "RobustVideoMatting")
    assert (tmp_path / "RobustVideoMatting" / "model" / "model.py").is_file()
    assert not (tmp_path / "RobustVideoMatting" / "RobustVideoMatting-master").exists()


def test_fetch_repo_is_idempotent(tmp_path):
    archive = make_zip(tmp_path / "r.zip", {"Repo-master/model/__init__.py": "x"})
    assert sw.fetch_repo("Repo", archive.as_uri(), tmp_path)
    (tmp_path / "Repo" / "mine.txt").write_text("keep")
    assert sw.fetch_repo("Repo", (tmp_path / "gone.zip").as_uri(), tmp_path), "이미 있으면 다시 받지 않습니다"
    assert (tmp_path / "Repo" / "mine.txt").read_text() == "keep"


def test_torch_plan_tries_cuda_tags_then_falls_back_to_cpu():
    assert sw.torch_plan(gpu=False, force_cpu=False) == [None]
    assert sw.torch_plan(gpu=True, force_cpu=True) == [None]
    plan = sw.torch_plan(gpu=True, force_cpu=False)
    assert plan[:-1] == list(sw.CUDA_TAGS) and plan[-1] is None


def test_weight_table_matches_app_default_paths():
    from bgmatte_app.config import Config

    names = {name for name, *_ in sw.WEIGHTS}
    cfg = Config()
    for configured in (cfg.checkpoint, cfg.checkpoint_resnet101, cfg.checkpoint_mobilenetv2,
                       cfg.rvm_checkpoint, cfg.rvm_checkpoint_resnet50):
        assert Path(configured).name in names, f"설치 도우미가 받지 않는 기본 가중치: {configured}"
    for configured in (cfg.repo_path, cfg.rvm_repo):
        assert Path(configured).name in sw.REPOS, f"설치 도우미가 받지 않는 기본 저장소: {configured}"


def test_minimal_set_includes_the_weights_each_engine_needs_to_start():
    core = {name for name, _u, _s, core in sw.WEIGHTS if core}
    assert {"pytorch_resnet50.pth", "rvm_mobilenetv3.pth"} <= core



def test_offline_report_lists_everything_missing_then_nothing(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    missing = sw.offline_missing(root)
    assert len(missing) == len(sw.REPOS) + len(sw.WEIGHTS)
    # 크기 검사를 우회하기 위해 작은 크기로 바꾼 표로 '모두 있는' 상태를 확인
    small = tuple((n, u, 10, c) for n, u, _s, c in sw.WEIGHTS)
    monkeypatch.setattr(sw, "WEIGHTS", small)
    for name in sw.REPOS:
        (tmp_path / name / "model").mkdir(parents=True)
    (root / "models").mkdir()
    for n, *_ in small:
        (root / "models" / n).write_bytes(b"x" * 10)
    assert sw.offline_missing(root) == []
    (root / "models" / small[2][0]).write_bytes(b"x" * 3)  # 크기가 틀린(받다 만) 파일
    assert sw.offline_missing(root) == [small[2][0]]


def test_default_downloads_every_weight_and_minimal_only_the_core(tmp_path, monkeypatch):
    got = []
    monkeypatch.setattr(sw, "download", lambda url, dest, size=None: got.append(dest.name) or True)
    monkeypatch.setattr(sw, "ROOT", tmp_path / "app")
    (tmp_path / "app").mkdir()
    for fn in ("torch_installed", "cuda_works", "has_nvidia_gpu"):
        monkeypatch.setattr(sw, fn, lambda *a, **k: True)
    monkeypatch.setattr(sw, "pip", lambda *a, **k: None)
    monkeypatch.setattr(sw, "fetch_repo", lambda *a, **k: True)
    monkeypatch.setattr(sw, "write_python_path", lambda: None)
    monkeypatch.setattr(sw, "make_shortcut", lambda: None)
    monkeypatch.setattr(sw.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sw, "offline_missing", lambda root=None: [])
    sw.main(["--skip-torch"])
    assert sorted(got) == sorted(n for n, *_ in sw.WEIGHTS)
    got.clear()
    sw.main(["--skip-torch", "--minimal"])
    assert sorted(got) == ["pytorch_resnet50.pth", "rvm_mobilenetv3.pth"]


def test_fetch_repo_falls_back_to_git_when_zip_download_fails(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sw.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        sw.subprocess, "run",
        lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 0})(),
    )
    bad = (tmp_path / "missing.zip").as_uri()
    assert sw.fetch_repo("Repo", bad.replace("missing.zip", "x/archive/refs/heads/master.zip"), tmp_path)
    assert calls and calls[0][:4] == ["git", "clone", "--depth", "1"] and calls[0][4].endswith("x.git")


def test_fetch_repo_reports_failure_without_git(tmp_path, monkeypatch):
    monkeypatch.setattr(sw.shutil, "which", lambda _name: None)
    assert not sw.fetch_repo("Repo", (tmp_path / "nope.zip").as_uri(), tmp_path)
    assert not (tmp_path / "Repo").exists()


def test_shortcut_uses_windowless_pythonw_when_available(tmp_path):
    (tmp_path / "python.exe").write_bytes(b"")
    (tmp_path / "pythonw.exe").write_bytes(b"")
    target, args = sw.shortcut_command(str(tmp_path / "python.exe"), root=tmp_path / "app")
    assert Path(target).name == "pythonw.exe" and args == "-m bgmatte_app"


def test_shortcut_falls_back_to_bat_without_pythonw(tmp_path):
    (tmp_path / "python.exe").write_bytes(b"")
    target, args = sw.shortcut_command(str(tmp_path / "python.exe"), root=tmp_path / "app")
    assert Path(target).name == "BGMatte.bat" and args == ""

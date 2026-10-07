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
    archive = make_zip(tmp_path / "r.zip", {"MODNet-master/src/models/modnet.py": "x", "MODNet-master/README.md": "r"})
    sw.extract_single_root(archive, tmp_path / "MODNet")
    assert (tmp_path / "MODNet" / "src" / "models" / "modnet.py").is_file()
    assert not (tmp_path / "MODNet" / "MODNet-master").exists()


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

    names = {name for name, *_ in sw.WEIGHTS} | {sw.MODNET_CKPT[0]}
    cfg = Config()
    for configured in (cfg.checkpoint, cfg.checkpoint_resnet101, cfg.checkpoint_mobilenetv2,
                       cfg.modnet_checkpoint, cfg.rvm_checkpoint, cfg.rvm_checkpoint_resnet50):
        assert Path(configured).name in names, f"설치 도우미가 받지 않는 기본 가중치: {configured}"
    for configured in (cfg.repo_path, cfg.modnet_repo, cfg.rvm_repo):
        assert Path(configured).name in sw.REPOS, f"설치 도우미가 받지 않는 기본 저장소: {configured}"


def test_default_install_includes_the_weights_each_engine_needs_to_start():
    default = {name for name, _u, _s, default in sw.WEIGHTS if default}
    assert {"pytorch_resnet50.pth", "rvm_mobilenetv3.pth"} <= default


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

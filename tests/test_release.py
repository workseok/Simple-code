"""배포(버전·설치 파일 빌드) 관련 파일이 서로 맞는지, 그리고 콘솔 없는 실행의 로깅을 확인합니다."""

import importlib.util
import logging
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bump = _load("bump_version", "packaging/bump_version.py")


def test_version_is_semver_and_single_source():
    import bgmatte_app

    assert re.fullmatch(r"\d+\.\d+\.\d+", bgmatte_app.__version__)
    iss = (ROOT / "packaging" / "BGMatte_Setup.iss").read_text(encoding="utf-8")
    assert "{#AppVersion}" in iss and 'define AppVersion "0.0.0"' in iss, "버전은 외부(/DAppVersion)에서 받습니다"
    assert not re.search(r'define AppVersion "[1-9]', iss), ".iss 에 버전을 직접 적어 두면 안 맞게 됩니다"


def test_release_workflow_builds_with_the_same_version_and_output_name():
    wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "/DAppVersion=" in wf and "BGMatte_Setup_v" in wf and "tags:" in wf
    iss = (ROOT / "packaging" / "BGMatte_Setup.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=BGMatte_Setup_v{#AppVersion}" in iss


def test_build_script_reads_version_and_passes_it(tmp_path):
    bat = (ROOT / "packaging" / "build_release.bat").read_bytes()
    assert b"\r\n" in bat, "배치 파일은 CRLF 여야 합니다"
    text = bat.decode("utf-8")
    assert "/DAppVersion=%VER%" in text and "__version__" in text


@pytest.mark.parametrize(
    "current,how,expected",
    [("1.0.0", "patch", "1.0.1"), ("1.0.9", "minor", "1.1.0"), ("1.4.2", "major", "2.0.0"), ("1.0.0", "3.2.1", "3.2.1")],
)
def test_next_version(current, how, expected):
    assert bump.next_version(current, how) == expected


def test_next_version_rejects_nonsense():
    with pytest.raises(ValueError):
        bump.next_version("1.0.0", "huge")


def test_bump_rewrites_only_the_version_line(tmp_path):
    f = tmp_path / "__init__.py"
    f.write_text('"""doc"""\n\n__version__ = "1.2.3"\nOTHER = "1.2.3"\n', encoding="utf-8")
    assert bump.bump("patch", f) == ("1.2.3", "1.2.4")
    assert f.read_text(encoding="utf-8") == '"""doc"""\n\n__version__ = "1.2.4"\nOTHER = "1.2.3"\n'


def test_logging_survives_missing_console_and_writes_a_file(tmp_path, monkeypatch):
    """pythonw.exe 처럼 sys.stdout/stderr 가 None 이어도 죽지 않고 로그 파일에 남깁니다."""
    from bgmatte_app import __main__ as entry

    saved_root = list(logging.getLogger().handlers)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log_file = tmp_path / "logs" / "app.log"
    try:
        assert entry.setup_logging(log_file) == log_file
        print("라이브러리가 stdout 에 출력해도 괜찮아야 합니다")
        sys.stderr.write("stderr 출력\n")
        logging.getLogger("bgmatte_app").info("기록 확인")
        for h in logging.getLogger().handlers:
            h.flush()
    finally:
        out, err = sys.stdout, sys.stderr
        logging.getLogger().handlers = saved_root
        for stream in (out, err):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
    text = log_file.read_text(encoding="utf-8")
    assert "기록 확인" in text and "stdout 에 출력" in text and "stderr 출력" in text


def test_fatal_box_falls_back_to_stderr_off_windows(capsys):
    from bgmatte_app import __main__ as entry

    if sys.platform == "win32":
        pytest.skip("윈도우에서는 실제 메시지 상자가 뜹니다")
    entry.fatal_box("BG Matte", "시작하지 못했습니다")
    assert "시작하지 못했습니다" in capsys.readouterr().err

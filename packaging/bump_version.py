"""버전 올리기: bgmatte_app/__init__.py 의 __version__ 한 곳만 고칩니다.

  python packaging/bump_version.py patch    # 1.0.0 → 1.0.1  (버그 수정)
  python packaging/bump_version.py minor    # 1.0.0 → 1.1.0  (기능 추가)
  python packaging/bump_version.py major    # 1.0.0 → 2.0.0
  python packaging/bump_version.py 1.4.2    # 직접 지정
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "bgmatte_app" / "__init__.py"
PATTERN = re.compile(r'^__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', re.M)


def next_version(current: str, how: str) -> str:
    if re.fullmatch(r"\d+\.\d+\.\d+", how):
        return how
    major, minor, patch = (int(x) for x in current.split("."))
    if how == "major":
        return f"{major + 1}.0.0"
    if how == "minor":
        return f"{major}.{minor + 1}.0"
    if how == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"알 수 없는 값: {how} (patch | minor | major | x.y.z)")


def bump(how: str, path: Path = INIT) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    match = PATTERN.search(text)
    if match is None:
        raise RuntimeError(f"{path} 에서 __version__ 을 찾지 못했습니다")
    old = ".".join(match.groups())
    new = next_version(old, how)
    path.write_text(PATTERN.sub(f'__version__ = "{new}"', text, count=1), encoding="utf-8")
    return old, new


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        old, new = bump(argv[1])
    except (ValueError, RuntimeError) as exc:
        print(exc)
        return 1
    print(f"{old} → {new}")
    print(f"다음: git commit -am 'release: v{new}' && git tag v{new} && git push origin HEAD v{new}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

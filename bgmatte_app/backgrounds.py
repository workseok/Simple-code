"""합성 배경 이미지 목록과 번호 매기기.

backgrounds/ 폴더의 이미지를 파일명 순(숫자는 크기순: 2 < 10)으로 정렬해
1번부터 번호를 붙입니다. 순서를 직접 정하려면 파일명 앞에 01_, 02_ 를 붙이면 됩니다.
폴더가 없거나 비어 있고 기존 ai_background.png가 있으면 그 파일 하나를 1번으로 씁니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(frozen=True)
class BackgroundItem:
    number: int  # 1부터 시작
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


def _natural_key(name: str):
    # re.split은 항상 [문자열, 숫자, 문자열, ...] 순서로 나오므로 서로 비교해도 안전합니다.
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", name)]


def scan_backgrounds(folder: Path, legacy: Optional[Path] = None) -> List[BackgroundItem]:
    files: List[Path] = []
    if folder.is_dir():
        files = [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
        ]
        files.sort(key=lambda p: _natural_key(p.name))
    if not files and legacy is not None and legacy.is_file():
        files = [legacy]
    return [BackgroundItem(number=i, path=p) for i, p in enumerate(files, start=1)]

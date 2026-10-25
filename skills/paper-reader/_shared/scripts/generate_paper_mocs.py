#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_SHARED_DIR = Path(__file__).resolve().parent
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from moc_builder import build_tree_mocs
from user_config import moc_filename_prefix, obsidian_vault_path, paper_notes_dir, paths_config
from venue_label import venue_label

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)


def _frontmatter_value(frontmatter: str, key: str) -> str:
    match = re.search(rf"^{key}:\s*(.*)$", frontmatter, re.M)
    return match.group(1).strip().strip("\"'") if match else ""


def paper_label(note: Path) -> str:
    """Note stem plus its venue label, e.g. ``Accel-Sim (ISPASS'20)``; the bare stem when there is none."""
    try:
        match = _FRONTMATTER.match(note.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        match = None
    if not match:
        return note.stem
    label = venue_label(_frontmatter_value(match.group(1), "venue"), _frontmatter_value(match.group(1), "year"))
    return f"{note.stem} ({label})" if label else note.stem


def main() -> int:
    summary = build_tree_mocs(
        vault_root=obsidian_vault_path(),
        root_dir=paper_notes_dir(),
        title_prefix="论文目录页",
        intro="用于浏览论文笔记、分类目录和子主题入口。",
        exclude_dir_names={paths_config()["concepts_folder"], "_inbox", "00_assets"},
        moc_filename_prefix=moc_filename_prefix(),
        note_label=paper_label,
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

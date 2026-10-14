#!/usr/bin/env python3
"""Check that every intended link in a paper note resolves.

Covers in-note heading links ``[[#标题|…]]``, block links ``[[#^id|…]]``,
duplicate ``^id`` anchors, wikilinks to other notes / concepts, ``![[…]]``
embeds, unescaped alias pipes inside table rows, and bare "Figure N /
Table N / 机制N / Insight N / 贡献N" mentions that should have been links.
Code fences, ``$$`` math blocks and inline code are not prose and are skipped.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared" / "scripts"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
ANCHOR = re.compile(r"(?:^|\s)\^([A-Za-z0-9-]+)\s*$")
WIKILINK = re.compile(r"(!?)\[\[([^\]]+)\]\]")
MD_IMAGE_OR_LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
INLINE_CODE = re.compile(r"`[^`]*`")
INLINE_MATH = re.compile(r"\$[^$\n]+\$")
BARE_REF = re.compile(
    r"(?<![\w#^])(?:Figure|Fig\.)\s?\d+[a-z]?\b"
    r"|(?<![\w#^])Table\s(?:[IVXLC]+|\d+)\b"
    r"|(?<![\w#^])Insight\s\d+"
    r"|(?:机制|贡献)\d+"
)
TABLE_TITLE = re.compile(r"^\*\*Table\b")


def _prose_lines(lines: list[str]) -> list[tuple[int, str]]:
    """(line number, text) for lines outside frontmatter, code fences, ``$$`` blocks and comments."""
    out: list[tuple[int, str]] = []
    fence: str | None = None
    in_math = in_comment = False
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for idx in range(start, len(lines)):
        line = lines[idx]
        if fence:
            if line.strip().startswith(fence[0] * len(fence)):
                fence = None
            continue
        match = FENCE.match(line)
        if match:
            fence = match.group(1)
            continue
        if line.strip() == "$$":
            in_math = not in_math
            continue
        if in_math:
            continue
        if in_comment or line.lstrip().startswith("<!--"):
            in_comment = "-->" not in line
            continue
        out.append((idx + 1, line))
    return out


def _resolve_note(target: str, note_path: Path, root: Path, names: dict[str, list[Path]]) -> bool:
    target = target.strip()
    if not target:
        return True
    if "/" in target:
        candidate = target if Path(target).suffix else target + ".md"
        if (note_path.parent / candidate).exists() or (root / candidate).exists():
            return True
        return any(str(p).endswith("/" + candidate) for paths in names.values() for p in paths)
    key = target if Path(target).suffix else target + ".md"
    return key in names


def check(text: str, note_path: Path, root: Path) -> list[tuple[int, str]]:
    note_path = Path(note_path)
    root = Path(root)
    lines = text.splitlines()
    prose = _prose_lines(lines)
    problems: list[tuple[int, str]] = []

    headings = set()
    anchors: dict[str, int] = {}
    for lineno, line in prose:
        heading = HEADING.match(line)
        if heading:
            headings.add(heading.group(2).strip())
            continue
        anchor = ANCHOR.search(line)
        if anchor:
            anchor_id = anchor.group(1)
            if anchor_id in anchors:
                problems.append((lineno, f"重复锚点 ^{anchor_id}（首次定义在第 {anchors[anchor_id]} 行）"))
            else:
                anchors[anchor_id] = lineno

    names: dict[str, list[Path]] = {}
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file():
                names.setdefault(path.name, []).append(path)

    for lineno, line in prose:
        is_table_row = line.lstrip().startswith("|")
        for match in WIKILINK.finditer(line):
            embed, inner = match.group(1), match.group(2)
            if is_table_row and re.search(r"(?<!\\)\|", inner):
                problems.append((lineno, f"表格行内 wikilink 别名要写成 `\\|`：[[{inner}]]"))
            target = re.split(r"\\?\|", inner, maxsplit=1)[0]
            if target.startswith("#"):
                ref = target[1:]
                if ref.startswith("^"):
                    if ref[1:] not in anchors:
                        problems.append((lineno, f"块链接指向不存在的锚点 {ref}"))
                else:
                    for part in ref.split("#"):
                        if part.strip() not in headings:
                            problems.append((lineno, f"标题链接找不到逐字一致的标题：{part.strip()}"))
                continue
            page = target.split("#", 1)[0]
            if embed and page:
                if not ((note_path.parent / page).exists() or (root / page).exists() or Path(page).name in names):
                    problems.append((lineno, f"嵌入的文件不存在：{page}"))
            elif not _resolve_note(page, note_path, root, names):
                problems.append((lineno, f"wikilink 找不到对应笔记：{page}"))

        if HEADING.match(line) or TABLE_TITLE.match(line.strip()):
            continue
        stripped = WIKILINK.sub(" ", line)
        stripped = MD_IMAGE_OR_LINK.sub(" ", stripped)
        stripped = INLINE_CODE.sub(" ", stripped)
        stripped = INLINE_MATH.sub(" ", stripped)
        for ref in BARE_REF.finditer(stripped):
            problems.append((lineno, f"裸引用未写成跳转链接：{ref.group(0)}"))

    problems.sort(key=lambda item: item[0])
    return problems


def _default_root() -> Path:
    from user_config import obsidian_vault_path

    return obsidian_vault_path()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notes", nargs="+", help="paper note Markdown files")
    parser.add_argument("--root", help="directory searched for wikilink targets (default: obsidian_vault from user config)")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser() if args.root else _default_root()
    status = 0
    for name in args.notes:
        path = Path(name)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        problems = check(text, path, root)
        for lineno, message in problems:
            print(f"{path}:{lineno}: {message}")
        if problems:
            status = 1
        else:
            print(f"{path}: OK")
    return status


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Add venue labels such as ``MICRO'25`` to existing paper notes.

For each paper note the ``venue:`` frontmatter line is normalized to its
abbreviation and the first ``#`` heading gets `` (MICRO'25)`` appended; a label
already there is replaced, so the script can be re-run. Notes whose venue is
not recognized are reported and left untouched. Without ``--apply`` nothing is
written. File names are never changed, so wikilinks keep working.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import moc_filename_prefix, paper_notes_dir, paths_config  # noqa: E402
from venue_label import short_venue, venue_label  # noqa: E402

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_EXISTING_LABEL = re.compile(r" \([^()]*'\d\d\)$")
_YEAR_IN_TEXT = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")


def _value(frontmatter: str, key: str) -> str | None:
    match = re.search(rf"^{key}:[ \t]*(.*)$", frontmatter, re.M)
    return match.group(1).strip().strip("\"'") if match else None


def relabel(text: str) -> tuple[str, str]:
    """(new text, status); status is updated, unchanged, unknown or no-frontmatter."""
    match = _FRONTMATTER.match(text)
    if not match:
        return text, "no-frontmatter"
    frontmatter = match.group(1)
    venue = _value(frontmatter, "venue")
    year = _value(frontmatter, "year")
    label = venue_label(venue, year)
    if label is None:
        return text, "unknown"

    new_frontmatter = re.sub(r"^venue:.*$", f"venue: {short_venue(venue)}", frontmatter, count=1, flags=re.M)
    if not year:
        found = _YEAR_IN_TEXT.search(venue or "")
        new_frontmatter = re.sub(r"^(venue:.*)$", rf"\1\nyear: {found.group(1)}", new_frontmatter, count=1, flags=re.M)

    body = text[match.end() :]
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines[i] = _EXISTING_LABEL.sub("", line.rstrip()) + f" ({label})"
            break
    new_text = f"---\n{new_frontmatter}\n---\n" + "\n".join(lines)
    return new_text, ("unchanged" if new_text == text else "updated")


def _paper_notes(root: Path) -> list[Path]:
    skip_dirs = {paths_config()["concepts_folder"], "00_assets"}
    prefix = moc_filename_prefix()
    return sorted(
        path
        for path in root.rglob("*.md")
        if not skip_dirs.intersection(path.relative_to(root).parts) and not path.name.startswith(prefix)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", help="paper notes directory (default: PaperNotes from user config)")
    parser.add_argument("--apply", action="store_true", help="write the changes; without it only report them")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser() if args.root else paper_notes_dir()
    counts: dict[str, int] = {}
    for path in _paper_notes(root):
        text = path.read_text(encoding="utf-8")
        new_text, status = relabel(text)
        counts[status] = counts.get(status, 0) + 1
        match = _FRONTMATTER.match(text)
        frontmatter = match.group(1) if match else ""
        venue = _value(frontmatter, "venue")
        label = venue_label(venue, _value(frontmatter, "year")) or "-"
        print(f"{status:14} {label:18} venue={venue!r:40} {path.relative_to(root)}")
        if args.apply and status == "updated":
            path.write_text(new_text, encoding="utf-8")
    action = "已写入" if args.apply else "预览（加 --apply 才写入）"
    print(f"\n{action}：" + "，".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

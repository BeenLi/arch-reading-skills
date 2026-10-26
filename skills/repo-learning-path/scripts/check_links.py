#!/usr/bin/env python3
"""Check relative links in learning notes.

For every Markdown link or image whose target is a relative path:
  - the target file or directory must exist;
  - a #L<n> or #L<n>-L<m> anchor must fall inside the file's line count.
External links (http, https, mailto) and pure #section anchors are skipped.

Usage: check_links.py <file-or-dir> [...]
Exit status is 1 if any link is broken.
"""
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINE_ANCHOR_RE = re.compile(r"^L(\d+)(?:-L?(\d+))?$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def iter_links(text):
    """Yield (line_no, target) for links outside fenced code blocks."""
    in_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in LINK_RE.finditer(line):
            yield no, m.group(1)


def line_count(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def check_file(md):
    errors = []
    text = md.read_text(encoding="utf-8", errors="replace")
    for no, target in iter_links(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
            continue
        path_part, _, anchor = target.partition("#")
        dest = (md.parent / path_part).resolve()
        if not dest.exists():
            errors.append(f"{md}:{no}: missing target {target}")
            continue
        m = LINE_ANCHOR_RE.match(anchor) if anchor else None
        if m and dest.is_file():
            n = line_count(dest)
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            if lo < 1 or hi < lo or (n is not None and hi > n):
                errors.append(f"{md}:{no}: line anchor #{anchor} out of range "
                              f"({path_part} has {n} lines)")
    return errors


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    files = []
    for arg in argv[1:]:
        p = Path(arg)
        files += sorted(p.rglob("*.md")) if p.is_dir() else [p]
    errors = []
    for md in files:
        errors += check_file(md)
    for e in errors:
        print(e)
    print(f"checked {len(files)} file(s): {len(errors)} broken link(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

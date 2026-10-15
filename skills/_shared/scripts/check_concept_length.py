#!/usr/bin/env python3
"""Check a concept note's length against the two-part budget.

The worked example (``## 直观例子`` up to the next ``##`` heading) and the
other sections are counted separately, because only a step-by-step derivation
may make a concept long. Frontmatter and Mermaid source are not counted: the
template requires a figure in the example, and a diagram's source lines say
nothing about how much prose the note has. A matplotlib figure is one
``![[…]]`` line and counts as one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXAMPLE_LIMIT = 100
OTHER_LIMIT = 90
EXAMPLE_HEADING = "## 直观例子"
H2 = re.compile(r"^##\s")
MERMAID_OPEN = re.compile(r"^\s*```mermaid\s*$")
FENCE_CLOSE = re.compile(r"^\s*```\s*$")


def _counted_lines(text: str) -> list[str]:
    """Lines after the frontmatter, with Mermaid blocks (fences included) removed."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1 :]
                break
    kept: list[str] = []
    in_mermaid = False
    for line in lines:
        if in_mermaid:
            in_mermaid = not FENCE_CLOSE.match(line)
            continue
        if MERMAID_OPEN.match(line):
            in_mermaid = True
            continue
        kept.append(line)
    return kept


def measure(text: str) -> tuple[int, int] | None:
    """(example lines, other lines), or None when the note has no ``## 直观例子``."""
    lines = _counted_lines(text)
    start = next((i for i, line in enumerate(lines) if line.strip() == EXAMPLE_HEADING), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if H2.match(lines[i])), len(lines))
    example = end - start
    return example, len(lines) - example


def check(text: str) -> list[str]:
    counts = measure(text)
    if counts is None:
        return [f"缺少 `{EXAMPLE_HEADING}` 段"]
    example, other = counts
    problems = []
    if example > EXAMPLE_LIMIT:
        problems.append(f"直观例子 {example} 行，超过上限 {EXAMPLE_LIMIT} 行")
    if other > OTHER_LIMIT:
        problems.append(f"其他段 {other} 行，超过上限 {OTHER_LIMIT} 行，请收敛")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notes", nargs="+", help="concept note Markdown files")
    args = parser.parse_args(argv)

    status = 0
    for name in args.notes:
        path = Path(name)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        problems = check(text)
        for message in problems:
            print(f"{path}: {message}")
        if problems:
            status = 1
        else:
            example, other = measure(text)
            print(f"{path}: OK（直观例子 {example} 行，其他段 {other} 行）")
    return status


if __name__ == "__main__":
    sys.exit(main())

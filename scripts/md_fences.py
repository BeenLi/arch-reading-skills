"""Fenced code blocks in Markdown, following the CommonMark closing rules.

Shared by ``check_doc.py`` and ``repo_facts.py`` so both agree on what is code.
A block opens with three or more backticks or tildes (any indentation, so fences
inside list items count). It closes on a line made only of the same character,
at least as long as the opener, with no info string. A shorter or different
fence inside, such as a ```mermaid example quoted in a ````markdown block, is content.
"""

from __future__ import annotations

import re

OPEN = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


def fence_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return ``(open_index, close_index, info)`` per top-level block.

    ``close_index`` is ``len(lines)`` for a block left open at the end of the file.
    """
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        m = OPEN.match(lines[i])
        if not m or (m.group(1)[0] == "`" and "`" in m.group(2)):
            i += 1
            continue
        char, width = m.group(1)[0], len(m.group(1))
        j = i + 1
        while j < len(lines):
            c = CLOSE.match(lines[j])
            if c and c.group(1)[0] == char and len(c.group(1)) >= width:
                break
            j += 1
        blocks.append((i, j, m.group(2).strip()))
        i = j + 1
    return blocks


def info_word(info: str) -> str:
    """The language tag of a fence, lowercased: ``"```Bash title=x"`` → ``"bash"``."""
    words = info.split()
    return words[0].lower() if words else ""

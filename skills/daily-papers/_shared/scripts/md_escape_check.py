#!/usr/bin/env python3
"""Find / fix Obsidian Markdown text that should be backslash-escaped.

Covers the most common rendering bugs in generated notes:

* array-index text such as ``C[i][j]`` / ``addr[42:39]`` -> ``C\\[i\\]\\[j\\]``
  (otherwise parsed as reference-style links);
* literal dollar signs such as ``$200`` / ``$HOME`` -> ``\\$200``
  (two of them on one line turn the text between into inline LaTeX).
* Obsidian tags triggered by accident, such as ``#SMs`` / ``#include`` ->
  ``\\#SMs`` (a ``#`` at line start or after whitespace, followed by a
  non-numeric tag name, becomes a clickable tag). Intentional tags are kept;
  see ``is_intentional_tag``.
* angle-bracket placeholders such as ``<note-name>`` / ``<T>`` ->
  ``\\<note-name\\>`` (parsed as an unknown HTML tag and swallowed). Real
  HTML such as ``<br>`` / ``<sub>`` is kept; see ``is_html_tag``.
* intra-word asterisks such as ``a*b*c`` / ``7*MEM`` -> ``a\\*b\\*c``
  (otherwise italic).
* ``|`` inside inline code or a wikilink in a table row, such as
  ``ccb ping <agent|all>`` in backticks / ``[[Note|alias]]`` -> ``\\|``
  (otherwise it splits the cell).

Code (fenced / inline), math (``$...$`` / ``$$...$$``), wikilinks, Markdown
links, URLs, HTML comments and YAML frontmatter are left untouched. The fix is
idempotent: already-escaped text is never escaped twice.

See the "Markdown 特殊符号转义" section of the vault ``AGENTS.md`` for the full
rule set. ``==highlight==``, ``~~strike~~``, ``%%comment%%`` and trailing
``^block-id`` are left alone: in the vault they are almost always intentional.

Usage::

    python3 md_escape_check.py PATH [PATH ...]          # report, exit 1 on hits
    python3 md_escape_check.py --fix PATH [PATH ...]    # rewrite files in place

PATH may be a Markdown file or a directory (searched recursively for *.md,
skipping auto-generated ``_index_*.md``).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A fence closes only on the same character, at least as long: a ````markdown
# block may contain a ```mermaid block. Group 2 is the opening run.
FENCED = r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\2[`~]*[ \t]*$"

PROTECTED = re.compile(
    r"(" + FENCED +                                            # fenced code block
    r"|```.*?```"                                              # ```inline fence```
    r"|``(?:[^`\n]|`(?!`))+?``"                               # ``inline `code` ``
    r"|`[^`\n]+`"                                              # `inline code`
    r"|\$\$.*?\$\$"                                            # display math
    r"|(?<![\\\w])\$(?=\S)[^$\n]+?(?<=\S)\$(?![\w$])"          # inline math $x$
    r"|!?\[\[[^\n]+?\]\]"                                      # wikilink / embed
    r"|<!--.*?-->"                                             # html comment
    r"|\A---\n.*?\n---\n"                                      # frontmatter
    r"|\[[^\]\n]*\]\([^)\n]*\)"                                # [text](url)
    r"|https?://\S+)",                                         # bare url
    re.S | re.M,
)
FENCED_BLOCK = re.compile(FENCED.replace("\\2", "\\1"), re.S | re.M)

# `[...]` directly after an identifier char, `)` or another `]`: C[i][j], f(x)[0]
INDEX = re.compile(r"(?<=[A-Za-z0-9_\)\]])\[([^\[\]\n]{1,24})\](?!\()")
# a `$` that starts a word/number and is not already escaped: $200, $HOME
DOLLAR = re.compile(r"(?<!\\)\$(?=[0-9A-Za-z])")
# Obsidian tag: `#` at line start or after whitespace, then [\w/-]+ that is
# not purely numeric (`#1` is not a tag). `# Heading` has a space, so no match.
TAG = re.compile(r"(?:(?<=^)|(?<=\s))#(?!\d+(?![\w/-]))([\w/-]+)", re.M)
# `<name ...>` / `</name>` with an ASCII tag name; `<https://..>` and `a < b` do not match
ANGLE = re.compile(r"(?<!\\)<(/?)([A-Za-z][\w-]*)((?:\s[^<>\n]*)?)>")
# `*` between two word characters: a*b*c, 7*MEM (`**bold**` never matches)
STAR = re.compile(r"(?<=[A-Za-z0-9\)\]])(?<!\\)\*(?=[A-Za-z0-9\(])")
# table rows, and the code spans / wikilinks inside them that may hold a raw `|`
TABLE_ROW = re.compile(r"^[ \t]*\|.*$", re.M)
TABLE_SPAN = re.compile(r"`[^`\n]+`|!?\[\[[^\]\n]+\]\]")
RAW_PIPE = re.compile(r"(?<!\\)\|")


# Inline tags the vault uses on purpose. Everything else that looks like a tag
# in body text is treated as accidental (`#SMs` = "number of SMs") and escaped.
# Add a namespace / name here when a new tag scheme is introduced.
INTENTIONAL_TAG_PREFIXES = (
    "t/",  # task time estimates in 003-daily/任务清单.md: #t/2h, #t/halfday
)
INTENTIONAL_TAGS = frozenset({
    "book-notes",
})


def is_intentional_tag(tag: str) -> bool:
    """Return True if ``#<tag>`` is a real Obsidian tag that must stay a tag.

    ``tag`` is the name without the leading ``#``, e.g. ``"t/2h"`` or ``"SMs"``.
    Whitelist only: guessing from the tag's shape would misfire both ways
    (lower-case ``#include`` is code, CamelCase could be a real tag).
    """
    return tag in INTENTIONAL_TAGS or tag.startswith(INTENTIONAL_TAG_PREFIXES)


# HTML that notes actually use, plus common inline / layout tags. Compared
# lower-case: HTML tag names are case-insensitive (<BR> is a line break too).
HTML_TAGS = frozenset({
    "a", "abbr", "b", "big", "blockquote", "br", "caption", "center", "cite", "code",
    "col", "colgroup", "dd", "del", "details", "div", "dl", "dt", "em", "figcaption",
    "figure", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "iframe", "img",
    "ins", "kbd", "li", "mark", "ol", "p", "picture", "pre", "q", "s", "samp", "small",
    "source", "span", "strike", "strong", "sub", "summary", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "u", "ul", "var", "video", "audio", "wbr",
})


def is_html_tag(name: str) -> bool:
    """Return True if ``<name>`` is real HTML that Obsidian should render.

    ``name`` is the tag name without ``<``, ``/`` or attributes, e.g. ``"br"``,
    ``"sub"``, ``"note-name"``, ``"T"``. False means the angle brackets are a
    placeholder in prose and get escaped.
    """
    return name.lower() in HTML_TAGS


def _is_hit(pattern: re.Pattern, m: re.Match) -> bool:
    if pattern is TAG:
        return not is_intentional_tag(m.group(1))
    if pattern is ANGLE:
        return not is_html_tag(m.group(2))
    return True


def _fix_plain(text: str) -> str:
    text = INDEX.sub(lambda m: "\\[" + m.group(1) + "\\]", text)
    text = DOLLAR.sub(r"\\$", text)
    text = STAR.sub(r"\\*", text)
    text = ANGLE.sub(
        lambda m: m.group(0) if not _is_hit(ANGLE, m) else "\\" + m.group(0)[:-1] + "\\>",
        text,
    )
    return TAG.sub(
        lambda m: m.group(0) if not _is_hit(TAG, m) else "\\" + m.group(0),
        text,
    )


def _table_pipes(source: str):
    """Yield (start, end) of raw `|` inside code spans / wikilinks of table rows."""
    fences = [(m.start(), m.end()) for m in FENCED_BLOCK.finditer(source)]
    for row in TABLE_ROW.finditer(source):
        if any(start <= row.start() < end for start, end in fences):
            continue
        for span in TABLE_SPAN.finditer(row.group(0)):
            base = row.start() + span.start()
            for pipe in RAW_PIPE.finditer(span.group(0)):
                yield base + pipe.start(), base + pipe.end()


def _plain_segments(source: str):
    """Yield (offset, text, is_plain) chunks covering the whole source."""
    pos = 0
    for match in PROTECTED.finditer(source):
        if match.start() > pos:
            yield pos, source[pos:match.start()], True
        yield match.start(), match.group(0), False
        pos = match.end()
    if pos < len(source):
        yield pos, source[pos:], True


def check(source: str) -> list[tuple[int, str]]:
    """Return (line_number, context) for every unescaped occurrence."""
    hits = []
    for offset, text, plain in _plain_segments(source):
        if not plain:
            continue
        for pattern in (INDEX, DOLLAR, TAG, ANGLE, STAR):
            for m in pattern.finditer(text):
                if not _is_hit(pattern, m):
                    continue
                line = source.count("\n", 0, offset + m.start()) + 1
                context = text[max(0, m.start() - 15): m.end() + 5].replace("\n", " ")
                hits.append((line, context))
    for start, end in _table_pipes(source):
        line = source.count("\n", 0, start) + 1
        context = source[max(0, start - 15): end + 5].replace("\n", " ")
        hits.append((line, context))
    return sorted(hits)


def fix(source: str) -> str:
    """Return source with every reported occurrence escaped."""
    # table pipes first: they sit inside code / wikilinks, which the plain-text pass skips
    pipes = list(_table_pipes(source))
    for start, _ in reversed(pipes):
        source = source[:start] + "\\" + source[start:]
    return "".join(
        _fix_plain(text) if plain else text
        for _, text, plain in _plain_segments(source)
    )


def iter_markdown(paths: list[str]):
    """Yield each Markdown file once; directories skip hidden folders
    (.obsidian, .agents …) and generated ``_index_*.md``."""
    seen = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found = sorted(
                p for p in path.rglob("*.md")
                if not p.name.startswith("_index_")
                and not any(part.startswith(".") for part in p.relative_to(path).parts)
            )
        else:
            found = [path]
        for p in found:
            key = p.resolve()  # CLAUDE.md -> AGENTS.md is one file
            if key not in seen:
                seen.add(key)
                yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="Markdown files or directories")
    parser.add_argument("--fix", action="store_true", help="rewrite files in place")
    args = parser.parse_args(argv)

    total = 0
    for path in iter_markdown(args.paths):
        source = path.read_text(encoding="utf-8")
        hits = check(source)
        if not hits:
            continue
        total += len(hits)
        print(f"== {path}  ({len(hits)})")
        for line, context in hits:
            print(f"   L{line}: {context}")
        if args.fix:
            path.write_text(fix(source), encoding="utf-8")

    if args.fix:
        print(f"fixed {total} occurrence(s)" if total else "nothing to fix")
        return 0
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

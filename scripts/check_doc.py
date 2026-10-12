#!/usr/bin/env python3
"""Validate an architecture-and-usage document against references/doc-format.md.

Usage::

    python3 check_doc.py <doc.md> [--name NAME]

Prints one ``OK``/``FAIL`` line per rule and exits 1 when anything failed.
The checks mirror the human contract one-to-one; change both together.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (number, accepted titles). Section 1 is matched by prefix; 6/8/11 accept either side of the slash.
SECTION_TITLES: list[tuple[int, tuple[str, ...]]] = [
    (1, ("一句话理解",)),
    (2, ("核心心智模型",)),
    (3, ("总体架构",)),
    (4, ("项目如何工作",)),
    (5, ("安装与启动",)),
    (6, ("常用命令 / 使用指南", "常用命令", "使用指南")),
    (7, ("配置项与环境变量",)),
    (8, ("常见使用场景 / 推荐工作流", "常见使用场景", "推荐工作流")),
    (9, ("源码入口索引",)),
    (10, ("排错指南",)),
    (11, ("开发者视角的模块关系 / 维护注意点", "开发者视角的模块关系", "维护注意点")),
    (12, ("已知不确定点",)),
]
TABLE_HEADERS: dict[int, list[str]] = {
    2: ["概念", "来源", "含义"],
    3: ["组件", "关键文件", "职责"],
    9: ["想了解", "优先看"],
    10: ["现象", "优先检查", "依据"],
}
HEADER_PREFIXES = ("源仓库：", "本次分析的本地路径：", "本次分析的提交：")
MACHINE_PREFIXES = ("/Users/", "/home/", "C:\\")
MIN_LINES, MAX_LINES = 250, 800
MIN_MERMAID, MAX_MERMAID = 2, 5
MIN_MODEL_ROWS, MAX_MODEL_ROWS = 6, 12

H2 = re.compile(r"^## (?:(\d+)\. (.+)|(附录.*))$")
BACKTICK = re.compile(r"`([^`\n]+)`")
TASK = re.compile(r"(?m)^\s*- \[[ xX]\]")
MERMAID = re.compile(r"(?m)^```mermaid")


def _table_header_pattern(columns: list[str]) -> re.Pattern[str]:
    return re.compile(r"(?m)^\|\s*" + r"\s*\|\s*".join(re.escape(c) for c in columns) + r"\s*\|$")


PATH_WORD = re.compile(r"(?:/|\.[A-Za-z][A-Za-z0-9]{0,7}$)")


def _is_source_token(token: str) -> bool:
    """A backtick token counts as a source when any word in it looks like a repo path.

    `src/main.py`, `README.md`, `python3 src/main.py --init` count; `vLLM`, `1.0`, `e.g.` do not.
    """
    for word in token.split():
        if word.startswith(MACHINE_PREFIXES):
            continue
        if PATH_WORD.search(word):
            return True
    return False


def _split_sections(lines: list[str]) -> tuple[list[tuple[int | None, str, int]], list[str]]:
    """Return ([(number or None for appendix, title, line_index)], failures)."""
    found: list[tuple[int | None, str, int]] = []
    failures: list[str] = []
    for i, line in enumerate(lines):
        m = H2.match(line)
        if not m:
            if line.startswith("## "):
                failures.append(f"多余的 H2：第 {i + 1} 行 `{line}` 既不是编号节也不是附录")
            continue
        if m.group(3):
            found.append((None, m.group(3), i))
        else:
            found.append((int(m.group(1)), m.group(2).strip(), i))
    return found, failures


def check(text: str, name: str | None = None) -> list[str]:
    failures: list[str] = []
    lines = text.splitlines()

    # --- header ---------------------------------------------------------
    non_empty = [(i, l) for i, l in enumerate(lines) if l.strip()]
    header_line_indexes: set[int] = set()
    if not non_empty or not non_empty[0][1].startswith("> ") or "说明书" not in non_empty[0][1]:
        failures.append("头部：第一个非空行必须是含“说明书”的引用块")
    else:
        header_line_indexes.add(non_empty[0][0])
        if name and name not in non_empty[0][1]:
            failures.append(f"名字：引用块未包含 `{name}`")
    following = non_empty[1:4]
    for prefix, (idx, line) in zip(HEADER_PREFIXES, following):
        if line.strip().startswith(prefix):
            header_line_indexes.add(idx)
        else:
            failures.append(f"头部：缺少以 `{prefix}` 开头的元信息行（实际：`{line.strip()[:30]}`）")
    if len(following) < 3:
        failures.append("头部：三行元信息不完整")

    # --- sections -------------------------------------------------------
    found, split_failures = _split_sections(lines)
    failures += split_failures
    numbered = [(n, t, i) for n, t, i in found if n is not None]
    appendices = [(n, t, i) for n, t, i in found if n is None]
    if [n for n, _, _ in numbered] != list(range(1, 13)):
        failures.append(f"章节：编号节必须恰好是 1..12 顺序出现，实际 {[n for n, _, _ in numbered]}")
    titles = {n: t for n, t, _ in numbered}
    for number, accepted in SECTION_TITLES:
        title = titles.get(number)
        if title is None:
            continue
        if number == 1:
            if not title.startswith(accepted[0]):
                failures.append(f"第 1 节：标题应以“一句话理解”开头，实际 `{title}`")
            elif name and name not in title:
                failures.append(f"名字：第 1 节标题未包含 `{name}`")
        elif title not in accepted:
            failures.append(f"第 {number} 节：标题应为 {' / '.join(accepted)} 之一，实际 `{title}`")
    if appendices and numbered and appendices[0][2] < numbered[-1][2]:
        failures.append("附录：必须出现在第 12 节之后")

    # section slices (from an H2 to the next H2 of any kind)
    h2_positions = sorted(i for _, _, i in found)
    def section_text(start: int) -> str:
        later = [i for i in h2_positions if i > start]
        end = later[0] if later else len(lines)
        return "\n".join(lines[start:end])
    bodies = {n: section_text(i) for n, _, i in numbered}

    for number, columns in TABLE_HEADERS.items():
        if number in bodies and not _table_header_pattern(columns).search(bodies[number]):
            failures.append(f"第 {number} 节：缺少表头 `| {' | '.join(columns)} |`")
    if 2 in bodies:
        rows = [l for l in bodies[2].splitlines() if l.startswith("|")]
        data_rows = max(len(rows) - 2, 0)  # 去掉表头与分隔行
        if not MIN_MODEL_ROWS <= data_rows <= MAX_MODEL_ROWS:
            failures.append(f"第 2 节：心智模型表需要 {MIN_MODEL_ROWS}–{MAX_MODEL_ROWS} 行数据行，实际 {data_rows}")
    if 4 in bodies and len(re.findall(r"(?m)^### 4\.", bodies[4])) < 2:
        failures.append("第 4 节：至少两个 `### 4.x` 主链路小节")
    if 4 in bodies:
        for step in re.findall(r"(?m)^\s*\d+\. .+$", bodies[4]):
            if not any(_is_source_token(tok) for tok in BACKTICK.findall(step)):
                failures.append(f"第 4 节：步骤“{step.strip()[:30]}”未引用文件")
    if 12 in bodies and len(re.findall(r"(?m)^\s*(?:-|\d+\.) ", bodies[12])) < 2:
        failures.append("第 12 节：至少两条列表项")
    for number, body in bodies.items():
        if number == 12:
            continue
        if not any(_is_source_token(tok) for tok in BACKTICK.findall(body)):
            failures.append(f"第 {number} 节：没有反引号包裹的来源路径")

    # --- global ---------------------------------------------------------
    mermaid = len(MERMAID.findall(text))
    if not MIN_MERMAID <= mermaid <= MAX_MERMAID:
        failures.append(f"Mermaid：需要 {MIN_MERMAID}–{MAX_MERMAID} 张，实际 {mermaid}")
    if not MIN_LINES <= len(lines) <= MAX_LINES:
        failures.append(f"长度：需要 {MIN_LINES}–{MAX_LINES} 行，实际 {len(lines)}")
    if TASK.search(text):
        failures.append("禁用：正文含 Obsidian task 语法 `- [ ]` / `- [x]`")
    for i, line in enumerate(lines):
        if i in header_line_indexes:
            continue
        if any(p in line for p in MACHINE_PREFIXES):
            failures.append(f"机器专属路径：第 {i + 1} 行 `{line.strip()[:60]}`")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an architecture-and-usage document.")
    parser.add_argument("doc", help="path to the Markdown document")
    parser.add_argument("--name", help="project name that must appear in the lead and section 1")
    args = parser.parse_args(argv)
    text = Path(args.doc).read_text(encoding="utf-8")
    failures = check(text, args.name)
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        print(f"{len(failures)} failure(s)")
        return 1
    print("OK 头部三要素 / 12 节顺序与标题 / 表头 / 心智模型表行数 / 第 4 节步骤引用 / Mermaid 数量 / 长度 / 来源标注 / 无 task 语法 / 无机器路径")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Collect deterministic facts about a repository and print them as Markdown.

Usage::

    python3 repo_facts.py <repo> [--depth N] [--max-entries N]

The output is the raw material for an architecture-and-usage document: git
remote / HEAD, a shallow directory tree, file counts by extension, entry-point
candidates, commands quoted in the README, config files and existing docs.
Nothing here interprets the code; that is the agent's job.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".claude", ".superpowers",
}
ENTRY_FILES = (
    "README", "SKILL.md", "ARCHITECTURE.md", "pyproject.toml", "setup.py",
    "package.json", "Makefile", "Dockerfile",
)
ENTRY_DIRS = ("bin", "scripts", "src", "tests")
COMMAND_PREFIXES = ("python3 ", "python ", "npm ", "pnpm ", "make ", "bash ", "pip ", "cargo ", "go ")
CONFIG_SUFFIXES = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"}
LOCK_MARKERS = ("lock",)
FENCE = re.compile(r"^\s*```")


def _git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out or None


def _walk(repo: Path, depth: int, max_entries: int) -> list[str]:
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        rel = Path(dirpath).relative_to(repo)
        level = len(rel.parts)
        if level > depth:
            dirnames[:] = []
            continue
        if level > 0:
            lines.append(f"{'  ' * (level - 1)}{rel.as_posix()}/  ({len(filenames)} files)")
        if level == depth:
            dirnames[:] = []
        if len(lines) >= max_entries:
            lines.append("…(truncated)")
            break
    return lines


def _ext_counts(repo: Path) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for name in filenames:
            counter[Path(name).suffix or "(none)"] += 1
    return counter.most_common(10)


def _entry_points(repo: Path) -> list[str]:
    found: list[str] = []
    for path in sorted(repo.iterdir()):
        if path.is_dir() and path.name in ENTRY_DIRS:
            found.append(path.name + "/")
        elif path.is_file() and (path.name.startswith(ENTRY_FILES) or path.suffix == ".sh"):
            found.append(path.name)
    return found


def _readme_commands(repo: Path) -> list[str]:
    readmes = sorted(p for p in repo.iterdir() if p.is_file() and p.name.lower().startswith("readme"))
    commands: list[str] = []
    for readme in readmes:
        in_fence = False
        pending = ""
        for raw in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            if FENCE.match(raw):
                in_fence = not in_fence
                pending = ""
                continue
            if not in_fence:
                continue
            line = raw.strip()
            if line.startswith("$ "):
                line = line[2:]
            if pending:
                line = f"{pending} {line}"
                pending = ""
            if line.endswith("\\"):
                pending = line[:-1].rstrip()
                continue
            if line.startswith(COMMAND_PREFIXES):
                commands.append(line)
    return commands


def _config_files(repo: Path) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        rel = Path(dirpath).relative_to(repo)
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        if len(rel.parts) >= 2:
            dirnames[:] = []
        for name in sorted(filenames):
            p = Path(name)
            if p.suffix in CONFIG_SUFFIXES and not any(m in p.stem.lower() for m in LOCK_MARKERS):
                found.append((rel / name).as_posix())
    return found


def _docs(repo: Path) -> list[str]:
    found: list[str] = []
    if (repo / "ARCHITECTURE.md").is_file():
        found.append("ARCHITECTURE.md")
    docs = repo / "docs"
    if docs.is_dir():
        found.extend(sorted(p.relative_to(repo).as_posix() for p in docs.rglob("*.md")))
    return found


def collect_facts(repo: Path, depth: int = 2, max_entries: int = 200) -> dict:
    repo = Path(repo).resolve()
    return {
        "name": repo.name,
        "path": str(repo),
        "remote": _git(repo, "remote", "get-url", "origin") or "本地仓库",
        "branch": _git(repo, "branch", "--show-current") or "(detached)",
        "head": _git(repo, "log", "-1", "--format=%h %ad %s", "--date=short") or "(no git)",
        "tree": _walk(repo, depth, max_entries),
        "ext_counts": _ext_counts(repo),
        "entry_points": _entry_points(repo),
        "readme_commands": _readme_commands(repo),
        "config_files": _config_files(repo),
        "docs": _docs(repo),
    }


def _bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items] or ["- (none)"]


def render_markdown(facts: dict) -> str:
    out = [f"## 仓库事实：{facts['name']}", ""]
    out += [
        f"- 本地路径：`{facts['path']}`",
        f"- 源仓库：`{facts['remote']}`",
        f"- 分支：`{facts['branch']}`",
        f"- HEAD：`{facts['head']}`",
        "",
        "### 目录树",
        "",
        "```text",
        *(facts["tree"] or ["(empty)"]),
        "```",
        "",
        "### 文件类型",
        "",
        *(f"- `{ext}`: {n}" for ext, n in facts["ext_counts"]),
        "",
        "### 入口候选",
        "",
        *_bullets(facts["entry_points"]),
        "",
        "### README 中的命令",
        "",
        *_bullets(facts["readme_commands"]),
        "",
        "### 配置文件",
        "",
        *_bullets(facts["config_files"]),
        "",
        "### 已有文档",
        "",
        *_bullets(facts["docs"]),
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print deterministic repository facts as Markdown.")
    parser.add_argument("repo", help="path to a local repository")
    parser.add_argument("--depth", type=int, default=2, help="directory tree depth (default 2)")
    parser.add_argument("--max-entries", type=int, default=200, help="max tree lines (default 200)")
    args = parser.parse_args(argv)
    repo = Path(args.repo).expanduser()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2
    print(render_markdown(collect_facts(repo, args.depth, args.max_entries)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

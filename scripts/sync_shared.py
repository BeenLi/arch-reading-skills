#!/usr/bin/env python3
"""把 skills/_shared（或其中几个文件，外加 concept-categories.md）复制进用到它的 skill，生成 skills/<name>/_shared/。

`npx skills add` 只复制单个 skill 文件夹，`_shared` 不会跟着装；软链接也不行，CLI 按 skill 文件夹的
git tree hash 判断更新，只改 `_shared` 时被链接方的 hash 不变，`skills update` 永远不触发。
所以 skills/_shared 是唯一源，各 skill 下的 `_shared/` 是生成的副本，一起入库。

用法：
    python3 scripts/sync_shared.py          # 重新生成副本
    python3 scripts/sync_shared.py --check  # 只检查副本是否与源一致，不一致时退出码 1
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "skills"
SOURCE = SKILLS / "_shared"
# skill → 要复制的 _shared 内相对路径；None 表示整个 _shared。
TARGETS = {
    "paper-reader": None,
    "concept-notes": None,
    "daily-papers": None,
    "repo-reader": ("scripts/md_escape_check.py", "references/mermaid-rules.md"),
    "book-reader": ("references/mermaid-rules.md",),
}
# 跨 skill 引用的文件：npx 下只有同时装了 concept-notes 才找得到，所以也复制进依赖它的 skill。
EXTRA_FILES = {
    SKILLS / "concept-notes" / "references" / "concept-categories.md": ("paper-reader", "daily-papers"),
}
# 个人配置和缓存不进副本。
EXCLUDED_NAMES = {"user-config.local.json", "__pycache__", ".DS_Store"}


def source_files(name: str) -> dict[Path, Path]:
    """返回 {副本内相对路径: 源文件}。"""
    files = {}
    for path in sorted(SOURCE.rglob("*")):
        rel = path.relative_to(SOURCE)
        if any(part in EXCLUDED_NAMES for part in rel.parts) or path.suffix == ".pyc" or not path.is_file():
            continue
        if TARGETS[name] is not None and rel.as_posix() not in TARGETS[name]:
            continue
        files[rel] = path
    for path, users in EXTRA_FILES.items():
        if name in users:
            files[Path("references") / path.name] = path
    return files


def target_files(target: Path) -> set[Path]:
    if not target.exists():
        return set()
    return {
        path.relative_to(target)
        for path in target.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_NAMES for part in path.relative_to(target).parts)
    }


def diff(expected: dict[Path, Path], target: Path) -> list[str]:
    problems = []
    existing = target_files(target)
    for rel, source in expected.items():
        if rel not in existing:
            problems.append(f"缺少 {rel}")
        elif (target / rel).read_bytes() != source.read_bytes():
            problems.append(f"内容不同 {rel}")
    problems.extend(f"多余 {rel}" for rel in sorted(existing - expected.keys()))
    return problems


def sync(expected: dict[Path, Path], target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    for rel, source in expected.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args()

    stale = False
    for name in TARGETS:
        expected = source_files(name)
        missing = set(TARGETS[name] or ()) - {rel.as_posix() for rel in expected}
        if missing:
            raise SystemExit(f"{name}: skills/_shared 里没有 {sorted(missing)}")
        target = SKILLS / name / "_shared"
        problems = diff(expected, target)
        if not problems:
            print(f"{name}: OK")
            continue
        if args.check:
            stale = True
            print(f"{name}: 与 skills/_shared 不一致")
            for problem in problems:
                print(f"  {problem}")
        else:
            sync(expected, target)
            print(f"{name}: 已同步 {len(expected)} 个文件")

    if stale:
        print("运行 python3 scripts/sync_shared.py 重新生成。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

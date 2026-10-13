import subprocess
import sys

from conftest import SCRIPTS
from repo_facts import collect_facts, render_markdown


def test_tree_excludes_junk_dirs(fixture_repo):
    facts = collect_facts(fixture_repo)
    joined = "\n".join(facts["tree"])
    assert "scripts/" in joined and "docs/" in joined
    assert "node_modules" not in joined and "__pycache__" not in joined


def test_entry_points_and_configs(fixture_repo):
    facts = collect_facts(fixture_repo)
    assert "README.md" in facts["entry_points"] and "scripts/" in facts["entry_points"]
    assert "package.json" in facts["config_files"] and "config.yaml" in facts["config_files"]
    assert "package-lock.json" not in facts["config_files"]
    assert facts["docs"] == ["docs/guide.md"]


def test_commands_extracted_from_readme_code_blocks(fixture_repo):
    cmds = collect_facts(fixture_repo)["readme_commands"]
    assert "python3 scripts/run.py --days 3" in cmds
    assert "make build ARGS=1" in cmds  # 续行合并
    assert all(not c.startswith("$") for c in cmds)


def test_git_facts_and_markdown(fixture_repo):
    facts = collect_facts(fixture_repo)
    assert facts["remote"] == "本地仓库"
    assert facts["head"].endswith("init")
    md = render_markdown(facts)
    assert md.startswith(f"## 仓库事实：{fixture_repo.name}")
    for heading in ("### 目录树", "### 入口候选", "### README 中的命令", "### 配置文件", "### 已有文档"):
        assert heading in md


def test_cli_prints_markdown_and_help_writes_nothing(fixture_repo, tmp_path):
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "repo_facts.py"), str(fixture_repo)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert out.startswith(f"## 仓库事实：{fixture_repo.name}")
    before = sorted(p.name for p in tmp_path.iterdir())
    subprocess.run([sys.executable, str(SCRIPTS / "repo_facts.py"), "--help"], cwd=tmp_path, check=True, capture_output=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


# --- deferred minors (2026-10-13) -------------------------------------------

from pathlib import Path


def _write_readme(repo: Path, text: str) -> None:
    (repo / "README.md").write_text(text, encoding="utf-8")


def test_readme_commands_follow_commonmark_fences(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _write_readme(repo, (
        "~~~sh\nnpm run dev\n~~~\n\n"
        "```toml\npython = \"^3.10\"\n```\n\n"
        "```\npython = 1\nmake test\n```\n\n"
        "````markdown\n```bash\npip install quoted\n```\n````\n\n"
        "```bash\nmake all \\\n\n```\n"
    ))
    cmds = collect_facts(repo)["readme_commands"]
    assert "npm run dev" in cmds  # ~~~ 围栏
    assert "make test" in cmds  # 无语言标记的块照常扫描
    assert not any(c.startswith("python =") for c in cmds)  # TOML 赋值不是命令
    assert "pip install quoted" not in cmds  # 嵌在 markdown 示例里的不是命令
    assert "make all" in cmds  # 续行后遇空行：结束且无尾随空格


def test_subdirectory_of_a_git_repo_is_reported_as_such(fixture_repo):
    facts = collect_facts(fixture_repo / "scripts")
    assert facts["name"] == "scripts"
    assert facts["subdir"] == "scripts"
    assert facts["git_root"] == str(fixture_repo.resolve())
    assert "子目录" in render_markdown(facts)
    root = collect_facts(fixture_repo)
    assert root["subdir"] is None and "子目录" not in render_markdown(root)


def test_entry_points_case_insensitive_and_second_level_skill_files(tmp_path):
    repo = tmp_path / "r"
    (repo / "skills" / "foo").mkdir(parents=True)
    (repo / "makefile").write_text("all:\n", encoding="utf-8")
    (repo / "Readme.rst").write_text("x\n", encoding="utf-8")
    (repo / "skills" / "foo" / "SKILL.md").write_text("---\n", encoding="utf-8")
    entries = collect_facts(repo)["entry_points"]
    assert "makefile" in entries and "Readme.rst" in entries
    assert "skills/foo/SKILL.md" in entries


def test_config_files_cover_the_top_three_levels_only(tmp_path):
    repo = tmp_path / "r"
    (repo / "a" / "b" / "c").mkdir(parents=True)
    (repo / "top.toml").write_text("", encoding="utf-8")
    (repo / "a" / "mid.yaml").write_text("", encoding="utf-8")
    (repo / "a" / "b" / "deep.yaml").write_text("", encoding="utf-8")  # skills/_shared/user-config.json 的深度
    (repo / "a" / "b" / "c" / "deeper.yaml").write_text("", encoding="utf-8")
    configs = collect_facts(repo)["config_files"]
    assert {"top.toml", "a/mid.yaml", "a/b/deep.yaml"} <= set(configs)
    assert "a/b/c/deeper.yaml" not in configs

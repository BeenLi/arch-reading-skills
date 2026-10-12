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

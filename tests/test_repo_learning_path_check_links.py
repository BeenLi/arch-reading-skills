import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_LINKS = REPO_ROOT / "skills" / "repo-learning-path" / "scripts" / "check_links.py"

_spec = importlib.util.spec_from_file_location("repo_learning_path_check_links", CHECK_LINKS)
check_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_links)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A tiny repo: src/core.sv with 10 lines, docs/learning/ for notes, one image."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.sv").write_text("".join(f"line {i}\n" for i in range(1, 11)), encoding="utf-8")
    learning = tmp_path / "docs" / "learning"
    (learning / "figs" / "drawn").mkdir(parents=True)
    (learning / "figs" / "drawn" / "top.png").write_bytes(b"\x89PNG")
    return tmp_path


def write_note(repo: Path, body: str) -> Path:
    note = repo / "docs" / "learning" / "00-1-demo.md"
    note.write_text(body, encoding="utf-8")
    return note


def test_valid_links_pass(repo):
    note = write_note(repo, (
        "[`core.sv:3`](../../src/core.sv#L3)、[`core.sv:2-10`](../../src/core.sv#L2-L10)\n"
        "![图](figs/drawn/top.png)\n"
        "[目录](../../src/)、[外部](https://example.com)、[本节](#精读结论)\n"
    ))
    assert check_links.check_file(note) == []


def test_missing_file_and_image_reported(repo):
    note = write_note(repo, "[x](../../src/gone.sv#L1)\n![y](figs/drawn/none.png)\n")
    errors = check_links.check_file(note)
    assert len(errors) == 2
    assert all("missing target" in e for e in errors)


@pytest.mark.parametrize("anchor", ["#L11", "#L2-L11", "#L0", "#L5-L3"])
def test_line_anchor_out_of_range(repo, anchor):
    note = write_note(repo, f"[x](../../src/core.sv{anchor})\n")
    errors = check_links.check_file(note)
    assert len(errors) == 1 and "out of range" in errors[0]


def test_links_inside_code_fences_are_ignored(repo):
    note = write_note(repo, "```markdown\n[x](../../src/gone.sv#L1)\n```\n")
    assert check_links.check_file(note) == []


def test_cli_exit_status(repo):
    learning = repo / "docs" / "learning"
    write_note(repo, "[ok](../../src/core.sv#L1)\n")
    ok = subprocess.run([sys.executable, str(CHECK_LINKS), str(learning)], capture_output=True, text=True)
    assert ok.returncode == 0 and "0 broken" in ok.stdout

    write_note(repo, "[bad](../../src/core.sv#L99)\n")
    bad = subprocess.run([sys.executable, str(CHECK_LINKS), str(learning)], capture_output=True, text=True)
    assert bad.returncode == 1 and "1 broken" in bad.stdout

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS
from check_doc import check

CHECK_DOC = str(SCRIPTS / "check_doc.py")
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid-doc.md"


@pytest.fixture
def valid_doc() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_valid_fixture_passes(valid_doc):
    assert check(valid_doc) == []


def test_header_lines_required(valid_doc):
    broken = valid_doc.replace("本次分析的提交：", "分析提交：", 1)
    assert any("本次分析的提交" in f for f in check(broken))


def test_sections_must_be_in_order_with_exact_titles(valid_doc):
    swapped = valid_doc.replace("## 9. 源码入口索引", "## 9. 入口索引")
    assert any("第 9 节" in f for f in check(swapped))


def test_slash_alternatives_only_for_sections_6_8_11(valid_doc):
    ok = valid_doc.replace("## 6. 常用命令 / 使用指南", "## 6. 使用指南")
    assert check(ok) == []
    bad = valid_doc.replace("## 10. 排错指南", "## 10. 排错")
    assert any("第 10 节" in f for f in check(bad))


def test_required_table_headers(valid_doc):
    broken = valid_doc.replace("| 想了解 | 优先看 |", "| 问题 | 文件 |")
    assert any("第 9 节" in f and "表头" in f for f in check(broken))


def test_mermaid_count_bounds(valid_doc):
    one = valid_doc.replace("```mermaid", "```text", 1)
    assert any("Mermaid" in f for f in check(one))


def test_source_token_requires_path_like_backtick(valid_doc):
    # 第 7 节唯一的路径 token 换成普通词后，该节不再有来源
    broken = valid_doc.replace("| interval | 60 | `config/settings.yaml` |", "| interval | 60 | `vLLM` |")
    assert any("第 7 节" in f and "来源" in f for f in check(broken))


def test_machine_paths_allowed_only_in_header(valid_doc):
    assert check(valid_doc) == []  # 头部的 /Users/example/repo 允许
    body_leak = valid_doc + "\n见 `/Users/me/x.py`。\n"
    assert any("机器专属" in f for f in check(body_leak))


def test_task_syntax_forbidden(valid_doc):
    assert any("task" in f.lower() for f in check(valid_doc + "\n- [ ] todo\n"))


def test_name_must_appear(valid_doc):
    assert check(valid_doc, name="demo") == []
    assert any("名字" in f for f in check(valid_doc, name="other"))


def test_cli_exit_code(tmp_path, valid_doc):
    p = tmp_path / "d.md"
    p.write_text(valid_doc, encoding="utf-8")
    assert subprocess.run([sys.executable, CHECK_DOC, str(p)], capture_output=True).returncode == 0
    p.write_text(valid_doc.replace("## 3. 总体架构", "## 3. 架构"), encoding="utf-8")
    assert subprocess.run([sys.executable, CHECK_DOC, str(p)], capture_output=True).returncode == 1


def test_section_2_table_row_bounds(valid_doc):
    assert check(valid_doc) == []  # fixture 恰好 6 行数据行
    too_few = valid_doc.replace("| Plugin | `src/plugins/__init__.py` | 扩展点 |\n", "")
    assert any("第 2 节" in f and "6–12" in f for f in check(too_few))
    extra = "".join(f"| X{i} | `src/x{i}.py` | 多余 |\n" for i in range(7))
    too_many = valid_doc.replace("| Plugin | `src/plugins/__init__.py` | 扩展点 |\n", "| Plugin | `src/plugins/__init__.py` | 扩展点 |\n" + extra)
    assert any("第 2 节" in f and "6–12" in f for f in check(too_many))


def test_section_4_steps_must_cite_files(valid_doc):
    broken = valid_doc.replace("1. `src/config.py` 读取 YAML。", "1. 读取 YAML。")
    assert any("第 4 节" in f and "引用文件" in f for f in check(broken))

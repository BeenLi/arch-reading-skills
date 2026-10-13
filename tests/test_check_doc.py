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


def test_fenced_code_blocks_are_ignored_by_structural_checks(valid_doc):
    quoted = valid_doc.replace(
        "改 `src/config.py` 的字段要同步改 `src/runner.py`。\n",
        "改 `src/config.py` 的字段要同步改 `src/runner.py`。\n\n```markdown\n## 问题定义\n## 2. 核心心智模型\n| 概念 | 来源 | 含义 |\n```\n",
    )
    assert check(quoted) == []
    steps_in_output = valid_doc.replace(
        "1. `src/config.py` 读取 YAML。\n",
        "1. `src/config.py` 读取 YAML。\n\n```text\n1. first line of output\n```\n",
    )
    assert check(steps_in_output) == []
    leak = valid_doc + "\n```bash\ncat /Users/me/secret\n```\n"
    assert any("机器专属" in f for f in check(leak))  # 代码块里的机器路径仍要抓


def test_source_token_accepts_well_known_extensionless_files_and_rejects_urls():
    from check_doc import _is_source_token

    for ok in ("Makefile", "Dockerfile", "LICENSE", ".gitignore", "src/main.py", "README.md", "python3 src/main.py --once"):
        assert _is_source_token(ok), ok
    for bad in ("vLLM", "1.0", "v1.2.3", "https://github.com/x/y", "e.g."):
        assert not _is_source_token(bad), bad


# --- deferred minors (2026-10-13) -------------------------------------------


def test_section_12_first_bullet_states_static_analysis(valid_doc):
    swapped = valid_doc.replace(
        "- 本次为静态源码分析，未执行 `python3 src/main.py`。\n- `src/store.py` 的并发语义未核实。\n",
        "- `src/store.py` 的并发语义未核实。\n- 本次为静态源码分析，未执行 `python3 src/main.py`。\n",
    )
    assert any("第 12 节" in f and "静态源码分析" in f for f in check(swapped))


def test_section_3_requires_the_3_1_heading(valid_doc):
    broken = valid_doc.replace("### 3.1 组件职责", "### 组件")
    assert any("第 3 节" in f and "3.1 组件职责" in f for f in check(broken))


def test_required_table_header_allows_extra_trailing_columns(valid_doc):
    wider = valid_doc.replace(
        "| 现象 | 优先检查 | 依据 |\n|---|---|---|\n| 找不到配置 | 工作目录 | `src/config.py` |",
        "| 现象 | 优先检查 | 依据 | 备注 |\n|---|---|---|---|\n| 找不到配置 | 工作目录 | `src/config.py` | 无 |",
    )
    assert check(wider) == []


def test_slash_section_error_lists_each_alternative_once(valid_doc):
    msgs = [f for f in check(valid_doc.replace("## 8. 常见使用场景 / 推荐工作流", "## 8. 场景")) if "第 8 节" in f]
    assert msgs
    assert "推荐工作流 / 常见使用场景" not in msgs[0]  # 不再把整句和两侧拼在一起
    assert "`常见使用场景 / 推荐工作流`" in msgs[0] and "`常见使用场景`" in msgs[0] and "`推荐工作流`" in msgs[0]


def test_cli_missing_file_exits_2_without_traceback(tmp_path):
    r = subprocess.run([sys.executable, CHECK_DOC, str(tmp_path / "nope.md")], capture_output=True, text=True)
    assert r.returncode == 2
    assert "Traceback" not in r.stderr and "nope.md" in r.stderr


def test_utf8_bom_does_not_break_the_header(tmp_path, valid_doc):
    assert check("﻿" + valid_doc) == []
    p = tmp_path / "bom.md"
    p.write_bytes(b"\xef\xbb\xbf" + valid_doc.encode("utf-8"))
    assert subprocess.run([sys.executable, CHECK_DOC, str(p)], capture_output=True).returncode == 0


SECOND_DIAGRAM = '```mermaid\nflowchart LR\n  A["src/config.py"] --> B["src/runner.py"]\n```\n'


def test_indented_and_tilde_mermaid_blocks_are_counted(valid_doc):
    indented = valid_doc.replace(SECOND_DIAGRAM, "".join("   " + l + "\n" for l in SECOND_DIAGRAM.splitlines()))
    assert indented != valid_doc and check(indented) == []
    tilde = valid_doc.replace(SECOND_DIAGRAM, SECOND_DIAGRAM.replace("```", "~~~"))
    assert tilde != valid_doc and check(tilde) == []


def test_mermaid_quoted_inside_a_longer_fence_is_not_counted(valid_doc):
    quoted = "````markdown\n```mermaid\nflowchart TB\n  X --> Y\n```\n````\n"
    doc = valid_doc.replace("附录内容不计入编号章节。\n", "附录内容不计入编号章节。\n\n" + quoted * 4)
    assert check(doc) == []  # 4 张被引用的骨架图不算，实际仍是 2 张


def test_header_meta_lines_must_not_end_with_whitespace(valid_doc):
    trailing = valid_doc.replace("源仓库：`https://example.com/demo.git`\n", "源仓库：`https://example.com/demo.git`  \n")
    assert any("头部" in f and "行尾空白" in f for f in check(trailing))

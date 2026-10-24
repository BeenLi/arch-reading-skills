# writing-architecture-docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重建"给任意仓库写架构和使用文档"的 skill，并用它重生成 `dailypaper-skills/ARCHITECTURE.md`。

**Architecture:** 两个独立的 Python 脚本承担确定性部分（事实收集、契约校验），`references/doc-format.md` 是人读的契约、`check_doc.py` 是机器读的同一契约；`SKILL.md` 只写流程和判断，按 writing-skills 的 RED → GREEN 用 subagent 基线验证。最后以本 skill 的流程重写 `ARCHITECTURE.md`，并回旧文档内容，保证硬链接与目标仓库测试不受影响。

**Tech Stack:** Python 3.10+ 标准库、pytest、git、Mermaid（`~/.claude/skills/_shared/references/mermaid-rules.md`）、subagent（Agent 工具）做 skill 基线测试。

**Spec:** `docs/superpowers/specs/2026-10-12-writing-architecture-docs-design.md`

## Global Constraints

- 脚本只用标准库；`python3 scripts/<x>.py --help` 必须可用且不写文件。
- 所有路径判断用 `pathlib`；目录树忽略集固定为 `.git node_modules __pycache__ .venv venv dist build .pytest_cache .claude .superpowers`。
- 文档契约的标题、表头、数量阈值以 spec §4、§6 为准，`check_doc.py` 与 `doc-format.md` 不得各说各话。
- SKILL.md frontmatter：`name: writing-architecture-docs`；`description` 以 "Use when" 开头，只写触发条件，不概括流程。
- 写目标仓库 `ARCHITECTURE.md` 时用 Python `open(path, "w")` 原地覆盖，不用先写临时文件再 rename 的工具，以免打断硬链接。
- `dailypaper-skills` 的 `python3 -m pytest tests/ -q` 在 Task 4 结束时必须全绿（当前 110 passed）。

## Review Focus

1. 目标仓库的 README 命令含 `$VAR`、`<占位符>`、多行续行 `\` 时 `repo_facts.py` 的命令提取不应截断或崩溃 → Task 1 `test_commands_extracted_from_readme_code_blocks` 覆盖续行与占位符。
2. `check_doc.py` 对第 6、8、11 节的斜杠替代标题必须接受，对其他节的近似标题必须拒绝 → Task 2 `test_slash_alternatives_only_for_sections_6_8_11`。
3. 来源标注检查不能被反引号里的普通词（如 `vLLM`）骗过，也不能误杀合法的 `README.md` → Task 2 `test_source_token_requires_path_like_backtick`。
4. 头部"本次分析的本地路径"行含 `/Users/…` 是允许的，正文其他地方不允许 → Task 2 `test_machine_paths_allowed_only_in_header`。
5. 原地写 `ARCHITECTURE.md` 后硬链接 inode 不变 → Task 4 用 `stat` 前后比对。

---

### Task 1: `scripts/repo_facts.py`

**Files:**
- Create: `scripts/repo_facts.py`, `tests/test_repo_facts.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `collect_facts(repo: Path, depth: int = 2, max_entries: int = 200) -> dict`，键：`name, remote, branch, head, tree (list[str]), ext_counts (list[tuple[str,int]]), entry_points (list[str]), readme_commands (list[str]), config_files (list[str]), docs (list[str])`；`render_markdown(facts: dict) -> str`；CLI `python3 scripts/repo_facts.py <repo> [--depth N] [--max-entries N]` 打印 Markdown，首行 `## 仓库事实：<name>`。

- [ ] **Step 1: 写 fixture 与失败测试**

`tests/conftest.py` 提供 `fixture_repo(tmp_path)`：`git init -q`，写 `README.md`（含一个 ```bash 块：`python3 scripts/run.py --days 3`、`npm install`、`make build \`+续行 `  ARGS=1`、`pip install -r requirements.txt`，以及一行 `$ echo skip` 不应提取）、`scripts/run.py`、`package.json`、`config.yaml`、`package-lock.json`、`docs/guide.md`、`node_modules/x/index.js`、`__pycache__/a.pyc`，`git add -A && git commit -q -m init`。

```python
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
    assert "make build ARGS=1" in cmds          # 续行合并
    assert all(not c.startswith("$") for c in cmds)

def test_git_facts_and_markdown(fixture_repo):
    facts = collect_facts(fixture_repo)
    assert facts["remote"] == "本地仓库"
    assert facts["head"].endswith("init")
    md = render_markdown(facts)
    assert md.startswith(f"## 仓库事实：{fixture_repo.name}")
    for heading in ("### 目录树", "### 入口候选", "### README 中的命令", "### 配置文件", "### 已有文档"):
        assert heading in md
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd ~/.claude/skills/writing-architecture-docs && python3 -m pytest tests/test_repo_facts.py -q`
Expected: FAIL，`ModuleNotFoundError: repo_facts`（conftest 把 `scripts/` 加入 `sys.path`）。

- [ ] **Step 3: 实现 `scripts/repo_facts.py`**

`collect_facts` 用 `subprocess.run(["git", ...], cwd=repo)` 取 remote / branch / head（失败时 remote=`本地仓库`、head=`(no git)`）；`os.walk` 构造树并在 `dirnames[:]` 上过滤忽略集；README 命令提取：遍历 ```` ``` ```` 围栏内的行，去掉行首 `$ `，以反斜杠结尾的行与下一行合并，再按前缀集 `python3 python npm pnpm make bash pip cargo go` 过滤；`render_markdown` 按五个 `###` 小节输出。`main()` 用 argparse。

- [ ] **Step 4: 运行测试与 --help**

Run: `python3 -m pytest tests/test_repo_facts.py -q && python3 scripts/repo_facts.py --help | head -1`
Expected: 4 passed；usage 行。

- [ ] **Step 5: Commit**

```bash
git add scripts/repo_facts.py tests/
git commit -m "feat: repo_facts.py collects deterministic repository facts"
```

---

### Task 2: 契约 `references/doc-format.md` 与校验器 `scripts/check_doc.py`

**Files:**
- Create: `references/doc-format.md`, `scripts/check_doc.py`, `tests/test_check_doc.py`, `tests/fixtures/valid-doc.md`

**Interfaces:**
- Produces: `check(text: str, name: str | None = None) -> list[str]`（失败原因列表，空表示通过）；`SECTION_TITLES: list[tuple[int, tuple[str, ...]]]`（12 节标题及其可接受替代）；CLI `python3 scripts/check_doc.py <doc.md> [--name NAME]`，逐条打印 `OK ` / `FAIL `，有 FAIL 退出码 1。

- [ ] **Step 1: 写 `tests/fixtures/valid-doc.md`**

一份最小合法文档：头部引用块（含"说明书"）+ 三行元信息（本地路径写 `/Users/example/repo`）；`## 1. 一句话理解 demo` … `## 12. 已知不确定点`，第 2、3.1、9、10 节含契约表头，`### 4.1`、`### 4.2`，两个 ```` ```mermaid ```` 块，每节至少一个 `` `src/x.py` `` 风格 token，第 12 节两条列表项，末尾用注释行补足到 260 行；再加 `## 附录 A. 备注`。

- [ ] **Step 2: 写失败测试**

```python
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
    # 把第 7 节唯一的路径 token 换成普通词
    broken = valid_doc.replace("`config/settings.yaml`", "`vLLM`")
    assert any("第 7 节" in f and "来源" in f for f in check(broken))

def test_machine_paths_allowed_only_in_header(valid_doc):
    assert check(valid_doc) == []                       # 头部的 /Users/example/repo 允许
    body_leak = valid_doc + "\n见 `/Users/me/x.py`。\n"
    assert any("机器专属" in f for f in check(body_leak))

def test_task_syntax_forbidden(valid_doc):
    assert any("task" in f.lower() for f in check(valid_doc + "\n- [ ] todo\n"))

def test_name_must_appear(valid_doc):
    assert check(valid_doc, name="demo") == []
    assert any("名字" in f for f in check(valid_doc, name="other"))

def test_cli_exit_code(tmp_path, valid_doc):
    p = tmp_path / "d.md"; p.write_text(valid_doc, encoding="utf-8")
    assert subprocess.run([sys.executable, CHECK_DOC, str(p)]).returncode == 0
    p.write_text(valid_doc.replace("## 3. 总体架构", "## 3. 架构"), encoding="utf-8")
    assert subprocess.run([sys.executable, CHECK_DOC, str(p)]).returncode == 1
```

- [ ] **Step 3: 运行，确认失败**

Run: `python3 -m pytest tests/test_check_doc.py -q`
Expected: FAIL（`check_doc` 不存在）。

- [ ] **Step 4: 写 `references/doc-format.md`**

内容 = spec §4 全文（头部三要素、12 节表、通用规则、附录规则），另加一段"自检：`python3 scripts/check_doc.py <doc> --name <Name>`"。

- [ ] **Step 5: 实现 `scripts/check_doc.py`**

`SECTION_TITLES` 列出 12 节：第 1 节匹配 `^## 1\. 一句话理解 `；6/8/11 为元组 `("常用命令 / 使用指南", "常用命令", "使用指南")` 等；其余单一标题。路径 token 正则：`` `[^`\n]*[./][^`\n]*` `` 且不以 `/Users/`、`/home/`、`C:\` 开头；机器路径检查跳过头部三行。来源检查按 H2 切片（附录之前），第 12 节除外。

- [ ] **Step 6: 运行测试**

Run: `python3 -m pytest tests/ -q`
Expected: 15 passed（4 + 11）。

- [ ] **Step 7: Commit**

```bash
git add references/doc-format.md scripts/check_doc.py tests/
git commit -m "feat: doc-format contract and check_doc.py validator"
```

---

### Task 3: `SKILL.md`（RED 基线 → GREEN → REFACTOR）与 `config.json`

**Files:**
- Create: `config.json`, `SKILL.md`
- Scratch: `<scratchpad>/arch-doc-baseline/`、`<scratchpad>/arch-doc-with-skill/`

**Interfaces:**
- Consumes: Task 1、2 的两个脚本。
- Produces: `SKILL.md`，`config.json` = `{"guide_dir": "/Users/beenli/Library/Mobile Documents/iCloud~md~obsidian/Documents/ob-career/002-notes/001 使用指南"}`。

- [ ] **Step 1: RED 基线（无 skill）**

用 Agent 工具（general-purpose）派一个 subagent，prompt 只给用户会给的信息："为 `~/.claude/skills/verilog-diagram` 这个仓库写一份『架构和使用文档』，格式参考 `<guide_dir>/LLMServingSim-架构和使用文档.md`，写到 `<scratchpad>/arch-doc-baseline/verilog-diagram-架构和使用文档.md`。不要修改仓库。" 结束后运行：

Run: `python3 scripts/check_doc.py <scratchpad>/arch-doc-baseline/verilog-diagram-架构和使用文档.md --name verilog-diagram`
Expected: 至少若干 FAIL。把 FAIL 条目和人工阅读发现的问题（杜撰命令？缺来源？无不确定点？）逐字记入 `docs/superpowers/plans/baseline-notes.md`。

- [ ] **Step 2: 写 `config.json` 与 `SKILL.md`（GREEN）**

SKILL.md 结构：frontmatter（name、description "Use when …"）；`## 适用` / `## 不适用`；`## 流程`（spec §5 六步，每步给命令）；`## 落盘规则`（三种情况 + 原地写 + 硬链接 `ln` 与 `stat` 核对）；`## 常见错误`（先放基线里出现的条目）；`## 汇报格式`。正文 ≤ 500 词，细节指向 `references/doc-format.md`。

- [ ] **Step 3: GREEN 运行（带 skill）**

派一个新 subagent："先读 `~/.claude/skills/writing-architecture-docs/SKILL.md` 并严格按它执行：为 `~/.claude/skills/verilog-diagram` 写架构和使用文档，输出到 `<scratchpad>/arch-doc-with-skill/`，不要写 vault、不要修改仓库。" 结束后：

Run: `python3 scripts/check_doc.py <scratchpad>/arch-doc-with-skill/verilog-diagram-架构和使用文档.md --name verilog-diagram`
Expected: 全部 OK，退出码 0。人工抽查 5 个论断能在 verilog-diagram 源码里找到。

- [ ] **Step 4: REFACTOR**

把 GREEN 运行中仍出现的偏差写进 `## 常见错误`；若 check_doc 发现契约与 doc-format.md 不一致，改契约文档而不是放宽校验。

- [ ] **Step 5: Commit**

```bash
git add SKILL.md config.json docs/superpowers/plans/baseline-notes.md
git commit -m "feat: SKILL.md with baseline-verified workflow"
```

---

### Task 4: 用 skill 重生成 `dailypaper-skills/ARCHITECTURE.md`

**Files:**
- Modify: `/Users/beenli/hardware-project/dailypaper-skills/ARCHITECTURE.md`（原地覆盖）
- Scratch: `<scratchpad>/arch-doc-dailypaper/`

**Interfaces:**
- Consumes: SKILL.md 流程；旧 `ARCHITECTURE.md`（并回来源）。

- [ ] **Step 1: 记录硬链接基线**

Run: `stat -f "%i %l" /Users/beenli/hardware-project/dailypaper-skills/ARCHITECTURE.md`
Expected: `<inode> 2`。

- [ ] **Step 2: 按 SKILL.md 六步生成草稿到 scratchpad**

`repo_facts.py` → 读源码（SKILL.md ×7、`_shared/scripts/*.py`、`paper-reader/scripts/*.py`、`daily-papers/scripts/*.py`、`tests/`）→ 写 12 节 + `## 附录 A. 目录约定`（三行表原样保留，测试要求 `` `scripts/` `` `` `references/` `` `` `assets/` `` 出现）+ `## 附录 B. Obsidian 硬链接`（保留 `<vault>` / `<repo>` 占位符写法）→ 逐节对照旧文档并回（排错表、配置加载顺序、history dedup 细节等）。

- [ ] **Step 3: 校验草稿**

```bash
python3 scripts/check_doc.py <draft> --name dailypaper-skills
python3 ~/.claude/skills/_shared/scripts/md_escape_check.py <draft>
```
Expected: 退出码都为 0。

- [ ] **Step 4: 原地写入并验证**

用 Python `open(ARCHITECTURE.md, "w")` 写入草稿；然后：

```bash
stat -f "%i %l" /Users/beenli/hardware-project/dailypaper-skills/ARCHITECTURE.md   # inode 不变，link count 2
cd /Users/beenli/hardware-project/dailypaper-skills && python3 -m pytest tests/ -q   # 110 passed
diff -q ARCHITECTURE.md "<guide_dir>/dailypaper-skills-架构和使用文档.md"            # 无输出
```

- [ ] **Step 5: Commit（dailypaper-skills）**

```bash
cd /Users/beenli/hardware-project/dailypaper-skills
git add ARCHITECTURE.md
git commit -m "docs: regenerate ARCHITECTURE.md with writing-architecture-docs skill"
```

---

### Task 5: 收尾

- [ ] **Step 1:** 在 skill 仓库运行 `python3 -m pytest tests/ -q`（15 passed）并 `git status` 干净。
- [ ] **Step 2:** 记忆文件补一行：skill 位置与 `config.json` 的 guide_dir。
- [ ] **Step 3:** 汇报：skill 路径、基线 vs 带 skill 的 check_doc 结果对比、ARCHITECTURE.md 行数 / 图数 / 并回条目数、硬链接核对、dailypaper-skills 测试结果；询问是否 push dailypaper-skills。

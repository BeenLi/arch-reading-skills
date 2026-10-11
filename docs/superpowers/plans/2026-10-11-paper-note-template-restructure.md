# 论文笔记模板重构、图表选型与目录统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 paper-reader 生成的笔记按"范围 → 问题 → 证据 → insight → 设计"一条链书写、证据只出现一次、全文可点击跳转，复杂图有 draw.io 路线，并把仓库统一成 `scripts/ · references/ · assets/` 目录约定。

**Architecture:** 先做目录迁移并用一个新的仓库布局测试把"文档里的脚本路径必须真实存在"钉死，让后续改动都在新路径上进行；再新增共享的 `diagram-rules.md`；最后重写模板前半部分与 `系统设计总览`，并同步更新把结构复制了一份的 `SKILL.md` 和 `paper_daemon.py` 内嵌 prompt。每一步都以 `pytest tests/` 全绿收尾。

**Tech Stack:** Python 3.10+ 标准库、unittest（经 `python3 -m pytest tests/` 运行）、Markdown、Obsidian wikilink / 块引用、Mermaid、draw.io 32.x CLI（可选依赖）。

**Spec:** `docs/superpowers/specs/2026-10-11-paper-note-template-restructure-design.md`

## Global Constraints

- 所有文件移动用 `git mv`，保留历史。
- `skills/_shared/user-config.json` 与 `user-config.local.json` 位置不变；`.gitignore` 不改。
- `skills/_shared/references/mermaid-rules.md` 内容一字不改，只移动位置。
- 测试基线：`python3 -m pytest tests/ -q` 当前 90 passed；每个任务结束必须全绿。
- 模板文本不得出现 `tests/test_systems_template.py` 中 `rigid_phrases` 的任一短语（注意 `数据流 / 控制流`、`关键组件`、`部署位置`、`关键指标 / 总览公式`），也不得出现 `forbidden_phrases`（`数据集`、`模型架构`、`可视化结果`、`损失函数`、`语言指令`、`动作块`）。写"数据流与控制流"、"组件"。
- 模板中所有 `![…](…)` 图片题注以 `Figure ` 开头（既有测试）；图片上方不写独立的 `**Figure …**` 行。
- 块 id 只用小写拉丁字母、数字、连字符；标题链接 `[[#标题|短名]]` 的标题部分必须与目标标题逐字一致。
- 笔记正文禁止 `- [ ]` / `- [x]`。
- 非目标（见 spec §2）：不迁移 vault 旧笔记；不改 `concept-categories.md` 中 architecture 概念"必须 Mermaid"规则；不改 README 的 `~/.codex/skills` 安装说明；模板后半部分除 `Overhead 与兼容性` 新增小节外结构不动。
- 编辑 vault 的 `CLAUDE.md` / `AGENTS.md` 时用 Python 读改写（断言替换次数），不用 `sed -i`；两文件 inode 不同，各改一次。

## Review Focus

1. 从 `~/.claude/skills/_shared/scripts/x.py`（symlink）或 `cp -R` 安装后运行脚本，`user_config` 仍要找到 `_shared/user-config.json` → Task 1 `test_user_config_loads_repo_config`。
2. 文档里的 `python3 …py` 路径与真实文件漂移是本次迁移最可能的回归 → Task 1 `test_markdown_script_paths_resolve` 扫描全部 Markdown。
3. `SKILL.md` 与 `paper_daemon.py` prompt 对"模块关系图 / 论文原图"给出矛盾指令 → Task 7 `test_skill_and_daemon_follow_new_structure` 断言旧字符串消失。
4. `md_escape_check.py --fix` 把 `^fig3` 或 `[[#^fig3|Figure 3]]` 改坏 → Task 5 `test_keeps_obsidian_block_ids_and_in_note_links`。
5. 模板示例里 `[[#机制1：…|机制1]]` 的标题文字与 `### 机制1：…` 不一致，agent 照抄后 Obsidian 跳转失败 → Task 6 `test_template_anchor_examples` 用正则比对。

---

### Task 1: `_shared` 迁移到 `scripts/` + `references/`，并加仓库布局测试

**Files:**
- Create: `tests/test_repo_layout.py`
- Move: `skills/_shared/{user_config,moc_builder,generate_concept_mocs,generate_paper_mocs,clean_old_mocs,regenerate_concepts,scan_missing_concepts,md_escape_check}.py` → `skills/_shared/scripts/`；`skills/_shared/mermaid-rules.md` → `skills/_shared/references/mermaid-rules.md`
- Modify: `skills/_shared/scripts/user_config.py:134`；`skills/daily-papers/fetch_and_score.py:26`；`skills/paper-reader/assets/zotero_helper.py:18`；`skills/paper-reader/assets/reorganize_notes.py:16`；`skills/paper-reader/paper_daemon.py:37`
- Modify docs: `skills/daily-papers-notes/SKILL.md:141-142`；`skills/generate-mocs/SKILL.md:38,44`；`skills/paper-reader/SKILL.md:74,160`；`skills/paper-reader/references/concept-categories.md:140,154`；`skills/book-reader/references/mindmap-rules.md:12`；`README.md:146-149,165`；`ARCHITECTURE.md:30,244-245,253-254,263,294-295`
- Modify tests: `tests/test_generate_paper_mocs.py:12`；`tests/test_md_escape_check.py:5`；`tests/test_regenerate_concepts.py:26,30`；`tests/test_zotero_helper.py:16`；`tests/test_scan_missing_concepts.py:9`
- Modify (仓库外，用户自己的文件): `…/ob-career/CLAUDE.md:55-56`、`…/ob-career/AGENTS.md:55-56`（路径 `~/.claude/skills/_shared/md_escape_check.py` → `~/.claude/skills/_shared/scripts/md_escape_check.py`）
- Modify: spec §5.3 末段，补"vault `CLAUDE.md` / `AGENTS.md` 引用 `md_escape_check.py`，一并更新"

**Interfaces:**
- Produces: `skills/_shared/scripts/` 下全部共享脚本；`tests/test_repo_layout.py` 中的 `resolve_script_ref(md_path: Path, ref: str) -> Path | None`，Task 2、3 往同文件追加各自的布局断言。

- [ ] **Step 1: 写布局测试 `tests/test_repo_layout.py`**

```python
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "skills"
SCRIPT_REF = re.compile(r"python3\s+(\S+\.py)")
RULE_REF = re.compile(r"_shared/(?:mermaid|diagram)-rules\.md")  # 正确路径是 _shared/references/…，不会命中


def markdown_files():
    yield from SKILLS.rglob("*.md")
    yield REPO_ROOT / "README.md"
    yield REPO_ROOT / "ARCHITECTURE.md"


def resolve_script_ref(md_path: Path, ref: str):
    """Map a `python3 <ref>` mention to a repo path; None = not ours, skip."""
    ref = ref.strip("\"'")
    if "$" in ref:            # "$DRAWIO/scripts/validate.py" 这类仓库外路径
        return None
    if ref.startswith("skills/"):
        return REPO_ROOT / ref
    for prefix in ("~/.claude/skills/", "~/.codex/skills/"):
        if ref.startswith(prefix):
            rel = ref[len(prefix):]
            return SKILLS / rel if (SKILLS / rel.split("/", 1)[0]).exists() else None
    if md_path.is_relative_to(SKILLS):
        skill_root = SKILLS / md_path.relative_to(SKILLS).parts[0]
        return (skill_root / ref).resolve()
    return (REPO_ROOT / ref).resolve()


class RepoLayoutTests(unittest.TestCase):
    def test_shared_scripts_live_in_scripts_dir(self):
        self.assertEqual(sorted((SKILLS / "_shared").glob("*.py")), [])
        self.assertTrue((SKILLS / "_shared" / "scripts" / "user_config.py").exists())
        self.assertTrue((SKILLS / "_shared" / "scripts" / "md_escape_check.py").exists())
        self.assertTrue((SKILLS / "_shared" / "references" / "mermaid-rules.md").exists())
        self.assertTrue((SKILLS / "_shared" / "user-config.json").exists())

    def test_markdown_script_paths_resolve(self):
        offenders = []
        for md in markdown_files():
            for ref in SCRIPT_REF.findall(md.read_text(encoding="utf-8")):
                target = resolve_script_ref(md, ref)
                if target is not None and not target.exists():
                    offenders.append(f"{md.relative_to(REPO_ROOT)} -> {ref}")
        self.assertEqual(offenders, [])

    def test_rule_files_referenced_under_references_dir(self):
        offenders = [
            f"{md.relative_to(REPO_ROOT)}:{m.group(0)}"
            for md in markdown_files()
            for m in RULE_REF.finditer(md.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

    def test_user_config_loads_repo_config(self):
        sys.path.insert(0, str(SKILLS / "_shared" / "scripts"))
        import user_config  # noqa: E402

        keywords = user_config.load_user_config()["daily_papers"]["keywords"]
        self.assertIn("kv cache", keywords)
```

- [ ] **Step 2: 运行，确认失败**

Run: `python3 -m pytest tests/test_repo_layout.py -q`
Expected: FAIL — `test_shared_scripts_live_in_scripts_dir`（`_shared/*.py` 仍存在）、`test_user_config_loads_repo_config`（`ModuleNotFoundError: user_config`）、`test_rule_files_referenced_under_references_dir`（5 处 `_shared/mermaid-rules.md` 旧路径）。

- [ ] **Step 3: 移动文件**

```bash
mkdir -p skills/_shared/scripts skills/_shared/references
for f in user_config moc_builder generate_concept_mocs generate_paper_mocs clean_old_mocs regenerate_concepts scan_missing_concepts md_escape_check; do
  git mv "skills/_shared/$f.py" "skills/_shared/scripts/$f.py"
done
git mv skills/_shared/mermaid-rules.md skills/_shared/references/mermaid-rules.md
```

- [ ] **Step 4: 修 Python 内部路径**

- `skills/_shared/scripts/user_config.py:134`：`config_dir = Path(__file__).resolve().parent` → `config_dir = Path(__file__).resolve().parent.parent`
- `skills/daily-papers/fetch_and_score.py:26`：`_SHARED_DIR = Path(__file__).resolve().parent.parent / "_shared"` → `_SHARED_DIR = Path(__file__).resolve().parents[1] / "_shared" / "scripts"`
- `skills/paper-reader/assets/zotero_helper.py:18`、`skills/paper-reader/assets/reorganize_notes.py:16`：`parents[2] / "_shared"` → `parents[2] / "_shared" / "scripts"`
- `skills/paper-reader/paper_daemon.py:37`：`parents[1] / "_shared"` → `parents[1] / "_shared" / "scripts"`

`_shared/scripts/*.py` 之间用 `Path(__file__).resolve().parent` 互相引用，一起迁移后不用改。

- [ ] **Step 5: 修测试里的路径常量**

五个文件中 `"skills" / "_shared" / "<x>.py"` 与 `"skills" / "_shared"`（sys.path）一律改为 `"skills" / "_shared" / "scripts" / …`：`test_generate_paper_mocs.py:12`、`test_md_escape_check.py:5`、`test_regenerate_concepts.py:26,30`、`test_zotero_helper.py:16`、`test_scan_missing_concepts.py:9`。`test_daily_papers_theme.py` 的 `CONFIG_PATH` 不动。

- [ ] **Step 6: 修文档里的调用路径与规则文件引用**

| 文件 | 旧 | 新 |
|---|---|---|
| `daily-papers-notes/SKILL.md:141-142`、`generate-mocs/SKILL.md:38,44` | `../_shared/generate_*_mocs.py` | `../_shared/scripts/generate_*_mocs.py` |
| `paper-reader/SKILL.md:74,160` | `../_shared/mermaid-rules.md` | `../_shared/references/mermaid-rules.md` |
| `paper-reader/references/concept-categories.md:140` | `../../_shared/mermaid-rules.md` | `../../_shared/references/mermaid-rules.md` |
| `concept-categories.md:154`、`book-reader/references/mindmap-rules.md:12` | `~/.claude/skills/_shared/mermaid-rules.md` | `~/.claude/skills/_shared/references/mermaid-rules.md` |
| `README.md:146-149`、`ARCHITECTURE.md:244-245,253-254` | `skills/_shared/<x>.py` | `skills/_shared/scripts/<x>.py` |
| `ARCHITECTURE.md:30,263,294-295` | `skills/_shared/user_config.py`、`moc_builder.py` 等 | 加 `scripts/` |
| `README.md:165` | `└── _shared/               # 配置、MOC 生成、概念扫描` | `└── _shared/               # 共享配置；scripts/ MOC 生成、概念扫描、转义检查；references/ 画图规则` |

- [ ] **Step 7: 更新 vault 的两份说明文件**

```bash
python3 - <<'PY'
from pathlib import Path
root = Path("/Users/beenli/Library/Mobile Documents/iCloud~md~obsidian/Documents/ob-career")
old, new = "~/.claude/skills/_shared/md_escape_check.py", "~/.claude/skills/_shared/scripts/md_escape_check.py"
for name in ("CLAUDE.md", "AGENTS.md"):
    p = root / name; t = p.read_text(encoding="utf-8")
    assert t.count(old) == 2, (name, t.count(old))
    p.write_text(t.replace(old, new), encoding="utf-8")
print("ok")
PY
```

- [ ] **Step 8: 在 spec §5.3 末段补一句**

在"已确认仓库外（…）没有引用这些路径。"之后追加："例外：Obsidian vault 的 `CLAUDE.md` 与 `AGENTS.md` 各两处引用 `~/.claude/skills/_shared/md_escape_check.py`，随 Task 1 一并改为 `_shared/scripts/`。"

- [ ] **Step 9: 全量测试**

Run: `python3 -m pytest tests/ -q`
Expected: 94 passed（90 + 4 新增）。

- [ ] **Step 10: 残留扫描**

Run: `grep -rn '_shared/[a-z_]*\.py\|_shared/mermaid-rules' --include='*.md' --include='*.py' skills tests README.md ARCHITECTURE.md | grep -v '_shared/scripts/\|_shared/references/'`
Expected: 无输出。

- [ ] **Step 11: Commit**

```bash
git add -A skills tests README.md ARCHITECTURE.md docs/superpowers/specs
git commit -m "refactor(_shared): move scripts to scripts/ and rules to references/; add repo layout test"
```

---

### Task 2: `paper-reader` 脚本迁到 `scripts/`

**Files:**
- Move: `skills/paper-reader/assets/zotero_helper.py`、`skills/paper-reader/assets/reorganize_notes.py`、`skills/paper-reader/paper_daemon.py` → `skills/paper-reader/scripts/`
- Modify: `skills/paper-reader/scripts/paper_daemon.py:37-42`
- Modify docs: `skills/paper-reader/SKILL.md:42-44`；`skills/paper-reader/references/zotero-guide.md`（13 处）；`ARCHITECTURE.md:31,66,67,201-203,290,291`
- Modify tests: `tests/test_reorganize_notes.py:7`；`tests/test_zotero_helper.py:15`；`tests/test_paper_daemon.py:9`；`tests/test_systems_template.py:11`（`PAPER_DAEMON`）；`tests/test_repo_layout.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `tests/test_repo_layout.py`。
- Produces: `skills/paper-reader/scripts/{zotero_helper,reorganize_notes,paper_daemon}.py`；`assets/` 只剩 `paper-note-template.md`。

- [ ] **Step 1: 追加布局断言**

```python
    def test_paper_reader_layout(self):
        root = SKILLS / "paper-reader"
        self.assertEqual(sorted(root.glob("*.py")), [])
        self.assertEqual(sorted(p.name for p in (root / "assets").iterdir() if p.suffix == ".py"), [])
        for name in ("zotero_helper.py", "reorganize_notes.py", "paper_daemon.py"):
            self.assertTrue((root / "scripts" / name).exists(), name)
        self.assertTrue((root / "assets" / "paper-note-template.md").exists())
```

- [ ] **Step 2: 运行，确认失败**

Run: `python3 -m pytest tests/test_repo_layout.py::RepoLayoutTests::test_paper_reader_layout -q`
Expected: FAIL（`paper_daemon.py` 在 skill 根目录）。

- [ ] **Step 3: 移动**

```bash
mkdir -p skills/paper-reader/scripts
git mv skills/paper-reader/assets/zotero_helper.py skills/paper-reader/scripts/zotero_helper.py
git mv skills/paper-reader/assets/reorganize_notes.py skills/paper-reader/scripts/reorganize_notes.py
git mv skills/paper-reader/paper_daemon.py skills/paper-reader/scripts/paper_daemon.py
```

- [ ] **Step 4: 修 `paper_daemon.py` 头部路径**

`_SHARED_DIR = Path(__file__).resolve().parents[1] / "_shared" / "scripts"` → `parents[2]`；删除 `_ASSETS_DIR = …` 及其下两行 `sys.path.insert`（`zotero_helper` 已是同目录，`from zotero_helper import …` 直接可用）。`zotero_helper.py`、`reorganize_notes.py` 的 `parents[2]` 深度不变，不改。

- [ ] **Step 5: 修测试常量**

`test_reorganize_notes.py:7`、`test_zotero_helper.py:15` 中 `"assets"` → `"scripts"`；`test_paper_daemon.py:9` 与 `test_systems_template.py:11`（`PAPER_DAEMON`）中 `"paper-reader" / "paper_daemon.py"` → `"paper-reader" / "scripts" / "paper_daemon.py"`。

- [ ] **Step 6: 修文档**

```bash
sed -i '' 's#assets/zotero_helper\.py#scripts/zotero_helper.py#g' skills/paper-reader/SKILL.md skills/paper-reader/references/zotero-guide.md ARCHITECTURE.md
sed -i '' 's#skills/paper-reader/paper_daemon\.py#skills/paper-reader/scripts/paper_daemon.py#g' ARCHITECTURE.md
```

- [ ] **Step 7: 全量测试**

Run: `python3 -m pytest tests/ -q`
Expected: 95 passed。

- [ ] **Step 8: 残留扫描**

Run: `grep -rn 'assets/zotero_helper\|assets/reorganize_notes\|paper-reader/paper_daemon' --include='*.md' --include='*.py' skills tests README.md ARCHITECTURE.md`
Expected: 无输出。

- [ ] **Step 9: Commit**

```bash
git add -A skills tests ARCHITECTURE.md
git commit -m "refactor(paper-reader): move helper scripts and daemon into scripts/"
```

---

### Task 3: `daily-papers` 脚本迁到 `scripts/`，写下目录约定

**Files:**
- Move: `skills/daily-papers/{fetch_and_score,enrich_papers,parse_arxiv,extract_affiliations,download_note_images}.py` → `skills/daily-papers/scripts/`
- Modify: `skills/daily-papers/scripts/fetch_and_score.py:26`
- Modify docs: `skills/daily-papers-fetch/SKILL.md:53,54,76`；`skills/paper-reader/references/image-troubleshooting.md:47`；`README.md:155-166,172-173`；`ARCHITECTURE.md:61,62,286,287` 及"核心心智模型"之后新增小节
- Modify tests: `tests/test_download_note_images.py:14`；`tests/test_fetch_and_score.py:10`；`tests/test_enrich_papers.py:8`；`tests/test_repo_layout.py`（追加）

**Interfaces:**
- Produces: `skills/daily-papers/scripts/*.py`；README / ARCHITECTURE 中的目录约定表。

- [ ] **Step 1: 追加布局断言**

```python
    def test_daily_papers_layout(self):
        root = SKILLS / "daily-papers"
        self.assertEqual(sorted(root.glob("*.py")), [])
        for name in ("fetch_and_score.py", "enrich_papers.py", "parse_arxiv.py",
                     "extract_affiliations.py", "download_note_images.py"):
            self.assertTrue((root / "scripts" / name).exists(), name)

    def test_readme_and_architecture_state_directory_convention(self):
        for doc in (REPO_ROOT / "README.md", REPO_ROOT / "ARCHITECTURE.md"):
            text = doc.read_text(encoding="utf-8")
            for cell in ("`scripts/`", "`references/`", "`assets/`"):
                self.assertIn(cell, text, doc.name)
```

- [ ] **Step 2: 运行，确认失败**

Run: `python3 -m pytest tests/test_repo_layout.py -q`
Expected: 两个新用例 FAIL。

- [ ] **Step 3: 移动并修路径**

```bash
mkdir -p skills/daily-papers/scripts
for f in fetch_and_score enrich_papers parse_arxiv extract_affiliations download_note_images; do
  git mv "skills/daily-papers/$f.py" "skills/daily-papers/scripts/$f.py"
done
```

`fetch_and_score.py:26`：`parents[1]` → `parents[2]`。`enrich_papers.py:734` 用 `Path(__file__).parent / "extract_affiliations.py"`，同目录迁移不改。

- [ ] **Step 4: 修测试常量**

三个测试文件中 `"daily-papers" / "<x>.py"` → `"daily-papers" / "scripts" / "<x>.py"`。

- [ ] **Step 5: 修文档调用路径**

```bash
sed -i '' 's#\.\./daily-papers/\([a-z_]*\.py\)#../daily-papers/scripts/\1#g' skills/daily-papers-fetch/SKILL.md skills/paper-reader/references/image-troubleshooting.md
sed -i '' 's#skills/daily-papers/\([a-z_]*\.py\)#skills/daily-papers/scripts/\1#g' README.md ARCHITECTURE.md
```

- [ ] **Step 6: README 仓库结构块与目录约定**

`README.md` "## 仓库结构" 的代码块替换为：

```text
skills/
├── daily-papers/          # 每日推荐一句话入口；scripts/ 抓取、打分、富化、图片本地化
├── daily-papers-fetch/    # 抓取、打分、富化
├── daily-papers-review/   # 推荐点评生成
├── daily-papers-notes/    # 可选批量精读
├── generate-mocs/         # 手动刷新目录页
├── paper-reader/          # 单篇论文阅读与 Zotero 集成；scripts/ references/ assets/
├── book-reader/           # 整本书读书笔记与全书思维导图（MIT, Tao Jiang）
└── _shared/               # 共享配置；scripts/ MOC 生成、概念扫描、转义检查；references/ 画图规则
```

其后新增小节 `### 目录约定`，正文为 spec §5.1 的三行表（`scripts/` 可执行代码 / `references/` agent 读进上下文的规则 / `assets/` 填充到输出里的模板）加一句"`book-reader` 已按此布局，新增文件按此归位"。

- [ ] **Step 7: ARCHITECTURE 目录约定**

在 "## 核心心智模型" 表格之后新增 `### 目录约定` 小节，内容同 README 的三行表。

- [ ] **Step 8: 全量测试 + 残留扫描**

Run: `python3 -m pytest tests/ -q`
Expected: 97 passed。
Run: `grep -rn 'daily-papers/[a-z_]*\.py' --include='*.md' --include='*.py' skills tests README.md ARCHITECTURE.md | grep -v 'daily-papers/scripts/'`
Expected: 无输出。

- [ ] **Step 9: Commit**

```bash
git add -A skills tests README.md ARCHITECTURE.md
git commit -m "refactor(daily-papers): move scripts into scripts/; document scripts/references/assets convention"
```

---

### Task 4: 新增 `_shared/references/diagram-rules.md`

**Files:**
- Create: `skills/_shared/references/diagram-rules.md`
- Test: `tests/test_systems_template.py`（新增常量 `DIAGRAM_RULES` 与一个用例）

**Interfaces:**
- Produces: 文件路径 `skills/_shared/references/diagram-rules.md`，Task 6、7 以 `../../_shared/references/diagram-rules.md`（模板、concept-categories）和 `../_shared/references/diagram-rules.md`（SKILL.md）引用。

- [ ] **Step 1: 写测试**

```python
DIAGRAM_RULES = REPO_ROOT / "skills" / "_shared" / "references" / "diagram-rules.md"

    def test_diagram_rules_define_selection_table_and_fallback(self):
        text = DIAGRAM_RULES.read_text(encoding="utf-8")

        assert_table_header(self, text, ["图的类型", "默认工具", "备注"])
        for phrase in [
            "drawio --version", "DRAWIO_SKILL_DIR", "VERILOG_DIAGRAM_DIR",
            "seqlayout.py", "arch2drawio.py", "validate.py", "repair_png.py",
            "退回 Mermaid", ".drawio.png", "00_assets/", "^diag-",
            "references/mermaid-rules.md",
        ]:
            self.assertIn(phrase, text, phrase)
        self.assertIn("-f xml", text)          # .mmd 先转 .drawio，再导出
        self.assertNotIn("-f svg", text)       # 不走 SVG
```

- [ ] **Step 2: 运行，确认失败**

Run: `python3 -m pytest tests/test_systems_template.py -k diagram_rules -q`
Expected: FAIL（文件不存在）。

- [ ] **Step 3: 写 `diagram-rules.md`**

结构固定为三节，表格与编号规则直接取自 spec §4.1：

- `# 图表选型与绘制规则`，首段说明适用范围（paper-reader / book-reader / concept 笔记里所有 agent 自画的图）。
- `## 0. 选型表`：spec §4.1 的 6 行表，表头 `| 图的类型 | 默认工具 | 备注 |`。
- `## 1. draw.io 路线`：spec §4.1 的 5 条编号规则，并给出命令块：

```bash
drawio --version                                   # 需 ≥ 30，否则退回 Mermaid
DRAWIO="${DRAWIO_SKILL_DIR:-$HOME/.claude/skills/drawio-skill}"
VLOG="${VERILOG_DIAGRAM_DIR:-$HOME/.claude/skills/verilog-diagram}"
[ -d "$DRAWIO" ] && [ -d "$VLOG" ] || echo "画图 skill 缺失：退回 Mermaid，并在汇报中注明"

python3 "$DRAWIO/scripts/seqlayout.py" seq.json -o x.drawio          # 时序 / 协议
drawio -x -f xml -o x.drawio x.mmd                                    # 甘特 / 时间线：Mermaid gantt 先转 .drawio
python3 "$VLOG/scripts/arch2drawio.py" render fig.yaml -o x.drawio    # 流水线分级架构图

python3 "$DRAWIO/scripts/validate.py" x.drawio --score                # error 必须为 0
drawio -x -f png -e -s 2 -o x.drawio.png x.drawio                     # 可编辑 PNG（内嵌 XML）
python3 "$DRAWIO/scripts/repair_png.py" x.drawio.png
```

  产物命名 `00_assets/<note-name>_<desc>.drawio` 与 `.drawio.png`，嵌入写法 `![[00_assets/<note-name>_<desc>.drawio.png|说明]] ^diag-<desc>`，目视检查最多两轮，不导出 SVG 的原因一句话。
- `## 2. Mermaid 路线`：一句话指向 `references/mermaid-rules.md`（渲染 → 看图 → 重排闭环），不复制内容。

- [ ] **Step 4: 运行测试**

Run: `python3 -m pytest tests/test_systems_template.py tests/test_repo_layout.py -q`
Expected: PASS（含 `test_rule_files_referenced_under_references_dir`：新文件内对 `mermaid-rules.md` 的路径引用写成 `references/mermaid-rules.md`，且 `test_markdown_script_paths_resolve` 跳过带 `$DRAWIO` / `$VLOG` 的命令）。

- [ ] **Step 5: Commit**

```bash
git add skills/_shared/references/diagram-rules.md tests/test_systems_template.py
git commit -m "docs(_shared): add diagram-rules.md with tool selection table and draw.io route"
```

---

### Task 5: `md_escape_check` 对锚点与跳转链接的回归测试

**Files:**
- Test: `tests/test_md_escape_check.py`
- Modify (仅当测试失败): `skills/_shared/scripts/md_escape_check.py`

- [ ] **Step 1: 写测试**

```python
    def test_keeps_obsidian_block_ids_and_in_note_links(self):
        source = (
            "![Figure 3: delta CDF](https://arxiv.org/html/x/x3.png) ^fig3\n\n"
            "| a | b |\n|---|---|\n| 1 | 2 |\n\n^tab1\n\n"
            "见 [[#^fig3|Figure 3]]、[[#^tab1|Table 1]] 与 [[#机制1：Change-based encoding|机制1]]。 ^eq-ttft\n"
            "1. **KV codec**: 三个观察 ^contrib-1\n"
        )
        self.assertEqual(fix(source), source)
        self.assertEqual(check(source), [])
```

- [ ] **Step 2: 运行**

Run: `python3 -m pytest tests/test_md_escape_check.py -q`
Expected: PASS（这是把 spec 依赖的现状钉住的特征测试）。若 FAIL，在 `md_escape_check.py` 的 `PROTECTED` 中加入 `\^[a-z0-9-]+` 使块 id 受保护，再运行至 PASS。

- [ ] **Step 3: Commit**

```bash
git add tests/test_md_escape_check.py skills/_shared/scripts/md_escape_check.py
git commit -m "test(md_escape_check): pin that block ids and in-note links survive --fix"
```

---

### Task 6: 重写模板前半部分与 `系统设计总览`，补 `quality-standards.md` 跳转小节

**Files:**
- Modify: `skills/paper-reader/assets/paper-note-template.md`（顶部注释、`这篇论文为什么重要` 至 `系统设计总览` 全部、`Overhead 与兼容性` 开头）
- Modify: `skills/paper-reader/references/quality-standards.md`（新增 `## 笔记内跳转`）
- Test: `tests/test_systems_template.py`

**Interfaces:**
- Consumes: Task 4 的 `diagram-rules.md` 路径。
- Produces: 新章节名（Task 7 的 SKILL / daemon 引用必须逐字一致）：`## 问题定义`、`### 系统范围与层次`、`### 要解决的问题`、`### 现有方法与设计空间`、`## 动机实验与核心 Insights`、`### Insight N：{一句话结论}`、`### 设计原则到机制的映射`、`### 系统架构`、`### 执行流`、`### 优化目标与度量口径`、`## Overhead 与兼容性` 下的 `### 实现改动清单`。

- [ ] **Step 1: 改 `test_asset_template_uses_systems_sections`**

`required_sections` 改为：

```python
        required_sections = [
            "## 这篇论文为什么重要",
            "## 核心贡献",
            "## 问题定义",
            "### 系统范围与层次",
            "### 要解决的问题",
            "### 现有方法与设计空间",
            "## 动机实验与核心 Insights",
            "### Insight 1：",
            "### 设计原则到机制的映射",
            "## 系统设计总览",
            "### 系统架构",
            "### 执行流",
            "### 优化目标与度量口径",
            "## 关键机制拆解",
            "## 实验设置",
            "## 核心结果",
            "## Overhead 与兼容性",
            "### 实现改动清单",
            "## 批判性思考",
            "## 经验与可迁移启示",
            "## 复现",
            "## 关联笔记",
            "## 速查卡片",
        ]
```

`forbidden_sections` 追加：`"## 问题定义与瓶颈"`, `"## 作者核心 Insights"`, `"## 动机实验 / Characterization"`, `"### 系统瓶颈"`, `"### 本文的动机"`, `"### 特征图与数字证据"`, `"### 由实验得到的设计原则"`, `"### 系统架构与执行流"`, `"### 系统组成与职责"`, `"#### 模块关系图"`。

删除两条 `模块关系图` 正则断言（`assertRegex(... 核心决策模块 ...)` 与 `assertNotRegex(... Source\[ ...)`）。其余断言（`### 实现改动清单`、`#### 参数与权衡`、`### 模拟器与微架构参数`、`#### Silicon-feasibility`、```` ```mermaid ````、`flowchart LR`、`flowchart TB`、组件表表头）保留。

- [ ] **Step 2: 新增四个用例**

```python
    def test_template_section_order_follows_problem_evidence_design_chain(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        idx = text.index
        self.assertLess(idx("## 问题定义"), idx("## 动机实验与核心 Insights"))
        self.assertLess(idx("## 动机实验与核心 Insights"), idx("## 系统设计总览"))
        self.assertLess(idx("## 系统设计总览"), idx("## 关键机制拆解"))
        self.assertLess(idx("## Overhead 与兼容性"), idx("### 实现改动清单"))
        self.assertLess(idx("### 实现改动清单"), idx("### Overhead\n"))
        overview = text[idx("## 系统设计总览"):idx("## 关键机制拆解")]
        self.assertNotIn("### 实现改动清单", overview)

    def test_template_summary_and_problem_sections_carry_no_evidence(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        summary = text[text.index("## 这篇论文为什么重要"):text.index("## 核心贡献")]
        problem = text[text.index("## 问题定义"):text.index("## 动机实验与核心 Insights")]
        for marker in ("![", "$$", "|---"):
            self.assertNotIn(marker, summary, marker)
        for marker in ("![", "|---"):
            self.assertNotIn(marker, problem, marker)

    def test_template_system_architecture_offers_original_figure_or_self_drawn(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        arch = text[text.index("### 系统架构"):text.index("### 执行流")]
        flow = text[text.index("### 执行流"):text.index("### 优化目标与度量口径")]
        self.assertEqual(arch.count("![Figure"), 1)
        self.assertEqual(arch.count("```mermaid"), 1)
        self.assertIn("二选一", arch)
        self.assertIn("diagram-rules.md", arch)
        self.assertNotIn("```mermaid", flow)
        self.assertRegex(flow, r"(?m)^1\. ")
        self.assertIn("[[#机制1：", flow)

    def test_template_anchor_examples(self):
        text = ASSET_TEMPLATE.read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"\) \^fig\d+\s*$", text, re.M)), 2)
        self.assertIn("\n\n^tab-components\n\n", text)
        self.assertRegex(text, r"(?m)^\d\. .+ \^contrib-\d$")
        for link in ("[[#^fig1|Figure 1]]", "[[#^contrib-1|贡献1]]", "[[#^tab-components|组件表]]"):
            self.assertIn(link, text, link)
        for heading, short in (("机制1", "机制1"), ("Insight 1", "Insight 1")):
            m = re.search(rf"(?m)^### {re.escape(heading)}：(.+)$", text)
            self.assertIsNotNone(m, heading)
            self.assertIn(f"[[#{heading}：{m.group(1)}|{short}]]", text)
        self.assertIn("## 笔记内跳转", QUALITY_STANDARDS.read_text(encoding="utf-8"))
```

- [ ] **Step 3: 运行，确认失败**

Run: `python3 -m pytest tests/test_systems_template.py -q`
Expected: 上述 5 个用例 FAIL，其余 PASS。

- [ ] **Step 4: 重写模板顶部注释**

第 2 条中的 `问题定义与瓶颈` 改为 `动机实验与核心 Insights`；在第 8 条后追加（逐字）：

```
9. `## 这篇论文为什么重要` 和 `## 问题定义` 只写结论：不放图、表、数字；公式只允许出现在 `### 现有方法与设计空间` 作为定义。所有定量证据只在 `## 动机实验与核心 Insights` 出现一次。
10. 每个 `### Insight N：…` 以 **设计启发** 收尾并链接到对应机制；没有实验证据、靠作者推理得出的 insight 标注"作者论证"而不是"实验"。纯 characterization 论文允许所有 insight 来自实验、没有机制可映射。
11. `### 系统架构` 的结构图：论文有总体架构图时直接嵌入原图并挂 `^figN`；没有、或原图看不出模块边界与数据流时，才按 `../../_shared/references/diagram-rules.md` 自画一张（锚点 `^diag-arch`）。二选一，不并存。`### 执行流` 用编号步骤走读，不画第二张框图。
12. 锚点与跳转：Figure 行尾 ` ^figN`（子图 `^fig8a`）；表格结束后空一行、单独一行 `^tab-…`、再空一行；公式锚点挂在公式下方解释段末尾；Insight / 机制 / 章节用标题链接 `[[#标题|短名]]`，标题部分必须与目标标题逐字一致；核心贡献条目末尾 ` ^contrib-N`。id 只用小写字母、数字、连字符，全文唯一。正文提到 Figure / Table / 公式 / Insight / 机制 / 贡献时一律写跳转链接，不写裸文字。
```

- [ ] **Step 5: 重写 `这篇论文为什么重要` 到 `系统设计总览`**

按 spec §3.1 大纲与 §3.2 写法逐节替换。必须出现的样例标记：

- `## 核心贡献` 三条末尾分别 ` ^contrib-1` ` ^contrib-2` ` ^contrib-3`。
- `## 动机实验与核心 Insights` 下 `### Insight 1：{一句话结论}`、`### Insight 2：{一句话结论}`；Insight 1 内 `![Figure 2: Motivation / characterization](...) ^fig2`，末尾 `**设计启发**：{一两句} → [[#机制1：{名称}|机制1]]`。
- `### 设计原则到机制的映射` 三列表，首行 `| {原则} | [[#Insight 1：{一句话结论}|Insight 1]] | [[#机制1：{名称}|机制1]] |`。
- `### 系统架构`：`![Figure 1: System overview / 系统总览](...) ^fig1`；紧随 HTML 注释 `<!-- 结构图二选一：论文有总体架构图用上面的原图；没有或看不清模块边界与数据流时删掉原图行，改用下面按 diagram-rules.md 自画的一张（Mermaid 或 draw.io 嵌图），锚点 ^diag-arch -->`；然后保留一个 `flowchart TB` 的 Mermaid 骨架（节点 Core / State / Monitor / Executor / Policy，数据流实线、控制流虚线）；自然段提示；组件表（表头不变）；表后 `^tab-components`（前后空行）。
- `### 执行流`：`1. {模块A} → {模块B}：…（见 [[#^fig1|Figure 1]]）`、`2. …（[[#机制1：{名称}|机制1]]）`、`3. …`，末尾一句"多角色协议交互可按 `diagram-rules.md` 改用时序图"。
- `### 优化目标与度量口径`：原文保留，公式解释段末尾加 ` ^eq-objective`。
- `## 关键机制拆解` 内 `### 机制1：{名称}` 的 `设计动机` 段加一句"来自 [[#Insight 1：{一句话结论}|Insight 1]]"；`机制说明` 段提到总览图时写 `[[#^fig1|Figure 1]]`。
- `## Overhead 与兼容性` 开头插入 `### 实现改动清单`（原表格与"只有论文确实提出实现改动时才保留"的引用块原样搬入，`改动对象` 列示例写 `[[#机制1：{名称}|机制1]]`），其后才是 `### Overhead`。
- 删除旧的 `### 系统架构与执行流`、`### 系统组成与职责`、`#### 模块关系图`、原位置的 `### 实现改动清单`。

- [ ] **Step 6: `quality-standards.md` 新增 `## 笔记内跳转`**

放在 "## 提取完整性自检清单" 之前，内容为 spec §3.4 的 Obsidian 规则三条、约定表（含"笔记自建表格"与"agent 自画图"两行）和三条规则，原文照抄。

- [ ] **Step 7: 运行全部测试**

Run: `python3 -m pytest tests/ -q`
Expected: 全部 PASS（含 `test_figure_and_formula_guidance_uses_natural_explanations` 的 `rigid_phrases` 与 `test_asset_template_removes_cv_robotics_defaults`）。若 `rigid_phrases` 命中，改措辞而不是改测试。

- [ ] **Step 8: Commit**

```bash
git add skills/paper-reader/assets/paper-note-template.md skills/paper-reader/references/quality-standards.md tests/test_systems_template.py
git commit -m "feat(paper-reader): restructure note template (problem -> evidence -> design), single architecture figure, in-note anchors"
```

---

### Task 7: 同步 `SKILL.md` 与 `paper_daemon.py` 内嵌 prompt

**Files:**
- Modify: `skills/paper-reader/SKILL.md`（§3 核心质量规则、systems 额外要求、§6 完成后自检）
- Modify: `skills/paper-reader/scripts/paper_daemon.py`（"质量要求"第 5、6、8、13 条，新增第 15 条）
- Test: `tests/test_systems_template.py`

**Interfaces:**
- Consumes: Task 6 的章节名；Task 4 的 `diagram-rules.md` 路径。

- [ ] **Step 1: 写测试**

```python
    def test_skill_and_daemon_follow_new_structure(self):
        skill = PAPER_READER_SKILL.read_text(encoding="utf-8")
        daemon = PAPER_DAEMON.read_text(encoding="utf-8")
        for name, blob in (("SKILL.md", skill), ("paper_daemon.py", daemon)):
            for stale in ["问题定义与瓶颈", "作者核心 Insights", "动机实验 / Characterization",
                          "系统架构与执行流", "系统组成与职责", "模块关系图"]:
                self.assertNotIn(stale, blob, f"{name} still mentions {stale}")
            for fresh in ["动机实验与核心 Insights", "### 系统架构", "执行流", "实现改动清单",
                          "diagram-rules.md", "论文原图", "[[#^"]:
                self.assertIn(fresh, blob, f"{name} lacks {fresh}")
        self.assertIn("../_shared/references/diagram-rules.md", skill)
        self.assertIn("退回 Mermaid", skill)
```

- [ ] **Step 2: 运行，确认失败**

Run: `python3 -m pytest tests/test_systems_template.py -k skill_and_daemon -q`
Expected: FAIL。

- [ ] **Step 3: 改 `SKILL.md`**

- §3 规则 3 末尾追加："图表选型按 `../_shared/references/diagram-rules.md`：时序 / 协议交互、时间线 / 甘特、流水线分级架构图优先 draw.io 路线，画图 skill 不可用时退回 Mermaid 并在汇报中注明。"
- §3 新增规则 8："`### 系统架构` 优先直接嵌入论文的总体架构原图并挂 `^figN`；没有原图或看不出模块边界与数据流时才自画一张，二选一。`### 执行流` 用编号步骤走读，不画第二张框图。"
- §3 新增规则 9："正文引用 Figure / Table / 公式 / Insight / 机制 / 贡献一律用 `[[#^id|…]]` 或 `[[#标题|…]]` 跳转链接；锚点约定见 `references/quality-standards.md` 的"笔记内跳转"。"
- systems 额外要求中"必须根据论文 evaluation platform 画一张 Mermaid 测试系统连接关系图" → "画一张测试系统连接关系图（Mermaid，或按 `diagram-rules.md` 产出的 draw.io 嵌图）"；新增一条"章节顺序：`问题定义` → `动机实验与核心 Insights` → `系统设计总览`；`实现改动清单` 放在 `Overhead 与兼容性` 开头"。
- §6 自检：Template 检查一条中补"章节顺序与 `实现改动清单` 位置"；把 `系统组成与职责 … 模块关系图 …` 一条整体替换为"`### 系统架构` 是否有且只有一张结构图（优先论文原图，否则按 `../_shared/references/diagram-rules.md` 自画并走完渲染 / 校验闭环），配组件表与 `### 执行流` 编号走读？"；`模拟器与微架构参数` 一条的 "Mermaid 连接关系图" → "连接关系图（Mermaid 或 draw.io 嵌图）"；新增"每个 Figure / Table / 公式 / 贡献是否挂了唯一锚点，正文引用是否都是 `[[#^…]]` / `[[#标题|…]]` 跳转链接，标题链接文字与目标标题是否逐字一致？"。

- [ ] **Step 4: 改 `paper_daemon.py` 质量要求**

第 5、6 条替换为：

```
5. **系统架构**: `### 系统架构` 一图一段一表：论文有总体架构图时直接嵌入论文原图并挂 `^figN`；没有或看不出模块边界与数据流时才按 `skills/_shared/references/diagram-rules.md` 自画（Mermaid 或 draw.io 嵌图，锚点 `^diag-arch`），二选一；随后自然段解释所在层次、边界、输入输出、离线/在线分工，再给组件表（表后 `^tab-components`）
6. **执行流与改动清单**: `### 执行流` 用编号步骤走读一次请求 / 一个周期，每步引用架构图模块名并用 `[[#机制N：…|机制N]]` 指向机制，不画第二张框图；`### 实现改动清单` 放在 `## Overhead 与兼容性` 开头，按硬件 / software runtime / characterization 条件生成，不要对纯软件论文强行写硬件表
```

第 8 条 "画一张 Mermaid 测试系统连接关系图" → "画一张测试系统连接关系图（Mermaid，或按 diagram-rules.md 的 draw.io 嵌图）"。第 13 条中 "问题定义与瓶颈 / 系统设计总览 / …" → "动机实验与核心 Insights / 系统设计总览 / 关键机制拆解 / 实验设置 / 核心结果 / Overhead 与兼容性"，并追加 "章节顺序为 `问题定义` → `动机实验与核心 Insights` → `系统设计总览`，`这篇论文为什么重要` 与 `问题定义` 不放图表和数字"。新增：

```
15. **锚点与跳转**: Figure 行尾 ` ^figN`（子图 `^fig8a`），表格结束后独立一行 `^tab-…`（前后空行），公式锚点挂在解释段末尾，核心贡献条目末尾 ` ^contrib-N`；正文引用 Figure / Table / 公式 / Insight / 机制 / 贡献一律写 `[[#^id|…]]` 或 `[[#标题|…]]` 跳转链接，标题链接文字与目标标题逐字一致
```

- [ ] **Step 5: 运行全部测试**

Run: `python3 -m pytest tests/ -q`
Expected: 全部 PASS（`test_enhanced_template_propagated_to_paper_daemon_and_daily_notes`、`test_concept_generation_prompts_prefer_recall_and_exclude_datasets` 等既有 daemon 断言不受影响）。

- [ ] **Step 6: Commit**

```bash
git add skills/paper-reader/SKILL.md skills/paper-reader/scripts/paper_daemon.py tests/test_systems_template.py
git commit -m "feat(paper-reader): align SKILL rules and daemon prompt with restructured template and diagram routing"
```

---

### Task 8: 端到端验证

**Files:**
- Create (scratchpad, 不入库): `<scratchpad>/cpi-sample-front.md`、`<scratchpad>/drawio-smoke/`

- [ ] **Step 1: 用 CPI 笔记素材按新模板写前半部分样例**

来源：`…/PaperNotes/Computer Architecture/Research Methods & Evaluation/Performance Analysis Methods/A performance counter architecture for computing accurate CPI components.md`。只写到 `## 动机实验与核心 Insights` 结束。检查命令与预期：

```bash
S=<scratchpad>/cpi-sample-front.md
grep -c '^### Insight ' "$S"                               # 期望 3–4
grep -c '设计启发' "$S"                                     # 期望 == Insight 数
awk '/^## 这篇论文为什么重要/,/^## 核心贡献/' "$S" | grep -c '!\[\|\$\$\||---'   # 期望 0
grep -o '\^fig[0-9a-z]*' "$S" | sort | uniq -d             # 期望空（锚点唯一）
python3 skills/_shared/scripts/md_escape_check.py "$S"     # 期望退出码 0
```

- [ ] **Step 2: draw.io 路线冒烟**

```bash
D=<scratchpad>/drawio-smoke; mkdir -p "$D"; cd "$D"
DRAWIO="${DRAWIO_SKILL_DIR:-$HOME/.claude/skills/drawio-skill}"
cp "$HOME/.claude/skill-repos/drawio-skill/assets/demo-sequence.drawio" CacheGen_seq-demo.drawio
python3 "$DRAWIO/scripts/validate.py" CacheGen_seq-demo.drawio --score
drawio -x -f png -e -s 2 -o CacheGen_seq-demo.drawio.png CacheGen_seq-demo.drawio
python3 "$DRAWIO/scripts/repair_png.py" CacheGen_seq-demo.drawio.png
python3 -c "import sys; d=open('CacheGen_seq-demo.drawio.png','rb').read(); print('PNG' if d[:4]==b'\x89PNG' else 'NOT PNG', 'embedded-xml' if b'mxfile' in d else 'no-xml')"
```

Expected: validate 报告 `error: 0`；最后一行输出 `PNG embedded-xml`。用 Read 打开 PNG 目视确认可读。

- [ ] **Step 3: 全量回归与残留扫描**

```bash
python3 -m pytest tests/ -q                       # 全部 PASS
git diff --check                                  # 无输出
git status --short                                # 无未提交改动
grep -rn '问题定义与瓶颈\|作者核心 Insights\|模块关系图\|系统组成与职责\|assets/zotero_helper\|_shared/mermaid-rules\.md' \
  --include='*.md' --include='*.py' skills tests README.md ARCHITECTURE.md   # 无输出
```

- [ ] **Step 4: 汇报**

写明：测试数（基线 90 → 最终数）、draw.io 冒烟结果（已渲染 / 退回）、样例检查五项结果、vault 两份说明文件已更新。

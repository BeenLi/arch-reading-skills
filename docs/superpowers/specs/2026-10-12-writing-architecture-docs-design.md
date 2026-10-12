# writing-architecture-docs — 设计文档

日期：2026-10-12
状态：待实施
位置：`~/.claude/skills/writing-architecture-docs/`（独立 git 仓库，个人通用 skill）

## 1. 背景与目标

vault `002-notes/001 使用指南/` 下已有 4 份同格式的"X-架构和使用文档.md"（CCB、LLMServingSim、plan-tree、dailypaper-skills），最初由旧机器上的一个 Codex skill 生成，该 skill 已不在本机。`dailypaper-skills/ARCHITECTURE.md` 在本次目录重构、模板重写后已过时，需要重生成。

目标：

- 重建这个生成器为可复用 skill：输入任意本地仓库（或 git URL），输出同格式的架构和使用文档。
- 文档的每个论断都能回溯到源码文件；结构固定，便于跨仓库阅读。
- 自带校验脚本，既是 agent 的自检，也是 skill 本身的自动化测试。
- 用它重生成 `dailypaper-skills/ARCHITECTURE.md`，并把旧文档里仍成立的内容并回。

## 2. 非目标

- 不自动执行目标仓库的程序或测试来"实证"行为；文档是静态源码分析，运行结论只来自仓库自带的 README / 脚本 / 测试。
- 不生成 README；不改目标仓库其他文件。
- 不替 Obsidian 做索引或 MOC。

## 3. 目录结构

```
~/.claude/skills/writing-architecture-docs/
├── SKILL.md                   # 流程（触发、六步、落盘规则、汇报）
├── config.json                # {"guide_dir": "<vault>/002-notes/001 使用指南"}；环境变量 ARCH_DOC_GUIDE_DIR 覆盖
├── references/
│   └── doc-format.md          # 12 节契约：标题、必填元素、表头、来源标注、图数、长度
├── scripts/
│   ├── repo_facts.py          # 确定性收集仓库事实 → Markdown
│   └── check_doc.py           # 校验文档是否符合契约 → 退出码 0/1 + 逐条报告
├── tests/
│   ├── test_repo_facts.py
│   └── test_check_doc.py
└── docs/superpowers/          # 本 spec 与 plan
```

Mermaid 规则复用 `~/.claude/skills/_shared/references/mermaid-rules.md`（dailypaper-skills 通过 symlink 提供）；该文件缺失时 SKILL.md 退回"渲染一次、目视检查"的最小闭环。

## 4. 文档契约（`references/doc-format.md`）

文件名：`<Name>-架构和使用文档.md`。`<Name>` 取仓库名或项目自称。

**头部**（固定三要素）：

1. 引用块一句话定位："一份面向日常研发的 `<Name>` 说明书：解释它是什么、…、以及排查问题时优先看哪些源码和文档。"
2. 三行元信息：`源仓库：`（remote URL 或"本地仓库"）、`本次分析的本地路径：`、`本次分析的提交：`（`<短 hash> <日期> <subject>`）。
3. 不写 frontmatter；不用 Obsidian task 语法。

**正文 12 节**（H2 编号与标题固定；`<Name>` 代入）：

| # | 标题 | 必填元素 |
|---|---|---|
| 1 | 一句话理解 `<Name>` | 三段：是什么；由哪几条主线/目录组成及各自职责；不是什么、核心输入输出 |
| 2 | 核心心智模型 | 表 `概念 \| 来源 \| 含义`，6–12 行，来源列写文件路径 |
| 3 | 总体架构 | 一张 Mermaid（`flowchart TB` 为默认）+ `### 3.1 组件职责` 表 `组件 \| 关键文件 \| 职责` |
| 4 | 项目如何工作 | ≥ 2 个 `### 4.x` 主链路走读，按时间顺序编号步骤，每步引用文件；多角色交互可用 `sequenceDiagram` |
| 5 | 安装与启动 | 命令块只能来自 README / 脚本 / 配置文件，逐条注明出处 |
| 6 | 常用命令 / 使用指南 | 按场景分 `### 6.x` |
| 7 | 配置项与环境变量 | 表格；每项写默认值与定义位置 |
| 8 | 常见使用场景 / 推荐工作流 | 编号场景，每个场景给命令或入口 |
| 9 | 源码入口索引 | 表 `想了解 \| 优先看` |
| 10 | 排错指南 | 表 `现象 \| 优先检查 \| 依据` |
| 11 | 开发者视角的模块关系 / 维护注意点 | 可含第二张 Mermaid；写耦合点、改一处要同步改哪些 |
| 12 | 已知不确定点 | 列表；第一条固定说明"静态源码分析，未执行 …"，其余为未核实或互相矛盾的地方 |

允许在 12 节之后加 `## 附录 X. …`（例如 Obsidian 硬链接、目录约定），附录不计入编号。

**通用规则**：

- 每个 H2 节（第 12 节除外）至少出现一个反引号包裹的仓库内路径作为来源；第 5 节每个命令块前后一句话写出处。
- Mermaid 图 2–5 张，每张图下方一段自然段解释；按 mermaid-rules 渲染、看图、重排。
- 正文 250–800 行；中文叙述，标识符、命令、路径保持英文原样。
- 除头部"本地路径"行外，正文不出现 `/Users/…` 等机器专属绝对路径。
- 不杜撰命令、参数、文件；读不到的写进第 12 节。

## 5. SKILL.md 流程

1. **定位**：确定仓库路径（URL 则 `git clone --depth 50` 到 scratchpad）；运行 `python3 scripts/repo_facts.py <repo>` 得到 remote / HEAD / 目录树 / 入口候选 / README 命令 / 配置文件 / 已有文档。
2. **读源码**：按 入口 → 主链路 → 配置 → 测试 的顺序读；每读一个文件记一行"文件 → 它回答了契约哪一节"。大仓库先读 README 和入口，再按主链路展开，不逐文件通读。
3. **写文档**：按 `references/doc-format.md` 逐节写；Mermaid 走 mermaid-rules 闭环；写到 scratchpad 草稿。
4. **并回旧文档**（目标位置已有同名文档时）：逐节对照，旧文档中经代码核实仍成立、新稿没有的条目（排错表行、历史教训、设计原因）并回；不再成立的删除并在汇报里列出。
5. **落盘**：
   - 仓库已有 `ARCHITECTURE.md`，或用户要求写进仓库 → 原地写仓库文件（Python 打开覆盖写，不走"写临时文件再 rename"，以免打断硬链接），再保证 `guide_dir/<Name>-架构和使用文档.md` 是它的硬链接（inode 相同；不同则备份旧文件后 `ln` 重建）。
   - 否则 → 只写 `guide_dir/<Name>-架构和使用文档.md`。
   - 运行 `python3 scripts/check_doc.py <doc>`；可用时再跑 `~/.claude/skills/_shared/scripts/md_escape_check.py <doc>`；目标仓库若有测试引用该文档（如 dailypaper-skills 的 `tests/`），跑一遍。
6. **汇报**：输出路径、分析的提交、章节/图/行数、并回与删除的条目数、第 12 节条目数、校验结果。

## 6. 脚本契约

`scripts/repo_facts.py <repo> [--depth 2] [--max-entries 200]` → stdout Markdown：

- `remote`（`git remote get-url origin`，无则"本地仓库"）、`head`（`git log -1 --format='%h %ad %s' --date=short`）、`branch`。
- 目录树（深度默认 2；忽略 `.git node_modules __pycache__ .venv venv dist build .pytest_cache .claude .superpowers`），每个目录标文件数。
- 按扩展名的文件计数（前 10）。
- 入口候选：`README*`、`SKILL.md`、`ARCHITECTURE.md`、`pyproject.toml`、`setup.py`、`package.json`、`Makefile`、`Dockerfile`、`*.sh`、`bin/`、`scripts/`、`src/`、`tests/`。
- README 代码块中的命令行（以 `python3 ` `python ` `npm ` `pnpm ` `make ` `bash ` `pip ` `cargo ` `go ` 开头）。
- 顶两层的配置文件（`*.json *.toml *.yaml *.yml *.ini *.cfg`，排除 lock 文件）。
- 已有文档：`ARCHITECTURE.md`、`docs/` 下的 `*.md` 列表。

`scripts/check_doc.py <doc.md> [--name NAME]` → 逐条 `OK/FAIL` 报告，任一 FAIL 退出码 1：

- 头部：第一个非空行是 `> ` 引用块且含"说明书"；随后 3 行以 `源仓库：`、`本次分析的本地路径：`、`本次分析的提交：` 开头。
- H2：恰好 12 个编号节 `## N. 标题`，N=1..12 顺序递增，标题与契约一致：第 1 节以"一句话理解"开头；第 6、8、11 节接受斜杠两侧任一表述或完整表述；其余逐字一致。允许其后的 `## 附录`。
- 表头：第 2、3.1、9、10 节含契约表头（`assert_table_header` 风格的行首正则）。
- 第 4 节至少两个 `### 4.`；第 12 节至少两条列表项。
- Mermaid 块数 2–5。
- 行数 250–800。
- 来源标注：除第 12 节外每个 H2 节内至少一个反引号包裹、含 `/` 或 `.` 的路径 token。
- 禁用：`- [ ]` / `- [x]`；正文（头部三行以外）不含 `/Users/`、`/home/`、`C:\\`。
- `--name` 给出时校验引用块与第 1 节标题包含该名字。

## 7. 验证（writing-skills 的 RED → GREEN → REFACTOR）

- 脚本：pytest 单元测试（fixture 仓库 / fixture 文档）。
- RED 基线：不带 skill，让一个 subagent 为 `~/.claude/skills/verilog-diagram` 写"架构和使用文档"到 scratchpad；用 `check_doc.py` 和人工阅读记录失败模式（结构漂移、无来源、杜撰命令、无不确定点）。
- GREEN：带 skill 重跑同一任务；`check_doc.py` 通过，人工复核论断可回溯。
- REFACTOR：把基线里出现的具体偏差写进 SKILL.md 的"常见错误"。
- 最终应用：用 skill 重生成 `dailypaper-skills/ARCHITECTURE.md`（并回旧文档的 目录约定、硬链接、排错表），硬链接 inode 不变，`dailypaper-skills` 的 `pytest tests/` 全绿（其中 `test_architecture_has_no_machine_specific_paths`、`test_readme_and_architecture_state_directory_convention`、`test_markdown_script_paths_resolve` 直接约束该文档）。

## 8. 影响面

- 仓库外：只写 `config.json` 指定的 vault 目录和目标仓库的 `ARCHITECTURE.md`。
- `dailypaper-skills`：`ARCHITECTURE.md` 全量重写为 12 节格式；README 不动。

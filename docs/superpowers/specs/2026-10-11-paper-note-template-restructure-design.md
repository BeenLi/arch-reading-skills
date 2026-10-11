# 论文笔记模板重构、图表选型与目录统一 — 设计文档

日期：2026-10-11
状态：待实施
范围：`skills/paper-reader`、`skills/_shared`、`skills/daily-papers*`、`skills/book-reader`（仅路径引用）、`tests/`、`README.md`、`ARCHITECTURE.md`

## 1. 背景与目标

现有 `paper-note-template.md` 的前半部分存在三处结构问题，最新生成的 CPI 笔记能直接看到后果：

1. `作者核心 Insights` 排在 `问题定义与瓶颈` 和 `动机实验` 之前。读者先看到结论，再看到问题，最后才看到证据，和论文的论证顺序相反。
2. `作者核心 Insights` 的"现象 / 证据"和 `动机实验` 的图解读是同一批 Figure 的两次解读；`设计启发` 和 `由实验得到的设计原则` 几乎一一对应。同一证据写两遍。
3. `问题定义与瓶颈` 的 `系统瓶颈` 小节又在复述动机实验里的证据；`本文的动机` 在复述 insight 的设计启发。真正该放在这里的"系统在哪一层考虑问题、关注哪个问题"反而没有独立位置。

另外两个问题与结构无关但同样影响笔记质量：

4. 模板强制用 Mermaid 画三张图（系统架构与执行流、模块关系图、评测平台连接图），并建议协议类论文改用 `sequenceDiagram`。Mermaid 对时序图、甘特 / 时间线、流水线分级架构图效果差。本机已安装 draw.io 32.3.0、`drawio-skill`、`verilog-diagram`，可以作为推荐路线。
5. 仓库目录职责混乱：`paper-reader/assets/` 里混放模板和两个大脚本，`paper_daemon.py` 在 skill 根目录，`daily-papers/` 和 `_shared/` 的脚本与规则文件平铺；只有 `book-reader` 用了 `scripts/ + references/` 的规范结构。

目标：

- 新笔记的前半部分读起来是"范围 → 问题 → 证据 → insight → 设计"一条链，每个证据只出现一次。
- 正文里提到 Figure / Table / 公式 / Insight / 机制 / 贡献时都能在 Obsidian 内点击跳转。
- 时序、时间线、流水线分级三类图有一条明确的 draw.io 产出路线，产物能嵌入 Obsidian；画图 skill 缺失时自动退回 Mermaid。
- 全仓统一 `scripts/ · references/ · assets/` 三个目录的职责，并写进 README 和 ARCHITECTURE。
- `pytest tests/` 全绿（当前基线 90 passed）。

## 2. 非目标

- 不迁移 vault 中已有的 21 篇旧结构笔记。
- 不改 `concept-categories.md` 中 architecture 类概念"必须 Mermaid 组件图"的规则。概念图是小型组件图，Mermaid 够用。
- 不把 README 的 `~/.codex/skills` 安装说明改成 `~/.claude/skills`。
- 模板后半部分（`系统设计总览` 到 `速查卡片`）的章节结构不动，只改图表选型提示和锚点约定。
- 不把 draw.io 设为任何一张图的硬性要求。

## 3. 设计 A：模板前半部分

### 3.1 新大纲

```
# 论文笔记：{Title}
## 元信息
## 一句话总结
## 这篇论文为什么重要          ← 改写
## 核心贡献                    ← 条目加块锚点
## 问题定义                    ← 原「问题定义与瓶颈」
   ### 系统范围与层次           ← 新
   ### 要解决的问题             ← 新
   ### 现有方法与设计空间       ← 原「现有方法的局限」
## 动机实验与核心 Insights      ← 合并原「作者核心 Insights」+「动机实验 / Characterization」
   ### Insight 1：{一句话结论}
   ### Insight 2：{一句话结论}
   ### 设计原则到机制的映射     ← 新，3 列表
## 系统设计总览                ← 以下全部不变
## 关键机制拆解
## 实验设置
## 核心结果
## Overhead 与兼容性
## 批判性思考
## 经验与可迁移启示
## 复现
## 关联笔记
## 相关工作定位
## 速查卡片
```

删除的小节及去向：

| 删除 | 内容去向 |
|---|---|
| `问题定义与瓶颈 > 系统瓶颈` | 定量证据归 `动机实验与核心 Insights`；定性的"瓶颈在哪一类资源"一句话归 `要解决的问题` |
| `问题定义与瓶颈 > 本文的动机` | 归各 Insight 末尾的 **设计启发** |
| `作者核心 Insights`（整节） | 并入 `动机实验与核心 Insights`，每个 Insight 一个 H3 |
| `动机实验 / Characterization > 特征图与数字证据` | 图和解读分散到各 Insight 内部 |
| `动机实验 / Characterization > 由实验得到的设计原则` | 被 `设计原则到机制的映射` 表取代 |

### 3.2 各节的写法

**`这篇论文为什么重要`**：保留 3 条 bullet，定位改为"不读正文也能带走"的执行摘要。三条分别是：系统范围与问题（一句）、最关键的一个 insight（一句）、对部署或设计的意义（一句）。只写结论，不放图、表、数字、公式。

**`问题定义 > 系统范围与层次`**：论文把系统边界画在哪里。栈的哪一层（硬件微架构 / runtime / 调度器 / 网络协议 / 存储 …）、边界内外各是什么、哪些东西当作给定不动（模型、硬件、workload 分布）、输入输出是什么。这是读者判断"这篇论文跟我的问题是否同一层"的依据。

**`问题定义 > 要解决的问题`**：目标 workload 或 deployment 场景、优化对象（延迟 / 吞吐 / 面积 / 带宽 …）、约束条件，以及瓶颈落在哪一类资源（一句定性判断，不带数字）。最后用一句话明确写出"本文回答的问题是：…"。

**`问题定义 > 现有方法与设计空间`**：按类别而不是逐篇写前人方法：每一类优化什么轴、隐含什么假设、卡在哪。只做定性判断和必要的定义性公式，不放图和数字。这里是"设计空间框定"，逐篇的 wikilink 和外链仍在文末 `相关工作定位` 表，定量失效证据在 `动机实验与核心 Insights`。三层各司其职：框定 / 证据 / 导航。

**`动机实验与核心 Insights`**：每个 Insight 一个 `### Insight N：{一句话结论}`，内部顺序固定为：

1. 图 / 表 / 公式嵌入（这是证据在全文唯一出现的位置）。
2. 自然段解读：现象、定量证据、它在论证链里的作用。
3. **设计启发**：一两句，指向后面的 `[[#机制N：…|机制N]]`。

数量 2–4 个。没有实验证据、靠作者推理得出的 insight 也可以列，但要标注"作者论证"而不是"实验"。纯 characterization 论文允许所有 insight 都来自实验、没有机制可映射。

**`设计原则到机制的映射`**：一张三列表，不写自然段：

| 设计原则 | 来自 | 落到 |
|---|---|---|
| {原则一句话} | `[[#Insight N：…\|Insight N]]` | `[[#机制N：…\|机制N]]` |

它是 `动机实验` 到 `系统设计总览` 的桥。

### 3.3 写作约束注释（模板顶部 HTML 注释）的变更

新增：

- `这篇论文为什么重要` 和 `问题定义` 不放图、表、数字、公式；证据只在 `动机实验与核心 Insights` 出现一次。
- 每个 Insight 必须以 **设计启发** 收尾并链接到对应机制；没有实验证据的 insight 标注"作者论证"。
- 锚点与跳转约定（见 3.4）。

修改：第 2 条列出的"必须嵌入的叙事位置"把 `问题定义与瓶颈` 改为 `动机实验与核心 Insights`。

### 3.4 笔记内锚点与跳转

依据 Obsidian 官方文档（当前安装 1.12.7，核心 1.14.4）：

- 同笔记标题链接 `[[#标题|显示文字]]`；标题里避免 ASCII `# | ^ : %%`。模板用全角 `：`，不受影响。
- 块引用 `[[#^id|显示文字]]`。id 只能用拉丁字母、数字、连字符。单行段落在行尾加 ` ^id`；表格、列表、callout 等多行块把 `^id` 单独放一行，前后各空一行；列表的单个条目可以在条目末尾直接加。表格内部的单行不能被链接。
- `$$` 公式块后挂 id 的行为官方未定义，因此公式锚点挂在公式下方的解释段末尾。

约定表：

| 对象 | 定义处写法 | 引用处写法 |
|---|---|---|
| Figure | `![Figure 3: …](url) ^fig3`；本地嵌入 `![[00_assets/…\|Figure 3: …]] ^fig3`；子图 `^fig8a` | `[[#^fig3\|Figure 3]]` |
| Table | 表格结束后空一行，单独一行 `^tab1`，再空一行 | `[[#^tab1\|Table 1]]` |
| 公式 | 公式下方解释段末尾 ` ^eq-ttft`（语义名） | `[[#^eq-ttft\|TTFT 分解式]]` |
| Insight / 机制 / 任何章节 | 标题本身 | `[[#Insight 2：…\|Insight 2]]`、`[[#机制1：…\|机制1]]` |
| 核心贡献条目 | 列表项末尾 ` ^contrib-1` | `[[#^contrib-1\|贡献1]]` |
| agent 自画的图（Mermaid / draw.io） | 图块或嵌入行后 ` ^diag-arch`（Mermaid 代码块后单独一行，前后空行） | `[[#^diag-arch\|架构图]]` |

规则：

1. 每个对象只在首次出现处挂一个 id，id 全文唯一，全小写。
2. 正文其他位置提到 Figure / Table / 公式 / Insight / 机制 / 贡献时一律写成跳转链接，不写裸文字。
3. 标题链接的别名用短名（`Insight 2`、`机制1`），正文不出现超长链接文字。

落点：模板注释 + 模板示例（至少一个 `^fig`、一个 `^tab`、一个 `[[#^…|…]]`、一个 `[[#机制…|…]]`）；`references/quality-standards.md` 新增"笔记内跳转"小节；`SKILL.md` §6 自检加一条；`paper_daemon.py` prompt 加一条。

## 4. 设计 B：图表选型与 draw.io 路线

### 4.1 新文件 `skills/_shared/references/diagram-rules.md`

`mermaid-rules.md` 原文不动，只被新文件引用。新文件结构：

**§0 选型表**

| 图的类型 | 默认工具 | 备注 |
|---|---|---|
| 线性流程、模块依赖、评测平台连接（约 12 节点以内） | Mermaid `flowchart` | 按 `mermaid-rules.md` 走渲染 → 看图 → 重排 |
| 多角色时序 / 协议交互 | draw.io `seqlayout.py` | Mermaid `sequenceDiagram` 仅作 fallback |
| 时间线 / 甘特 / 调度与流水时序 | draw.io：Mermaid `gantt` 经 `drawio -x -f xml` 转为 `.drawio`，或直接 XML | 不要 `.mmd` 直接导出图片（drawio-skill 已记录会崩） |
| 流水线分级架构图、硬件数据通路 | `verilog-diagram` 的 `arch2drawio.py`（YAML 描述 → 论文插图风格） | 级、级间寄存器、SRAM 表字段、反馈线 |
| 空间结构（矩阵分块、内存布局） | matplotlib | 沿用 `concept-categories.md` 既有规则 |
| 树状导图 | Mermaid `flowchart LR` | 沿用 `book-reader/references/mindmap-rules.md` |

**§1 draw.io 路线**

1. 前置检查：`drawio --version`（需 ≥ 30）；`DRAWIO_SKILL_DIR`（默认 `~/.claude/skills/drawio-skill`）和 `VERILOG_DIAGRAM_DIR`（默认 `~/.claude/skills/verilog-diagram`）两个目录存在。任一缺失 → 退回 Mermaid，并在汇报中写明"draw.io 不可用，已退回 Mermaid"。
2. 产物：`.drawio` 源文件 + 可编辑 PNG（`drawio -x -f png -e -s 2` 后跑 `repair_png.py`；PNG 内嵌 XML，可用 draw.io 重新打开）。两者都放到笔记同目录 `00_assets/<note-name>_<desc>.drawio` 和 `.drawio.png`，命名沿用现有 note-name 截断 / hash 规则。
3. 嵌入：`![[00_assets/<note-name>_<desc>.drawio.png|说明]] ^diag-arch`。agent 自画的图用 `diag-` 前缀的语义 id，和论文 Figure 的 `figN` 区分；它不是论文原图，不影响 frontmatter `image_source`。
4. 校验：`validate.py` 零 error；Read PNG 目视检查，最多两轮修正。
5. 不用 SVG：draw.io 导出的文字是 `foreignObject`，在 Obsidian 的 `<img>` 嵌入下不保证渲染。

**§2 Mermaid 路线**：指向 `mermaid-rules.md`，不重复内容。

### 4.2 模板、SKILL、daemon 的改动

- 模板三张 Mermaid 骨架保留作为默认；旁边的说明段改为"按 `diagram-rules.md` 选型；若选 draw.io，用 `![[…drawio.png]]` 嵌入替换本块"。
- `SKILL.md` §3 规则 3 和 §6 自检中"必须 Mermaid"改为"Mermaid 或按 `diagram-rules.md` 产出的 draw.io 嵌图"，并要求汇报写明用了哪条路线、是否退回。
- `paper_daemon.py` prompt 第 5、6、8 条同步。

## 5. 设计 C：全仓目录统一

### 5.1 约定

| 目录 | 放什么 | 判断标准 |
|---|---|---|
| `scripts/` | 可执行代码 | `python3 …` 能跑的东西 |
| `references/` | agent 读进上下文的规则、指南、分类标准 | 读完影响 agent 怎么做 |
| `assets/` | 填充或复制到输出里的模板 | 内容会出现在生成物里 |

写进 `README.md` 的目录结构小节和 `ARCHITECTURE.md` 的"核心心智模型"。

### 5.2 目标结构

```
skills/
├── _shared/
│   ├── scripts/        user_config.py, moc_builder.py, generate_concept_mocs.py,
│   │                   generate_paper_mocs.py, clean_old_mocs.py, regenerate_concepts.py,
│   │                   scan_missing_concepts.py, md_escape_check.py
│   ├── references/     mermaid-rules.md, diagram-rules.md（新）
│   ├── user-config.json
│   └── user-config.local.json          （配置留在根目录，路径对用户可见，不动）
├── paper-reader/
│   ├── SKILL.md
│   ├── scripts/        zotero_helper.py, reorganize_notes.py, paper_daemon.py
│   ├── references/     concept-categories.md, image-troubleshooting.md,
│   │                   quality-standards.md, zotero-guide.md（不动）
│   └── assets/         paper-note-template.md
├── daily-papers/
│   ├── SKILL.md
│   └── scripts/        fetch_and_score.py, enrich_papers.py, parse_arxiv.py,
│                       extract_affiliations.py, download_note_images.py
├── book-reader/        已符合，不动
└── daily-papers-fetch / daily-papers-review / daily-papers-notes / generate-mocs
                        只有 SKILL.md，更新调用路径
```

全部用 `git mv` 迁移，保留历史。

### 5.3 必须同步修改的硬编码路径

Python 内部：

| 文件 | 现状 | 改为 |
|---|---|---|
| `_shared/scripts/user_config.py` | `config_dir = Path(__file__).resolve().parent` | `.parent.parent`（配置文件留在 `_shared/` 根） |
| `paper-reader/scripts/paper_daemon.py` | `_SHARED_DIR = parents[1] / "_shared"`；`_ASSETS_DIR = parent / "assets"` 插入 sys.path 以导入 zotero_helper | `_SHARED_DIR = parents[2] / "_shared" / "scripts"`；删除 `_ASSETS_DIR` 插入（zotero_helper 已是同目录） |
| `paper-reader/scripts/zotero_helper.py`、`reorganize_notes.py` | `parents[2] / "_shared"` | `parents[2] / "_shared" / "scripts"`（深度不变） |
| `daily-papers/scripts/fetch_and_score.py` | `parent.parent / "_shared"` | `parents[2] / "_shared" / "scripts"` |
| `daily-papers/scripts/enrich_papers.py` | `Path(__file__).parent / "extract_affiliations.py"` | 不变（同目录迁移） |
| `_shared/scripts/*.py` 互相引用 | `Path(__file__).resolve().parent` | 不变（一起迁移） |

文档里的调用路径：

| 文件 | 处数 | 改为 |
|---|---|---|
| `daily-papers-fetch/SKILL.md` | 3 | `../daily-papers/scripts/…` |
| `daily-papers-notes/SKILL.md`、`generate-mocs/SKILL.md` | 2 + 2 | `../_shared/scripts/…` |
| `paper-reader/SKILL.md` | 3 处 `assets/zotero_helper.py` + 2 处 `../_shared/mermaid-rules.md` | `scripts/zotero_helper.py`；`../_shared/references/mermaid-rules.md` |
| `paper-reader/references/zotero-guide.md` | 13 | `scripts/zotero_helper.py` |
| `paper-reader/references/image-troubleshooting.md` | 1 | `../daily-papers/scripts/download_note_images.py` |
| `paper-reader/references/concept-categories.md` | 2（一处相对、一处硬编码 `~/.claude/skills/_shared/`） | 加 `references/` 一层 |
| `book-reader/references/mindmap-rules.md` | 1（硬编码 `~/.claude/skills/_shared/`） | 加 `references/` 一层 |
| `paper_daemon.py` prompt 文本 | 3 处 `skills/paper-reader/references/…`、`assets/paper-note-template.md` | 不变（这两个目录没动） |
| `README.md` | 目录结构块、命令示例（`skills/_shared/*.py`、`skills/daily-papers/*.py`）、模板链接 | 对应加 `scripts/` |
| `ARCHITECTURE.md` | 组件表、源码入口表、Zotero 命令、MOC 命令 | 对应加 `scripts/` |

测试：11 个 `MODULE_PATH` / `SCRIPT_PATH` / `sys.path.insert` 常量对应加 `scripts/`。`test_zotero_helper.py` 里扫描全仓找旧 Zotero 命令的用例不依赖具体路径，不用改。

`.gitignore` 中 `skills/_shared/user-config.local.json` 和 `skills/paper-reader/assets/collection_mapping.json` 路径不变。已确认仓库外（`~/.claude/skills` 下其他 skill、`~/.claude/CLAUDE.md`）没有引用这些路径。

## 6. 测试与验证

### 6.1 `tests/test_systems_template.py`

- `required_sections` 删除 `## 问题定义与瓶颈`、`## 作者核心 Insights`、`## 动机实验 / Characterization`；新增 `## 问题定义`、`### 系统范围与层次`、`### 要解决的问题`、`### 现有方法与设计空间`、`## 动机实验与核心 Insights`、`### Insight 1：`、`### 设计原则到机制的映射`。
- `forbidden_sections` 新增上面三个旧 H2 以及 `### 系统瓶颈`、`### 本文的动机`、`### 由实验得到的设计原则`、`### 特征图与数字证据`。
- 新增顺序断言：`## 问题定义` 的位置 < `## 动机实验与核心 Insights` < `## 系统设计总览`。
- 新增锚点断言：模板包含 `^fig`、`^tab`、`[[#^`、`[[#机制` 样例；`这篇论文为什么重要` 到 `## 核心贡献` 之间没有 `![`、`$$`、`|---|`。
- 新增：模板和 `SKILL.md` 都提到 `diagram-rules.md`；`_shared/references/diagram-rules.md` 存在且含选型表表头和"退回 Mermaid"字样。
- 现有 `assertIn("```mermaid", text)` 等 Mermaid 骨架断言保留。
- `rigid_phrases` 列表保留；新模板文案不能命中其中任何一条。

### 6.2 `tests/test_md_escape_check.py`

新增用例：`![Figure 3: x](u) ^fig3`、`见 [[#^fig3|Figure 3]] 与 [[#机制1：X|机制1]]`、独立一行的 `^tab1` 三类文本经 `--fix` 后原样不变。

### 6.3 其他测试

路径常量更新后 `pytest tests/` 全绿。对迁移后的每个脚本至少跑一次 `python3 <script> --help` 或等价导入冒烟（`user_config` 能找到配置文件是关键）。

### 6.4 手工验证

- 用 CPI 笔记的素材按新模板手写一份前半部分样例（只到 `动机实验与核心 Insights`），放在 scratchpad 里对照检查：证据是否只出现一次、每个 Insight 是否以设计启发收尾、锚点和链接是否成对。
- draw.io 路线用 drawio-skill 自带样例走一遍 `.drawio → .drawio.png → 00_assets 命名`，确认产物能被 `![[…]]` 引用。

## 7. 影响面与兼容性

- `daily-papers-notes` 的质量门只检查 `批判性思考 / 复现 / 关联笔记 / 速查卡片` 四个 H2 和行数，不受本次改动影响。
- vault 里已有 21 篇旧结构笔记继续可读，MOC 生成不依赖章节名。
- 用户本机 `~/.claude/skills/*` 是指向仓库 `skills/*` 的 symlink，目录内部迁移后 symlink 仍有效；`user-config.local.json` 位置不变，用户配置不丢。
- 旧结构已被 `paper_daemon.py` prompt 复制了一份，必须一起改，否则批量模式继续产出旧结构。

## 8. 实施顺序（供 writing-plans 展开）

1. 目录迁移 + 路径修正 + 测试路径常量（先让仓库在新结构下全绿，后续改动都在新路径上做）。
2. `diagram-rules.md` + 相关引用。
3. 模板重构 + 锚点约定 + `quality-standards.md`。
4. `SKILL.md`、`paper_daemon.py` prompt、`daily-papers-notes` 核对。
5. 测试补齐、README / ARCHITECTURE 更新、手工验证。

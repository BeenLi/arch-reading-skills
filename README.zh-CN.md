# arch-reading-skills

[English](README.md) | **简体中文**

面向 `computer architecture`（多核、缓存与内存层次、异构计算、互连）和 `LLM systems` 的 Claude Code skills。默认推荐配置开箱即用：体系结构为主、LLM 系统为辅。把每日论文发现、单篇精读、概念库、整本书阅读、代码仓库阅读、Zotero 文献库和 Obsidian 笔记库连成一条本地工作流。

https://github.com/user-attachments/assets/1abe137d-5dd1-46b5-b766-40f239380d6c

<p align="center"><sub>51 秒演示 <code>daily-papers</code>：抓取 → 打分（关键词 + CCF 分级）→ 点评，数字和推荐都来自一次真实的 7 天运行。用 Remotion 制作。
⬇ <a href="https://github.com/BeenLi/arch-reading-skills/raw/main/media/daily-papers-demo.mp4">下载 mp4</a></sub></p>

| Skill | 一句话 |
|---|---|
| `daily-papers` | 每日论文推荐：抓取 → 点评 → 可选批量精读 |
| `paper-reader` | 读一篇论文，按模板写 Obsidian 笔记，并附带生成本篇新概念 |
| `concept-notes` | 概念库的唯一归属：生成 / 重写概念笔记，刷新论文与概念目录页 |
| `book-reader` | 读整本书，输出带全书思维导图的读书笔记 |
| `repo-reader` | 读一个代码仓库，写出可回溯到源码的架构和使用文档 |
| `verilog-diagram` | 把 Verilog / SystemVerilog（或论文、描述）画成可编辑的 draw.io 架构图、框图、状态机和控制结构图 |

Agent 负责理解意图、写点评和长篇笔记；Python 脚本负责确定性的抓取、打分、去重、Zotero 读取、路径规划、目录页生成和文本检查。

典型 Obsidian 输出：

```text
ObsidianVault/
├── DailyPapers/YYYY-MM-DD-论文推荐.md
└── PaperNotes/
    ├── Research Topics/.../{MethodName}.md
    ├── _concepts/{concept_type}/{ConceptName}.md
    ├── _inbox/{MethodName}.md
    └── _index_*.md
```

## 安装与配置

前置环境：

- Claude Code
- Python 3.10+
- Obsidian
- Zotero，可选但推荐（Zotero 10 本地 API 用于写操作）
- `poppler`（`pdftotext`、`pdfimages`）：`daily-papers` 抽取作者机构、从 PDF 裁图
- 可选，笔记里的自画图用（见 `skills/_shared/references/diagram-rules.md`）：
  - [diagram-design](https://github.com/cathrynlavery/diagram-design) 加 Playwright：默认路线，导出 PNG
  - draw.io 桌面版和 [drawio-skill](https://github.com/Agents365-ai/drawio-skill)：时序图、甘特图、流水线图；`verilog-diagram` 也需要
  - `mmdc`（mermaid-cli）：渲染退回的 Mermaid 图，供目检

macOS 上：

```bash
brew install poppler
npm install -g @mermaid-js/mermaid-cli
python3 -m pip install --user playwright && python3 -m playwright install chromium
npx skills add cathrynlavery/diagram-design -g -a claude-code
npx skills add Agents365-ai/drawio-skill -g -a claude-code
brew install --cask drawio
```

三种安装方式任选一种：

```bash
# 1. skills CLI：把每个 skill 复制到 ~/.claude/skills；之后用 `npx skills update -g` 更新
npx skills add BeenLi/arch-reading-skills -g -a claude-code
```

```text
# 2. Claude Code plugin：在 Claude Code 里运行；skill 名会带上插件前缀（arch-reading:paper-reader）
/plugin marketplace add BeenLi/arch-reading-skills
/plugin install arch-reading@arch-reading-skills
```

```bash
# 3. git clone + 软链接，适合开发：仓库里的改动立即生效
git clone https://github.com/BeenLi/arch-reading-skills.git && cd arch-reading-skills
mkdir -p ~/.claude/skills
for d in paper-reader concept-notes daily-papers book-reader repo-reader verilog-diagram _shared; do
  ln -sfn "$PWD/skills/$d" "$HOME/.claude/skills/$d"
done
```

`verilog-diagram` 还依赖第三方的 [drawio-skill](https://github.com/Agents365-ai/drawio-skill)（`npx skills add Agents365-ai/drawio-skill -g -a claude-code`），画框图和控制结构图另需 `yosys`、`sv2v` 和 Graphviz。

`skills/_shared` 不是 skill，是各 skill 共用的配置、脚本和画图规则。`paper-reader`、`concept-notes`、`daily-papers` 各自的 `_shared/` 目录里带一份生成的副本，所以三种安装方式都能单独装某个 skill。`book-reader` 和 `repo-reader` 只在 `~/.claude/skills/_shared` 存在时才用其中的转义检查和 Mermaid 规则，所以方式 3 也把它链接过去。

初始化 Obsidian 目录：

```bash
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

共享配置在 `skills/_shared/user-config.json`。个人路径和关键词覆盖写在 `~/.config/dailypaper-skills/user-config.json`，放在 skill 目录之外，更新 skill 时不会被覆盖；想用别的文件就设环境变量 `DAILYPAPER_CONFIG`。加载顺序：`user_config.py` 默认值 → `user-config.json` → 个人配置。两者都不存在时，仍兼容读取旧的 `skills/_shared/user-config.local.json`。

| 配置组 | 说明 |
|---|---|
| `paths.*` | Obsidian vault、论文笔记目录、每日推荐目录、概念库目录、Zotero DB / storage |
| `daily_papers.keywords` | 论文打分主关键词（标题命中 +3，摘要命中 +1） |
| `daily_papers.negative_keywords` | 标题命中即排除（`-999`）；只放和体系结构 / LLM 系统毫无关联的主题 |
| `daily_papers.domain_boost_keywords` | 体系结构相关性加分词 |
| `daily_papers.focus_phrases` | 重点方向短语（多核、缓存 / 内存层次、异构计算…），每命中一个 +1 |
| `daily_papers.venue_rank_scores` | venue 按 CCF 等级加分，默认 A / B / C = 3 / 2 / 1；主题不相关时不加 |
| `daily_papers.arxiv_categories` / `min_score` / `top_n` | arXiv 查询范围、最低分、单日候选上限 |
| `automation.*` | 是否自动刷新 MOC、commit、push；`git_push` 只有 `git_commit=true` 时生效 |
| `mocs.filename_prefix` | MOC 文件名前缀，常用 `_index_` |

## 工作流

下面每节先列对 Claude Code 说的话，再说明它做什么。

### 每日论文推荐 — `daily-papers`

```text
今日论文推荐
过去3天论文推荐
过去一周论文推荐
跑一下论文笔记
```

一个 skill 走完三步：

1. 抓取：DBLP、会议 program 页面、arXiv，候选不足时用 Semantic Scholar 补充；按关键词打分、历史去重、富化，输出 `/tmp/daily_papers_enriched.json`。
2. 点评：生成 `{DailyPapers}/YYYY-MM-DD-论文推荐.md`（主推 1–2 篇、备选最多 3 篇），更新 `.history.json`。
3. 笔记（可选）：为主推论文逐篇调用 `paper-reader` 生成精读笔记，并把笔记链接回填到推荐文件。

默认只跑前两步，避免一次推荐直接生成大量长笔记。`跑一下论文抓取 / 点评 / 笔记` 可以单独跑某一步。

### 读论文 — `paper-reader`

```text
读一下这篇论文 https://arxiv.org/abs/2509.24527
读一下这篇论文 ~/Downloads/paper.pdf
快速看一下这篇论文 https://arxiv.org/abs/2509.24527
批判性分析这篇论文 ~/Downloads/paper.pdf
读一下 Zotero item 2487
读一下 Zotero 里的 vLLM
批量读一下 Zotero 里 Link & Fabric Integration 分类下的论文
```

支持本地 PDF、arXiv / DOI / 网页链接、Zotero item、Zotero 搜索和 Zotero collection（批量时由 agent 逐篇调用本 skill）。

- 严格按 [`skills/paper-reader/assets/paper-note-template.md`](skills/paper-reader/assets/paper-note-template.md) 写笔记。
- 文件名用主方法名 / 系统名：`{MethodName}.md`。有 Zotero collection 时保存到 `{PaperNotes}/{collection_path}/`，没有就保存到 `{PaperNotes}/_inbox/`。
- `zotero_item_id`、`doi`、`arxiv_id` 写入 frontmatter，用于精确去重；批量模式默认跳过已有笔记。
- 笔记写完后调用 `concept-notes` 的模式 E，附带生成这篇论文新碰到的概念，再用 `check_note_links.py` 一起复查论文笔记和新概念的链接。
- Zotero 默认只读。只有用户明确要求移动、添加、移除 collection，或修正字段、删除条目时，才经 Zotero 本地 API 写入。

### 概念库与目录页 — `concept-notes`

```text
生成概念 KV Cache
补全缺失的概念
重新生成概念笔记
检查概念长度
更新索引
```

概念相关的规则和脚本只在这里维护：概念笔记模板在 [`skills/concept-notes/assets/concept-note-template.md`](skills/concept-notes/assets/concept-note-template.md)，分类规则在 [`skills/concept-notes/references/concept-categories.md`](skills/concept-notes/references/concept-categories.md)，扫描、重写、长度自检脚本在 `skills/concept-notes/scripts/`。

概念笔记放在 `{PaperNotes}/_concepts/`，按概念本身的性质分类，不按论文研究领域分类：

```text
data-structure / algorithm / mechanism / architecture
hardware / software-abstraction / metric / theory-model
```

也可以直接跑脚本：

```bash
python3 skills/concept-notes/scripts/scan_missing_concepts.py --with-seed --dry-run
python3 skills/concept-notes/scripts/check_concept_length.py "<概念笔记>"
python3 skills/_shared/scripts/generate_concept_mocs.py
python3 skills/_shared/scripts/generate_paper_mocs.py
```

扫描器会排除 `_concepts/`、`_inbox/`、`_index_*.md` 和论文笔记之间的互链。

### 读书 — `book-reader`

```text
帮我读这本书 ~/Downloads/book.epub
```

PDF / EPUB / MOBI / TXT 按页或按章提取，分批提炼知识点，输出带全书思维导图的读书笔记。

### 读代码仓库 — `repo-reader`

```text
读一下这个仓库 https://github.com/vllm-project/vllm
给 ~/hardware-project/tiny-gpu 写架构和使用文档
```

只做静态源码分析（不运行目标仓库的脚本、测试或构建），按固定 12 节契约写出《架构和使用文档》，每个论断可回溯到源码文件。

- 契约：[`skills/repo-reader/references/doc-format.md`](skills/repo-reader/references/doc-format.md)；机器校验：`python3 skills/repo-reader/scripts/check_doc.py <draft> --name <Name>`
- 原始材料：`python3 skills/repo-reader/scripts/repo_facts.py <repo>`（remote、HEAD、目录树、入口候选、README 命令、配置文件）
- 落盘：仓库已有 `ARCHITECTURE.md` 或用户要求时写进仓库并硬链接到 vault 的使用指南目录；否则只写 vault。目录由 `~/.config/dailypaper-skills/repo-reader.json` 的 `guide_dir` 决定（从 `skills/repo-reader/config.example.json` 复制），也可用环境变量 `ARCH_DOC_GUIDE_DIR` 覆盖

### 画硬件图 — `verilog-diagram`

```text
把这个 module 画成架构图 rtl/dcache_pipe.v
画出 load_pipe.v 的状态机
根据这篇论文画架构图
```

四种视角：论文插图风格的架构图（默认，agent 读代码写出排版描述，脚本确定性出图）、基于 Yosys 网表的门级框图、状态机图、整体控制结构图。产物是可编辑的 `.drawio`，有 draw.io 导出器时再出 PNG / SVG；没有 root 的 Linux 服务器用 `skills/verilog-diagram/scripts/install-drawio-linux.sh` 装导出器。

## 仓库结构

```text
skills/
├── daily-papers/          # 每日推荐：抓取 → 点评 → 可选批量笔记；scripts/ 抓取、打分、富化、图片本地化
├── paper-reader/          # 单篇论文阅读与 Zotero 集成；scripts/ references/ assets/
├── concept-notes/         # 概念的唯一归属：assets/ 概念笔记模板；references/ 分类规则；scripts/ 扫描、重写、长度自检；也负责刷新目录页
├── book-reader/           # 整本书读书笔记与全书思维导图（MIT, Tao Jiang）
├── repo-reader/           # 代码仓库 → 架构和使用文档；scripts/ 仓库事实采集、文档校验；references/ 12 节契约
├── verilog-diagram/       # Verilog / 论文 → draw.io 图；scripts/ 生成器、导出器、Linux draw.io 安装脚本；examples/ 样例
└── _shared/               # 共享配置；scripts/ MOC 生成、转义检查、venue 标签、CCF 分级；references/ 画图规则
scripts/sync_shared.py     # 把 skills/_shared 复制进用到它的三个 skill
```

### 目录约定

每个 skill 目录内按职责分三类子目录：

| 目录 | 放什么 | 判断标准 |
|---|---|---|
| `scripts/` | 可执行代码 | `python3 …` 能跑的东西 |
| `references/` | agent 读进上下文的规则、指南、分类标准 | 读完影响 agent 怎么做 |
| `assets/` | 填充或复制到输出里的模板 | 内容会出现在生成物里 |

新增文件按此归位；`tests/test_repo_layout.py` 会检查 `.py` 只在 `scripts/` 下，以及所有 Markdown 里的 `python3 …py` 路径都能解析。

## 开发维护

`skills/_shared` 是唯一源；`skills/{paper-reader,concept-notes,daily-papers}/_shared/` 是生成的副本，提交进 git，但不要手改。脚本先找源、找不到再用副本，所以在 clone 下改 `skills/_shared` 立即生效。提交前重新生成副本；pre-commit hook 和 CI 都会检查：

```bash
git config core.hooksPath .githooks   # 每个 clone 运行一次
python3 scripts/sync_shared.py         # 重新生成副本
python3 scripts/sync_shared.py --check # 只检查
```

```bash
python3 -m pytest tests/ -q
python3 skills/daily-papers/scripts/fetch_and_score.py > /tmp/daily_papers_top30.json
cat /tmp/daily_papers_top30.json | python3 skills/daily-papers/scripts/enrich_papers.py /tmp/daily_papers_enriched.json
```

Zotero helper 兼容期规则：

- 新文档和脚本使用 `zotero_helper.py resolve ...` 和 `zotero_helper.py note-path ...`
- 旧命令 `papers`、`search`、`info`、`find-collection` 暂时保留，会打印 deprecation warning；下一次相关清理时移除

## 注意事项

- 去重优先使用 `zotero_item_id`、`doi`、`arxiv_id`，再退到规范化标题 / 方法名匹配。
- 不用 Zotero 也可以跑每日推荐和 PDF / arXiv 论文阅读；Zotero 主要用于本地文献检索、PDF 定位和 collection path。
- `git_commit` 和 `git_push` 默认关闭。
- AI 生成的推荐、点评和笔记可能有事实错误或遗漏，应作为阅读辅助，不应替代研究判断。

## License

Apache-2.0. See [`LICENSE`](LICENSE).

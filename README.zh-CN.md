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
| `paper-to-zotero` | 给论文题目、DOI、arXiv ID 或链接，经 Zotero 10 本地 API 建条目、挂 PDF、放进正确的叶子分类 |
| `concept-notes` | 概念库的唯一归属：生成 / 重写概念笔记，刷新论文与概念目录页 |
| `book-reader` | 读整本书，输出带全书思维导图的读书笔记 |
| `kepu-research-doc` | 写带配图的中文科普 / 调研文档，把一个说法很乱的主题拆成几条独立的坐标轴 |
| `repo-reader` | 读一个代码仓库，写出可回溯到源码的架构和使用文档 |
| `verilog-diagram` | 把 Verilog / SystemVerilog（或论文、描述）画成可编辑的 draw.io 架构图、框图、状态机和控制结构图 |
| `gpt-image-bridge` | 经 `codex` CLI 用 ChatGPT 订阅调用 GPT Image 生成图片；每张图生成前先征得同意 |

Agent 负责理解意图、写点评和长篇笔记；Python 脚本负责确定性的抓取、打分、去重、Zotero 读取、路径规划、目录页生成和文本检查。各部分怎么配合（数据流、文件归属、模板、打分规则、测试）见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

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

```bash
# 2. Claude Code plugin：在 Claude Code 里运行；skill 名会带上插件前缀（arch-reading:paper-reader）
/plugin marketplace add BeenLi/arch-reading-skills
/plugin install arch-reading@arch-reading-skills
```

```bash
# 3. git clone + 软链接，适合开发：仓库里的改动立即生效
git clone https://github.com/BeenLi/arch-reading-skills.git && cd arch-reading-skills
mkdir -p ~/.claude/skills
for d in paper-reader concept-notes daily-papers paper-to-zotero book-reader repo-reader kepu-research-doc verilog-diagram gpt-image-bridge; do
  ln -sfn "$PWD/skills/$d" "$HOME/.claude/skills/$d"
done
```

`skills/_shared` 不是 skill，是各 skill 共用的配置、脚本和画图规则。用到它的 skill 都在自己的 `_shared/` 目录里带一份生成的副本（`paper-reader`、`concept-notes`、`daily-papers` 带整份，`repo-reader`、`book-reader`、`paper-to-zotero` 只带用到的文件），所以不管用哪种方式安装，每个 skill 都能单独工作。

### `verilog-diagram` 的额外依赖

`gpt-image-bridge` 就在本仓库里，上面三种方式装全仓库时会一起装上，不用另装；它是可选的，只给 `verilog-diagram` 出构图草图，没装时这一步直接跳过。

不在本仓库的是第三方 [drawio-skill](https://github.com/Agents365-ai/drawio-skill)：skills CLI 和 plugin 都只装本仓库里的 skill，不会顺带装它，要单独装一次（上面 macOS 依赖里那行就是它，装过可以跳过）：

```bash
npx skills add Agents365-ai/drawio-skill -g -a claude-code -y
```

只想装画图相关的 skill、不要整个仓库时，用 `--skill` 挑选：

```bash
npx skills add BeenLi/arch-reading-skills -g -a claude-code --skill verilog-diagram gpt-image-bridge -y
```

| 用到的视图 | 需要 |
|---|---|
| 架构图、状态机图（`.drawio`） | 只要本 skill |
| 框图、控制结构图、`validate.py` 校验 | drawio-skill，外加 `yosys`、`sv2v`（SystemVerilog）、Graphviz：`brew install yosys sv2v graphviz` |
| 导出 PNG / SVG | draw.io 桌面版（`brew install --cask drawio`）；无 root 的 Linux 服务器用 `skills/verilog-diagram/scripts/install-drawio-linux.sh` |
| 构图草图 | `gpt-image-bridge`（已随仓库安装）和登录过的 [`codex` CLI](https://github.com/openai/codex) |

skill 出图前会按 `$DRAWIO_SKILL_DIR` → `~/.claude/skills/drawio-skill` → `~/.agents/skills/drawio-skill` → plugin 缓存的顺序找 drawio-skill；找不到时给出上面的安装命令，你同意后才代为安装，不装就只画不依赖它的视图。

### 初始化 Obsidian vault

Obsidian 的 vault 就是本地一个普通文件夹：笔记是里面的 Markdown 文件，Obsidian 在它的根目录建一个隐藏的 `.obsidian/` 放这个 vault 的设置和插件（见官方文档 [How Obsidian stores data](https://obsidian.md/help/data-storage)）。这些 skill 只往这个文件夹里写 Markdown 和图片，不依赖 Obsidian 是否开着。

**1. 新建或打开 vault**（官方步骤见 [Manage vaults](https://obsidian.md/help/manage-vaults)）

- 新建：打开 Obsidian → 左下角 vault 图标 → **Manage Vaults…** → **Create new vault** 右边的 **Create** → 填 vault 名，**Browse** 选存放位置 → **Create**。
- 已有一个装笔记的文件夹：同一个菜单里选 **Open folder as vault** → **Open**，选中那个文件夹。

**2. 选存放位置**

- 只在这台电脑上用：放在主目录下即可，例如 `~/ObsidianVault`（也是默认配置里的路径）。
- 要在 Mac 和 iPhone / iPad 之间同步、用 iCloud：新建时在文件选择框里选 **iCloud Drive → Obsidian**，vault 落在 `iCloud Drive/Obsidian/<vault 名>`，终端里的路径是 `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<vault 名>`；在 Finder 里对它选“保持下载”，免得 iCloud 把文件挪到云端。其他同步方式（Obsidian Sync、Git 等）见 [Sync your notes across devices](https://obsidian.md/help/sync-notes)。
- 不要把一个 vault 建在另一个 vault 里面（内部链接只在本 vault 内解析），也不要建在系统目录里。

**3. 建这些 skill 要用的子目录**

`paths.obsidian_vault`（见下方[配置](#配置)）指向的目录下要有 `DailyPapers/` 和 `PaperNotes/`。它可以是 vault 根目录，也可以是 vault 里的一个子目录，下面两种任选：

```bash
# a. 直接放在 vault 根目录
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

```bash
# b. 集中放进 vault 的一个子目录，例如 001-input/PaperRead，把 paths.obsidian_vault 设成这个子目录
VAULT=~/ObsidianVault/001-input/PaperRead
mkdir -p "$VAULT/DailyPapers" "$VAULT/PaperNotes/_concepts" "$VAULT/PaperNotes/_inbox"
```

`_concepts/` 下的 8 个分类子目录和 `_index_*.md` 目录页由 skill 第一次写入时自动创建。`repo-reader` 的架构文档另写到 `repo_reader.guide_dir`，用到时再建。

**4. 建议的 Obsidian 设置**

- 设置 → 文件与链接 → 附件默认存放路径：选“当前文件所在文件夹下指定的子文件夹”，填 `00_assets`。skill 生成的笔记把图片放在笔记旁边的 `00_assets/`，这样你手动粘贴的图片也落在同一处。
- 社区插件 [Dataview](https://github.com/blacksmithgu/obsidian-dataview)：可选，想对 frontmatter（`venue`、`year`、`tags`、`zotero_collection`）做查询表时装。
- 用 Git 备份 vault 时，按官方建议把 `.obsidian/workspace.json` 和 `.obsidian/workspaces.json` 加进 `.gitignore`；`automation.git_commit` 要在 vault 是 git 仓库时才起作用。

### 配置

所有个人设置都放在**一个文件**里：`~/.config/arch-reading-skills/user-config.json`。它在 skill 目录之外，`npx skills update`、plugin 更新或 `git pull` 都不会覆盖它。个人配置只写和默认值（[`skills/_shared/user-config.json`](skills/_shared/user-config.json)）不同的部分：

```bash
mkdir -p ~/.config/arch-reading-skills
cat > ~/.config/arch-reading-skills/user-config.json <<'EOF'
{
  "paths": {
    "obsidian_vault": "~/ObsidianVault",
    "zotero_db": "~/Zotero/zotero.sqlite",
    "zotero_storage": "~/Zotero/storage"
  },
  "repo_reader": {
    "guide_dir": "~/ObsidianVault/002-notes/001 使用指南"
  }
}
EOF
```

读取规则：

- 先读默认值，再叠加你的个人配置文件。嵌套的对象按键逐层合并，所以 `{"daily_papers": {"min_score": 4}}` 只改这一个值。**列表会整个替换**：想加关键词，要先把默认的 `keywords` 列表复制过来再加。
- 设置 `ARCH_READING_CONFIG=/path/to/other.json` 就改用这个环境变量指定的个人配置文件：比如使用另一个 vault，或者想试一组别的关键词。设了它就不会再读`~/.config/arch-reading-skills/user-config.json`，即使它指向的文件不存在（测试靠这一点隔离本机配置）。
- 改完下次运行就生效。查看某项最终生效的值：

  ```bash
  cd skills/_shared/scripts && python3 -c "import user_config as u; print(u.paper_notes_dir(), u.daily_papers_config()['min_score'])"
  ```

| 配置项 | 说明 |
|---|---|
| `paths.obsidian_vault` | 放 `PaperNotes/` 和 `DailyPapers/` 的目录（可以是 vault 里的子目录，比如 `…/001-input/PaperRead`） |
| `paths.paper_notes_folder` / `daily_papers_folder` / `concepts_folder` | 它下面的文件夹名，默认 `PaperNotes` / `DailyPapers` / `_concepts` |
| `paths.zotero_db` / `zotero_storage` | Zotero 数据库和附件目录 |
| `paths.zotero_base_attachment_path` | 以 `attachments:…` 记录的链接附件的根目录（ZotMoov 之类），可选 |
| `daily_papers.keywords` | 论文打分主关键词（标题命中 +3，摘要命中 +1） |
| `daily_papers.negative_keywords` | 标题命中即排除（`-999`）；只放和体系结构 / LLM 系统毫无关联的主题 |
| `daily_papers.domain_boost_keywords` | 体系结构相关性加分词 |
| `daily_papers.focus_phrases` | 重点方向短语（多核、缓存 / 内存层次、异构计算…），每命中一个 +1 |
| `daily_papers.venue_rank_scores` | venue 按 CCF 等级加分，默认 A / B / C = 3 / 2 / 1；主题不相关时不加 |
| `daily_papers.arxiv_categories` / `min_score` / `top_n` | arXiv 查询范围、最低分、单日候选上限 |
| `automation.*` | 是否自动刷新 MOC、commit、push；`git_push` 只有 `git_commit=true` 时生效 |
| `mocs.filename_prefix` | MOC 文件名前缀，常用 `_index_` |
| `repo_reader.guide_dir` | `repo-reader` 写架构文档的 vault 目录 |
| `paper_to_zotero.collection_root` | `paper-to-zotero` 在哪个 Zotero 分类下挑叶子；默认 `Computer Architecture`；空字符串表示整个库。库里没有这个分类时 skill 会停下，告诉你原因和怎么改 |
| `paper_to_zotero.collection_hints` | 叶子说明，键是相对分类根的路径（`Memory & Storage / Storage Systems`），值写这里放什么论文。默认带 18 个体系结构叶子的说明，可以照着在 Zotero 里建分类；想按自己的方式分类就在个人配置里写自己的。说明按键逐条合并，只显示在库里真实存在的叶子旁，对不上的默认说明不会出现 |

哪个 skill、哪个脚本读哪一项，见 [`ARCHITECTURE.md` §5](ARCHITECTURE.md#5-配置)。

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

默认只跑前两步，避免一次推荐直接生成大量长笔记。`跑一下论文抓取 / 点评 / 笔记` 可以单独跑某一步。打分规则、点评分流和中间文件见 [`ARCHITECTURE.md` §2](ARCHITECTURE.md#2-每日推荐daily-papers)。

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

- 严格按 [`skills/paper-reader/assets/paper-note-template.md`](skills/paper-reader/assets/paper-note-template.md) 写笔记；章节结构、写作硬约束和写完后的检查见 [`ARCHITECTURE.md` §4](ARCHITECTURE.md#4-论文笔记模板paper-reader)。
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

扫描器会排除 `_concepts/`、`_inbox/`、`_index_*.md` 和论文笔记之间的互链。文件归属、五种模式、过滤规则和 8 类分类见 [`ARCHITECTURE.md` §3](ARCHITECTURE.md#3-概念库concept-notes)。

### 论文入库 Zotero — `paper-to-zotero`

```text
把 https://arxiv.org/abs/2405.10170 加到 Zotero
```

取元数据（Crossref / arXiv）→ 查重 → 按摘要判定放进哪个叶子分类（在 `paper_to_zotero.collection_root` 下挑，参考 `collection_hints` 的说明） → 下载 PDF（arXiv → 开放获取 → 出版社）→ 经 Zotero 10 本地 API 建条目并挂上 PDF。拿不到 PDF 就停下，不建条目。入库后问一次要不要用 `paper-reader` 精读。

### 科普调研文档 — `kepu-research-doc`

```text
写一份科普调研文档：DPU 的来由与软硬件架构
```

把主题和参考资料写成中文 Markdown + PDF：先给结论和坐标轴，再给术语速查，每条轴一节，讲每个对象“原本是干什么的”和怎么组合使用；另出封面图、宣传简介，以及和公开正文分开的私人映射文档。封面由 `scripts/make_cover.py` + `scripts/export_cover.py` 生成（需要 Playwright + Chromium），规范在 `references/COVER-STYLE.md`，样例在 `assets/`。

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
- 落盘：仓库已有 `ARCHITECTURE.md` 或用户要求时写进仓库并硬链接到 vault 的使用指南目录；否则只写 vault。目录由配置文件里的 `repo_reader.guide_dir` 决定（见[配置](#配置)）

### 画硬件图 — `verilog-diagram`

```text
把这个 module 画成架构图 rtl/dcache_pipe.v
画出 load_pipe.v 的状态机
根据这篇论文画架构图
```

四种视角：论文插图风格的架构图（默认，agent 读代码写出排版描述，脚本确定性出图）、基于 Yosys 网表的门级框图、状态机图、整体控制结构图。产物是可编辑的 `.drawio`，有 draw.io 导出器时再出 PNG / SVG；没有 root 的 Linux 服务器用 `skills/verilog-diagram/scripts/install-drawio-linux.sh` 装导出器。

### 生成图片 — `gpt-image-bridge`

```text
画一张这个系统的示意图
```

经 [`codex` CLI](https://github.com/openai/codex) 用你的 ChatGPT 登录调用 GPT Image，不需要 API key。每张图都消耗 ChatGPT 额度、要几分钟，所以 agent 先列出计划生成的图片，等你同意再生成。装了它时，`verilog-diagram` 会用它出可选的构图草图。导入自 [BeenLi/gpt-image-bridge](https://github.com/BeenLi/gpt-image-bridge)，它 fork 自 [oakplank/gpt-image-bridge](https://github.com/oakplank/gpt-image-bridge)（MIT）。

## 仓库结构

```text
skills/
├── daily-papers/          # 每日推荐：抓取 → 点评 → 可选批量笔记；scripts/ 抓取、打分、富化、图片本地化
├── paper-to-zotero/       # 论文 → 带 PDF 和分类的 Zotero 条目；scripts/zotero_add.py（Zotero 10 本地 API）
├── paper-reader/          # 单篇论文阅读与 Zotero 集成；scripts/ references/ assets/
├── concept-notes/         # 概念的唯一归属：assets/ 概念笔记模板；references/ 分类规则；scripts/ 扫描、重写、长度自检；也负责刷新目录页
├── book-reader/           # 整本书读书笔记与全书思维导图（MIT, Tao Jiang）
├── kepu-research-doc/     # 带配图、封面和宣传简介的中文科普 / 调研文档；scripts/ 封面与示意图生成、PNG 导出；references/ 封面规范；assets/ 样例
├── repo-reader/           # 代码仓库 → 架构和使用文档；scripts/ 仓库事实采集、文档校验；references/ 12 节契约
├── verilog-diagram/       # Verilog / 论文 → draw.io 图；scripts/ 生成器、导出器、Linux draw.io 安装脚本；examples/ 样例
├── gpt-image-bridge/      # 经 codex CLI 调 GPT Image；bin/ 包装脚本（MIT, oakplank）
└── _shared/               # 共享配置；scripts/ MOC 生成、转义检查、venue 标签、CCF 分级；references/ 画图规则
scripts/sync_shared.py     # 把 skills/_shared 复制进用到它的 skill
```

### 目录约定

每个 skill 目录内按职责分三类子目录：

| 目录 | 放什么 | 判断标准 |
|---|---|---|
| `scripts/` | 可执行代码 | `python3 …` 能跑的东西 |
| `references/` | agent 读进上下文的规则、指南、分类标准 | 读完影响 agent 怎么做 |
| `assets/` | 填充或复制到输出里的模板 | 内容会出现在生成物里 |

新增文件按此归位；`tests/test_repo_layout.py` 会检查 `.py` 只在 `scripts/` 下，以及所有 Markdown 里的 `python3 …py` 路径都能解析。哪些 skill 带哪些 `_shared` 文件，见 [`ARCHITECTURE.md` §6.1](ARCHITECTURE.md#61-_shared-怎么分发)。

## 新增一个 skill

以加一个 `foo-reader` 为例。skills CLI 和 plugin 都会自动发现 `skills/*/SKILL.md`，所以不需要在什么清单里注册它，但下面几处约定要照做，否则单独安装后会缺文件。

**1. 建目录和 `SKILL.md`**

```text
skills/foo-reader/
├── SKILL.md          # 必需
├── scripts/          # 可执行代码，SKILL.md 里相对 skill 目录调用
├── references/       # agent 读进上下文的规则、指南
└── assets/           # 会被填写或复制进输出的模板
```

`SKILL.md` 开头是 YAML frontmatter：

```markdown
---
name: foo-reader
description: 一两句话说明它做什么，再列出用户会说的触发词，比如「读一下这个 XXX」「帮我总结 XXX」。
---

# foo-reader

正文：分步骤写 agent 要做什么、调用哪些脚本、产出什么、什么情况下停下来问用户。
```

- `name` 和文件夹名一致，用小写字母和短横线。
- `description` 决定 Claude 什么时候自动调用它：先写用途，再写触发词，总长不超过约 1500 字符（Claude Code 列表里超出的部分会被截掉）。
- 字段和写法的完整说明见 Claude Code 官方文档 [Extend Claude with skills](https://code.claude.com/docs/en/skills)；也可以在 Claude Code 里让 `skill-creator` 或 `superpowers:writing-skills` 帮你起草和测试。

**2. 守住“单独安装也能用”**

`npx skills add` 只复制 skill 自己的文件夹，所以：

- 不要写 `../_shared/…`、`../concept-notes/…` 这类指向兄弟目录的路径，也不要在仓库里放软链接。
- 要用 `skills/_shared` 里的脚本或配置，就在 [`scripts/sync_shared.py`](scripts/sync_shared.py) 的 `TARGETS` 里登记这个 skill（`None` 是整份，或者列出要的几个文件），运行 `python3 scripts/sync_shared.py` 生成 `skills/foo-reader/_shared/` 副本。脚本里照抄 `skills/paper-to-zotero/scripts/zotero_add.py` 的 `_find_shared_scripts()`：在仓库里用源，单独安装时用副本。
- 个人设置（路径、分类名等）不要写死在 skill 里：在 `skills/_shared/user-config.json` 和 `user_config.py` 的 `DEFAULT_CONFIG` 里加一个通用的默认值，再加一个读取函数；你自己的值写进 `~/.config/arch-reading-skills/user-config.json`。
- 依赖本仓库之外的 skill 或命令行工具时，在 SKILL.md 开头写一段检查：缺失时告诉用户安装命令，用户同意后才安装，不装就跳过依赖它的步骤（参考 `verilog-diagram` 对 drawio-skill 的处理）。
- 从别处搬来的 skill 保留它的 `LICENSE`，并在 README 里写明来源（参考 `gpt-image-bridge`、`book-reader`）。

**3. 测试**

在 `tests/test_foo_reader.py` 里给脚本的确定性部分写测试，用到配置时用 `ARCH_READING_CONFIG` 指向临时文件，不要读本机配置。提交前跑：

```bash
python3 scripts/sync_shared.py --check
python3 -m pytest tests/ -q
```

`tests/test_repo_layout.py` 会自动检查新 skill：`.py` 只能放在 `scripts/` 下，Markdown 里每个 `python3 …py` 路径都能找到文件。

**4. 登记到文档和本机**

- 两份 README：开头的 skill 表、“工作流”里加一小节（触发词 + 做什么）、“仓库结构”里加一行。
- [`ARCHITECTURE.md`](ARCHITECTURE.md)：[§1](ARCHITECTURE.md#1-总览) 的 skill 总表和 [§6.1](ARCHITECTURE.md#61-_shared-怎么分发) 的 `_shared` 用法。它和作者 vault 里的使用指南是硬链接（见[附录](ARCHITECTURE.md#附录obsidian-硬链接)），要原地修改，不要整个替换文件。
- “安装与配置”第 3 种方式的 `for d in …` 列表里加上新名字，然后在本机建软链接，开一个新的 Claude Code 会话就能用：

  ```bash
  ln -sfn "$PWD/skills/foo-reader" ~/.claude/skills/foo-reader
  ```

## 开发维护

`skills/_shared` 是唯一源；`skills/<name>/_shared/` 是生成的副本，提交进 git，但不要手改。脚本先找源、找不到再用副本，所以在 clone 下改 `skills/_shared` 立即生效。提交前重新生成副本；pre-commit hook 和 CI 都会检查：

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

每个测试文件覆盖什么，见 [`ARCHITECTURE.md` §7](ARCHITECTURE.md#7-测试)。

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

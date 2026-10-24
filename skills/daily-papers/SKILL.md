---
name: daily-papers
description: |
  每日论文推荐：抓取 → 点评 → （可选）批量笔记，一个 skill 走完。
  用户说“今日论文推荐”“过去3天论文推荐”“过去一周论文推荐”“最近3天论文”“看看这周有啥论文”时使用；
  单步调试入口“论文抓取”“跑一下论文抓取”“论文点评”“跑一下论文点评”“批量笔记”“跑一下论文笔记”也走这里。

  默认只串联论文抓取和推荐生成两步，不自动精读；是否精读交给用户决定。
---

> **开始前**: 先说一声 "开始今日论文推荐 🐕" 并告知今天日期；多天模式同时告知抓取范围。

# 每日论文推荐

面向 `computer architecture`（为主）与 `LLM systems`（为辅）的每日推荐。流水线三步：

1. **抓取**：抓取、打分、去重、富化，输出 `/tmp/daily_papers_enriched.json`
2. **点评**：生成 `{DAILY_PAPERS_PATH}/YYYY-MM-DD-论文推荐.md`，更新 `.history.json`
3. **笔记**（可选）：为主推论文调用 `paper-reader` 生成精读笔记，补概念库，回填链接

## Step 0: 读取共享配置

先读取 `../_shared/user-config.json`，如果 `../_shared/user-config.local.json` 存在，再用它覆盖默认值。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `NOTES_PATH`
- `CONCEPTS_PATH`
- `DAILY_PAPERS_PATH`
- `KEYWORDS`
- `NEGATIVE_KEYWORDS`
- `DOMAIN_BOOST_KEYWORDS`
- `ARXIV_CATEGORIES`
- `MIN_SCORE`
- `TOP_N`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`
- `ENRICHED_INPUT = /tmp/daily_papers_enriched.json`

其中：

- `NOTES_PATH = {VAULT_PATH}/{paper_notes_folder}`
- `CONCEPTS_PATH = {NOTES_PATH}/{concepts_folder}`
- `DAILY_PAPERS_PATH = {VAULT_PATH}/{daily_papers_folder}`
- 所有关键词、分类、阈值都以共享配置为准
- `GIT_PUSH_ENABLED` 只有在 `GIT_COMMIT_ENABLED=true` 时才可能为真

## 路由：跑哪几步

| 用户说 | 执行 |
|--------|------|
| `今日论文推荐`、`每日推荐`、`今日论文` | Step 1 → Step 2（当天） |
| `过去3天论文推荐`、`最近3天论文`、`过去一周论文推荐`、`看看这周有啥论文` 等多天说法 | Step 1 → Step 2；天数只影响 Step 1 的 `--days`，推荐文件仍按今天日期命名 |
| `论文抓取`、`跑一下论文抓取` | 只跑 Step 1 |
| `论文点评`、`跑一下论文点评` | 只跑 Step 2；`/tmp/daily_papers_enriched.json` 不存在或不是今天生成的，先跑 Step 1 |
| `批量笔记`、`跑一下论文笔记` | 只跑 Step 3；今天的推荐文件不存在时，告知用户先跑 `今日论文推荐` 并停止，不自动补跑 |
| 推荐完成后用户明确说“精读主推”“都读一下” | 接着跑 Step 3 |

判断“是不是今天生成的”看文件修改时间（`stat`）；只想精读某一篇时，用户说 `读一下 论文标题`，交给 `paper-reader`，不走 Step 3。


## 解析天数

从用户输入中解析 `--days N` 参数：

- "过去一周"、"最近7天"、"一周的论文"、"看看这周有啥论文" → `--days 7`
- "过去3天"、"最近三天"、"抓3天" → `--days 3`
- "过去两周" → `--days 14`
- 无特殊指定 / "今日论文推荐" / "跑一下论文抓取" → 默认当天

## Step 1: 抓取

### 1a: 抓取 + 打分 + 合并去重

运行：

```bash
python3 scripts/fetch_and_score.py > /tmp/daily_papers_top30.json
python3 scripts/fetch_and_score.py --days N > /tmp/daily_papers_top30.json
```

脚本负责：

- 优先抓取 `DBLP proceedings / journal pages`
- 补抓最近会议的 `program pages`
- 抓 `arXiv API`
- 候选不足时再用 `Semantic Scholar` 做补充
- 按 `user-config.json` 的关键词、重点方向短语和 venue 的 CCF 等级打分，历史去重、Top-N 选择

默认目标 venue 包括：

- `ISCA`、`MICRO`、`HPCA`、`ASPLOS`
- `NSDI`、`SIGCOMM`、`OSDI`、`USENIX ATC`、`EuroSys`
- `SC`、`MLSys`

### 1b: 批量富化

运行：

```bash
cat /tmp/daily_papers_top30.json | python3 scripts/enrich_papers.py /tmp/daily_papers_enriched.json
```

脚本自动并发抓取 arXiv HTML/PDF 页面，补全：

- `figure_url`
- `authors`
- `affiliations`
- `section_headers`
- `captions`
- `has_hardware_eval`
- `has_end_to_end_eval`
- `has_real_workload`
- `method_name`
- `method_names`
- `method_summary`

检查 `/tmp/daily_papers_enriched.json` 是否存在且为有效 JSON 数组，记下抓取篇数和富化成功篇数。

抓取注意事项：

- 默认不再依赖 Hugging Face daily / trending。
- 候选应优先落在计算机体系结构问题上：多核与处理器、缓存与内存层次、内存扩展与分解、异构计算与加速器、互连与网络侧硬件；LLM 系统的硬件、内存与通信问题其次。
- venue 分按 CCF 等级给（A / B / C），但只是加分项，主题不对的论文不会因为 venue 强就自动进推荐。
- 如果 DBLP 或 program page 不可用，允许退化到 arXiv + Semantic Scholar。
- 本步不做 git 操作，不生成推荐文件，只输出临时 JSON。

## Step 2: 点评

前置检查：`/tmp/daily_papers_enriched.json` 不存在时，先跑 Step 1；单独要求“论文点评”时提示用户先抓取并停止。

### 2a: 扫描笔记库并匹配已有论文

- 扫描 `{NOTES_PATH}` 下所有分类目录（跳过 `_` 开头但保留 `_inbox`）。
- 扫描 `{CONCEPTS_PATH}` 下所有概念目录。
- 将候选论文和已有笔记按 `method_names`、标题中的方法名、文件名做不区分大小写匹配。

### 2b: 毒舌点评

#### 点评人设

你是一个毒舌但判断准确的 computer architecture researcher。用户的研究方向只聚焦以下两类，第一类为主：

1. 计算机体系结构（主）：
   - 多核 / 众核与处理器微架构（core、branch prediction、out-of-order、RISC-V）
   - 缓存层次与内存层次（cache coherence、replacement、prefetch、DRAM / HBM、虚拟内存）
   - 内存扩展与分解（CXL、memory pooling、tiered / hybrid memory）
   - 异构计算与加速器（GPU、FPGA、domain-specific accelerator、near-data processing、PIM）
   - 片上与系统互连、网络侧硬件（NoC、RDMA、SmartNIC / DPU、datacenter network）
   - 体系结构评测方法（模拟器、性能建模、workload characterization）
2. LLM 系统（辅）：LLM inference / serving / training 的硬件、内存层次、KV cache 与通信问题

#### 数据来源提醒

每篇论文的 `source` 来自抓取数据，常见取值包括：

- `dblp`
- `dblp-journal`
- `conference-program`
- `arxiv`
- `semantic-scholar`

`method_summary` 来自富化数据，用于撰写核心方法描述。`method_name` 是保守提取的单一系统/方法主名，优先用于命名和笔记匹配；`method_names` 是候选系统/方法名列表。

来源显示规则：

- `dblp` / `dblp-journal` → `🏛️ Venue 页面`
- `conference-program` → `📅 Conference Program`
- `arxiv` → `📄 arXiv`
- `semantic-scholar` → `🔎 Semantic Scholar`

#### 兜底过滤

如果某篇论文既不属于上面的体系结构方向，也不是 LLM 系统的硬件 / 内存 / 通信问题，直接跳过不写。与 LLM 无关的纯体系结构论文**不排除**，它们是主推的首选。典型可排除方向包括：

- 医学影像、蛋白质、药物发现
- 纯模型结构创新、纯 prompt、纯 agent workflow
- 纯 NLP / 纯多模态应用、没有系统贡献
- 纯 GUI agent、纯文档理解、纯金融
- 机器人 / 具身智能 / 自动驾驶 / 图形学
- 没有硬件或系统贡献的纯算法、纯软件工程、纯应用论文

补货规则：

- 按 `score` 从高到低选。
- 默认只保留少量 shortlist，不要凑满 20 篇。
- 没有 `has_hardware_eval` 的论文默认不进主推。
- 没有 `has_end_to_end_eval` 的 serving 论文只能做备选，除非证据特别强。
- 有 `has_real_workload` 的论文在同分情况下优先级更高。
- 在末尾 `被排除的论文` 一节注明标题和原因。

#### 评价标准

必须基于富化数据、摘要、章节标题和表格标题来判断。重点质疑：

- 瓶颈定义是否成立
- 端到端收益是否可信
- baseline 是否足够强
- 工作负载是否有代表性
- 硬件/部署假设是否过强
- 提升是否只在特定系统栈下成立
- 是否只是工程堆料或 measurement 不充分

禁止编造论文中不存在的缺陷。对不确定信息明确写 `摘要未提及` 或 `需要看全文确认`。

#### 输出结构

1. 开头用 `# 🔪 今日锐评`
2. 紧跟 `## 分流表`
3. 之后只输出两个短 section：
   - `## 主推（1-2 篇）`
   - `## 备选（最多 3 篇）`

主推/备选分流规则：

- `主推` 必须优先满足：主题高度相关 + `has_hardware_eval=true`
- 做 serving 的论文若 `has_end_to_end_eval=false`，最多只能进 `备选`
- 同分情况下，优先选择 `has_real_workload=true` 的论文
- 不满足以上信号、但方向仍然相关的论文，可以进入 `备选` 或 `可跳过`

分流表示例应改成 systems 语境，例如：

```markdown
## 分流表

| 等级 | 论文 |
|------|------|
| 🔥 主推 | [[FlashInfer]]（把 serving bottleneck 讲透了）· [[NetShaper]]（互连优化有硬数据） |
| 👀 备选 | [[CacheFlow]]（思路对，但评测还不够） |
| 💤 可跳过 | [[XXX]]（只有模型花活，没有系统贡献） |
```

完整点评中：

- 每篇只写 2 句，不要展开成长评：
  1. 这篇解决什么问题、核心方法是什么
  2. 为什么值得看 / 为什么只配做备选 / 为什么可跳过
- 仍然保留标题、链接、来源、必要时的首图
- `借鉴意义` 合并进第二句，不单独开小节
- 仅对 `主推` 和 `备选` 显示 `读一下 论文标题`

### 2c: 保存到 Obsidian

保存到 `{DAILY_PAPERS_PATH}/YYYY-MM-DD-论文推荐.md`。

frontmatter 示例：

```yaml
---
date: YYYY-MM-DD
keywords: computer architecture, multicore, cache hierarchy, memory hierarchy, heterogeneous computing, accelerator architecture, cxl, interconnect, rdma, llm serving, llm inference
tags: [daily-papers, auto-generated]
---
```

之后更新 `.history.json`，保留最近 30 天的记录。若启用了 git 自动化，再按现有规则执行 `git add / commit / push`。


## Step 3: 笔记（可选）

> 只有用户说“批量笔记”“跑一下论文笔记”，或在推荐完成后明确要求精读时才执行。

前置检查：`/tmp/daily_papers_enriched.json` 和今天的推荐文件 `{DAILY_PAPERS_PATH}/YYYY-MM-DD-论文推荐.md` 都要存在；任一不存在，告知用户需要先跑 Step 1 / 2，然后停止。

### 3a: 概念库补充

1. 扫描今天的推荐文件，提取所有 `[[...]]` 链接
2. 额外从 `/tmp/daily_papers_enriched.json` 的 `method_name` 和 `method_names` 中提取系统名 / 方法名
3. 读取 `../concept-notes/references/concept-categories.md` 的 seed list；命中的术语保留为候选
4. 合并去重后，按 `concept-notes` skill 的模式 A（过滤 → 查重 → 按增强模板创建 → `check_concept_length.py` 自检）补齐缺失概念；之后每篇论文笔记里的概念由 `paper-reader` 调用 `concept-notes` 模式 E 补齐

### 3b: 论文笔记生成

为推荐论文生成完整论文笔记：

1. 从今天的推荐文件中，读取分流表，筛选出 `🔥 主推` 的论文（`👀 备选` 和 `💤 可跳过` 不生成笔记，除非用户点名）
2. **质量检查已有笔记**（不是只看文件是否存在）：
   - 对已有 `📒 **笔记**` 标记的论文，用 Glob 找到对应笔记文件，检查行数
   - **行数 < 100 的视为骨架笔记，必须重新生成**（删除旧文件，重新调用 paper-reader）
   - 行数 >= 100 且包含 `## 批判性思考`、`## 复现`、`## 关联笔记`、`## 速查卡片` 的才算合格，可以跳过
3. 对每篇需要生成/重新生成的论文，调用 `paper-reader` skill（传入 arXiv 链接）
4. 笔记生成时，命中 `../concept-notes/references/concept-categories.md` seed list 的术语首次出现必须写成 `[[概念名]]`
5. 笔记生成后，paper-reader 会调用 `concept-notes` 模式 E 补充概念库，无需重复

> **铁律**：不论论文数量多少，`主推` 的论文**全部**生成笔记，一篇不能少。
> 耗时长是正常的，不是偷懒的理由。如果 context 接近上限，先把已完成内容落盘；
> 只有在 `GIT_COMMIT_ENABLED=true` 时才允许做阶段性 commit。然后告知用户剩余论文需要在新会话中继续，**绝对不能默默跳过**。

#### ⚠️ 笔记质量硬性要求

**绝对禁止自己手写简化版笔记。每篇论文必须通过 `paper-reader` skill 生成。**
不要因为"怕 context overflow"或"论文太多"就自己写个 70 行的骨架糊弄过去。
如果当前会话上下文接近上限，可以开启新会话继续剩余论文；但不能跳过任何一篇主推论文。

笔记质量由 paper-reader skill 自身保证（模板、公式、图片、概念链接等规则均在 paper-reader 中定义）。

#### 🔍 生成后质量验证（每篇必须执行）

每篇笔记生成后，立即验证：
1. 文件行数 >= 120（低于此值说明内容不完整）
2. 包含 `$$` 或 `$` LaTeX 公式（至少 2 处）
3. 包含 `![` 图片引用（至少 1 张）
4. 包含 `## 批判性思考`、`## 复现`、`## 关联笔记`、`## 速查卡片` section header
5. **不包含**独立的 `## 关键公式` 或 `## 关键图表` section header
6. 如果任一条件不满足，**删除文件并重新生成**

### 3c: 笔记链接回填

论文笔记全部生成完成后，将笔记链接回填到当天的推荐文件中。

**收集已有笔记**

用 Glob 扫描 `{NOTES_PATH}/` 下所有子目录（跳过 `{CONCEPTS_PATH}`），获取所有 `.md` 文件列表，建立 `{文件名(不含.md): 相对路径}` 的索引。

**匹配论文与笔记**

读取当天推荐文件 `{DAILY_PAPERS_PATH}/YYYY-MM-DD-论文推荐.md`，对每篇论文（`### N.` 开头的段落）：

1. 从论文标题中提取方法名/模型名（通常是标题冒号前的缩写，如 "DM0"、"BPP"、"PA3FF"）
2. 与上一步的笔记索引匹配（不区分大小写）
3. 也检查富化数据的 `method_name` 与 `method_names`（如果有残留数据）

**插入笔记链接**

对匹配到笔记的论文，在 `- **来源**:` 行之后插入一行：

```markdown
- 📒 **笔记**: [[笔记名]]
```

其中 `笔记名` 是不含 `.md` 后缀的文件名（Obsidian 会自动解析到正确路径）。

- 如果该论文已有 `📒 **已有笔记**` 或 `📒 **笔记**` 行，跳过不重复添加
- 使用 Edit 工具逐篇插入，确保不破坏文件其他内容

### 3d: 刷新 MOC 索引

只有在 `AUTO_REFRESH_INDEXES=true` 时才执行：

```bash
python3 ../_shared/scripts/generate_concept_mocs.py
python3 ../_shared/scripts/generate_paper_mocs.py
```

默认配置下这个开关是开启的，所以新增的概念和论文笔记通常会自动反映到各分类目录页中。

### 3e: Git 提交

仅当 `GIT_COMMIT_ENABLED=true` 时执行，并且必须先检查：

1. `VAULT_PATH/.git` 存在
2. `git add -A` 后确实有 staged changes

满足条件后才 commit：

```bash
cd {VAULT_PATH} && git add -A && git commit -m "daily papers: notes YYYY-MM-DD"
```

只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push。

## 输出

只跑 Step 1 + 2 时，用一句话告诉用户：

- 推荐文件已生成，路径是什么
- 抓取 / 富化了多少篇；主推 / 备选 / 可跳过各多少篇
- 默认不自动精读；如想精读，运行 `读一下 论文标题`，或 `跑一下论文笔记` 批量精读主推论文

跑了 Step 3 时，额外告知：

- 创建了多少个新概念
- 生成了多少篇论文笔记
- 回填了多少个笔记链接

## 重要约束

- 不要先要求用户手动跑 `跑一下论文抓取 / 点评 / 笔记`；这三句是单步调试入口，不是首页主交互。
- 默认不生成论文笔记；本地定时任务也应触发 `今日论文推荐`，而不是写死三条内部命令。

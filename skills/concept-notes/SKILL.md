---
name: concept-notes
description: |
  生成和维护 Obsidian 概念库（`_concepts/`），并刷新论文 / 概念目录页（MOC）。
  用户说“生成概念 XXX”“补一下概念 XXX”“补全缺失的概念”“扫描缺失概念”“重新生成概念笔记”
  “检查概念长度”“更新索引”“更新论文和概念目录”“刷新论文和概念目录”“刷新MOC”时使用。
  `paper-reader` 写完论文笔记后也调用本 skill（模式 E）补齐这篇论文新碰到的概念。
  概念的分类、模板、过滤规则和相关脚本都只在本 skill 里维护。
---

# 概念库与目录页

概念相关的规则只在这里维护：分类规则在 `references/concept-categories.md`，概念笔记模板在 `assets/concept-note-template.md`，脚本在 `scripts/`。这个 skill 负责三件事：

1. **生成概念**：为给定术语、为一篇论文笔记新碰到的概念，或为笔记里缺失的 `[[wikilink]]`，按增强模板创建概念笔记。
2. **维护概念**：扫描缺失概念、按增强模板批量重写旧概念、检查长度。
3. **刷新目录页**：重新生成论文目录页和概念目录页（MOC）。

## Step 0: 读取共享配置

先读取 `../_shared/user-config.json`，如果 `../_shared/user-config.local.json` 存在，再用它覆盖默认值。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `NOTES_PATH`
- `CONCEPTS_PATH`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`

其中：

- `NOTES_PATH = {VAULT_PATH}/{paper_notes_folder}`
- `CONCEPTS_PATH = {NOTES_PATH}/{concepts_folder}`
- `GIT_PUSH_ENABLED` 只有在 `GIT_COMMIT_ENABLED=true` 时才可能为真

后续步骤统一使用上面的变量。

## 路由

| 用户说 | 执行 |
|--------|------|
| `生成概念 XXX`、`补一下概念 XXX` | 模式 A，候选 = 用户给的术语 |
| `paper-reader` / `daily-papers` 写完一篇论文笔记后 | 模式 E，输入 = 论文笔记路径 |
| `补全缺失的概念`、`扫描缺失概念` | 模式 B 扫描 → 模式 A 创建 |
| `重新生成概念笔记`、`按新模板重写概念` | 模式 C |
| `检查概念长度` | 只跑 `check_concept_length.py` |
| `更新索引`、`刷新MOC` 等 | 只跑模式 D |

模式 A / B / C / E 写完概念后，若 `AUTO_REFRESH_INDEXES=true`，接着跑模式 D。

## 模式 A: 生成概念笔记

**A1: 过滤候选**

只保留 systems 技术概念、硬件 / 网络 / runtime / compiler / scheduling / metric / theory 术语、已经形成通用意义的方法名或系统抽象。跳过通用词、论文自身名称、公司名、人名。

过滤默认规则：
- 宁可漏判几个通用词，也不要误杀真正的 systems concept；不确定就创建，后续再 review。
- `Admission Control`、`Kernel Fusion`、`RDMA`、`NVLink`、`PCIe`、`NUMA`、`HBM`、`CXL`、`AllReduce`、`NCCL`、`CUDA` 等 seed list 或 systems 基石术语必须保留为候选。
- 数据集 / 仿真器不作为 concept；不要为 AMASS、LaFan1、MotionX、OmniGibson、IsaacLab、Acados 这类数据集、benchmark suite、仿真器、纯实验环境名称创建 concept。
- paper-method 按三档处理：论文首创且仅本论文实验 → `status/paper-specific`；论文具名实现且前人工作 / 被多篇当 baseline → 通用 concept；完全是前人工作且该论文只是引用 → 不独立建 concept。

**A2: 查重**

检查 `{CONCEPTS_PATH}/` 下是否已存在（搜索所有子目录，文件名和 `aliases` 都算，不区分大小写）。已存在的不重复创建。

**A3: 创建（自动归类）**

对缺失的概念，**根据概念类型自动归类到对应子目录**，不要全扔 `0-uncategorized/`。

分类规则见 `references/concept-categories.md`；**增强模板**骨架是 `assets/concept-note-template.md`，复制后填占位符。概念按性质分 8 类（`data-structure / algorithm / mechanism / architecture / hardware / software-abstraction / metric / theory-model`），**不**按论文研究领域分类。

每篇 concept 必须按增强模板生成：含「动机与痛点 / 直观例子 / 边界与对比 / 学习索引」4 个新必选段 + 按 `concept_type` 加的差异化段。长度：直观例子 ≤ 100 行、其他段 ≤ 90 行（不计 frontmatter 和图的源码）。`学习索引` 找不到证据时允许整段写 `TODO`，禁止凭空编造。

自画图按 `../_shared/references/diagram-rules.md`：默认用 diagram-design 画并导出 PNG 嵌入，不可用时才退回 Mermaid（`../_shared/references/mermaid-rules.md`）。

**A4: 自检**

每篇写完立即跑：

```bash
python3 scripts/check_concept_length.py "<新建的概念笔记路径>" ...
```

超长就压缩后重跑，直到通过。

## 模式 B: 扫描缺失概念

```bash
python3 scripts/scan_missing_concepts.py --dry-run
python3 scripts/scan_missing_concepts.py --with-seed --dry-run
```

脚本扫描 `{NOTES_PATH}` 里所有 `[[wikilink]]`，列出 `{CONCEPTS_PATH}` 中还没有的目标（CSV：术语、引用次数、来源笔记）。`--with-seed` 额外列出 seed list 中还没建的术语。

拿到列表后：按引用次数从高到低，先给用户看候选（数量 > 20 时只列前 20 并说明总数），再对候选走模式 A。

## 模式 C: 按增强模板重写已有概念

`regenerate_concepts.py` 为每个概念收集引用它的论文片段，拼成重写 prompt。按步骤走，**`--install` 前必须征得用户同意**：

```bash
python3 scripts/regenerate_concepts.py --dry-run --only "KV Cache"
python3 scripts/regenerate_concepts.py --write-prompts /tmp/concept_prompts
python3 scripts/regenerate_concepts.py --apply --llm-cmd <命令及参数>
python3 scripts/regenerate_concepts.py --diff
python3 scripts/regenerate_concepts.py --install
```

- `--apply` 输出写到 `_concepts_regen/`，不覆盖原文件。
- `--install` 会覆盖原概念；要求 vault git 工作区干净，除非用户明确要求 `--force`。
- 不想调外部 LLM 时，可以读 `--write-prompts` 的 prompt，由当前 agent 自己按模式 A 的模板重写，再跑长度自检。

## 模式 E: 为一篇论文笔记补概念

由 `paper-reader`（包括 `daily-papers` 笔记步骤里调用的 paper-reader）在论文笔记写完后调用。输入是论文笔记路径。

1. 扫描这篇笔记里所有 `[[概念]]` 链接（跳过 `[[#…]]` 笔内跳转和指向其他论文笔记的链接）。
2. 读 `references/concept-categories.md` 的 seed list，笔记正文里命中但没加链接的术语也列为候选，并回到论文笔记把首次出现改成 `[[概念名]]`。
3. 对候选走模式 A（过滤 → 查重，`{CONCEPTS_PATH}` 下**递归**查找 → 按 8 类 `concept_type` 归类、按增强模板创建 → 长度自检）。新概念的 `代表工作与具体用法` 段写上这篇论文 `[[笔记名]]` 怎么用它。
4. 已存在的概念不重写；如果这篇论文是它的新代表工作，只在 `代表工作与具体用法` 段追加一条。
5. 返回本次新建 / 追加的概念笔记路径列表，交给调用方做链接复查。

## 模式 D: 刷新目录页（MOC）

```bash
python3 ../_shared/scripts/generate_concept_mocs.py
python3 ../_shared/scripts/generate_paper_mocs.py
```

旧命名规则留下的目录页，先 dry-run 列出，用户确认后再 `--apply`：

```bash
python3 ../_shared/scripts/clean_old_mocs.py
```

用户手动要求刷新目录页时，不受 `AUTO_REFRESH_INDEXES` 开关影响。目录页生成逻辑必须来自仓库自带脚本，不依赖 `VAULT_PATH/scripts/*`；重复运行应保持幂等。

## git 自动化

默认配置下：

- `AUTO_REFRESH_INDEXES=true`
- `GIT_COMMIT_ENABLED=false`
- `GIT_PUSH_ENABLED=false`

只有在 `GIT_COMMIT_ENABLED=true` 时才做 git 操作，并且必须先检查：

1. `VAULT_PATH/.git` 是否存在
2. `git add` 之后是否真的有 staged changes

只有在上面两项都满足时才 commit。只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push。

## 输出

完成后告知用户：

- 新建 / 重写了多少个概念，各落在哪个 `concept_type` 目录
- 哪些候选被过滤掉、为什么
- 长度自检是否全部通过
- 目录页是否刷新、写到了哪里

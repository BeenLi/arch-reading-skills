---
name: repo-reader
description: 读一个代码仓库（本地路径或 GitHub/git URL），写出固定 12 节、每个论断可回溯到源码的「架构和使用文档」。当用户说「读一下这个仓库 / 这个项目」「帮我看看这个 GitHub 项目是干什么的、怎么用」「写/更新架构和使用文档 / 使用指南 / 说明书 / ARCHITECTURE.md」，或给出仓库路径、git URL 想了解它是什么、怎么用时使用。与 paper-reader（论文）、book-reader（书）并列：对象是代码工程。
---

# Repo Reader：代码仓库 → 架构和使用文档

给一个代码仓库写一份"架构和使用文档"：固定 12 节、每个论断可回溯到源码文件、只做静态源码分析。契约在 `references/doc-format.md`，机器校验在 `scripts/check_doc.py`，两者是同一份规则。

## 适用 / 不适用

- 适用：本地仓库路径、git URL、`~/.claude/skills/<x>` 这类 skill 目录；首次生成或重生成已有文档。
- 不适用：只想改文档里某一段（直接编辑即可）；想要 README、API 参考或教程（结构不同）。

## 流程

1. **定位仓库**：URL 则 `git clone --depth 50 <url> <scratchpad>/<name>`。然后：

   ```bash
   python3 ~/.claude/skills/repo-reader/scripts/repo_facts.py <repo>
   ```

   输出里的 remote / HEAD / 目录树 / 入口候选 / README 命令 / 配置文件 / 已有文档，就是头部三行和第 5、7、9 节的原始材料。
2. **读源码，不执行**：按 入口（README、SKILL.md、`__main__` / `main()`）→ 主链路（入口调用的模块，顺着 import 走）→ 配置（config 文件、argparse、环境变量）→ 测试（`tests/` 说明了哪些行为被保证）的顺序读。每读一个文件记一行 `文件 → 回答契约第几节`。大仓库不逐文件通读：README 和入口读全，主链路按调用展开，其余只看文件头和函数签名。**分析阶段只读取，不运行目标仓库的脚本、测试或构建**；文档里出现的每条命令都来自 README、脚本或配置文件，并注明出处。
3. **按契约写草稿**：到 scratchpad 写 `<Name>-架构和使用文档.md`，逐节对照 `references/doc-format.md`：
   - 头部三行标签逐字固定（`源仓库：` / `本次分析的本地路径：` / `本次分析的提交：`）；不是 git 仓库时提交行写 `无 git 仓库；最新文件 mtime <日期>`；要写进仓库的文档（见落盘规则），草稿里“本地路径”就直接写 `<repo>`。
   - 12 个 H2 标题逐字照抄契约（第 6、8、11 节可取完整标题或斜杠任一侧），不要按仓库"更贴切"地改词。
   - 第 3 节必须有 `### 3.1 组件职责` 表；第 2、9、10 节表头照抄。
   - 正文里的仓库路径写成相对路径或 `<repo>` / `<skill>` / `<vault>` 占位符，绝对路径只允许出现在头部"本地路径"一行。
   - Mermaid 2–5 张，按本 skill 的 `_shared/references/mermaid-rules.md` 渲染 → 看图 → 重排。
4. **并回旧文档**：目标位置已有同名文档时，先把它复制到 scratchpad 留底，再逐节对照。旧文档里经源码核实仍成立、新稿没有的条目（排错表行、历史教训、设计原因、附录）并回；不再成立的删除并在汇报里列出。不要为了保留旧内容改动章节结构。
5. **校验**：

   在本 skill 目录下运行：

   ```bash
   python3 scripts/check_doc.py <draft> --name <Name>
   python3 _shared/scripts/md_escape_check.py <draft>
   ```

   任一 FAIL 回到第 3 步修稿，不要放宽校验。
6. **落盘**（见下）→ 目标仓库若有引用该文档的测试（例如 `tests/` 里 grep 文档内容的用例），跑一遍。这是检查文档有没有破坏仓库的回归测试，不属于第 2 步的分析，结果也不写进文档。

## 落盘规则

`guide_dir` 是 vault 使用指南目录，按顺序取第一个有值的：环境变量 `ARCH_DOC_GUIDE_DIR`；`~/.config/arch-reading-skills/repo-reader.json` 的 `guide_dir`（首次使用从本 skill 的 `config.example.json` 复制过去改路径，放在 skill 目录外，更新 skill 不会覆盖）；旧位置本 skill 目录下的 `config.json`。

| 情况 | 写哪里 |
|---|---|
| 仓库已有 `ARCHITECTURE.md`，或用户要求写进仓库 | 原地覆盖写 `<repo>/ARCHITECTURE.md`，头部“本地路径”行写 `<repo>` 占位符（仓库里不记录机器路径），再保证 `guide_dir/<Name>-架构和使用文档.md` 是它的硬链接 |
| 其他（第三方仓库、skill 目录） | 只写 `guide_dir/<Name>-架构和使用文档.md` |
| 用户指定了输出路径 | 只写该路径 |

覆盖任何已有文件之前（仓库里的 `ARCHITECTURE.md` 或 vault 里只有一份的旧文档），确认第 4 步的 scratchpad 备份已经存在。原地覆盖用 Python `open(path, "w")`，不要用"写临时文件再 rename"的方式，否则硬链接会断。硬链接核对与重建：

```bash
stat -f "%i %l" <repo>/ARCHITECTURE.md "<guide_dir>/<Name>-架构和使用文档.md"   # inode 相同、link count ≥ 2
# inode 不同时：备份 vault 旧文件到 scratchpad → rm 它 → ln <repo>/ARCHITECTURE.md "<guide_dir>/<Name>-架构和使用文档.md"
```

## 常见错误

| 错误 | 修法 |
|---|---|
| 目标不是 git 仓库，就自创头部标签（"源位置"、"文件版本（mtime）"） | 三个标签不变，提交行写"无 git 仓库；最新文件 mtime …" |
| 把第 5 节改成"安装与依赖"、第 7 节改成"配置项与参数" | 标题是跨文档索引键，逐字照抄；仓库特有的措辞放在节内小标题 |
| 第 3 节用正文描述组件，没有 3.1 表 | 先填 `组件 \| 关键文件 \| 职责` 表，再写正文 |
| 用 `$S=/Users/...` 定义变量方便写命令 | 写 `<skill>` 或 `<repo>` 占位符，并在第 6 节开头说明代入方式 |
| 为了"实测"跑了目标仓库的脚本并把结果写成事实 | 只读源码；运行结论只引用 README / 测试 / 脚本注释，写不出的进第 12 节 |
| 第 2 节心智模型表堆到 13 行；第 4 节步骤只叙述不引用文件 | 表控制在 6–12 行，合并同类概念；每个编号步骤至少一个反引号路径 |
| 第 7 节默认值靠推断（"本机路径""无"），正文引用代码行号（"第 470 行附近"） | 默认值逐字抄代码里的常量；位置写函数名或小节标题，行号下次编辑就失效 |
| 把 check_doc 的 FAIL 当成校验器太严 | 校验器和契约是同一份规则；改稿，不改校验器 |

## 汇报格式

一段话写清：输出路径（及硬链接状态）、分析的提交、行数 / 图数 / 章节数、并回与删除的条目数、第 12 节条目数、`check_doc.py` 与 `md_escape_check.py` 结果。

# RED 基线：无 skill 时 subagent 的行为（2026-10-12）

任务：为 `~/.claude/skills/verilog-diagram` 写架构和使用文档，格式参考 vault 里的 LLMServingSim 文档。产出 516 行、3 张 Mermaid、12 节。

`check_doc.py --name verilog-diagram` 结果（9 条 FAIL，逐字）：

```
FAIL 头部：缺少以 `源仓库：` 开头的元信息行（实际：`源位置：`/Users/beenli/.claude/ski`）
FAIL 头部：缺少以 `本次分析的本地路径：` 开头的元信息行（实际：`本次分析的文件版本（mtime）：`SKILL.md` 20`）
FAIL 头部：缺少以 `本次分析的提交：` 开头的元信息行（实际：`外部依赖的 skill：`~/.claude/skills/`）
FAIL 第 5 节：标题应为 安装与启动 之一，实际 `安装与依赖`
FAIL 第 7 节：标题应为 配置项与环境变量 之一，实际 `配置项与参数`
FAIL 第 3 节：缺少表头 `| 组件 | 关键文件 | 职责 |`
FAIL 机器专属路径：第 3 行 `源位置：`/Users/beenli/.claude/skills/verilog-diagram`（本地 Claude`
FAIL 机器专属路径：第 220 行 `启动方式：skill 由 Claude Code 按 `SKILL.md` description 中的触发词自动加载（`
FAIL 机器专属路径：第 224 行 `以下 `$S=/Users/beenli/.claude/skills/verilog-diagram`。`
```

人工阅读补充：

1. **头部标签自由发挥**：目标不是 git 仓库时，agent 自创 `源位置：`、`本次分析的文件版本（mtime）：`、`外部依赖的 skill：` 三个标签，而不是沿用参考文档的三行固定标签并写"无 git"。
2. **章节标题意译**：`安装与启动` → `安装与依赖`，`配置项与环境变量` → `配置项与参数`，按仓库内容"更贴切"地改了标题，破坏跨文档一致性。
3. **漏掉固定子结构**：第 3 节没有 `### 3.1 组件职责` 表，组件职责散落在正文里。
4. **机器专属路径进正文**：第 6 节用 `$S=/Users/beenli/...` 定义变量，而不是 `<skill>` 占位符。
5. **擅自执行目标仓库的脚本**：做了 `outline`×2、`fsm list`、`rtl --list`、`render`×2 等"只读探针"，在 scratchpad 生成并删除产物，并把结论写成"本次实测"（4 处）。静态分析之外的行为，对用户仓库有副作用风险，且耗时（约 14 分钟、23 万 token）。
6. 做得好的：来源标注密度高（每节都有文件路径），第 12 节诚实列出未核实项，Mermaid 数量合规。

→ SKILL.md 需要：固定头部标签（含无 git 的写法）、标题逐字照抄契约、3.1 表必填、路径占位符规则、"只读源码、不执行"的明确边界，以及写完必跑 `check_doc.py`。

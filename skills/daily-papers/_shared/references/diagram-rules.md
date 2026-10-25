# 图表选型与绘制规则

适用于 paper-reader / concept 笔记里所有由 agent 自己画的图。先按 §0 选工具；选中 draw.io 的按 §1 产出并嵌入；选中 diagram-design 的按 §2 产出 PNG 并嵌入；两者都不可用时才按 §3 退回 Mermaid。论文原图不在本文范围内：论文有总体架构图时直接嵌入原图，不要重画。

## 0. 选型表

| 图的类型 | 默认工具 | 备注 |
|---|---|---|
| 线性流程、模块依赖、系统架构、评测平台连接、概念组件图（约 12 节点以内） | diagram-design（Flowchart / Architecture / Data flow） | 按 §2 导出 PNG 嵌入；不可用时按 §3 退回 Mermaid（`references/mermaid-rules.md`） |
| 多角色时序 / 协议交互 | draw.io `seqlayout.py` | draw.io 不可用时用 diagram-design 的 Sequence |
| 时间线 / 甘特 / 调度与流水时序 | draw.io：Mermaid `gantt` 经 `drawio -x -f xml` 转为 `.drawio`，或直接写 XML | 不要把 `.mmd` 直接导出成图片，drawio-skill 记录过该路径会崩 |
| 流水线分级架构图、硬件数据通路 | `verilog-diagram` 的 `arch2drawio.py`（YAML 描述 → 论文插图风格） | 级、级间寄存器、SRAM 表字段、反馈线 |
| 空间结构（矩阵分块、内存布局） | matplotlib | 沿用 `concept-categories.md` 既有规则 |
| 树状导图（book-reader） | Mermaid `flowchart LR` | 沿用 `book-reader/references/mindmap-rules.md`，不走 diagram-design |

## 1. draw.io 路线

1. **前置检查**：`drawio --version` 需 ≥ 30，且 `DRAWIO_SKILL_DIR`（默认 `~/.claude/skills/drawio-skill`）存在，否则所有 draw.io 路线 **退回 diagram-design**（§2，它也不可用时再退回 Mermaid）；`VERILOG_DIAGRAM_DIR`（默认 `~/.claude/skills/verilog-diagram`）只被流水线分级架构图路线需要，缺失时仅该路线退回。退回时在汇报中写明退到了哪条路线。
2. **产物**：`.drawio` 源文件 + 可编辑 PNG（内嵌 XML，可用 draw.io 重新打开）。两者都放到笔记同目录 `00_assets/<note-name>_<desc>.drawio` 和 `00_assets/<note-name>_<desc>.drawio.png`；`<note-name>` 沿用图片本地化的截断 / hash 规则。
3. **嵌入**：`![[00_assets/<note-name>_<desc>.drawio.png|说明]] ^diag-<desc>`。draw.io / diagram-design 的 PNG 嵌入行在行尾加锚点；退回 Mermaid 时代码块之后单独一行 `^diag-<desc>`，前后空行（与 `quality-standards.md` 的“笔记内跳转”一致）。agent 自画的图用 `^diag-` 前缀的语义 id，和论文 Figure 的 `^figN` 区分；它不是论文原图，不影响 frontmatter `image_source`。
4. **校验**：`validate.py` 零 error；用 Read 打开 PNG 目视检查，最多两轮修正。
5. **不导出 SVG**：draw.io 导出的文字是 `foreignObject`，在 Obsidian 的 `<img>` 嵌入下不保证渲染，所以统一用上面的可编辑 PNG。

```bash
drawio --version                                   # 需 ≥ 30，否则退回 diagram-design
DRAWIO="${DRAWIO_SKILL_DIR:-$HOME/.claude/skills/drawio-skill}"
VLOG="${VERILOG_DIAGRAM_DIR:-$HOME/.claude/skills/verilog-diagram}"
[ -d "$DRAWIO" ] || echo "drawio-skill 缺失：所有 draw.io 路线退回 diagram-design，并在汇报中注明"
[ -d "$VLOG" ] || echo "verilog-diagram 缺失：流水线分级架构图退回 diagram-design，其余路线不受影响"

python3 "$DRAWIO/scripts/seqlayout.py" seq.json -o x.drawio          # 时序 / 协议（participants + messages JSON）
drawio -x -f xml -o x.drawio x.mmd                                    # 甘特 / 时间线：Mermaid gantt 先转 .drawio
python3 "$VLOG/scripts/arch2drawio.py" render fig.yaml -o x.drawio    # 流水线分级架构图（YAML 描述）

python3 "$DRAWIO/scripts/validate.py" x.drawio --score                # error 必须为 0
drawio -x -f png -e -s 2 -o x.drawio.png x.drawio                     # 可编辑 PNG（内嵌 XML）
python3 "$DRAWIO/scripts/repair_png.py" x.drawio.png
```

`x` 替换为 `<note-name>_<desc>`，产物移入笔记同目录的 `00_assets/`。`seqlayout.py` 的输入格式见其文件头注释；`arch2drawio.py` 的 YAML 格式见 `verilog-diagram/SKILL.md` 第零节。

## 2. diagram-design 路线（流程、组件、评测平台的默认路线）

1. **前置检查**：`DIAGRAM_DESIGN_DIR`（默认 `~/.claude/skills/diagram-design`）存在，且 `python3 -c "import playwright"` 成功（PNG 导出依赖 Playwright + Chromium）。任一不满足就 **退回 Mermaid**（§3），并在汇报中写明"diagram-design 不可用，已退回 Mermaid"。
2. **画图**：按 `$DIAGRAM_DESIGN_DIR/SKILL.md` 选类型（模块结构 → Architecture，流程 / 执行流 → Flowchart 或 Data flow，评测平台 → Architecture 或 Deployment），输出参数取 Size `doc-inline`、Detail `balanced`（≤ 12 节点）、Audience `engineer`。首次使用时它会按 style guide gate 问一次配色；在 vault 根目录放一个 `.diagram-design` marker 指定 profile 后不再询问。
3. **产物**：`.html` 源文件和导出的 PNG 都放到笔记同目录 `00_assets/<note-name>_<desc>.html` / `00_assets/<note-name>_<desc>.png`；`<note-name>` 沿用图片本地化的截断 / hash 规则。本规则已明确要求导出，不受 diagram-design "导出需用户要求" 的限制。
4. **嵌入**：`![[00_assets/<note-name>_<desc>.png|说明]] ^diag-<desc>`，嵌入行在行尾加锚点。导出的 PNG 是透明背景，Obsidian 深色主题下若文字看不清，改用 diagram-design 的 dark 变体重新导出。
5. **校验**：用 Read 打开 PNG 目视检查，确认没有交叉线、回头线和语义错误的边，最多两轮修正。

```bash
DD="${DIAGRAM_DESIGN_DIR:-$HOME/.claude/skills/diagram-design}"
[ -d "$DD" ] && python3 -c "import playwright" || echo "diagram-design 不可用：退回 Mermaid，并在汇报中注明"
python3 "$DD/scripts/export_png.py" x.html x.png                      # 只截 <svg>，透明背景
```

`x` 替换为 `00_assets/<note-name>_<desc>`。

## 3. Mermaid 路线（仅作退回）

diagram-design 或 draw.io 都不可用时才画 Mermaid 代码块，一律遵守 `_shared/references/mermaid-rules.md`：方向选择、消除回头线、控制流与数据流分离，以及必做的"渲染 → 看图 → 重排"闭环。Mermaid 代码块之后单独一行 `^diag-<desc>`，前后空行。本文不复制其内容。

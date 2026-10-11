# 图表选型与绘制规则

适用于 paper-reader / book-reader / concept 笔记里所有由 agent 自己画的图。先按 §0 选工具；选中 draw.io 的按 §1 产出并嵌入；选中 Mermaid 的按 §2 指向的规则走"渲染 → 看图 → 重排"闭环。论文原图不在本文范围内：论文有总体架构图时直接嵌入原图，不要重画。

## 0. 选型表

| 图的类型 | 默认工具 | 备注 |
|---|---|---|
| 线性流程、模块依赖、评测平台连接（约 12 节点以内） | Mermaid `flowchart` | 按 `references/mermaid-rules.md` 走渲染 → 看图 → 重排 |
| 多角色时序 / 协议交互 | draw.io `seqlayout.py` | Mermaid `sequenceDiagram` 仅作 fallback |
| 时间线 / 甘特 / 调度与流水时序 | draw.io：Mermaid `gantt` 经 `drawio -x -f xml` 转为 `.drawio`，或直接写 XML | 不要把 `.mmd` 直接导出成图片，drawio-skill 记录过该路径会崩 |
| 流水线分级架构图、硬件数据通路 | `verilog-diagram` 的 `arch2drawio.py`（YAML 描述 → 论文插图风格） | 级、级间寄存器、SRAM 表字段、反馈线 |
| 空间结构（矩阵分块、内存布局） | matplotlib | 沿用 `concept-categories.md` 既有规则 |
| 树状导图 | Mermaid `flowchart LR` | 沿用 `book-reader/references/mindmap-rules.md` |

## 1. draw.io 路线

1. **前置检查**：`drawio --version` 需 ≥ 30；`DRAWIO_SKILL_DIR`（默认 `~/.claude/skills/drawio-skill`）和 `VERILOG_DIAGRAM_DIR`（默认 `~/.claude/skills/verilog-diagram`）两个目录存在。任一缺失 → **退回 Mermaid**，并在汇报中写明"draw.io 不可用，已退回 Mermaid"。
2. **产物**：`.drawio` 源文件 + 可编辑 PNG（内嵌 XML，可用 draw.io 重新打开）。两者都放到笔记同目录 `00_assets/<note-name>_<desc>.drawio` 和 `00_assets/<note-name>_<desc>.drawio.png`；`<note-name>` 沿用图片本地化的截断 / hash 规则。
3. **嵌入**：`![[00_assets/<note-name>_<desc>.drawio.png|说明]] ^diag-<desc>`。agent 自画的图用 `^diag-` 前缀的语义 id，和论文 Figure 的 `^figN` 区分；它不是论文原图，不影响 frontmatter `image_source`。
4. **校验**：`validate.py` 零 error；用 Read 打开 PNG 目视检查，最多两轮修正。
5. **不导出 SVG**：draw.io 导出的文字是 `foreignObject`，在 Obsidian 的 `<img>` 嵌入下不保证渲染，所以统一用上面的可编辑 PNG。

```bash
drawio --version                                   # 需 ≥ 30，否则退回 Mermaid
DRAWIO="${DRAWIO_SKILL_DIR:-$HOME/.claude/skills/drawio-skill}"
VLOG="${VERILOG_DIAGRAM_DIR:-$HOME/.claude/skills/verilog-diagram}"
[ -d "$DRAWIO" ] && [ -d "$VLOG" ] || echo "画图 skill 缺失：退回 Mermaid，并在汇报中注明"

python3 "$DRAWIO/scripts/seqlayout.py" seq.json -o x.drawio          # 时序 / 协议（participants + messages JSON）
drawio -x -f xml -o x.drawio x.mmd                                    # 甘特 / 时间线：Mermaid gantt 先转 .drawio
python3 "$VLOG/scripts/arch2drawio.py" render fig.yaml -o x.drawio    # 流水线分级架构图（YAML 描述）

python3 "$DRAWIO/scripts/validate.py" x.drawio --score                # error 必须为 0
drawio -x -f png -e -s 2 -o x.drawio.png x.drawio                     # 可编辑 PNG（内嵌 XML）
python3 "$DRAWIO/scripts/repair_png.py" x.drawio.png
```

`x` 替换为 `<note-name>_<desc>`，产物移入笔记同目录的 `00_assets/`。`seqlayout.py` 的输入格式见其文件头注释；`arch2drawio.py` 的 YAML 格式见 `verilog-diagram/SKILL.md` 第零节。

## 2. Mermaid 路线

Mermaid 图一律遵守同目录的 `references/mermaid-rules.md`：方向选择、消除回头线、控制流与数据流分离，以及必做的"渲染 → 看图 → 重排"闭环。本文不复制其内容。

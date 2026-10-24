---
name: verilog-diagram
description: 把 Verilog / SystemVerilog（以及论文、专利、口头描述）画成可编辑的 draw.io 图，四种视角——① 体系结构风格架构图（论文插图风格）：读代码提纲后由 agent 抓核心设计点，按流水级虚线分栏并标级名，流水寄存器/FIFO 落在分界线上，反馈线画出，多条流水按级对齐，SRAM 表写出单个 entry 的字段，加法器/乘法器/MUX 用经典电路符号，重点结构反差色/加粗，只在必要时编号；② 结构框图（门级细节）：Yosys 网表按流水级排布，画出寄存器、MUX、运算单元、比较器、逻辑门、存储阵列、FIFO、子模块；③ 状态机图：case(state) 形式的 FSM，圆圈表示状态、均匀排布；④ 整体控制结构图：只画控制信号，看各状态机之间如何互相驱动。当用户说「画架构图」「按论文风格画」「根据这篇论文/专利/描述画架构图」「把这个 module 画成框图」「画出 RTL 结构/数据通路/流水线」「Verilog 转框图」「画状态机 / FSM」「控制通路」「控制结构」「xxx 是怎么控制的」，或给出 .v/.sv 文件想看结构或控制流时使用。默认先画①（架构图），用户要看门级细节时用②。时序图用 drawio-skill。
allowed-tools: [Bash, Read, Write]
---

# Verilog → draw.io：架构图 / 结构框图 / 状态机 / 控制结构

四个视角，按问题选：**设计思想是什么**（给人讲、放论文/报告）→ `arch2drawio.py`（第零节，默认）；
**门级长什么样**（逐单元的数据通路）→ `rtl2drawio.py`；**怎么走的**（单个 FSM）→ `fsm2drawio.py fsm`；
**谁指挥谁**（整体控制结构）→ `fsm2drawio.py ctrl`。以控制为主的模块（FSM、译码、仲裁控制器）用框图会乱，改用后两者。

依赖：PyYAML；导出 PNG/SVG 需要 `drawio`（查找顺序 `$DRAWIO_BIN` → PATH → macOS app → `~/.local/opt/drawio`；
Linux 无 `$DISPLAY` 时自动套 `xvfb-run`，无 root 的服务器用本 skill 的 `scripts/install-drawio-linux.sh` 装）。**没有导出器时所有命令照常生成
`.drawio`，只少 PNG，stderr 提示一行**。框图/控制结构另需 `yosys`、`sv2v`（SystemVerilog）、`dot`（Graphviz），以及已安装的 drawio-skill
（默认 `~/.claude/skills/drawio-skill`，可用环境变量 `DRAWIO_SKILL_DIR` 覆盖；只调用它的 `autolayout.py`，不改它）。
三个生成脚本都接受 `--png` / `--svg` / `--scale N`（PNG 默认 scale 3，约 1 model unit = 3 px；`$DRAWIO_SCALE` 可改默认），
也可以单独导出：`python3 $S/scripts/drawio_export.py X.drawio --png --svg`。放进 Markdown/Obsidian 优先给 SVG，不糊。
`$S` 指本 skill 目录。`examples/` 里有两个对照样例：`wrr_arbiter.v`（单级 + 状态寄存器）、`load_pipe.v`（带 replay 的多级流水）。

## 零、体系结构风格架构图（arch2drawio.py）——默认

输入是**代码**（也可以是论文 / 专利 / 用户描述）。Yosys 网表太细、不适合架构图，所以这里不综合：脚本给出源码提纲，
**由你（agent）读代码、抓核心、写出图描述**，再由脚本确定性地排版出图。用户不需要写任何描述文件；只给用户看图，
除非用户想自己改描述。

```bash
python3 $S/scripts/arch2drawio.py outline src/*.sv --top gpu [--module core]   # 源码提纲（不综合）
python3 $S/scripts/arch2drawio.py render  fig.yaml -o diagrams/arch_core.drawio --png
```

`outline` 列出：层次树（generate 复制 ×N）、端口、**存储阵列**（深度 × 位宽，packed struct 的字段，同深度数组提示「可能同一张表」）、
**按级号命名的时序寄存器**（s1_ / stage2_ / if_id_ …）、状态机、疑似反馈信号（replay/kill/flush/stall/forward/refill…）、
实例间数据流（经共享信号，已去掉 clk/reset/循环变量）。论文/专利/描述输入时跳过这一步。

### 画图规则（写描述时遵守）
1. **只画核心**：先用一两句话说清设计的核心思想，只保留体现它的部件；胶合逻辑、clk/reset、调试口、零散控制都省略。
   一般 8–20 个框；超过就拆成两张（顶层一张 + 关键单元一张）。
2. **重点突出**：1–3 个关键设计点 `hl: true`（反差色：深底白字）或 `bold: true`（加粗）；关键路径的线也可 `| hl`。
   需要强调一块区域时用 `groups` + `hl: true`（浅底色框）。
3. **不给每个组件编号**：只在需要文字对照时给核心组件 `num: N`，并在 `callouts` 里写说明。
4. **单元框言简意赅**：框内只写名字（≤ 2 行），含义靠形状表达：运算用 `adder` / `mult` / `cmp` / `op` 圆形符号或 `alu`，
   选择用 `mux`（选择端 `x.sel` 从底部进），存储用 `table`，队列用 `fifo`，寄存器用 `reg`，门用 `and/or/xor/not`。
5. **SRAM 表写出单个 entry 的字段**：`table` 的 `fields` 写每个字段的含义（如 `[V, Tag (20b), Data (32b)]`），
   多路组相联用 `stack: 4`（叠放 + ×4）；同深度、同地址的并行数组合成一张表，每个数组一个字段。
6. **流水线**：`stages` 定义级（`id` + 功能 `sub`，如 `{id: S1, sub: 命中判断}`），脚本画虚线分界和级名；
   级间寄存器 / FIFO 用 `between: [S0, S1]`，脚本把它画在**分界线上**；反馈（目标在更早的级）自动沿底部走廊绕回，
   也可 `| fb`、`| fb via=top`（从上方绕）。**多条流水**用 `lanes`，各 lane 共用级的列，时序上对应的级自动对齐。
7. 不分级的块级图（顶层、SoC）不写 `stages`；复制的单元用 `stack: N`，每线程/每核资源用 `groups` 框起来。

### 描述格式（YAML）
```yaml
title: dcache_pipe：直接映射 D-Cache 查找流水线
stages: [{id: S0, sub: 选择 / 读阵列}, {id: S1, sub: 命中判断}, {id: S2, sub: 缺失 / 重放}]
lanes:  [{id: ld, name: Load 流水}, {id: st, name: Store 流水}]     # 可选，多条流水时
nodes:
  - {id: arr, type: table, label: "Cache 阵列 · 64 项", fields: [V, "Tag (20b)", "Data (32b)"], stage: S0}
  - {id: r1, type: reg, label: addr, between: [S0, S1]}              # 落在 S0|S1 分界线上
  - {id: tcmp, type: cmp, label: Tag 比较, stage: S1, hl: true}      # 圆形 "="，说明文字在下方
  - {id: rmux, type: mux, stage: S0, ports: 2}
edges:
  - "rmux => arr : idx | w=6"            # -> 数据  => 总线(粗)  ~> 控制(虚线)；w=N 位宽
  - "rpl -> rmux.sel : replay | fb hl"   # .sel/.en 从底部进，.top 从顶部进；fb 反馈，hl 强调，via=top，pos=src|dst
groups: [{label: "每线程 ×4", members: [rf, alu, lsu], hl: true}]
legend: {reg: 流水寄存器, fb: 反馈, ctrl: 控制, hl: 关键设计}      # 可用键：data bus ctrl fb hl hl_edge hl_region reg
callouts: {1: "只有在需要对照说明时才编号"}
```
节点类型：`block` `reg` `fifo` `table`(fields, rows, stack) `array`(dims, cell) `mux`(ports) `adder` `mult` `cmp`/`op`(sym)
`alu` `and` `or` `xor` `nand` `nor` `xnor` `not` `cloud` `mem` `xbar` `in` `out` `text` `dot`。
通用属性：`stage` / `lane` / `between`，`hl` `bold` `num` `stack`，微调用 `row` / `col`（在级内的行 / 列，可为负）、`dx` / `dy`、`w` / `h`。
其它：`array` 支持 `cell_labels`（逐格标签，如 T0..T3）和 `cell_h`（长方格，画线程通道）；`groups` 支持 `stack: N`
（整块区域叠放，如「Core ×2」并露出内部）和 `label_align: right`；`lanes` 的 `name` 留空 = 只分带不画标签；
边的 `| both` 画双向箭头（请求/响应）；同一列上下两个单元之间的反馈画成紧贴的短竖线（如 Dispatcher ⇅ Core）。

### 流程
1. `outline` + 读关键源码（或读论文/专利），写下核心思想 → 决定画哪一层、哪些是重点。
2. 把描述写到临时目录（scratchpad），**每个节点都给 `stage`**（有级时）。环路自动断开：名字像控制器的节点
   （sched / ctrl / fsm / arbiter / dispatch / 调度 / 控制 …，其次是控制线扇出多的）先开始，它的输出往右、回到它的边画成反馈；
   判断不对时对那条边显式写 `| fb`。
   **可选：构图参考（gpt-image-bridge，需用户逐张确认）**——网格排版器保证连线正确，但不会「构图」。模块 ≥ 10 或
   有明显分区（控制面/数据面/存储层次）时，可先出 draw.io 基线，再把**从代码得出的模块清单和连接**写进提示词
   （论文插图风格、白底、单一强调色、三区布局、文字极少、英文短标签），用 gpt-image-bridge 生成 1 张草图并 Read 它。
   **只借鉴布局与视觉层次**（分区、谁在谁上方、阵型、留白、重点位置），换算成 `lane` / `row` / `col` / `groups`；
   **模块、连线、名称一律以代码为准**——草图常见错误：连错源头、多画/少画模块、深色背景。生成前按该 skill 规定
   列出图片（用途、路径、尺寸、提示词摘要）并等用户明确同意；草图存 `diagrams/sketch_*.png`，描述文件头部注释引用它。
3. `render --png` → `validate.py`（error 必须为 0；分界虚线穿过级头/寄存器的 overlap 警告是设计如此）→ Read PNG 目视检查，
   用 `row` / `col` 微调最多两轮（常见：让主数据通路占 row 0 走直线，旁路 / 控制放下一行）。
4. 交付 `.drawio` + `.png`；描述文件留在 scratchpad，用户要自己改时再给。

样例：tiny-gpu 顶层 `~/hardware-project/tiny-gpu/diagrams/arch_gpu.*`（由草图 `sketch_gpu_top.png` 指导构图，
对照未用草图的 `arch_gpu_baseline.png`）；`examples/dcache_pipe.v` → `dcache_pipe.arch.yaml`（由代码写出的描述）→ `.png`；`arch_dual_issue.yaml`（双流水对齐 + 前递 +
编号注释）、`arch_mac.yaml`（电路级：乘 / 加符号、累加反馈、MUX 选择端）。tiny-gpu core 的块级图见
`~/hardware-project/tiny-gpu/diagrams/arch_core.*`。

## 一、结构框图（rtl2drawio.py，门级细节）

```bash
python3 $S/scripts/rtl2drawio.py src/*.sv --top gpu --list                     # 模块及单元构成
python3 $S/scripts/rtl2drawio.py src/*.sv --top gpu --module alu -o diagrams/alu.drawio --png
```

流程：sv2v（遇到 .sv 自动）→ Yosys `proc; opt; opt_dff; wreduce; memory -nomap` → JSON 网表 → 单元级流水分析 → 化简 → 列约束布局。
生成后跑 `python3 ~/.claude/skills/drawio-skill/scripts/validate.py X.drawio`（error 必须为 0；穿过级分界线/寄存器压在分界线上
产生的 through-vertex / overlap 警告是设计如此），再 Read PNG 目视检查。

### 布局规则（`--layout pipeline`；默认 `auto`：以子模块实例为主的层次模块用自由布局，其余用流水级布局）
- **输入在左、输出在右**，逻辑按组合深度从左往右分列；多级流水按 **S0 → Sn 从左到右**，虚线分界，列头标级号。
- **寄存器分两类**：
  - 流水寄存器（窄竖条）放在级分界线上；最后只接输出端口的一排是**输出寄存器**（不算一级、不画分界线）。
  - 状态寄存器（FSM / 计数器 / 指针：输出只经组合逻辑就回到自己输入）画在级内，输出作为反馈。
  - 寄存器名带级号时（`s2_x`、`x_s2`、`stage2_x`、`if_id_`/`id_ex_`/`ex_mem_`/`mem_wb_`，且至少两种）**以名字为准**——
    带 kill 的 valid 位即使有组合环路也仍是流水寄存器。设计不按级命名时只能靠结构推断，输入端口的到达时间未知，级号可能偏早。
- **级号推算**：从带级号寄存器出发，单元的级 = 最晚到达的寄存器操作数（取最大）；只由输入端口驱动的逻辑按「被哪一级寄存器采走」
  归级（ALAP），对应的输入端口也放到那一级开头（例如 TLB 响应放在 S1）。
- **反馈**：进入某个带级号寄存器输入锥、却只可能来自更后级的信号（replay→S0、kill→S1），以及状态寄存器的回环，画成
  **红线沿底部外圈绕回**，跨度大的在外；同一对级之间反馈多于 3 根时只画**一根粗线代表一捆**（标 `反馈 ×N：…`）。
- **成捆**：同一分界上流水寄存器多于 4 个时合并为一个寄存器组（竖条标 `S1→S2 寄存器 ×N` 和总位宽）。
- **化简**：同名寄存器切片合并；嵌套 if/case 的 MUX 链合成一个 `N:1` MUX；只驱动一个 MUX 选择端 / 寄存器使能的小译码逻辑
  并进去画成选择线 / 使能线；3 个以内的门画成**与/或/非/异或门符号**，更大的折叠成「组合逻辑」云（会在夹着运算单元处切开，
  避免假环路）；generate 循环展开的同源（同一源码位置）单元与 `threads[i].x` 实例折叠成 **「×N」**（带阴影）。
  所有合并都只在**同一级内**进行。clk/reset 默认隐藏。
- 连线：实线=数据（粗=多位总线，`/N`=位宽）；紫虚线=MUX 选择；蓝点线=使能；红线=反馈。

### 参数
| 参数 | 作用 |
|---|---|
| `--list` | 列模块及单元构成后退出 |
| `--module M` | 画哪个模块（参数化变体画第一个，会提示） |
| `--layout auto\|pipeline\|free` | 默认 auto：有子模块实例且组合逻辑节点不多于实例（顶层胶合模块）用 free（块间双向通信不是流水反馈），否则 pipeline |
| `--show-clock` | 画出 clk/reset |
| `--no-fold` | 不折叠 generate 实例 / 同源单元 |
| `--no-collapse` | 不折叠控制/组合逻辑 |
| `--sv2v auto\|always\|never` | SV 前端（非压缩数组端口等语法需要 sv2v） |
| `--keep-json PATH` | 保留 Yosys JSON 网表 |

## 二、状态机图（fsm2drawio.py fsm）

```bash
python3 $S/scripts/fsm2drawio.py list src/*.sv
python3 $S/scripts/fsm2drawio.py fsm  src/*.sv [--module M] -d diagrams --png [--no-actions]
```

- **直接解析源码**，转移条件保留原始表达式。识别 `case (S)` 分支里给 S（或 `S <= N` 的次态变量 N）赋值；状态名取 localparam；
  比较**别的 FSM 状态变量**的常量翻译成对方状态名（`core_state == 3'b001` → `core_state == FETCH`）。
- 转移条件 = 直接包住状态赋值的 if/case/for；`else if` 只写自己的条件；`for` 里的条件写成 `∃j: …`；外层 `for i` 包住整个 case
  表示按 i 复制；case 外的守卫（enable、读/写分支）进注释框；循环里置 1 的局部布尔变量在注释框给出定义。
- **画法**：每个状态一个**等大圆圈**（名字在 `_` 处折行，下方小字为编码和 ⟳），终态双圈，黑点=复位入口。
  主流程覆盖大部分状态时排成 **U 形环**（上排左→右、拐下、下排右→左）；分支型按离初始状态的步数**均匀分列**。
  相邻状态直连；跳过其他状态的转移**从上方/下方拱过**，标签在拱顶；A↔B 往返各弯向一侧；显式自环画在圆上方。
  列距按最长标签自适应。`/` 后为转移时的赋值（最多显示 2 个）。
- 不识别：没有 `case(state)` 结构的控制（计数器式、纯组合译码）——`list` 里不出现，属预期。

## 三、整体控制结构（fsm2drawio.py ctrl）

```bash
python3 $S/scripts/fsm2drawio.py ctrl src/*.sv --top gpu --module core -o diagrams/ctrl_core.drawio --png
```

- 画模块 L 里的子模块实例（generate 实例折叠 ×N），**只保留控制信号**：橙粗线=FSM 状态广播；蓝线=valid/ready 握手；
  紫虚线=start/done/使能/选择/复位等；数据总线省略。含 FSM 的实例框列出状态序列，子层次里有 FSM 的标「内含 FSM」。
- 控制信号穿透最多 3 层基本单元（比较器、门、寄存器）追到源头。分类靠信号名，命名不规范时可能漏画/多画。
- 建议从上往下：先 top（谁启动谁、谁和存储器握手）→ 下一层（主控 FSM 怎么调度）→ 关键 FSM 的状态机图。

## 局限
- 布局由 Graphviz 按列约束自动完成，交叉无法完全消除；精修在 draw.io 里拖动（全是原生可编辑对象）。
- 大型控制类模块（上百单元）框图仍会乱，按上文改用状态机图 / 控制结构图，或逐个子模块画。
- 状态机图的圆圈/弧线是按坐标直接画的，拖动状态时弧线的拐点不会跟着走，需要顺手调一下。

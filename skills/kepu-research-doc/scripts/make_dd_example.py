#!/usr/bin/env python3
"""正文示意图的样例：用 diagram-design 的版式生成《看懂 DPU》的五张示意图（HTML + 内联 SVG）。

写新文档时复制本文件到 <topic>/figs/dd/make_dd.py，保留 Svg 类、KIND 节点样式和 legend()，只改画图函数。
运行：python3 scripts/make_dd_example.py <topic>/figs/dd       生成 *.html
导出：python3 scripts/export_cover.py <topic>/figs/dd/*.html   每个 HTML 栅格化成同名 2x PNG
配色与字体取自 diagram-design 的默认 style-guide（paper / ink / muted / accent / link）。
"""
import sys
from html import escape
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

PAPER, PAPER2, WHITE = "#f5f5f5", "#ececec", "#ffffff"
INK, MUTED, SOFT = "#2d3142", "#4f5d75", "#5a6580"
RULE, RULE_SOLID = "rgba(45,49,66,0.12)", "#bfc0c0"
ACCENT, ACCENT_TINT, LINK = "#bf4520", "rgba(191,69,32,0.08)", "#2e5aa8"
SANS = "'Geist', 'Noto Sans SC', 'WenQuanYi Zen Hei', sans-serif"
MONO = "'Geist Mono', ui-monospace, monospace"

# 节点样式（style-guide § Node type → treatment）
KIND = {
    "backend": (WHITE, INK, None),
    "focal": (ACCENT_TINT, ACCENT, None),
    "store": ("rgba(45,49,66,0.05)", MUTED, None),
    "external": ("rgba(45,49,66,0.03)", "rgba(45,49,66,0.30)", None),
    "input": ("rgba(79,93,117,0.10)", SOFT, None),
    "optional": ("rgba(45,49,66,0.02)", "rgba(45,49,66,0.20)", "4,3"),
    "security": ("rgba(191,69,32,0.05)", "rgba(191,69,32,0.50)", "4,4"),
}

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: {sans}; background: {paper}; color: {ink}; padding: 2rem; }}
.frame {{ max-width: {w}px; margin: 0 auto; }}
.diagram-container {{ width: 100%; overflow-x: auto; }}
svg {{ width: 100%; min-width: {w}px; display: block; }}
@media print {{ .diagram-container {{ overflow-x: visible; }} svg {{ min-width: 0; }} }}
</style>
</head>
<body>
<div class="frame"><div class="diagram-container">
<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
<title id="{slug}-title">{title}</title>
<desc id="{slug}-desc">{desc}</desc>
<defs>
<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{muted}"/></marker>
<marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{accent}"/></marker>
<marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{link}"/></marker>
</defs>
<rect width="100%" height="100%" fill="{paper}"/>
{body}
</svg>
</div></div>
</body>
</html>
"""


class Svg:
    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=13, fill=INK, weight=400, anchor="middle",
             family=SANS, italic=False, spacing=None):
        extra = ' font-style="italic"' if italic else ""
        if spacing:
            extra += f' letter-spacing="{spacing}"'
        self.add(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
                 f'font-weight="{weight}" font-family="{family}" '
                 f'text-anchor="{anchor}"{extra}>{escape(s)}</text>')

    def lines(self, cx, cy, items, size=13, lh=20, anchor="middle"):
        """items: [(text, fill, weight)]，整体在 cy 处垂直居中。"""
        top = cy - lh * (len(items) - 1) / 2 + size * 0.36
        for i, (s, fill, weight) in enumerate(items):
            self.text(cx, round(top + i * lh, 1), s, size, fill, weight, anchor)

    def rect(self, x, y, w, h, fill, stroke=None, rx=6, dash=None, sw=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        if dash:
            st += f' stroke-dasharray="{dash}"'
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}/>')

    def node(self, x, y, w, h, title, sub=(), kind="backend", size=14, subsize=12, lh=20):
        fill, stroke, dash = KIND[kind]
        self.rect(x, y, w, h, PAPER)
        self.rect(x, y, w, h, fill, stroke, dash=dash)
        items = []
        if title:
            items.append((title, INK, 600))
        items += [(s, MUTED, 400) for s in sub]
        self.lines(x + w / 2, y + h / 2, items, size, lh)

    def path(self, d, color=MUTED, dash=None, sw=1.2, marker="arrow"):
        st = f' stroke-dasharray="{dash}"' if dash else ""
        mk = f' marker-end="url(#{marker})"' if marker else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{st}{mk}/>')

    def line(self, x1, y1, x2, y2, color=RULE, sw=1, dash=None):
        st = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{st}/>')

    def write(self, slug, title, desc, w, h):
        html = PAGE.format(title=escape(title), desc=escape(desc), slug=slug, w=w, h=h,
                           body="\n".join(self.parts), sans=SANS, paper=PAPER, ink=INK,
                           muted=MUTED, accent=ACCENT, link=LINK)
        (OUT / f"{slug}.html").write_text(html, encoding="utf-8")


def legend(s, y, w, items):
    """底部横向图例：items = [(样式, 文本)]，样式为 (颜色, dash, marker)。"""
    s.line(24, y - 8, w - 24, y - 8, "rgba(45,49,66,0.10)", 0.8)
    s.text(24, y + 12, "LEGEND", 8, MUTED, 500, "start", MONO, spacing="0.14em")
    x = 104
    for (color, dash, marker), label in items:
        s.path(f"M{x},{y + 8} H{x + 32}", color, dash, 1.4, marker)
        s.text(x + 44, y + 12, label, 12, MUTED, 500, "start")
        x += 56 + 13 * len(label)


# ---------------------------------------------------------------- 图 2：三大作用
def roles():
    s, W, H = Svg(), 960, 552
    cols = [
        ("NETWORK", "网络（转发之外）",
         ["VM / 容器", "看到：一块 VF 网卡"],
         ["虚拟交换（OVS 规则）", "VXLAN / Geneve 封装解封", "连接跟踪 · NAT · 负载均衡",
          "QoS 限速 · 遥测采样", "RDMA 拥塞控制"],
         ["underlay 网络", "物理交换机只看外层头"],
         ["隧道封装：软件 ~1 Mpps", "→ DPU ~63 Mpps"]),
        ("SECURITY", "安全",
         ["主机 OS", "看到：普通网卡，无感知"],
         ["IPsec / TLS 内联加解密", "有状态防火墙 · 微分段", "IDS/IPS 免检流 bypass",
          "RegEx 深度包检测", "信任根 · 卡上持有密钥"],
         ["东西向流量", "数据中心内部，占比最高 80%"],
         ["Suricata：40 → ~390 Gbps", "主机核 4 → ~0"]),
        ("STORAGE", "存储",
         ["应用", "看到：一块“本地” NVMe 盘"],
         ["NVMe / virtio-blk 设备仿真", "翻译成 NVMe-oF / RDMA", "内联加密 · CRC",
          "压缩 · 去重", "（target 端）卸载快路径"],
         ["远端存储集群", "EBS 卷、JBOF、分布式块存储"],
         ["NVMe-oF target：", "延迟降为约 1/3"]),
    ]
    xs, cw = [104, 392, 680], 264
    # 左侧行标签
    for y, lab in [(112, "主机看到"), (260, "DPU 上做"), (404, "数据去向")]:
        s.text(20, y + 5, lab, 13, MUTED, 500, "start")
    # DPU 区带
    s.rect(96, 176, 856, 168, PAPER2, RULE, rx=8)
    s.text(944, 196, "DPU", 8, MUTED, 500, "end", MONO, spacing="0.18em")
    for i, (eb, name, top, mid, bot, gain) in enumerate(cols):
        x, cx = xs[i], xs[i] + cw / 2
        # 连线先画
        s.path(f"M{cx},144 V196", marker="arrow")
        s.path(f"M{cx},332 V368", marker="arrow")
        s.text(cx, 30, eb, 8, MUTED, 500, "middle", MONO, spacing="0.18em")
        s.text(cx, 56, name, 17, INK, 600)
        s.node(x, 80, cw, 64, top[0], top[1:], "input")
        s.node(x, 200, cw, 132, None, (), "focal" if i == 2 else "backend")
        s.lines(cx, 266, [(t, INK, 400) for t in mid], 13, 22)
        s.node(x, 372, cw, 64, bot[0], bot[1:], "external")
        s.lines(cx, 478, [(t, MUTED, 500) for t in gain], 13, 20)
    s.line(24, 512, W - 24, 512, "rgba(45,49,66,0.10)", 0.8)
    s.text(W / 2, 536, "收益数字转引自 Kfoury et al. 2024（多为 NVIDIA BlueField 实验，厂商来源）",
           12, SOFT, 400)
    s.write("fig7_roles", "DPU 的三大作用",
            "网络、安全、存储三列，各自展示主机看到什么、DPU 在中间做什么、数据最后去哪。", W, H)


# ---------------------------------------------------------------- 图 3：四种网络栈
def netpaths():
    s, W, H = Svg(), 960, 600
    xs, cw = [112, 324, 536, 748], 196
    heads = [("KERNEL", "Linux 内核协议栈"), ("DPDK", "DPDK"),
             ("XDP", "eBPF / XDP"), ("OFFLOAD", "卸载网卡 / DPU")]
    bands = [("用户态", 72, 216), ("内核", 228, 348), ("驱动", 360, 432), ("网卡 / DPU", 444, 528)]
    for lab, y0, y1 in bands:
        s.rect(104, y0, 848, y1 - y0, PAPER2, None, rx=4)
        s.text(20, (y0 + y1) / 2 + 5, lab, 13, MUTED, 500, "start")
    s.text(20, 573, "线上包", 13, MUTED, 500, "start")

    APP, RECV, KER, DRV, NIC = (84, 40), (144, 60), (240, 96), (372, 48), (456, 60)
    cells = [
        [["应用"], ["系统调用 recv()", "拷贝到用户 buffer"],
         ["IP / TCP 协议栈", "netfilter · 内核 OVS", "路由 · 隧道解封", "→ socket 队列"],
         ["中断 → NAPI 收包", "分配 sk_buff"], ["普通网卡", "DMA 写入 RX 环"]],
        [["应用（同进程）"], ["PMD 独占核轮询", "OVS-DPDK / 用户态栈"], None, None,
         ["普通网卡", "DMA 写入大页内存"]],
        [["应用"], ["recv() 或", "AF_XDP 零拷贝"],
         ["只有 XDP_PASS 的包", "才进协议栈", "其余在驱动层就结束"],
         ["XDP 钩子跑 eBPF 程序", "丢弃 / 转发 / 重定向"], ["普通网卡", "offload 模式可跑程序"]],
        [["应用（VM / 容器）"], ["recv()"],
         ["交换、隧道、防火墙", "已在卡上做完", "这一层只剩 TCP"],
         ["标准 VF / virtio 驱动", "只收已处理好的包"],
         ["eSwitch 硬件查表", "解封 · NAT · 过滤", "首包由卡上 Arm 决策"]],
    ]
    rows = [APP, RECV, KER, DRV, NIC]
    for i, (eb, name) in enumerate(heads):
        x, cx = xs[i], xs[i] + cw / 2
        s.text(cx, 30, eb, 8, MUTED, 500, "middle", MONO, spacing="0.18em")
        s.text(cx, 54, name, 15, ACCENT if i == 3 else INK, 600)
        # 先画箭头：从线上包往上，逐格相连
        present = [r for r, c in zip(rows, cells[i]) if c is not None]
        ax = cx if i != 1 else x + 32
        s.path(f"M{ax},{588} V{NIC[0] + NIC[1] + 4}", MUTED)
        stack = present[::-1]  # 自下而上
        for a, b in zip(stack, stack[1:]):
            s.path(f"M{ax},{a[0]} V{b[0] + b[1] + 4}", MUTED)
        for (y, h), c in zip(rows, cells[i]):
            if c is None:
                continue
            kind = "focal" if (i == 3 and (y, h) == NIC) else "backend"
            if len(c) == 1:
                s.node(x, y, cw, h, c[0], (), kind, 13)
            else:
                s.node(x, y, cw, h, None, (), kind)
                s.lines(cx, y + h / 2, [(t, INK if j == 0 else MUTED, 600 if j == 0 else 400)
                                        for j, t in enumerate(c)], 13, 19)
    # DPDK 被绕过的两层：虚线幽灵格，箭头从左侧空隙直上
    gx = xs[1] + 56
    s.node(gx, KER[0], cw - 64, KER[1], None, (), "optional")
    s.lines(gx + (cw - 64) / 2, KER[0] + KER[1] / 2,
            [("整个内核协议栈", SOFT, 500), ("被绕过", SOFT, 500)], 13, 20)
    s.node(gx, DRV[0], cw - 64, DRV[1], None, (), "optional")
    s.lines(gx + (cw - 64) / 2, DRV[0] + DRV[1] / 2, [("内核驱动被解绑", SOFT, 500)], 13, 20)
    s.write("fig8_netpaths", "同一个收包路径的四种实现",
            "Linux 内核栈、DPDK、eBPF/XDP、卸载网卡四列并排，展示一个收到的包分别在哪一层被处理。", W, H)


# ---------------------------------------------------------------- 图 7：DPU 解剖
def anatomy():
    s, W, H = Svg(), 960, 600
    # DPU 边界
    s.rect(168, 64, 576, 456, "rgba(45,49,66,0.02)", "rgba(45,49,66,0.30)", rx=8, dash="4,3")
    s.text(184, 90, "DPU · 一块 PCIe 卡 / 一颗 SoC", 12, MUTED, 500, "start")
    # 连线（先画）
    # 控制面：云 → 信任根 → Arm
    s.path("M784,140 H724", MUTED, "5,4")
    s.path("M544,140 H508", MUTED, "5,4")
    # 慢路径：首包上送、装回规则
    s.path("M240,260 V180", ACCENT, "5,4", 1.4, "arrow-accent")
    s.path("M288,176 V256", ACCENT, "5,4", 1.4, "arrow-accent")
    s.rect(300, 198, 88, 40, PAPER, rx=2)
    s.text(304, 212, "① 首包上送", 12, ACCENT, 500, "start")
    s.text(304, 232, "② 装回规则", 12, ACCENT, 500, "start")
    # 快路径
    for d in ["M136,300 H188", "M336,300 H364", "M512,300 H540", "M720,300 H780",
              "M440,340 V376", "M512,412 H624 Q632,412 632,404 V344"]:
        s.path(d, LINK, None, 1.4, "arrow-link")
    # 节点
    s.node(192, 104, 312, 72, "Arm 核 + 独立 Linux", ["OVS 控制面 · 存储代理 · 策略"])
    s.node(544, 104, 176, 72, "信任根 / 安全启动", ["带外管理口"], "security")
    s.node(784, 104, 160, 72, "云 / 集群控制器", ["经带外口下发"], "external")
    s.node(16, 260, 120, 80, "以太网 / IB", ["400–800G"], "input")
    s.node(192, 260, 144, 80, "eSwitch", ["流表 + 连接跟踪"])
    s.node(368, 260, 144, 80, "可编程流水线", ["解析→匹配→动作"])
    s.node(368, 380, 144, 64, "领域加速器", ["加密 · RegEx · 压缩"], "store")
    s.node(544, 260, 176, 80, "PCIe 端点 + DMA", ["仿真 VF · virtio · NVMe"])
    s.node(784, 252, 160, 96, "主机 CPU", ["只看到：一块网卡", "+ 一块本地盘"], "external")
    s.line(192, 472, 720, 472, RULE)
    s.text(456, 496, "片上 SRAM（流缓存）· 板载 DRAM（大表）· DPA 线程阵列（部分产品）", 12, SOFT)
    legend(s, 556, W, [((LINK, None, "arrow-link"), "快路径：命中流表，全程硬件"),
                       ((ACCENT, "5,4", "arrow-accent"), "慢路径：首包经 Arm 决策"),
                       ((MUTED, "5,4", "arrow"), "控制面")])
    s.write("fig3_anatomy", "off-path DPU 的内部结构",
            "一块 off-path DPU 的部件，以及新流首包经 Arm 核的慢路径和命中流表后的硬件快路径。", W, H)


# ---------------------------------------------------------------- 图 8：软件栈
def stack():
    s, W, H = Svg(), 960, 480
    xs, ws = [136, 384, 736], [224, 320, 208]
    heads = [("HOST", "主机侧"), ("ARM SUBSYSTEM", "DPU 的 Arm 子系统"), ("SILICON", "DPU 硬件")]
    rows = [
        ("编排与控制", ["K8s / 云控制器", "下发意图"], ["DPU 上跑自己的 K8s 节点", "DOCA 服务 · 存储目标"], ["BMC / 带外口"]),
        ("服务", ["租户 VM / 容器", "只用标准驱动"], ["OVS-DPDK · SPDK · 存储/安全代理", "DOCA Flow / Comm Channel"],
         ["加速器队列", "压缩 · 加密 · RegEx"]),
        ("驱动与抽象", ["mlx5 / virtio-net", "nvme 驱动"], ["DPDK · rte_flow · TC Flower · P4 运行时", "OPI / IPDK / SONiC-DASH 抽象层"],
         ["eSwitch 流表 / P4 流水线", "ASAP² · FXP · MPU"]),
        ("设备仿真", ["看到 PF / VF / SF", "或仿真 NVMe 盘"], ["设备仿真后端（SNAP 等）", "把 NVMe / virtio 翻译成 NVMe-oF / RDMA"],
         ["PCIe 端点 + DMA", "仿真设备寄存器"]),
        ("信任", ["主机 OS 不再持有", "网络 / 存储策略"], ["安全启动链", "卡上持有密钥与防火墙规则"], ["硬件信任根"]),
    ]
    # Arm 列整体是焦点：一个 accent 区域
    s.rect(xs[1] - 12, 68, ws[1] + 24, 400, ACCENT_TINT, ACCENT, rx=8)
    for i, (eb, name) in enumerate(heads):
        cx = xs[i] + ws[i] / 2
        s.text(cx, 26, eb, 8, ACCENT if i == 1 else MUTED, 500, "middle", MONO, spacing="0.18em")
        s.text(cx, 52, name, 15, ACCENT if i == 1 else INK, 600)
    for r, (tag, *cols) in enumerate(rows):
        y = 80 + r * 76
        s.text(16, y + 37, tag, 13, MUTED, 500, "start")
        for i, c in enumerate(cols):
            kind = ["input", "backend", "store"][i]
            s.node(xs[i], y, ws[i], 64, None, (), kind)
            s.lines(xs[i] + ws[i] / 2, y + 32, [(t, INK if j == 0 else MUTED, 600 if j == 0 else 400)
                                                 for j, t in enumerate(c)], 13, 19)
    s.write("fig6_stack", "DPU 软件栈分层",
            "主机侧、DPU 的 Arm 子系统、DPU 硬件三列，按编排、服务、驱动、设备仿真、信任五层对照。", W, H)


# ---------------------------------------------------------------- 图 4：时间线
def timeline():
    s, W, H = Svg(), 920, 672
    eras = [
        ("第一圈", "大型机通道处理器", [
            ("1958", "IBM 709 数据通道：I/O 交给独立的通道处理器"),
            ("1964", "System/360 通道：主机只下发“通道程序”，自己去算"),
            ("1968", "Myer & Sutherland 提出“轮回之轮”：搬出去、长大、再被收回"),
            ("1983", "4.2BSD 把 TCP/IP 放进内核：协议处理收回主 CPU")]),
        ("第二圈", "协议卸载，被收回", [
            ("1999", "TOE / iSCSI HBA：把整个 TCP 搬上网卡"),
            ("2003", "Mogul：TOE 是“时机已到的蠢主意”，TCP 随后收回主 CPU")]),
        ("第三圈", "基础设施卸载：DPU", [
            ("2013", "AWS C3：第一张 Nitro 网络卸载卡"),
            ("2015", "Azure 用 FPGA 跑 SDN 快路径（AccelNet）；AWS 收购 Annapurna"),
            ("2016", "Mellanox 发布 BlueField：ConnectX + Arm 阵列"),
            ("2017", "AWS C5：I/O 与管理全部搬出主机；Fungible 提出 “DPU”"),
            ("2020", "NVIDIA 以 “DPU” 命名 BlueField-2，推出 DOCA"),
            ("2021", "Intel 与 Google 合作的 IPU（Mount Evans）"),
            ("2022", "AMD 收购 Pensando；Microsoft 收购 Fungible"),
            ("2024", "Azure Boost DPU；AMD Pensando Salina 400")]),
        ("延伸", "AI 数据通路", [
            ("2025", "BlueField-4：64 核 Grace + 800G ConnectX-9"),
            ("2026", "BlueField-4 驱动 KV cache 上下文存储平台")]),
    ]
    gaps = {0: "相隔 16 年", 1: "相隔 10 年"}
    AX, step = 232, 36
    y = 48
    layout = []
    for e, (k, name, evs) in enumerate(eras):
        y0 = y
        ys = [y + j * step for j in range(len(evs))]
        y = ys[-1] + step
        layout.append((k, name, evs, ys, y0))
        if e in gaps:
            y += 20
        elif e == 2:
            y += 4
    # 轴线：每一圈一段，圈与圈之间断开
    for e, (k, name, evs, ys, y0) in enumerate(layout):
        s.line(AX, ys[0] - 14, AX, ys[-1] + 14, RULE_SOLID, 1.2)
        s.line(152, ys[0] - 14, 152, ys[-1] + 14, RULE_SOLID, 2)
        mid = (ys[0] + ys[-1]) / 2
        s.text(140, mid - 4, k, 13, INK, 600, "end")
        s.text(140, mid + 16, name, 12, MUTED, 400, "end")
        if e in gaps:
            gy = ys[-1] + step / 2 + 10
            s.line(AX - 6, gy - 6, AX + 6, gy - 10, SOFT, 1)
            s.line(AX - 6, gy + 2, AX + 6, gy - 2, SOFT, 1)
            s.text(AX + 24, gy + 1, gaps[e], 12, SOFT, 400, "start", italic=True)
        for (yr, ev), yy in zip(evs, ys):
            focal = yr in ("2003", "2013")
            s.add(f'<circle cx="{AX}" cy="{yy}" r="{6 if focal else 4}" '
                  f'fill="{ACCENT if focal else MUTED}"/>')
            s.text(AX - 20, yy + 5, yr, 13, ACCENT if focal else MUTED, 500, "end", MONO)
            s.text(AX + 24, yy + 5, ev, 14, INK, 600 if focal else 400, "start")
    s.write("fig2_timeline", "I/O 卸载的三次轮回",
            "1958 年到 2026 年的 I/O 卸载事件，按通道处理器、协议卸载、DPU、AI 数据通路四段排列。", W, H)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    roles(); netpaths(); anatomy(); stack(); timeline()
    print("ok")

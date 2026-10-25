#!/usr/bin/env python3
"""科普调研文档的固定封面：diagram-design 默认皮肤 + 编辑式排版，小红书竖版 3:4（默认，导出 1242×1656）；
cover.json 写 "orientation": "landscape" 时出 4:3 横版（1440×1080）。

用法：python3 scripts/make_cover.py <topic>/figs/cover/cover.json <topic>/figs/cover
  cover.json 字段见 references/COVER-STYLE.md，样例在 assets/cover-example/cover.json；
  输出 cover.html，再用 python3 scripts/export_cover.py <topic>/figs/cover/cover.html 导出 cover.png。
竖版自上而下是标题区、"同心圆"母题、"这篇要讲什么"；母题圆心是主题的核心对象，
每一圈是一个阶段或层级，焦点圈用 accent，其余用 muted。
"""
import json
import math
import sys
from html import escape
from pathlib import Path

PAPER, PAPER2 = "#f5f5f5", "#ececec"
INK, MUTED, SOFT = "#2d3142", "#4f5d75", "#5a6580"
RULE = "rgba(45,49,66,0.12)"
ACCENT, ACCENT_TINT = "#bf4520", "rgba(191,69,32,0.08)"
SERIF = "'Instrument Serif', 'Noto Serif SC', serif"
SANS = "'Geist', 'Noto Sans SC', 'WenQuanYi Zen Hei', sans-serif"
MONO = "'Geist Mono', ui-monospace, monospace"
FONTS = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
         "&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500"
         "&family=Noto+Serif+SC:wght@500;700&family=Noto+Sans+SC:wght@400;500;600&display=swap")


def t(x, y, s, size, fill=INK, family=SANS, weight=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-family="{family}" '
            f'font-weight="{weight}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def arc(cx, cy, r, a0, a1):
    """角度制，0° 指向正上方，顺时针。"""
    p = lambda a: (cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a)))
    (x0, y0), (x1, y1) = p(a0), p(a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f}"


def build_portrait(c):
    """竖版 3:4（1080×1440，导出 1242×1656）。四周留 96px 安全边距，避免 App 裁边和底部遮挡。"""
    W, H = 1080, 1440
    o = []
    M = 96
    o.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    # 上部：标题区
    x = M
    o.append(t(x, 120, c["eyebrow"], 18, MUTED, MONO, 500, extra=' letter-spacing="0.16em"'))
    y = 220
    for i, line in enumerate(c["title"]):
        o.append(t(x, y + i * 100, line, 84, INK, SERIF, 700, extra=' letter-spacing="-0.01em"'))
    y += 100 * (len(c["title"]) - 1) + 60
    o.append(f'<rect x="{x}" y="{y}" width="56" height="4" fill="{ACCENT}"/>')
    for i, line in enumerate(c["subtitle"]):
        o.append(t(x, y + 60 + i * 44, line, 30, MUTED, SANS, 400))
    # 中部：点阵纸上的同心圆母题
    cx, cy = W / 2, 800
    rings = c["rings"]
    radii = [96 + 68 * i for i in range(len(rings))]
    band0, band1 = cy - radii[-1] - 40, cy + radii[-1] + 72
    o.append(f'<rect x="0" y="{band0}" width="{W}" height="{band1 - band0}" fill="url(#dots)"/>')
    o.append(f'<line x1="{M}" y1="{band0}" x2="{W - M}" y2="{band0}" stroke="{RULE}"/>')
    o += rings_svg(c, cx, cy, radii)
    o.append(t(cx, band1 - 24, c["motif_caption"], 24, MUTED, SERIF, 400, "middle",
               ' font-style="italic"'))
    o.append(f'<line x1="{M}" y1="{band1}" x2="{W - M}" y2="{band1}" stroke="{RULE}"/>')
    # 下部：这篇要讲的几个问题（不放数字统计）
    ty = band1 + 64
    for i, (tag, text) in enumerate(c.get("topics", [])):
        yy = ty + i * 44
        o.append(t(x, yy, tag, 16, SOFT, MONO, 500, extra=' letter-spacing="0.12em"'))
        o.append(t(x + 100, yy, text, 26, INK, SANS, 500))
    o.append(t(x, H - 88, c["meta"], 16, SOFT, MONO, 400, extra=' letter-spacing="0.08em"'))
    return "\n".join(o), W, H


def rings_svg(c, cx, cy, radii):
    """同心圆母题：弧长表示进行到哪一步，焦点圈用 accent。"""
    o = []
    rings = c["rings"]
    for r, ring in zip(radii, rings):
        focal = ring.get("focal", False)
        color = ACCENT if focal else MUTED
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RULE}" stroke-width="1.2"/>')
        dash = ' stroke-dasharray="7,6"' if ring.get("dashed") else ""
        o.append(f'<path d="{arc(cx, cy, r, 8, ring.get("sweep", 250))}" fill="none" stroke="{color}" '
                 f'stroke-width="{3.2 if focal else 2}"{dash} marker-end="url(#{"ma" if focal else "mm"})"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="64" fill="{PAPER}" stroke="{INK}" stroke-width="1.6"/>')
    o.append(t(cx, cy + 4, c["core"][0], 26, INK, SANS, 600, "middle"))
    if len(c["core"]) > 1:
        o.append(t(cx, cy + 32, c["core"][1], 15, SOFT, MONO, 400, "middle"))
    for r, ring in zip(radii, rings):
        focal = ring.get("focal", False)
        color = ACCENT if focal else MUTED
        ny = cy - r
        o.append(f'<circle cx="{cx}" cy="{ny}" r="{8 if focal else 6}" fill="{color}"/>')
        yw = 11 * len(ring["year"])
        wpx = 20 * len(ring["label"]) + yw + 40
        o.append(f'<rect x="{cx - 22 - wpx}" y="{ny - 17}" width="{wpx}" height="32" rx="2" fill="{PAPER}"/>')
        o.append(t(cx - 28, ny + 7, ring["year"], 18, color, MONO, 500, "end"))
        o.append(t(cx - 28 - yw - 14, ny + 7, ring["label"], 20,
                   ACCENT if focal else INK, SANS, 600 if focal else 500, "end"))
    return o


def build_landscape(c):
    """横版 4:3（1440×1080）。所有内容留在四周 96px 的安全边距内，避免 App 裁边。"""
    W, H = 1440, 1080
    o = []
    M, DIV = 96, 816
    o.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    # 右栏铺点阵纸，给母题一个"图纸"底；左右用一条竖直细线分开
    o.append(f'<rect x="{DIV}" y="0" width="{W - DIV}" height="{H}" fill="url(#dots)"/>')
    o.append(f'<line x1="{DIV}" y1="{M}" x2="{DIV}" y2="{H - M}" stroke="{RULE}"/>')

    # 左栏：标题区
    x = M
    o.append(t(x, 168, c["eyebrow"], 18, MUTED, MONO, 500, extra=' letter-spacing="0.16em"'))
    y = 280
    for i, line in enumerate(c["title"]):
        o.append(t(x, y + i * 100, line, 84, INK, SERIF, 700, extra=' letter-spacing="-0.01em"'))
    y += 100 * (len(c["title"]) - 1) + 60
    o.append(f'<rect x="{x}" y="{y}" width="56" height="4" fill="{ACCENT}"/>')
    for i, line in enumerate(c["subtitle"]):
        o.append(t(x, y + 60 + i * 44, line, 30, MUTED, SANS, 400))
    # 左栏下部：这篇要讲的几个问题（不放数字统计）
    ty = 700
    for i, (tag, text) in enumerate(c.get("topics", [])):
        yy = ty + i * 52
        o.append(t(x, yy, tag, 16, SOFT, MONO, 500, extra=' letter-spacing="0.12em"'))
        o.append(t(x + 100, yy, text, 26, INK, SANS, 500))
    o.append(f'<line x1="{x}" y1="{H - M - 44}" x2="{DIV - 56}" y2="{H - M - 44}" stroke="{RULE}"/>')
    o.append(t(x, H - M, c["meta"], 16, SOFT, MONO, 400, extra=' letter-spacing="0.08em"'))

    # 右栏：同心圆母题
    cx, cy = 1092, 512
    radii = [104 + 74 * i for i in range(len(c["rings"]))]
    o += rings_svg(c, cx, cy, radii)
    o.append(t(cx, cy + radii[-1] + 84, c["motif_caption"], 24, MUTED, SERIF, 400, "middle",
               ' font-style="italic"'))
    return "\n".join(o), W, H


PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="{fonts}" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{paper};padding:2rem}}
.diagram-container{{width:100%;overflow-x:auto}}
svg{{width:100%;min-width:{w}px;display:block}}
</style></head><body><div class="diagram-container">
<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cover-title cover-desc">
<title id="cover-title">{title}</title>
<desc id="cover-desc">{desc}</desc>
<defs>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="rgba(45,49,66,0.10)"/></pattern>
<marker id="mm" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{muted}"/></marker>
<marker id="ma" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{accent}"/></marker>
</defs>
{body}
</svg></div></body></html>
"""

if __name__ == "__main__":
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    build = build_landscape if cfg.get("orientation") == "landscape" else build_portrait
    body, W, H = build(cfg)
    html = PAGE.format(title=escape("".join(cfg["title"])), desc=escape(cfg["desc"]), fonts=FONTS,
                       paper=PAPER, muted=MUTED, accent=ACCENT, w=W, h=H, body=body)
    (out / "cover.html").write_text(html, encoding="utf-8")
    print(out / "cover.html")

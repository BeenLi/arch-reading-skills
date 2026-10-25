# 科普调研文档：封面与配图的固定风格

第一份样板是 `assets/cover-example/cover.png`（《看懂 DPU》，2026-10-24），它的 `cover.json` 在同目录。本文路径都相对 skill 目录 `kepu-research-doc/`。之后每份科普调研文档的封面和示意图都按这里的规定来做。

## 生成方式

```bash
python3 scripts/make_cover.py <topic>/figs/cover/cover.json <topic>/figs/cover
python3 scripts/export_cover.py <topic>/figs/cover/cover.html   # 导出 1242×1656 PNG（小红书 3:4 竖版）
```

`export_cover.py` 只依赖 Playwright（`python3 -m pip install --user playwright && python3 -m playwright install chromium`；要用别的浏览器时设 `CHROMIUM=/path/to/chromium`）。正文示意图的写法相同：`scripts/make_dd_example.py` 是五张样例图的生成器，复制到 `<topic>/figs/dd/` 改画图函数，再用同一个 `export_cover.py` 导出 2x PNG。

## cover.json 字段

| 字段 | 内容 |
|---|---|
| eyebrow | 顶部小标签：英文大写的关键词，用 · 分隔，最后一项写“科普调研” |
| title | 标题，分 1 到 2 行，每行不超过 7 个汉字 |
| subtitle | 副标题，分 1 到 2 行，每行不超过 12 个汉字，用一句话说出“原本是怎么回事” |
| topics | 底部 3 到 4 行“这篇要讲什么”，格式为 [英文标签, 一句话问题]，标签用 WHY / WHAT / HOW / WHO 这类词。不放图数、参考数等统计数字 |
| meta | 页脚：日期 · 页数 · 语言 |
| core | 同心圆圆心：主题的核心对象，[中文名, 英文小字] |
| rings | 2 到 4 圈，每圈写 {year, label, sweep, dashed?, focal?}。只能有一圈 focal |
| motif_caption | 母题下方的一句斜体说明 |
| desc | 无障碍描述，一句话 |

## 视觉规定

- **画幅（定稿：竖版）**：小红书封面 3:4 竖版。画布 1080×1440，导出 ×1.15 得到 1242×1656 的 PNG。四周留 96px 安全边距，iPhone 预览裁边或底部被遮挡时也不会切到文字。版式自上而下分三段：标题区（eyebrow、标题、橙色短横、副标题），点阵纸上的同心圆母题（上下各一条细线），“这篇要讲什么”的 3 到 4 行，最后是页脚。确实需要横版时，在 cover.json 里写 `"orientation": "landscape"`，会出 4:3 横版 1440×1080（左栏文字，右栏母题）。
- **配色**（diagram-design 默认皮肤）：底色 paper `#f5f5f5`，主色 ink `#2d3142`，次要色 muted `#4f5d75` 和 soft `#5a6580`，细线 rule `rgba(45,49,66,0.12)`，强调色 accent `#bf4520`。
- **强调色只用两处**：标题下方的短横条，以及焦点圈（连同它的节点和标签）。
- **字体**：标题用 Instrument Serif，中文标题回落到 Noto Serif SC 700；正文用 Geist 和 Noto Sans SC；eyebrow、年份、页脚用 Geist Mono。
- **母题**：固定是“同心圆”，圆心放核心对象，每一圈代表一个阶段或层级。用弧线和箭头表示演进方向。弧长本身就是信息：已经走完的阶段画到约 300°，几乎闭合；还在进行的阶段画到约 200°，留出缺口。被淘汰或收回的阶段画成虚线。换主题时只替换圈的内容，不改换图形。
- **不要**：渐变、阴影、圆角超过 6px、emoji、一张图里多于一处焦点。

## 正文示意图（diagram-design）

- 节点只用这几种样式：backend（白底、ink 描边）、input（muted 10% 底）、store（ink 5% 底）、external（ink 3% 底）、optional（虚线），focal 用 accent-tint 底加 accent 描边。
- 连线一律走直角，不画斜线；快路径用 link `#2e5aa8`，慢路径和焦点用 accent 虚线，控制面用 muted 虚线。
- 每张图最多两处 accent，图例放在底部横条。中文字号不小于 12px，正文节点用 13–14px。

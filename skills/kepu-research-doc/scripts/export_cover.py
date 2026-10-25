#!/usr/bin/env python3
"""把 make_cover.py / make_dd_example.py 生成的 HTML（内联 SVG）栅格化成同名 PNG。只依赖 Playwright。

用法：python3 scripts/export_cover.py <topic>/figs/cover/cover.html [更多 .html]
  封面竖版画布 1080×1440 按 1.15 倍导出，得到小红书 3:4 的 1242×1656；
  封面横版 1440×1080 按原尺寸导出；其余（正文示意图）按 2 倍导出。
  --scale N 可强制指定倍数。

依赖：python3 -m pip install --user playwright && python3 -m playwright install chromium
  想用别的 Chromium 时设环境变量 CHROMIUM=/path/to/chromium。
"""
import argparse
import os
import pathlib
import re

from playwright.sync_api import sync_playwright

VIEWBOX = re.compile(r'viewBox="0 0 (\d+) (\d+)"')


def default_scale(html_text: str) -> float:
    m = VIEWBOX.search(html_text)
    size = (int(m.group(1)), int(m.group(2))) if m else None
    if size == (1080, 1440):
        return 1.15
    if size == (1440, 1080):
        return 1
    return 2


def rasterize(html: pathlib.Path, png: pathlib.Path, scale: float) -> None:
    text = html.read_text(encoding="utf-8")
    m = VIEWBOX.search(text)
    if not m:
        raise SystemExit(f"{html}: 找不到 <svg viewBox>，不是 make_cover.py 生成的页面")
    w, h = int(m.group(1)), int(m.group(2))
    kw = {}
    if os.environ.get("CHROMIUM"):
        kw["executable_path"] = os.environ["CHROMIUM"]
    with sync_playwright() as p:
        browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        page.goto(html.resolve().as_uri())
        page.wait_for_load_state("networkidle")  # 等 Google Fonts 下载完
        page.evaluate("document.fonts.ready")
        # 只截 SVG 本身：去掉 body 的 padding，让 SVG 正好等于画布尺寸
        page.add_style_tag(content=(
            "body{padding:0!important}.frame{max-width:none!important}"
            f"svg{{min-width:0!important;width:{w}px!important;height:{h}px!important}}"))
        page.locator("svg").first.screenshot(path=str(png))
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="+", type=pathlib.Path)
    ap.add_argument("--scale", type=float, default=None, help="强制导出倍数；默认按画布尺寸自动选")
    args = ap.parse_args()
    for html in args.html:
        scale = args.scale or default_scale(html.read_text(encoding="utf-8"))
        rasterize(html, html.with_suffix(".png"), scale)
        print("png", html.with_suffix(".png"), f"x{scale:g}")

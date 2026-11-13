#!/usr/bin/env python3
"""检查科普文档的引用都能点击跳到文末参考文献。

用法：python3 scripts/check_refs.py <主题>.md [--pdf <主题>.pdf]
  md：参考文献每条都有 <a id="ref-N"></a> 锚点，编号连续、不重复；
      正文里的 [参考 N](#ref-N) 都指向存在的锚点，且链接文字和目标编号一致；
      没有残留的裸"参考 N"（没做成链接的）；列出从未被正文引用的条目（提示，不算错）。
  --pdf：导出后的 PDF 里每个 ref-N 都是命名目标，所有内部跳转链接都能解析到目标。需要 pypdf。
全部通过时输出 OK，否则逐条列出问题并以退出码 1 结束。
"""
import argparse
import re
import sys
from pathlib import Path

ANCHOR = re.compile(r'<a id="ref-(\d+)"></a>')
LINK = re.compile(r"\[参考\s*(\d+)\]\(#ref-(\d+)\)")
BARE = re.compile(r"参考\s*(\d+)")
REF_HEADING = re.compile(r"^##\s+参考\s*$", re.M)


def check_md(text: str) -> tuple[list[str], list[str]]:
    """返回 (错误, 提示)。"""
    errors, notes = [], []
    m = REF_HEADING.search(text)
    if not m:
        return ["找不到“## 参考”一节"], notes
    body, refs = text[:m.start()], text[m.start():]
    tail = refs.split("\n> ", 1)[1] if "\n> " in refs else ""  # 数字口径说明也算正文引用

    ids = [int(n) for n in ANCHOR.findall(refs)]
    if not ids:
        errors.append("参考文献没有任何 <a id=\"ref-N\"></a> 锚点")
    dup = sorted({n for n in ids if ids.count(n) > 1})
    if dup:
        errors.append(f"重复的锚点：{', '.join(f'ref-{n}' for n in dup)}")
    if ids and sorted(set(ids)) != list(range(1, max(ids) + 1)):
        missing = sorted(set(range(1, max(ids) + 1)) - set(ids))
        errors.append(f"锚点编号不连续，缺：{', '.join(f'ref-{n}' for n in missing)}")
    items = len(re.findall(r"^\d+\.\s", refs, re.M))
    if items != len(ids):
        errors.append(f"参考文献有 {items} 条，但只有 {len(ids)} 个锚点")

    cited = set()
    for where in (body, tail):
        for label, target in LINK.findall(where):
            cited.add(int(target))
            if label != target:
                errors.append(f"[参考 {label}] 的链接指向 #ref-{target}，文字和目标对不上")
            if int(target) not in ids:
                errors.append(f"[参考 {label}](#ref-{target}) 指向不存在的锚点")
        stripped = LINK.sub("", where)
        for n in BARE.findall(stripped):
            errors.append(f"裸“参考 {n}”没有做成链接，改成 [参考 {n}](#ref-{n})")
    unused = sorted(set(ids) - cited)
    if unused:
        notes.append(f"正文从未引用的条目：{', '.join(f'ref-{n}' for n in unused)}")
    return errors, notes


def check_pdf(path: Path, ids: list[int]) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    dests = {str(k).lstrip("/") for k in reader.named_destinations}  # Chromium 写成 /ref-N
    errors = [f"PDF 里没有命名目标 ref-{n}" for n in ids if f"ref-{n}" not in dests]
    internal = broken = 0
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            a = annot.get_object()
            if a.get("/Subtype") != "/Link":
                continue
            target = a.get("/Dest")
            if target is None and a.get("/A") and a["/A"].get("/S") == "/GoTo":
                target = a["/A"].get("/D")
            if target is None:
                continue  # 外链 URI
            internal += 1
            if isinstance(target, str) and target.lstrip("/") not in dests:
                broken += 1
                errors.append(f"内部链接指向不存在的目标 {target}")
    if internal == 0 and ids:
        errors.append("PDF 里没有任何内部跳转链接，导出时锚点可能丢了")
    print(f"pdf: {internal} 个内部链接，{len(dests)} 个命名目标，{broken} 个解析不到")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", type=Path)
    ap.add_argument("--pdf", type=Path)
    args = ap.parse_args(argv)
    text = args.md.read_text(encoding="utf-8")
    errors, notes = check_md(text)
    if args.pdf:
        refs = text[REF_HEADING.search(text).start():] if REF_HEADING.search(text) else ""
        errors += check_pdf(args.pdf, sorted({int(n) for n in ANCHOR.findall(refs)}))
    for n in notes:
        print("note:", n)
    for e in errors:
        print("error:", e, file=sys.stderr)
    if not errors:
        print("OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

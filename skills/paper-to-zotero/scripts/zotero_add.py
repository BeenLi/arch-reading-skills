#!/usr/bin/env python3
"""Add a paper (metadata JSON + PDF) to Zotero through the Zotero 10 local API.

  python3 zotero_add.py collections [--root "Computer Architecture"]   # leaf collections with keys and hints
  python3 zotero_add.py search "title words"                            # duplicate check: collections + local PDF paths
  python3 zotero_add.py add --meta meta.json --pdf paper.pdf --collection KEY [--collection KEY2]

Writes go through the running Zotero app (http://localhost:23119/api): Zotero pops an
authorization dialog; choose "Always Allow" once, otherwise every write asks again.
"""
import argparse, glob, hashlib, json, os, re, sys, urllib.parse, urllib.request, urllib.error
from pathlib import Path

def _find_shared_scripts():
    """Source first (repo or plugin cache), else the copy sync_shared.py vendors into <skill>/_shared."""
    here = Path(__file__).resolve()
    if (here.parents[3] / "scripts" / "sync_shared.py").exists():
        return here.parents[2] / "_shared" / "scripts"
    return here.parents[1] / "_shared" / "scripts"

sys.path.insert(0, str(_find_shared_scripts()))
from user_config import paper_to_zotero_config

BASE = os.environ.get("ZOTERO_LOCAL_API", "http://localhost:23119/api")
LIB = "users/0"
APP = "paper-to-zotero"

class Api:
    def __init__(self):
        self.sid = None; self.key = None; self.remember = False
    def req(self, method, path, body=None, headers=None, ctype="application/json", raw=False):
        if body is not None and not raw:
            body = json.dumps(body).encode()
        r = urllib.request.Request(BASE + "/" + path.lstrip("/"), data=body, method=method)
        r.add_header("Zotero-API-Version", "3")
        if body is not None: r.add_header("Content-Type", ctype)
        for k, v in (headers or {}).items(): r.add_header(k, v)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()
        except (urllib.error.URLError, OSError) as e:
            sys.exit(f"无法连接 Zotero 本地 API（{BASE}）：请确认 Zotero 10 已打开并在 设置→高级 启用本地 API（{e}）")
    def get(self, path):
        st, _, raw = self.req("GET", path)
        if st != 200: sys.exit(f"GET {path} 失败 HTTP {st}: {raw[:300]!r}")
        return json.loads(raw)
    def server_id(self):
        if not self.sid:
            st, h, _ = self.req("GET", "/")
            self.sid = h.get("Zotero-Server-ID")
            if not self.sid: sys.exit("本地 API 没有返回 Zotero-Server-ID，写入需要 Zotero 10 及以上")
        return self.sid
    def authorize(self):
        st, h, raw = self.req("POST", "local/authorize", {"appName": APP}, {"Zotero-Server-ID": self.server_id()})
        if st == 403: sys.exit("Zotero 里拒绝了写入授权，没有做任何修改")
        if st == 429: sys.exit(f"授权请求太频繁，请 {h.get('Retry-After','60')} 秒后再试")
        if st != 200: sys.exit(f"写入授权失败 HTTP {st}: {raw[:300]!r}")
        p = json.loads(raw); self.key = p["key"]; self.remember = bool(p.get("remember"))
    def write(self, method, path, body=None, headers=None, ctype="application/json", raw=False):
        """Authorized write; re-authorizes once on 401; drops single-use key after success."""
        for attempt in range(2):
            if not self.key: self.authorize()
            hdr = {"Zotero-Server-ID": self.server_id(), "Zotero-API-Key": self.key}
            hdr.update(headers or {})
            st, h, out = self.req(method, path, body, hdr, ctype, raw)
            if st == 401 and attempt == 0:
                self.key = None; continue
            break
        if 200 <= st < 300 and not self.remember: self.key = None
        return st, h, out

def leaf_tree(api, root_name, hints=None):
    """Print the tree under root_name ("" = every top-level collection); leaves get key= and their hint.

    hints maps a leaf path below the root ("Memory & Storage / Storage Systems") to what belongs there.
    """
    hints = hints or {}
    cols = api.get(f"{LIB}/collections?limit=1000")
    by_key = {c["key"]: c["data"] for c in cols}
    kids = {}
    for k, d in by_key.items(): kids.setdefault(d.get("parentCollection") or None, []).append(k)
    roots = [k for k, d in by_key.items() if d["name"] == root_name] if root_name else kids.get(None, [])
    if root_name and not roots:
        tops = ", ".join(sorted(by_key[k]["name"] for k in kids.get(None, []))) or "（库里还没有任何 collection）"
        sys.exit(
            f"Zotero 里没有名为 {root_name!r} 的 collection，没有可放的分类，已停止。\n"
            f"库里现有的顶层 collection：{tops}\n"
            "任选一种处理：\n"
            f"  1. 在 Zotero 里新建 {root_name!r} 和它下面的叶子分类；\n"
            "  2. 在 ~/.config/arch-reading-skills/user-config.json 里指定自己的分类根（说明可选）：\n"
            '     {"paper_to_zotero": {"collection_root": "<你的分类根>", "collection_hints": {"<子分类> / <叶子>": "放什么论文"}}}\n'
            '  3. 把 collection_root 设成 ""，在整个库里挑叶子。'
        )
    def walk(k, depth, rel):
        d = by_key[k]; ch = sorted(kids.get(k, []), key=lambda x: by_key[x]["name"])
        tag = ""
        if not ch:
            tag = f"  key={k}"
            if rel in hints: tag += f"  -- {hints[rel]}"
        print("  " * depth + d["name"] + tag)
        for c in ch:
            name = by_key[c]["name"]
            walk(c, depth + 1, f"{rel} / {name}" if rel else name)
    for r in sorted(roots, key=lambda x: by_key[x]["name"]):
        walk(r, 0, "" if root_name else by_key[r]["name"])

def collection_paths(api):
    """key -> 'Parent / Child / Leaf' for every collection in the library."""
    cols = {c["key"]: c["data"] for c in api.get(f"{LIB}/collections?limit=1000")}
    def path(k):
        d = cols[k]; parent = d.get("parentCollection")
        return (path(parent) + " / " if parent in cols else "") + d["name"]
    return {k: path(k) for k in cols}

def base_attachment_dir():
    """Zotero's 'Linked Attachment Base Directory' (used by ZotMoov etc.): env, then prefs.js."""
    if os.environ.get("ZOTERO_BASE_ATTACHMENT_PATH"):
        return os.path.expanduser(os.environ["ZOTERO_BASE_ATTACHMENT_PATH"])
    pattern = os.path.expanduser("~/Library/Application Support/Zotero/Profiles/*/prefs.js")  # macOS
    for prefs in glob.glob(pattern) + glob.glob(os.path.expanduser("~/.zotero/zotero/*/prefs.js")):
        m = re.search(r'user_pref\("extensions\.zotero\.baseAttachmentPath",\s*"(.*?)"\);',
                      open(prefs, encoding="utf-8").read())
        if m: return m.group(1)
    return None

def pdf_paths(api, item_key):
    """Local paths of the item's PDF attachments: stored files and linked files."""
    out = []
    for c in api.get(f"{LIB}/items/{item_key}/children"):
        d = c["data"]
        if d.get("itemType") != "attachment" or d.get("contentType") != "application/pdf":
            continue
        href = c.get("links", {}).get("enclosure", {}).get("href", "")
        if href.startswith("file://"):                     # imported into Zotero storage
            out.append(urllib.request.url2pathname(urllib.parse.urlparse(href).path))
        elif d.get("path", "").startswith("attachments:"):  # linked, relative to the base directory
            base = base_attachment_dir()
            rel = d["path"][len("attachments:"):]
            out.append(os.path.join(base, rel) if base else d["path"])
        elif d.get("path"):                                 # linked, absolute
            out.append(d["path"])
    return out

def search(api, q):
    items = api.get(f"{LIB}/items/top?q={urllib.parse.quote(q)}&qmode=titleCreatorYear&limit=20")
    if not items: print("(no match)"); return
    paths = collection_paths(api)
    for it in items:
        d = it["data"]
        print(f"{it['key']}  {d.get('date','')[:4]:4}  {d.get('title','')[:100]}")
        print(f"    zotero://select/library/items/{it['key']}")
        cols = [paths.get(k, k) for k in d.get("collections", [])]
        print("    collections: " + ("; ".join(cols) if cols else "(none)"))
        pdfs = pdf_paths(api, it["key"])
        for pdf in pdfs:
            print(f"    pdf: {pdf}" + ("" if os.path.exists(pdf) else "  (file missing)"))
        if not pdfs: print("    pdf: (none)")

def add(api, meta_path, pdf_path, col_keys):
    meta = json.load(open(meta_path))
    meta.setdefault("itemType", "journalArticle")
    meta["collections"] = sorted(set(meta.get("collections", []) + col_keys))
    meta.setdefault("tags", []); meta.setdefault("relations", {})
    # 1. parent item
    st, _, raw = api.write("POST", f"{LIB}/items", [meta])
    res = json.loads(raw) if raw else {}
    if st != 200 or "0" not in res.get("successful", {}):
        sys.exit(f"创建条目失败 HTTP {st}: {raw[:800]!r}")
    item_key = res["successful"]["0"]["key"]
    print(f"item created: {item_key}  zotero://select/library/items/{item_key}")
    if not pdf_path: return
    # 2. attachment item
    data = open(pdf_path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    fname = os.path.basename(pdf_path)
    att = {"itemType": "attachment", "linkMode": "imported_file", "parentItem": item_key,
           "title": "Full Text PDF", "contentType": "application/pdf", "filename": fname,
           "md5": None, "mtime": None, "tags": [], "relations": {}}
    st, _, raw = api.write("POST", f"{LIB}/items", [att])
    res = json.loads(raw) if raw else {}
    if st != 200 or "0" not in res.get("successful", {}):
        sys.exit(f"创建附件条目失败 HTTP {st}: {raw[:800]!r}（父条目 {item_key} 已建好）")
    att_key = res["successful"]["0"]["key"]
    # 3. upload: authorize -> bytes -> register
    form = urllib.parse.urlencode({"md5": md5, "filename": fname, "filesize": len(data),
                                   "mtime": int(os.path.getmtime(pdf_path) * 1000),
                                   "contentType": "application/pdf"}, quote_via=urllib.parse.quote)
    st, _, raw = api.write("POST", f"{LIB}/items/{att_key}/file", form.encode(), {"If-None-Match": "*"},
                           ctype="application/x-www-form-urlencoded", raw=True)
    if st != 200: sys.exit(f"上传授权失败 HTTP {st}: {raw[:800]!r}（附件条目 {att_key} 已建，文件未传）")
    up = json.loads(raw)
    if up.get("exists"):
        print(f"pdf already present on attachment {att_key}"); return
    body = (up.get("prefix") or "").encode() + data + (up.get("suffix") or "").encode()
    r = urllib.request.Request(up["url"], data=body, method="POST")
    r.add_header("Content-Type", up.get("contentType") or "application/octet-stream")
    try:
        with urllib.request.urlopen(r, timeout=300) as resp: st = resp.status
    except urllib.error.HTTPError as e:
        sys.exit(f"上传文件字节失败 HTTP {e.code}: {e.read()[:300]!r}")
    if st != 201: sys.exit(f"上传文件字节返回 HTTP {st}")
    st, _, raw = api.write("POST", f"{LIB}/items/{att_key}/file", f"upload={up['uploadKey']}".encode(),
                           {"If-None-Match": "*"}, ctype="application/x-www-form-urlencoded", raw=True)
    if st != 204: sys.exit(f"登记上传失败 HTTP {st}: {raw[:300]!r}")
    print(f"pdf attached: {att_key}  ({len(data)} bytes, md5 {md5})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    cfg = paper_to_zotero_config()
    c = sub.add_parser("collections"); c.add_argument("--root", default=cfg.get("collection_root", ""))
    s = sub.add_parser("search"); s.add_argument("query")
    a = sub.add_parser("add"); a.add_argument("--meta", required=True); a.add_argument("--pdf")
    a.add_argument("--collection", action="append", default=[], help="collection key (repeatable)")
    ns = ap.parse_args(); api = Api()
    if ns.cmd == "collections": leaf_tree(api, ns.root, cfg.get("collection_hints") if ns.root == cfg.get("collection_root", "") else None)
    elif ns.cmd == "search": search(api, ns.query)
    else:
        if not ns.collection: sys.exit("--collection KEY 必填")
        add(api, ns.meta, ns.pdf, ns.collection)

#!/usr/bin/env python3
"""Architecture figure in computer-architecture paper style -> editable draw.io.

Input is a small YAML/JSON spec written after reading a paper / patent / description / RTL
(see SKILL.md section 4 and examples/arch_*.yaml). Layout is a deterministic grid, no Graphviz:
  * stages = columns, left -> right, dashed boundaries, named headers; every lane shares the
    stage columns, so parallel pipelines stay aligned in time;
  * lanes  = parallel pipelines stacked top -> bottom;
  * registers / FIFOs given `between: [Sa, Sb]` sit ON the dashed boundary line;
  * feedback (target in an earlier stage, an intra-stage loop, or `fb`) returns along a
    corridor under (or, with via=top, over) its lane;
  * forward edges are orthogonal and routed around blocks.

Usage
  arch2drawio.py render SPEC.yaml [-o OUT.drawio] [--png] [--svg] [--scale N]
"""
import argparse, html, json, os, re, shutil, subprocess, sys
from collections import defaultdict
from xml.sax.saxutils import quoteattr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtl2drawio import stencil, REG_SHAPE, ALU_SHAPE, MUX_SHAPE, FIFO_SHAPE  # noqa: E402
from drawio_export import export_all  # noqa: E402

INK, MUTED, FBC = "#262626", "#6b6b6b", "#b03a2e"
FILL, STORE, LOGIC, HEAD, TINT = "#ffffff", "#eef2f7", "#f2f2f2", "#dde3ea", "#e8eef6"
ACCENT = "#1f3a5f"
FONT = "fontFamily=Helvetica;"
GX, GY, MARGIN, LANE_GAP, TRACK, MINW, STK = 60, 34, 40, 40, 12, 110, 6
RH = 22                                                    # table row height

PIPE_BAR = stencil('<shape name="pipe" w="20" h="100" aspect="variable" strokewidth="inherit"><background>'
                   '<rect x="0" y="0" w="20" h="100"/></background><foreground><fillstroke/><path>'
                   '<move x="3" y="100"/><line x="10" y="91"/><line x="17" y="100"/></path><stroke/></foreground></shape>')
XBAR = stencil('<shape name="xbar" w="100" h="100" aspect="variable" strokewidth="inherit"><background>'
               '<rect x="0" y="0" w="100" h="100"/></background><foreground><fillstroke/>'
               '<path><move x="0" y="0"/><line x="100" y="100"/></path><stroke/>'
               '<path><move x="100" y="0"/><line x="0" y="100"/></path><stroke/></foreground></shape>')

CIRCLE = {"adder": "+", "mult": "×", "cmp": "=", "op": "?"}
GATES = {"and": ("and", 0), "or": ("or", 0), "xor": ("xor", 0), "nand": ("and", 1), "nor": ("or", 1), "xnor": ("xor", 1)}
TYPES = {"block", "reg", "fifo", "mux", "alu", "cloud", "mem", "xbar", "in", "out", "text", "dot", "table", "array",
         "not", *CIRCLE, *GATES}
ALIAS = {"sram": "table", "cam": "table", "cache": "table", "tbl": "table", "queue": "fifo", "buffer": "fifo",
         "logic": "cloud", "comb": "cloud", "add": "adder", "sum": "adder", "mul": "mult", "multiplier": "mult",
         "comparator": "cmp", "register": "reg", "input": "in", "port": "in", "output": "out", "pe_array": "array",
         "grid": "array", "crossbar": "xbar", "inv": "not", "box": "block", "unit": "block", "memory": "mem"}
CTRL_NAME = re.compile(r"sched|ctrl|control|fsm|arbit|dispatch|sequenc|调度|控制|仲裁|状态机", re.I)
PORTS = {"sel": "bottom", "en": "bottom", "bottom": "bottom", "top": "top", "left": "left", "right": "right"}
DISTRIB_OUT = {"reg", "block", "table", "fifo", "mem", "array", "cloud", "xbar", "alu"}
OUTSIDE_LABEL = {"mux", "xbar", "table", "array", "not", *GATES}   # label drawn above/below the shape
EDGE_RE = re.compile(r"^\s*([^\s:|]+?)\s*(->|=>|~>)\s*([^\s:|]+)\s*(?::\s*([^|]*?))?\s*(?:\|\s*(.*?))?\s*$")
TAG_OK = re.compile(r"</?(?:b|i|u|sub|sup|br|font|span)(?:\s[^<>]*)?/?>", re.I)


def die(msg):
    sys.exit(f"error: {msg}")


def lab(s):
    """Label -> draw.io HTML value: keep simple inline tags, escape the rest, \\n -> <br>."""
    if s is None: return ""
    s, out, i = str(s), [], 0
    for m in TAG_OK.finditer(s):
        out += [html.escape(s[i:m.start()], quote=False), m.group(0)]; i = m.end()
    out.append(html.escape(s[i:], quote=False))
    return "".join(out).replace("\n", "<br>")


def _plain(s):
    s = re.sub(r"<br\s*/?>", "\n", str(s or "")); return re.sub(r"<[^>]+>", "", s)


def tw(s, fs=11):
    """Rough rendered width of a label (CJK ~1em, Latin ~0.6em)."""
    return max((sum(fs * (1.0 if ord(c) > 0x2E80 else 0.6) for c in ln) for ln in _plain(s).split("\n")), default=0)


def nlines(s): return len(_plain(s).split("\n")) if s else 0


def median(v):
    v = sorted(v); return v[(len(v) - 1) // 2] if v else None


def seg_hits(a, b, x0, y0, x1, y1):
    (ax, ay), (bx, by) = a, b
    if abs(ay - by) < 0.5: return y0 < ay < y1 and min(ax, bx) < x1 and max(ax, bx) > x0
    if abs(ax - bx) < 0.5: return x0 < ax < x1 and min(ay, by) < y1 and max(ay, by) > y0
    return not (max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1)


def overlap(s1, s2, tol=4, minlen=6):
    (ax, ay), (bx, by) = s1; (cx, cy), (dx, dy) = s2
    if abs(ay - by) < 0.5 and abs(cy - dy) < 0.5 and abs(ay - cy) < tol:
        return min(max(ax, bx), max(cx, dx)) - max(min(ax, bx), min(cx, dx)) > minlen
    if abs(ax - bx) < 0.5 and abs(cx - dx) < 0.5 and abs(ax - cx) < tol:
        return min(max(ay, by), max(cy, dy)) - max(min(ay, by), min(cy, dy)) > minlen
    return False


def sty(d): return "".join(f"{k}={v};" for k, v in d.items())


def vcell(cid, value, style, x, y, w, h, parent="1", extra=""):
    return (f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(style)} vertex="1" '
            f'parent={quoteattr(parent)}{extra}><mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" '
            f'height="{h:.0f}" as="geometry"/></mxCell>')


def load_spec(path):
    txt = open(path, encoding="utf-8").read()
    if not path.endswith(".json"):
        try:
            import yaml
            return yaml.safe_load(txt)
        except ImportError:
            pass
    return json.loads(txt)


class Fig:
    def __init__(self, spec):
        self.spec, self.acc, self.warn = spec, spec.get("accent", ACCENT), []
        self.stages = []
        for s in spec.get("stages") or []:
            if isinstance(s, dict):
                sid = str(s.get("id", s.get("name")))
                self.stages.append(dict(id=sid, name=str(s.get("name", sid)), sub=s.get("sub")))
            else:
                self.stages.append(dict(id=str(s), name=str(s), sub=None))
        self.implicit = not self.stages
        if self.implicit: self.stages = [dict(id="_", name="", sub=None)]
        self.lanes = []
        for l in spec.get("lanes") or []:
            if isinstance(l, dict):
                lid = str(l.get("id", l.get("name"))); self.lanes.append(dict(id=lid, name=str(l.get("name", lid))))
            else:
                self.lanes.append(dict(id=str(l), name=str(l)))
        self.show_lanes = any(l["name"] for l in self.lanes)       # unnamed lanes: bands without labels
        if not self.lanes: self.lanes = [dict(id="_", name="")]
        self._nodes(spec.get("nodes") or [])
        self._edges(spec.get("edges") or [])

    # ------------------------------------------------------------------ parsing
    def _find(self, items, v, what, where):
        k = str(v)
        for i, s in enumerate(items):
            if k in (s["id"], s["name"]): return i
        if isinstance(v, int) and 0 <= v < len(items): return v
        die(f"{where}: unknown {what} {v!r} (have {[s['id'] for s in items]})")

    def _nodes(self, raw):
        if isinstance(raw, dict): raw = [dict(v or {}, id=k) for k, v in raw.items()]
        self.N = {}
        for i, r in enumerate(raw):
            n = dict(r)
            nid = str(n.get("id") or die(f"node #{i} has no id"))
            if nid in self.N: die(f"duplicate node id {nid!r}")
            t = str(n.get("type", "block")).lower(); t = ALIAS.get(t, t)
            if t not in TYPES: die(f"{nid}: unknown type {t!r} (known: {sorted(TYPES)})")
            n.update(id=nid, type=t, _i=i, bnd=None, pos=None, fixed=False,
                     pin_col=n.pop("col", None), pin_row=n.pop("row", None))
            if n.get("label") is None and t in ("block", "reg", "fifo", "cloud", "mem", "in", "out", "text"):
                n["label"] = nid
            bt = n.get("between")
            if bt is not None:
                if self.implicit: die(f"{nid}: `between` needs `stages`")
                if isinstance(bt, str): bt = [x.strip() for x in re.split(r"[|/,]", bt) if x.strip()]
                a_, b_ = (self._find(self.stages, x, "stage", nid) for x in bt)
                if b_ != a_ + 1: die(f"{nid}: between {bt} must name two adjacent stages")
                n.update(bnd=a_, pos=2 * a_ + 1, fixed=True)
            elif n.get("stage") is not None:
                n.update(pos=2 * self._find(self.stages, n["stage"], "stage", nid), fixed=True)
            elif self.implicit:
                n.update(pos=0, fixed=True)
            n["ln"] = self._find(self.lanes, n["lane"], "lane", nid) if n.get("lane") is not None else None
            self.N[nid] = n

    def _ep(self, x, default):
        x = str(x)
        if "." in x:
            a_, p = x.rsplit(".", 1)
            if p in PORTS:
                if a_ not in self.N: die(f"edge endpoint {a_!r} is not a node")
                return a_, PORTS[p]
        if x not in self.N: die(f"edge endpoint {x!r} is not a node")
        return x, default

    def _edges(self, raw):
        self.E = []
        for i, r in enumerate(raw):
            if isinstance(r, str):
                m = EDGE_RE.match(r) or die(f"cannot parse edge {r!r} (use 'a -> b : label | opts')")
                s, arrow, d, label, opts = m.groups()
                e = dict(frm=s, to=d, label=label or None, kind={"->": "data", "=>": "bus", "~>": "ctrl"}[arrow])
                for tok in re.split(r"[\s,]+", opts or ""):
                    if not tok: continue
                    if "=" in tok: k, v = tok.split("=", 1); e[k] = v
                    else: e[tok] = True
            elif isinstance(r, dict) and len(r) == 1 and re.search(r"(->|=>|~>)", str(next(iter(r)))):
                k_, v_ = next(iter(r.items()))              # YAML parsed `a -> b : label` as {a -> b: label}
                return self._edges(list(raw[:i]) + [f"{k_} : {v_}"] + list(raw[i + 1:]))
            elif isinstance(r, (list, tuple)):
                e = dict(frm=r[0], to=r[1], label=r[2] if len(r) > 2 else None, kind="data")
            else:
                e = dict(r); e["frm"] = e.pop("from", None); e.setdefault("kind", "data")
            s, sp = self._ep(e["frm"], "right")
            d, dp = self._ep(e["to"], "left")
            kind = e.get("kind", "data")
            if e.get("w") and kind == "data" and int(e["w"]) > 1: kind = "bus"
            self.E.append(dict(i=i, s=s, d=d, sp=sp, dp=dp, kind=kind, label=e.get("label"),
                               hl=bool(e.get("hl")), fb=bool(e.get("fb")), w=e.get("w"), both=bool(e.get("both")),
                               via=str(e.get("via", "bottom")), lpos=str(e.get("pos", "mid")), back=False))

    # ------------------------------------------------------------------ inference
    def infer(self):
        N, E = self.N, self.E
        fw = [e for e in E if not e["fb"]]
        for _ in range(len(N) + 1):                          # ASAP stage from producers
            ch = False
            for e in fw:
                s, d = N[e["s"]], N[e["d"]]
                if d["fixed"] or s["pos"] is None: continue
                c = s["pos"] + s["pos"] % 2                   # after a boundary register -> next stage
                if d["pos"] is None or c > d["pos"]: d["pos"] = c; ch = True
            if not ch: break
        for _ in range(len(N) + 1):                          # pure sources: stage of the consumer
            ch = False
            for e in fw:
                s, d = N[e["s"]], N[e["d"]]
                if s["pos"] is None and d["pos"] is not None: s["pos"] = d["pos"] - d["pos"] % 2; ch = True
            if not ch: break
        for n in N.values():
            if n["pos"] is None: n["pos"] = 0
            if not n["fixed"] and not self.implicit and n["type"] not in ("in", "out", "text", "dot"):
                self.warn.append(f"{n['id']}: no stage given, inferred {self.stages[n['pos'] // 2]['id']}")
        for pick in ("s", "d"), ("d", "s"):                   # lanes: from producers, then consumers
            for _ in range(len(N) + 1):
                ch = False
                for e in E:
                    a_, b_ = N[e[pick[0]]], N[e[pick[1]]]
                    if b_["ln"] is None and a_["ln"] is not None: b_["ln"] = a_["ln"]; ch = True
                if not ch: break
        for n in N.values():
            if n["ln"] is None: n["ln"] = 0
        for e in E:
            e["back"] = e["fb"] or N[e["d"]]["pos"] < N[e["s"]]["pos"] or e["s"] == e["d"]

    def columns(self):
        N, E = self.N, self.E
        by = defaultdict(list)
        for n in sorted(N.values(), key=lambda n: n["_i"]): by[n["pos"]].append(n["id"])
        indeg_any = defaultdict(int)
        for e in E:
            if not e["back"]: indeg_any[e["d"]] += 1
        for pos, ids in by.items():
            if pos % 2:
                for u in ids: N[u]["col"] = 0
                continue
            S = set(ids)
            succ = defaultdict(list)
            for e in E:
                if not e["back"] and e["s"] in S and e["d"] in S: succ[e["s"]].append(e)
            color = {}                                        # DFS: intra-stage loops -> feedback edges
            for r in self.loop_roots(ids, succ):
                if r in color: continue
                color[r] = 1; st = [(r, iter(succ[r]))]
                while st:
                    u, it = st[-1]; e = next(it, None)
                    if e is None: color[u] = 2; st.pop(); continue
                    v = e["d"]
                    if color.get(v) == 1: e["back"] = True
                    elif v not in color: color[v] = 1; st.append((v, iter(succ[v])))
            preds, succs, indeg = defaultdict(list), defaultdict(list), {u: 0 for u in ids}
            for u in ids:
                for e in succ[u]:
                    if e["back"]: continue
                    preds[e["d"]].append(u); succs[u].append(e["d"]); indeg[e["d"]] += 1
            order, q = [], [u for u in ids if indeg[u] == 0]
            while q:
                u = q.pop(0); order.append(u)
                for v in succs[u]:
                    indeg[v] -= 1
                    if indeg[v] == 0: q.append(v)
            col = {}
            for u in order:
                col[u] = int(N[u]["pin_col"]) if N[u]["pin_col"] is not None else \
                    max((col[p] + 1 for p in preds[u]), default=0)
            for u in reversed(order):                         # pure sources sit right before their consumer
                if indeg_any[u] == 0 and succs[u] and N[u]["pin_col"] is None:
                    col[u] = min(col[v] for v in succs[u]) - 1
            mx = max((c for u, c in col.items() if N[u]["type"] != "out"), default=0)
            for u in ids:                                     # output ports: a column of their own on the right
                if N[u]["type"] == "out" and not succs[u] and N[u]["pin_col"] is None: col[u] = mx + 1
            remap = {c: i for i, c in enumerate(sorted(set(col.values())))}
            for u in ids: N[u]["col"] = remap[col[u]]

    def loop_roots(self, ids, succ):
        """Order in which the loop-breaking DFS starts inside one stage. In every loop, the edge that closes
        back onto a node visited earlier becomes the feedback edge (drawn along the corridor), and the node the
        DFS entered first ends up leftmost. ids: node ids in spec order; succ[u]: forward edge dicts out of u
        (e["d"] is the target). Node attributes: self.N[u]["type"], ["label"], ["hl"], ..."""
        def score(u):
            n = self.N[u]
            named = 10 if CTRL_NAME.search(f"{u} {_plain(n.get('label'))}") else 0   # the name is the strongest hint
            fanout = sum(1 for e in self.E if e["s"] == u and e["kind"] == "ctrl")    # then control fan-out
            return named + fanout
        return sorted(ids, key=lambda u: -score(u))              # stable: ties keep the spec order

    # ------------------------------------------------------------------ sizes
    def sizes(self):
        for n in self.N.values():
            t, L = n["type"], n.get("label")
            if t == "table":
                fields = []
                for f in n.get("fields") or ["entry"]:
                    nm, wt, fh = (str(f.get("name", "")), float(f.get("w", 1)), bool(f.get("hl"))) \
                        if isinstance(f, dict) else (str(f), 1.0, False)
                    fields.append((nm, max(34, tw(nm, 10) + 14) * wt, fh))
                n["_fields"], n["_rows"] = fields, max(1, int(n.get("rows", 3)))
                w, h = sum(fw for _, fw, _ in fields), RH * n["_rows"]
            elif t == "array":
                r_, c_ = (list(n.get("dims") or [4, 4]) + [4, 4])[:2]
                cs = float(n.get("cell", 22)); ch = float(n.get("cell_h", cs))
                n["_dims"], n["_cs"], n["_ch"] = (int(r_), int(c_)), cs, ch
                w, h = 14 + int(c_) * cs + (int(c_) - 1) * 5, 14 + int(r_) * ch + (int(r_) - 1) * 5
            elif t == "block": w, h = max(84, tw(L, 11) + 26), max(44, 17 * nlines(L) + 16)
            elif t == "reg": w, h = (18, 72) if n["bnd"] is not None else (max(52, tw(L, 11) + 22), 38)
            elif t == "fifo": w, h = max(96, tw(L, 11) + 60), 34
            elif t == "mux": w, h = 22, max(52, 20 * int(n.get("ports", 2)) + 16)
            elif t in CIRCLE: w = h = 38
            elif t == "alu": w, h = 46, 76
            elif t in GATES: w, h = 50, 32
            elif t == "not": w, h = 40, 26
            elif t == "cloud": w, h = max(96, tw(L, 10) + 44), 56
            elif t == "mem": w, h = max(100, tw(L, 11) + 30), 60
            elif t == "xbar": w, h = 56, 56
            elif t in ("in", "out", "text"): w, h = tw(L, 11) + 10, 17 * max(1, nlines(L)) + 4
            else: w = h = 8                                   # dot
            n["w"], n["h"] = float(n.get("w") or w), float(n.get("h") or h)
            stk = 2 * STK if n.get("stack") else 0
            cap_t = cap_b = 0
            capw = 0
            if L and t in ("table", "array"): cap_t, capw = 18, tw(L, 11) + 8
            elif L and t == "reg" and n["bnd"] is not None: cap_t, capw = 15 * nlines(L) + 2, tw(L, 10) + 6
            elif L and t == "mux": cap_t, capw = 15 * nlines(L) + 2, tw(L, 10) + 6
            elif L and (t in CIRCLE or t in GATES or t in ("not", "xbar")): cap_b, capw = 15 * nlines(L) + 2, tw(L, 10) + 6
            if n.get("num"): cap_t = max(cap_t, 9)
            n["stk"], n["ct"], n["cb"] = stk, cap_t + stk, cap_b
            n["wx"] = max(n["w"] + stk + (26 if stk else 0), capw)

    # ------------------------------------------------------------------ geometry
    def xgeom(self):
        N, nst = self.N, len(self.stages)
        self.colL, self.colR, self.xb, self.span = {}, {}, {}, {}
        x = 0.0
        for s in range(nst):
            ids = [n for n in N.values() if n["pos"] == 2 * s]
            ncol = max((n["col"] for n in ids), default=-1) + 1
            widths = [max((n["wx"] for n in ids if n["col"] == c), default=40) for c in range(ncol)]
            total = sum(widths) + GX * max(ncol - 1, 0)
            st = self.stages[s]
            minw = 0 if self.implicit else max(MINW, tw(st["name"], 13) + 24, tw(st["sub"], 10) + 16)
            pad = max(0.0, (minw - total) / 2)
            left = x; x += pad
            for c, w in enumerate(widths):
                self.colL[(2 * s, c)], self.colR[(2 * s, c)] = x, x + w; x += w + GX
            if ncol: x -= GX
            x += pad
            self.span[s] = [left, x]
            if s < nst - 1:
                hw = max((n["wx"] / 2 for n in N.values() if n["pos"] == 2 * s + 1), default=0)
                xb = x + hw + MARGIN
                self.xb[s] = xb
                self.colL[(2 * s + 1, 0)], self.colR[(2 * s + 1, 0)] = xb - hw, xb + hw
                x = xb + hw + MARGIN
        for s in range(nst):                                  # header spans run boundary to boundary
            self.span[s] = [self.xb[s - 1] if s else self.span[s][0] - 24, self.xb[s] if s < nst - 1 else self.span[s][1] + 24]

    def tracks(self):
        """Assign feedback edges to corridors (lane, side) and tracks; wider spans outside."""
        N, E = self.N, self.E
        self.ntrk = defaultdict(int)
        groups = defaultdict(list)
        for e in E:
            if not e["back"] or self.vertical_back(e): continue
            side = "top" if e["via"] == "top" else "bottom"
            lane = (min if side == "top" else max)(N[e["s"]]["ln"], N[e["d"]]["ln"])
            x1 = self.colR[(N[e["s"]]["pos"], N[e["s"]]["col"])]; x2 = self.colL[(N[e["d"]]["pos"], N[e["d"]]["col"])]
            e["corr"] = (lane, side); groups[(lane, side)].append((abs(x1 - x2), e["i"], e))
        for key, es in groups.items():
            for k, (_, _, e) in enumerate(sorted(es, key=lambda t: t[:2])): e["track"] = k
            self.ntrk[key] = len(es)

    def vertical_back(self, e):
        """Feedback between two units stacked in one column (Dispatcher over Core): a short vertical return
        line beside the forward one instead of a trip around the corridor."""
        S, T = self.N[e["s"]], self.N[e["d"]]
        return e["s"] != e["d"] and (S["pos"], S["col"]) == (T["pos"], T["col"]) and \
            (S["ln"], S.get("row")) != (T["ln"], T.get("row")) and e["dp"] == "left" and e["sp"] == "right"

    def rows(self):
        N, E = self.N, self.E
        fpred, fsucc = defaultdict(list), defaultdict(list)
        for e in E:
            if not e["back"]: fpred[e["d"]].append(e); fsucc[e["s"]].append(e)
        row, occ = {}, defaultdict(set)
        ck = lambda n: (n["ln"], n["pos"], n["col"])

        def put(n, pref):
            used = occ[ck(n)]
            if pref is None:
                r = 0
                while r in used: r += 1
            else:
                r = next(c for c in [pref + d for d in range(64)] + [pref - d for d in range(1, 64)] if c not in used)
            row[n["id"]] = r; used.add(r)

        for n in N.values():
            if n["pin_row"] is not None: row[n["id"]] = int(n["pin_row"]); occ[ck(n)].add(int(n["pin_row"]))
        order = sorted(N.values(), key=lambda n: (n["pos"], n["col"], n["_i"]))
        sources = [n for n in order if not fpred[n["id"]] and fsucc[n["id"]] and n["id"] not in row]
        srcset = {n["id"] for n in sources}
        cols = defaultdict(list)
        for n in order:
            if n["id"] not in row and n["id"] not in srcset: cols[(n["pos"], n["col"])].append(n)
        gcol = {k: i for i, k in enumerate(sorted({(n["pos"], n["col"]) for n in N.values()}))}
        for key in sorted(cols):
            prefs = []
            for n in cols[key]:
                same = [e for e in fpred[n["id"]] if e["s"] in row and N[e["s"]]["ln"] == n["ln"]]
                lp = [row[e["s"]] for e in same if e["dp"] == "left"] or [row[e["s"]] for e in same]
                near = max((gcol[(N[e["s"]]["pos"], N[e["s"]]["col"])] for e in same), default=-1)
                prefs.append((median(lp), -near, n))           # the closest producer wins a contested row
            prefs.sort(key=lambda t: (t[0] is None, t[1], t[0] or 0, t[2]["_i"]))
            later = []
            for pref, near, n in prefs:                        # exact wishes first, then the displaced ones
                if pref is not None and pref not in occ[ck(n)]: put(n, pref)
                else: later.append((pref, n))
            for pref, n in later: put(n, pref)
        for n in sources:
            ls = [row[e["d"]] + (1 if e["dp"] == "bottom" else -1 if e["dp"] == "top" else 0)
                  for e in fsucc[n["id"]] if e["d"] in row and N[e["d"]]["ln"] == n["ln"]]
            put(n, median(ls))
        for l in range(len(self.lanes)):                      # compress
            used = sorted({row[i] for i, n in N.items() if n["ln"] == l})
            rm = {r: k for k, r in enumerate(used)}
            for i, n in N.items():
                if n["ln"] == l: n["row"] = rm[row[i]]

    def ygeom(self):
        N = self.N
        self.lane_top, self.lane_bot, self.center, self.chan = {}, {}, {}, []
        y = 0.0
        for l in range(len(self.lanes)):
            nt = self.ntrk[(l, "top")]
            if nt: y += 16 + TRACK * nt
            self.lane_top[l] = y
            ids = [n for n in N.values() if n["ln"] == l]
            for r in sorted({n["row"] for n in ids}):
                rn = [n for n in ids if n["row"] == r]
                up = max(n["h"] / 2 + n["ct"] for n in rn); dn = max(n["h"] / 2 + n["cb"] for n in rn)
                if r: self.chan.append(y - GY / 2)
                self.center[(l, r)] = y + up; y += up + dn + GY
            if ids: y -= GY
            self.lane_bot[l] = y
            self.chan += [self.lane_top[l] - 10, y + 10]
            nb = self.ntrk[(l, "bottom")]
            y += (16 + TRACK * nb if nb else 0) + LANE_GAP
        for n in N.values():
            key = (n["pos"], n["col"])
            cx = self.xb[n["bnd"]] if n["bnd"] is not None else (self.colL[key] + self.colR[key]) / 2
            n["x"] = cx - (n["w"] + n["stk"]) / 2 + float(n.get("dx", 0))
            n["y"] = self.center[(n["ln"], n["row"])] - n["h"] / 2 + float(n.get("dy", 0))
            n["cx"], n["cy"] = n["x"] + n["w"] / 2, n["y"] + n["h"] / 2
        self.obst = []
        for n in N.values():
            capw = n["wx"] - n["stk"] - (26 if n["stk"] else 0)
            x0 = min(n["x"], n["cx"] - capw / 2)
            x1 = max(n["x"] + n["w"] + n["stk"] + (24 if n["stk"] else 0), n["cx"] + capw / 2)
            self.obst.append((n["id"], x0, n["y"] - n["ct"], x1, n["y"] + n["h"] + n["cb"]))

    # ------------------------------------------------------------------ ports & routing
    @staticmethod
    def spread(ds, n_, lo_pad=8, gap=12):
        top, h, t = n_["y"], n_["h"], n_["type"]
        k = len(ds)
        if t in ("in", "out", "dot") or k == 0: return [n_["cy"]] * k
        if t == "alu":
            fr = [0.25] if k == 1 else [0.22 + 0.56 * i / (k - 1) for i in range(k)]
            return [top + f * h for f in fr]
        pad = min(lo_pad, h / 4)
        lo, hi = top + pad, top + h - pad
        g = min(gap, (hi - lo) / (k - 1)) if k > 1 else 0
        ys = [min(max(d, lo), hi) for d in ds]
        for i in range(1, k): ys[i] = max(ys[i], ys[i - 1] + g)
        if ys[-1] > hi:
            ys[-1] = hi
            for i in range(k - 2, -1, -1): ys[i] = min(ys[i], ys[i + 1] - g)
        return ys

    def ports(self):
        N, E = self.N, self.E
        outs, ins = defaultdict(list), defaultdict(list)
        for e in E:
            if e["sp"] == "right": outs[e["s"]].append(e)
            if e["dp"] == "left": ins[e["d"]].append(e)
        for e in E:                                           # defaults
            S, T = N[e["s"]], N[e["d"]]
            e["sy"], e["ey"] = S["cy"], T["cy"]
        for sid, es in outs.items():
            S = N[sid]
            if S["type"] not in DISTRIB_OUT or len({e["d"] for e in es}) < 2: continue
            key = lambda e: 1e6 if e["back"] else N[e["d"]]["cy"]
            es.sort(key=lambda e: (key(e), e["i"]))
            ys, seen = self.spread([key(e) for e in es], S), {}
            for e, y in zip(es, ys): e["sy"] = seen.setdefault(e["d"], y)
        for tid, es in ins.items():
            T = N[tid]
            arr = lambda e: (-1e6 if e["via"] == "top" else 1e6) if e["back"] else e["sy"]
            es.sort(key=lambda e: (arr(e), N[e["s"]]["cx"], e["i"]))
            for e, y in zip(es, self.spread([arr(e) for e in es], T)): e["ey"] = y
            ranked = [e for e in es if e["back"] or abs(e["sy"] - e["ey"]) > 2.5]
            above = sorted([e for e in ranked if arr(e) < e["ey"]], key=lambda e: e["ey"])
            below = sorted([e for e in ranked if arr(e) >= e["ey"]], key=lambda e: -e["ey"])
            for grp in (above, below):
                for r, e in enumerate(grp): e["rank"] = r

    def col_lr(self, n):
        k = (n["pos"], n["col"]); return self.colL[k], self.colR[k]

    def cost(self, poly, skip, src):
        """1000 per block crossed, 50 per stretch shared with another signal, 2 per bend, + length."""
        c = 2.0 * (len(poly) - 2)
        for a_, b_ in zip(poly, poly[1:]):
            c += (abs(a_[0] - b_[0]) + abs(a_[1] - b_[1])) / 1000
            for nid, x0, y0, x1, y1 in self.obst:
                if nid not in skip and seg_hits(a_, b_, x0 - 3, y0 - 3, x1 + 3, y1 + 3): c += 1000
            for p, q, s_ in self.segs:
                if s_ != src and overlap((a_, b_), (p, q)): c += 50
        return c

    def route(self):
        N = self.N
        self.segs = []
        spans = sorted(set(self.colL) | set(self.colR))
        edges_x = sorted([(self.colL[k], self.colR[k]) for k in self.colL])
        gaps = [(edges_x[i][1] + edges_x[i + 1][0]) / 2 for i in range(len(edges_x) - 1)]
        span = lambda e: abs(N[e["d"]]["x"] - N[e["s"]]["x"])
        for e in sorted(self.E, key=lambda e: (not e["back"], span(e), e["i"])):
            S, T = N[e["s"]], N[e["d"]]
            sL, sR = self.col_lr(S); tL, tR = self.col_lr(T)
            # exit point
            if S["type"] == "dot": sx, sy = S["cx"], S["cy"]
            elif e["sp"] == "bottom": sx, sy = S["cx"], S["y"] + S["h"]
            elif e["sp"] == "top": sx, sy = S["cx"], S["y"]
            elif e["sp"] == "left": sx, sy = S["x"], S["cy"]
            else: sx, sy = S["x"] + S["w"], e["sy"]
            # entry point
            if T["type"] == "dot": tx, ty = T["cx"], T["cy"]
            elif e["dp"] == "bottom": tx, ty = T["cx"], T["y"] + T["h"] * (0.9 if T["type"] == "mux" else 1)
            elif e["dp"] == "top": tx, ty = T["cx"], T["y"] + T["h"] * (0.1 if T["type"] == "mux" else 0)
            elif e["dp"] == "right": tx, ty = T["x"] + T["w"], T["cy"]
            else: tx, ty = T["x"], e["ey"]
            xg = tL - 12 - 7 * e.get("rank", 0)
            xs = sR + 12
            skip, src = {S["id"], T["id"]}, (S["id"], round(sy))
            pts = []
            if e["back"] and self.vertical_back(e):
                up = T["cy"] < S["cy"]; x = min(S["cx"], T["cx"]) + 16
                sx, sy = x, S["y"] if up else S["y"] + S["h"]
                tx, ty = x, T["y"] + T["h"] if up else T["y"]
                e["sp"], e["dp"] = ("top", "bottom") if up else ("bottom", "top")
                pts, best = [], 0
            elif e["back"]:
                lane, side = e["corr"]; k = e["track"]
                yc = (self.lane_bot[lane] + 16 + TRACK * k) if side == "bottom" else (self.lane_top[lane] - 16 - TRACK * k)
                x1 = sR + 10 + 6 * k
                head = [(S["cx"], yc)] if e["sp"] in ("bottom", "top") else [(x1, sy), (x1, yc)]
                if e["dp"] in ("bottom", "top"): pts = head + [(tx, yc)]
                else: pts = head + [(xg, yc), (xg, ty)]
                best = 0
            elif e["dp"] == "left" and T["x"] < sx + 6 and e["sp"] == "right":   # stacked on one boundary
                below_ = T["cy"] > S["cy"]
                clamp = lambda v, n_: min(max(v, n_["x"] + 12), n_["x"] + n_["w"] - 12)
                sx, sy = clamp(T["cx"], S), S["y"] + S["h"] if below_ else S["y"]
                tx, ty = clamp(S["cx"], T), T["y"] if below_ else T["y"] + T["h"]
                e["dp"] = "top" if below_ else "bottom"; e["sp"] = "bottom" if below_ else "top"
                pts, best = ([] if abs(sx - tx) < 1 else [(sx, (sy + ty) / 2), (tx, (sy + ty) / 2)]), 0
            else:
                lo_x, hi_x = sx + 4, tx - 4
                xl = [x for x in [xg, xg - 7, xg - 14, xs, xs + 7, xs + 14] + [g + d for g in gaps for d in (0, -7, 7)]
                      if lo_x < x < hi_x] or [(sx + tx) / 2]
                xl = list(dict.fromkeys(round(x) for x in xl))
                chans = sorted(self.chan, key=lambda c: abs(c - sy) + abs(c - ty))[:6]
                if e["dp"] == "left":
                    if abs(sy - ty) < 3 and T["y"] + 2 < sy < T["y"] + T["h"] - 2: ty = sy      # snap straight
                    if e["sp"] in ("bottom", "top"):
                        cands = [[(sx, ty)]]
                    else:
                        cands = ([[]] if abs(sy - ty) < 0.5 else []) + [[(x, sy), (x, ty)] for x in xl]
                        cands += [[(x1_, sy), (x1_, yc + d), (x2_, yc + d), (x2_, ty)]
                                  for yc in chans for d in (0, -7, 7) for x1_ in xl[:4] for x2_ in xl[:4] if x1_ < x2_]
                else:                                         # into a bottom / top port (MUX select, enable)
                    sgn = 1 if e["dp"] == "bottom" else -1
                    ybs = [ty + sgn * (16 + 6 * e.get("rank", 0) + 7 * j) for j in range(3)]
                    cands = []
                    if (sgn > 0 and sy > ty + 6 or sgn < 0 and sy < ty - 6) and sx < tx - 6: cands.append([(tx, sy)])
                    cands += [[(x, sy), (x, yb), (tx, yb)] for x in xl for yb in ybs]
                scored = [(self.cost([(sx, sy)] + c + [(tx, ty)], skip, src), i, c) for i, c in enumerate(cands)]
                best, _, pts = min(scored)
            if best >= 1000: self.warn.append(f"edge {e['s']} -> {e['d']}: no clear orthogonal route, crosses a block")
            poly = [(sx, sy)] + pts + [(tx, ty)]
            self.segs += [(a_, b_, src) for a_, b_ in zip(poly, poly[1:])]
            e["pts"], e["sxy"], e["txy"] = pts, (sx, sy), (tx, ty)
            lens = [abs(a_[0] - b_[0]) + abs(a_[1] - b_[1]) for a_, b_ in zip(poly, poly[1:])]
            tot = sum(lens) or 1
            hz = [(l_, i) for i, (l_, (a_, b_)) in enumerate(zip(lens, zip(poly, poly[1:]))) if abs(a_[1] - b_[1]) < 0.5]
            if hz:                                            # label on the longest horizontal stretch
                l_, i = max(hz); e["lx"] = 2 * (sum(lens[:i]) + l_ / 2) / tot - 1
            if T["type"] in CIRCLE and e["dp"] == "left":     # land exactly on the circle outline
                r = T["w"] / 2; dy = max(-r, min(r, ty - T["cy"]))
                e["txy"] = (T["cx"] - (r * r - dy * dy) ** 0.5, ty)

    # ------------------------------------------------------------------ rendering
    def node_style(self, n):
        t, hl, bold, acc = n["type"], n.get("hl"), n.get("bold"), self.acc
        d = {"html": 1, "whiteSpace": "wrap", "fontFamily": "Helvetica", "fontSize": 11, "fontColor": INK,
             "strokeColor": INK, "fillColor": FILL, "strokeWidth": 1.3}
        shp, outside = "", t in OUTSIDE_LABEL or (t == "reg" and n["bnd"] is not None)
        if t == "block": shp = "rounded=1;arcSize=10;"
        elif t == "reg" and n["bnd"] is not None:
            shp = PIPE_BAR + "verticalLabelPosition=top;verticalAlign=bottom;"; d.update(fillColor=STORE, fontSize=10)
        elif t == "reg": shp = REG_SHAPE; d.update(fillColor=STORE)
        elif t == "fifo": shp = FIFO_SHAPE + "align=left;spacingLeft=6;"; d.update(fillColor=STORE)
        elif t == "mux": shp = MUX_SHAPE + "verticalLabelPosition=top;verticalAlign=bottom;"; d.update(fontSize=10)
        elif t in CIRCLE: shp = "ellipse;"; d.update(fontSize=19, fontStyle=1, verticalAlign="middle", spacingBottom=3)
        elif t == "alu": shp = ALU_SHAPE + "spacingLeft=12;"; d.update(fontSize=11, fontStyle=1)
        elif t in GATES:
            op, neg = GATES[t]
            shp = (f"shape=mxgraph.electrical.logic_gates.logic_gate;operation={op};negating={neg};"
                   "verticalLabelPosition=bottom;verticalAlign=top;")
            d.update(fontSize=10)
        elif t == "not": shp = "shape=mxgraph.electrical.logic_gates.inverter_2;verticalLabelPosition=bottom;verticalAlign=top;"; d.update(fontSize=10)
        elif t == "cloud": shp = "ellipse;shape=cloud;"; d.update(fillColor=LOGIC, fontSize=10)
        elif t == "mem": d.update(fillColor=STORE)
        elif t == "xbar": shp = XBAR + "verticalLabelPosition=bottom;verticalAlign=top;"; d.update(fontSize=10)
        elif t in ("in", "out", "text"):
            shp = "text;"; d.update(strokeColor="none", fillColor="none", align={"in": "right", "out": "left"}.get(t, "center"))
        elif t == "dot": shp = "ellipse;"; d.update(fillColor=INK, strokeColor=INK)
        elif t in ("table", "array"):
            shp = "container=1;collapsible=0;recursiveResize=0;verticalLabelPosition=top;verticalAlign=bottom;"
            d.update(fillColor="none", fontStyle=1, strokeWidth=1.5)
            if n["stk"]: d["spacingBottom"] = n["stk"] + 2
        if outside: d["whiteSpace"] = "nowrap"
        if hl:
            if t in ("in", "out", "text"): d.update(fontColor=acc, fontStyle=1)
            elif t in ("table", "array"): d.update(strokeColor=acc, fontColor=acc, strokeWidth=2.4)
            elif t == "xbar": d.update(fillColor=TINT, strokeColor=acc, fontColor=acc, fontStyle=1, strokeWidth=2.6)  # keep the X visible
            else:
                d.update(fillColor=acc, strokeColor=acc, fontStyle=1, strokeWidth=1.6)
                d["fontColor"] = acc if outside else "#ffffff"
        if bold: d.update(strokeWidth=2.6, fontStyle=1)
        return shp + sty(d) + (n.get("style") or "")

    def node_cells(self, n):
        out, t, nid, acc = [], n["type"], n["id"], self.acc
        st = self.node_style(n)
        val = "" if t == "dot" else lab(CIRCLE.get(t) if t in CIRCLE else n.get("label"))
        if t in CIRCLE: val = lab(n.get("sym", CIRCLE[t]))
        parent, x, y = "1", n["x"], n["y"]
        if n["stk"]:                                          # stacked copies (×N) behind, grouped with the node
            g, o = f"{nid}__stk", STK
            out.append(vcell(g, "", "group;", x, y - 2 * o, n["w"] + 2 * o, n["h"] + 2 * o, extra=' connectable="0"'))
            cst = re.sub(r"fontColor=[^;]*;", "", st)
            if t in ("table", "array"): cst = cst.replace("fillColor=none", f"fillColor={FILL}")
            out.append(vcell(f"{nid}__c2", "", cst, 2 * o, 0, n["w"], n["h"], parent=g))
            out.append(vcell(f"{nid}__c1", "", cst, o, o, n["w"], n["h"], parent=g))
            parent, x, y = g, 0, 2 * o
        out.append(vcell(nid, val, st, x, y, n["w"], n["h"], parent=parent))
        w, h = n["w"], n["h"]
        if t == "table":
            rows, xx = n["_rows"], 0
            for j, (nm, fw, fh) in enumerate(n["_fields"]):
                for r in range(rows):
                    if rows >= 3 and r == rows - 1: continue
                    if r == 0:
                        hot = n.get("hl") or fh
                        cs = {"fillColor": acc if hot else HEAD, "fontColor": "#ffffff" if hot else INK, "fontStyle": 1}
                        v = lab(nm)
                    else:
                        cs = {"fillColor": TINT if fh else FILL, "fontColor": INK}; v = ""
                    out.append(vcell(f"{nid}__f{j}_{r}", v, sty({"html": 1, "whiteSpace": "wrap", "fontFamily": "Helvetica",
                                     "fontSize": 10, "strokeColor": INK, **cs}), xx, r * RH, fw, RH, parent=nid))
                xx += fw
            if rows >= 3:
                out.append(vcell(f"{nid}__more", "⋮", sty({"html": 1, "fontFamily": "Helvetica", "fontSize": 12,
                                 "strokeColor": INK, "fillColor": FILL, "fontColor": MUTED}), 0, (rows - 1) * RH, w, RH, parent=nid))
        elif t == "array":
            (R, C), cs, ch = n["_dims"], n["_cs"], n["_ch"]
            cl = n.get("cell_label", "PE" if cs >= 28 else "")
            cls = list(n.get("cell_labels") or [])            # per-cell labels, row-major (e.g. T0..T3)
            for r in range(R):
                for c in range(C):
                    v = cls[r * C + c] if r * C + c < len(cls) else cl
                    out.append(vcell(f"{nid}__pe{r}_{c}", lab(v), sty({"html": 1, "whiteSpace": "wrap", "fontFamily": "Helvetica", "fontSize": 9,
                                     "strokeColor": acc if n.get("hl") else INK, "fillColor": acc if n.get("hl") else STORE,
                                     "fontColor": "#ffffff" if n.get("hl") else INK}),
                                     7 + c * (cs + 5), 7 + r * (ch + 5), cs, ch, parent=nid))
        if n.get("label") and (t in CIRCLE):
            cw = tw(n["label"], 10) + 6
            out.append(vcell(f"{nid}__cap", lab(n["label"]), sty({"text": None, "html": 1, "whiteSpace": "nowrap", "align": "center",
                             "verticalAlign": "top", "fontFamily": "Helvetica", "fontSize": 10,
                             "fontColor": acc if n.get("hl") else INK, **({"fontStyle": 1} if n.get("hl") else {})}).replace("text=None;", "text;"),
                             (w - cw) / 2, h + 1, cw, 15, parent=nid))
        if n.get("stack"):
            out.append(vcell(f"{nid}__xn", f"×{n['stack']}", sty({"text": None, "html": 1, "align": "left", "fontFamily": "Helvetica",
                             "fontSize": 10, "fontStyle": 1, "fontColor": MUTED}).replace("text=None;", "text;"),
                             w + 2 * STK - 22, -2 * STK - 15, 26, 14, parent=nid))
        if n.get("num") is not None:
            out.append(vcell(f"{nid}__num", str(n["num"]), sty({"ellipse": None, "html": 1, "fillColor": INK, "strokeColor": "#ffffff",
                             "fontColor": "#ffffff", "fontStyle": 1, "fontSize": 10, "fontFamily": "Helvetica"}).replace("ellipse=None;", "ellipse;"),
                             -9, -9, 18, 18, parent=nid))
        return out

    def edge_cell(self, e):
        N, acc = self.N, self.acc
        S, T = N[e["s"]], N[e["d"]]
        col, sw = INK, 1.3
        dash = ""
        if e["kind"] == "bus": sw = 2.6
        if e["kind"] == "ctrl": col, sw, dash = "#555555", 1.1, "dashed=1;dashPattern=5 3;"
        if e["back"]: col = FBC
        if e["hl"]: col, sw = acc, sw + 1.4
        arrow = "none" if T["type"] == "dot" else "block"
        (sx, sy), (tx, ty) = e["sxy"], e["txy"]
        fx = lambda n, x: (x - n["x"]) / n["w"]; fy = lambda n, y: (y - n["y"]) / n["h"]
        s = (f"html=1;rounded=0;edgeStyle=none;endArrow={arrow};endFill=1;endSize={7 if e['kind'] == 'bus' else 5};"
             + (f"startArrow=block;startFill=1;startSize={7 if e['kind'] == 'bus' else 5};" if e.get("both") else "") +
             f"strokeColor={col};strokeWidth={sw};{dash}fontSize=10;fontColor={col if col != '#555555' else INK};{FONT}"
             f"labelBackgroundColor=#ffffff;verticalAlign=bottom;"
             f"exitX={fx(S, sx):.3f};exitY={fy(S, sy):.3f};exitDx=0;exitDy=0;exitPerimeter=0;"
             f"entryX={fx(T, tx):.3f};entryY={fy(T, ty):.3f};entryDx=0;entryDy=0;entryPerimeter=0;")
        eid = f"e{e['i']}"
        poly_ = [e["sxy"]] + list(e["pts"]) + [e["txy"]]
        vert = all(abs(a_[0] - b_[0]) < 0.5 for a_, b_ in zip(poly_, poly_[1:]))
        loff = ""
        if vert and e["label"]:
            side = 1 if e["back"] else -1
            loff = f'<mxPoint x="{side * (tw(e["label"], 10) / 2 + 8):.0f}" y="0" as="offset"/>'
        lp = {"src": -0.6, "dst": 0.6}.get(e["lpos"], round(e.get("lx", 0), 3))
        pts = "".join(f'<mxPoint x="{px:.0f}" y="{py:.0f}"/>' for px, py in e["pts"])
        out = [f'<mxCell id="{eid}" value={quoteattr(lab(e["label"]))} style={quoteattr(s)} edge="1" parent="1" '
               f'source={quoteattr(S["id"])} target={quoteattr(T["id"])}><mxGeometry x="{lp}" relative="1" as="geometry">'
               + (f'<Array as="points">{pts}</Array>' if pts else "") + loff + '</mxGeometry></mxCell>']
        poly = [e["sxy"]] + list(e["pts"]) + [e["txy"]]
        run = max((abs(a_[0] - b_[0]) for a_, b_ in zip(poly, poly[1:]) if abs(a_[1] - b_[1]) < 0.5), default=0)
        if e["w"] and (run < 150 or not e["pts"] and e["label"]) and e["label"]:   # short: width goes into the label
            out[0] = out[0].replace(f'value={quoteattr(lab(e["label"]))}', f'value={quoteattr(lab(e["label"]) + " /" + str(e["w"]))}', 1)
        elif e["w"]:                                          # bus width: tick + number near the source
            for k, (v, fs, ox, oy) in enumerate((("/", 14, 0, 0), (str(e["w"]), 9, 9, -8))):
                out.append(f'<mxCell id="{eid}w{k}" value={quoteattr(v)} style={quoteattr(f"edgeLabel;html=1;align=center;verticalAlign=middle;fontSize={fs};fontColor={col};labelBackgroundColor=none;{FONT}")} '
                           f'vertex="1" connectable="0" parent="{eid}"><mxGeometry x="-0.8" relative="1" as="geometry">'
                           f'<mxPoint x="{ox}" y="{oy}" as="offset"/></mxGeometry></mxCell>')
        return out

    def extent(self):
        xs, ys = [], []
        for _, x0, y0, x1, y1 in self.obst: xs += [x0, x1]; ys += [y0, y1]
        for e in self.E:
            for px, py in e["pts"]: xs.append(px); ys.append(py)
        return min(xs), min(ys), max(xs), max(ys)

    def regions(self):
        out = []
        for i, g in enumerate(self.spec.get("groups") or []):
            mem = [self.N[m] for m in g.get("members", []) if m in self.N]
            if not mem: continue
            bb = [o for o in self.obst if o[0] in {m["id"] for m in mem}]
            x0 = min(o[1] for o in bb) - 14; y0 = min(o[2] for o in bb) - 24
            x1 = max(o[3] for o in bb) + 14; y1 = max(o[4] for o in bb) + 12
            inside = [o[0] for o in self.obst if o[0] not in {m["id"] for m in mem}
                      and o[1] > x0 and o[3] < x1 and o[2] > y0 and o[4] < y1]
            if inside: self.warn.append(f"group {g.get('label')!r} also encloses {inside}")
            hl = g.get("hl")
            d = {"rounded": 1, "arcSize": 4, "html": 1, "whiteSpace": "wrap", "fontFamily": "Helvetica", "fontSize": 11,
                 "fontStyle": 1, "align": g.get("label_align", "left"), "verticalAlign": "top", "spacingLeft": 6,
                 "spacingRight": 8, "spacingTop": 1,
                 "fillColor": TINT if hl else "none", "strokeColor": self.acc if hl else "#8c8c8c",
                 "fontColor": self.acc if hl else MUTED, "dashed": 0 if g.get("style") == "solid" else 1}
            k = min(int(g.get("stack") or 1), 3)
            if k > 1:                                         # replicated region (e.g. Core ×2): stacked cards behind
                d["fillColor"] = TINT if hl else FILL
                for j in range(k - 1, 0, -1):
                    out.append(vcell(f"grp{i}c{j}", "", sty(dict(d, dashed=0)), x0 + 8 * j, y0 - 8 * j, x1 - x0, y1 - y0))
                out.append(vcell(f"grp{i}xn", f"×{g['stack']}", f"text;html=1;align=left;fontSize=11;fontStyle=1;{FONT}fontColor={MUTED};",
                                 x1 + 8 * (k - 1) + 4, y0 - 8 * (k - 1) - 4, 30, 16))
                d["dashed"] = 0
            out.append(vcell(f"grp{i}", lab(g.get("label", "")), sty(d), x0, y0, x1 - x0, y1 - y0))
        return out

    def render(self):
        self.infer(); self.columns(); self.sizes(); self.xgeom(); self.tracks(); self.rows(); self.ygeom()
        self.ports(); self.route()
        N = self.N
        body = []
        body += self.regions()
        X0, Y0, X1, Y1 = self.extent()
        for g in re.findall(r'x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)"', "".join(body)):
            X0, Y0 = min(X0, float(g[0])), min(Y0, float(g[1])); X1, Y1 = max(X1, float(g[0]) + float(g[2])), max(Y1, float(g[1]) + float(g[3]))
        deco = []
        top = Y0 - (48 if not self.implicit else 12)
        bot = Y1 + 12
        if not self.implicit:
            for s, st in enumerate(self.stages):
                l_, r_ = self.span[s]
                v = f"<b>{lab(st['name'])}</b>" + (f"<br><font style=\"font-size:10px\" color=\"{MUTED}\">{lab(st['sub'])}</font>" if st["sub"] else "")
                deco.append(vcell(f"sh{s}", v, f"text;html=1;align=center;verticalAlign=middle;fontSize=13;{FONT}fontColor={INK};",
                                  (l_ + r_) / 2 - (r_ - l_) / 2 + 4, top, r_ - l_ - 8, 36))
            for s, xb in self.xb.items():
                deco.append(vcell(f"sb{s}", "", "line;direction=south;dashed=1;dashPattern=6 4;strokeColor=#8c8c8c;strokeWidth=1.2;html=1;",
                                  xb - 5, top + 2, 10, bot - top - 2))
        lx = X0 - 16
        if self.show_lanes:
            lw = max(tw(l["name"], 12) for l in self.lanes) + 12
            for l, ln in enumerate(self.lanes):
                deco.append(vcell(f"ln{l}", f"<b>{lab(ln['name'])}</b>", f"text;html=1;align=right;verticalAlign=middle;fontSize=12;{FONT}fontColor={MUTED};",
                                  lx - lw, (self.lane_top[l] + self.lane_bot[l]) / 2 - 12, lw, 24))
                if l:
                    ys = (self.lane_top[l] + self.lane_bot[l - 1] + 16 + TRACK * self.ntrk[(l - 1, 'bottom')]) / 2 - (8 if self.ntrk[(l, "top")] else 0)
                    deco.append(vcell(f"lsep{l}", "", "line;strokeColor=#cccccc;strokeWidth=1;html=1;", lx - lw, ys - 5, X1 + 20 - (lx - lw), 10))
            X0 = lx - lw
        title = self.spec.get("title")
        if title:
            deco.insert(0, vcell("title", f"<b>{lab(title)}</b>", f"text;html=1;align=left;verticalAlign=middle;fontSize=15;{FONT}fontColor={INK};",
                                 X0, top - 38, max(300, tw(title, 15) + 20), 28))
        nodes = []
        for n in sorted(N.values(), key=lambda n: n["_i"]): nodes += self.node_cells(n)
        edges = []
        for e in self.E: edges += self.edge_cell(e)
        tail = self.legend(X0, bot + 18)
        cells = deco + body + nodes + edges + tail
        return self.shift('<mxfile host="arch2drawio"><diagram id="arch" name="Page-1"><mxGraphModel dx="1400" dy="900" grid="0" gridSize="10" '
                'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" math="0" shadow="0"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + '</root></mxGraphModel></diagram></mxfile>')

    @staticmethod
    def shift(xml, margin=20):
        """Move the figure into the positive quadrant (top-level cells only; children stay relative)."""
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml); cells = root.find(".//root")
        pts, xs, ys = [], [], []
        for c in cells.findall("mxCell"):
            if c.get("parent") != "1": continue
            g = c.find("mxGeometry")
            if g is None: continue
            if c.get("vertex") == "1" and g.get("x") is not None:
                pts.append((g, "x", "y")); xs.append(float(g.get("x"))); ys.append(float(g.get("y")))
            for pt in g.iter("mxPoint"):
                if pt.get("x") is not None and pt.get("as") != "offset":
                    pts.append((pt, "x", "y")); xs.append(float(pt.get("x"))); ys.append(float(pt.get("y", 0)))
        if not xs: return xml
        dx, dy = margin - min(xs), margin - min(ys)
        for el, kx, ky in pts:
            el.set(kx, f"{float(el.get(kx)) + dx:.0f}"); el.set(ky, f"{float(el.get(ky, 0)) + dy:.0f}")
        return ET.tostring(root, encoding="unicode")

    def legend(self, x, y):
        out, spec = [], self.spec
        items = spec.get("legend") or []
        if isinstance(items, dict): items = list(items.items())
        cx = x
        edge_kind = {"data": ("data", False, False), "bus": ("bus", False, False), "ctrl": ("ctrl", False, False),
                     "fb": ("data", True, False), "hl_edge": ("bus", False, True)}
        for i, (k, txt) in enumerate(items):
            if k in edge_kind:
                kind, back, hl = edge_kind[k]
                e = dict(i=f"lg{i}", kind=kind, back=back, hl=hl, w=None, label=None, lpos="mid", pts=[])
                col = FBC if back else (self.acc if hl else ("#555555" if kind == "ctrl" else INK))
                sw = (2.6 if kind == "bus" else 1.1 if kind == "ctrl" else 1.3) + (1.4 if hl else 0)
                dash = "dashed=1;dashPattern=5 3;" if kind == "ctrl" else ""
                out.append(f'<mxCell id="lge{i}" value="" style="html=1;rounded=0;endArrow=block;endFill=1;endSize=5;strokeColor={col};'
                           f'strokeWidth={sw};{dash}" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                           f'<mxPoint x="{cx:.0f}" y="{y + 9:.0f}" as="sourcePoint"/><mxPoint x="{cx + 34:.0f}" y="{y + 9:.0f}" as="targetPoint"/>'
                           '</mxGeometry></mxCell>')
            elif k == "hl":
                out.append(vcell(f"lgs{i}", "", f"rounded=1;arcSize=10;html=1;fillColor={self.acc};strokeColor={self.acc};", cx + 6, y + 2, 24, 14))
            elif k == "hl_region":
                out.append(vcell(f"lgs{i}", "", f"rounded=1;arcSize=10;html=1;dashed=1;fillColor={TINT};strokeColor={self.acc};", cx + 6, y + 2, 24, 14))
            elif k == "reg":
                out.append(vcell(f"lgs{i}", "", PIPE_BAR + f"html=1;fillColor={STORE};strokeColor={INK};", cx + 13, y - 3, 9, 24))
            else:
                self.warn.append(f"legend key {k!r} unknown (use data/bus/ctrl/fb/hl/hl_edge/hl_region/reg)"); continue
            out.append(vcell(f"lgt{i}", lab(txt), f"text;html=1;align=left;verticalAlign=middle;fontSize=11;{FONT}fontColor={INK};",
                             cx + 40, y, tw(txt, 11) + 10, 18))
            cx += 40 + tw(txt, 11) + 28
        yy = y + (30 if out else 0)
        call = spec.get("callouts") or {}
        if isinstance(call, list): call = {i + 1: c for i, c in enumerate(call)}
        for j, (k, txt) in enumerate(sorted(call.items(), key=lambda t: str(t[0]))):
            out.append(vcell(f"co{j}", str(k), f"ellipse;html=1;fillColor={INK};strokeColor=none;fontColor=#ffffff;fontStyle=1;fontSize=10;{FONT}",
                             x, yy, 18, 18))
            out.append(vcell(f"cot{j}", lab(txt), f"text;html=1;align=left;verticalAlign=middle;fontSize=11;{FONT}fontColor={INK};",
                             x + 26, yy - 1, tw(txt, 11) + 12, 20))
            yy += 24
        return out

    def summary(self):
        nb = sum(1 for e in self.E if e["back"])
        return (f"{len(self.N)} nodes, {len(self.E)} edges ({nb} feedback), "
                f"{0 if self.implicit else len(self.stages)} stage(s), {len(self.lanes)} lane(s)")


# ====================================================================== source outline
# Architecture figures are drawn at the level a designer thinks in (modules, arrays and their entry
# fields, pipeline stages, key datapath units, feedback), not at netlist level. `outline` pulls that
# skeleton straight from the source text — no synthesis — so the agent can read it next to the code,
# decide what is core, and write the figure spec that `render` draws.
FEEDBACK_RE = re.compile(r"replay|kill|flush|redirect|stall|bypass|forward|fwd|wakeup|retry|hazard|mispred|refill|"
                         r"rollback|squash|cancel|recover|writeback|wb_", re.I)
STAGE_TAG = re.compile(r"(?:^|_)(?:s|st|stage|p)(\d+)(?:_|$)", re.I)
CLASSIC_TAG = re.compile(r"(?:^|_)(if_id|id_ex|ex_mem|mem_wb)(?:_|$)", re.I)
TYPEDEF_RE = re.compile(r"typedef\s+struct\s+packed\s*\{(.*?)\}\s*(\w+)\s*;", re.S)
FIELD_RE = re.compile(r"(?:logic|reg|bit|wire|\w+_t)?\s*(?:signed\s*)?((?:\[[^\]]*\]\s*)*)\s*(\w+)\s*;")
DECL_RE = re.compile(r"\b(reg|logic|wire|bit|\w+_t)\s+(?:signed\s+|unsigned\s+)?((?:\[[^\]]*\]\s*)*)"
                     r"([A-Za-z_]\w*)\s*((?:\[[^\]]*\]\s*)*)\s*(?=[;,=])")
PORT_RE = re.compile(r"^\s*(input|output|inout)?\s*(?:wire|reg|logic|var)?\s*(?:signed\s+|unsigned\s+)?"
                     r"((?:\[[^\]]*\]\s*)*)\s*([A-Za-z_]\w*)\s*((?:\[[^\]]*\]\s*)*)\s*$", re.S)
CLKRST = re.compile(r"^(clk|clock|\w*_clk|clk_\w*|rst|reset|rst_?n|reset_?n|\w*_rst|\w*_rst_?n|\w*_reset)$", re.I)
KEYWORDS = {"module", "begin", "end", "if", "else", "for", "case", "assign", "always", "always_ff", "always_comb",
            "generate", "endgenerate", "input", "output", "inout", "wire", "reg", "logic", "localparam", "parameter",
            "genvar", "integer", "function", "task", "return", "typedef", "initial"}


def _balanced(t, i):
    """t[i] == '(' -> (inside text, index after ')')."""
    d, j = 0, i
    while j < len(t):
        if t[j] == "(": d += 1
        elif t[j] == ")":
            d -= 1
            if d == 0: return t[i + 1:j], j + 1
        j += 1
    return t[i + 1:], len(t)


def _split_top(t, sep=","):
    out, d, cur = [], 0, []
    for ch in t:
        if ch in "([{": d += 1
        elif ch in ")]}": d -= 1
        if ch == sep and d == 0: out.append("".join(cur)); cur = []
        else: cur.append(ch)
    if "".join(cur).strip(): out.append("".join(cur))
    return out


def _eval(expr, params):
    e = expr.strip()
    if not e: return None
    e = re.sub(r"\$clog2\s*\(", "_clog2(", e)
    e = re.sub(r"(\d+)?'[sS]?[dD](\d+)", r"\2", e)
    e = re.sub(r"(\d+)?'[sS]?[hH]([0-9a-fA-F_]+)", lambda m: str(int(m.group(2).replace("_", ""), 16)), e)
    e = re.sub(r"(\d+)?'[sS]?[bB]([01_]+)", lambda m: str(int(m.group(2).replace("_", ""), 2)), e)
    for k in sorted(params, key=len, reverse=True):
        v = params[k]
        if v is not None: e = re.sub(rf"\b{re.escape(k)}\b", f"({v})", e)
    if re.search(r"[A-Za-z_](?<!_clog2)", e.replace("_clog2", "")): return None
    try:
        return int(eval(e, {"__builtins__": {}, "_clog2": lambda x: max(0, (int(x) - 1).bit_length())}, {}))
    except Exception:
        return None


def _width(dims, params):
    """'[31:0][3:0]' -> 128 (None if not evaluable)."""
    tot = 1
    for d in re.findall(r"\[([^\]]*)\]", dims or ""):
        if ":" in d:
            a_, b_ = d.split(":", 1); x, y = _eval(a_, params), _eval(b_, params)
            if x is None or y is None: return None
            tot *= abs(x - y) + 1
        else:
            x = _eval(d, params)
            if x is None: return None
            tot *= x
    return tot


def _loops(body, params):
    """[(start, end, trip)] for `for (...) begin ... end` regions (generate or procedural)."""
    out = []
    for m in re.finditer(r"\bfor\s*\(", body):
        hdr, j = _balanced(body, m.end() - 1)
        parts = hdr.split(";")
        trip = None
        if len(parts) >= 2:
            st = re.search(r"=\s*(.+)$", parts[0]); cond = re.search(r"(<=|<|>=|>)\s*(.+)$", parts[1])
            if st and cond:
                a_, b_ = _eval(st.group(1), params), _eval(cond.group(2), params)
                if a_ is not None and b_ is not None:
                    trip = abs(b_ - a_) + (1 if cond.group(1) in ("<=", ">=") else 0)
        bm = re.match(r"\s*begin\b", body[j:])
        if not bm: continue
        depth, k = 0, j
        for t in re.finditer(r"\b(begin|end)\b", body[j:]):
            depth += 1 if t.group(1) == "begin" else -1
            if depth == 0: k = j + t.end(); break
        out.append((m.start(), k, trip))
    return out


class Mod:
    def __init__(self, name, text, params, file):
        self.name, self.file, self.params = name, file, dict(params)
        self.ports, self.arrays, self.insts, self.seq, self.decls = [], [], [], [], {}
        m = re.match(r"\s*module\s+\w+\s*", text)
        i = m.end() if m else 0
        if text[i:i + 1] == "#":
            j = text.index("(", i); _, i = _balanced(text, j)
            while text[i:i + 1].isspace(): i += 1
        plist = ""
        if text[i:i + 1] == "(": plist, i = _balanced(text, i)
        body = text[text.find(";", i) + 1:]
        self.body = body
        pv = {k: v[0] for k, v in self.params.items()}
        for mm in re.finditer(r"\b(?:parameter|localparam)\s+(?:\w+\s+)?(?:\[[^\]]*\]\s*)?(\w+)\s*=\s*([^,;)]+)", text):
            if mm.group(1) not in pv: pv[mm.group(1)] = _eval(mm.group(2), pv)
        self.pv = pv
        dirn, dims = None, ""
        for item in _split_top(plist):
            pm = PORT_RE.match(item)
            if not pm: continue
            if pm.group(1): dirn, dims = pm.group(1), pm.group(2)
            elif pm.group(2): dims = pm.group(2)
            if dirn: self.ports.append((dirn, pm.group(3), _width(dims, pv) if dims else 1, pm.group(4).strip()))
        for dm in re.finditer(r"\b(input|output|inout)\s+(?:wire|reg|logic)?\s*(?:signed\s+)?((?:\[[^\]]*\]\s*)*)([^;]+);", body):
            for nm in _split_top(dm.group(3)):
                nm = nm.strip().split("=")[0].strip()
                if re.fullmatch(r"\w+", nm) and nm not in {p[1] for p in self.ports}:
                    self.ports.append((dm.group(1), nm, _width(dm.group(2), pv) if dm.group(2) else 1, ""))
        for dm in DECL_RE.finditer(body):
            ty, packed, nm, unpacked = dm.groups()
            self.decls[nm] = (ty, packed)
            if unpacked.strip():
                self.arrays.append(dict(name=nm, type=ty, width=_width(packed, pv) if packed else 1,
                                        depth=_width(unpacked, pv), depth_txt=unpacked.strip()))
        for p in self.ports:
            if p[3]:
                self.arrays.append(dict(name=p[1], type="port", width=p[2], depth=_width(p[3], pv), depth_txt=p[3]))

    def find_insts(self, known):
        loops = _loops(self.body, self.pv)
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(#\s*\()?", self.body):
            typ = m.group(1)
            if typ not in known or typ in KEYWORDS: continue
            j = m.end()
            if m.group(2): _, j = _balanced(self.body, j - 1)
            im = re.match(r"\s*([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*\(", self.body[j:])
            if not im: continue
            conns_txt, _ = _balanced(self.body, j + im.end() - 1)
            conns = {}
            for c in _split_top(conns_txt):
                cm = re.match(r"\s*\.(\w+)\s*\((.*)\)\s*$", c, re.S)
                if cm: conns[cm.group(1)] = cm.group(2).strip()
            mult = 1
            for a_, b_, trip in loops:
                if a_ < m.start() < b_: mult *= trip or 1
            if im.group(2): mult *= _width(im.group(2), self.pv) or 1
            self.insts.append(dict(type=typ, name=im.group(1), mult=mult, conns=conns))


def outline(files, top=None, module=None, as_json=False):
    import fsm2drawio as F
    mods = {}
    structs = {}
    for f in files:
        src = open(f, encoding="utf-8", errors="replace").read()
        clean = F.strip_comments(src)
        for body, nm in TYPEDEF_RE.findall(clean):
            structs[nm] = [(fn, fd.strip()) for fd, fn in FIELD_RE.findall(body)]
        for name, (text, toks, params, always) in F.modules(src).items():
            md = Mod(name, text, params, f); md.always = always; mods[name] = md
    if not mods: die("no module found")
    for md in mods.values():
        md.find_insts(set(mods))
        regs = []
        for blk in md.always:
            def fn(n, _):
                if n[0] == "assign" and n[2] == "<=":
                    b = F.lhs_base(n[1])
                    if b and b not in regs: regs.append(b)
            F.walk(blk, fn)
        md.seq = regs
    fsms = F.extract_fsms(F.load(files))
    used = {i["type"] for md in mods.values() for i in md.insts}
    tops = [m for m in mods if m not in used]
    root = top or (tops[0] if tops else next(iter(mods)))
    if root not in mods: die(f"module {root!r} not found; available: {', '.join(mods)}")
    focus = module or root
    if focus not in mods: die(f"module {focus!r} not found; available: {', '.join(mods)}")

    def tree(m, depth=0, seen=()):
        lines = []
        for i in mods[m].insts:
            lines.append("  " * depth + f"- {i['name']}: {i['type']}" + (f" ×{i['mult']}" if i["mult"] > 1 else ""))
            if i["type"] not in seen: lines += tree(i["type"], depth + 1, seen + (m,))
        return lines

    def dataflow(md):
        """instance-level edges through shared nets: driver -> consumer : nets."""
        drv, load = defaultdict(set), defaultdict(set)
        for d, nm, w, _ in md.ports:
            if CLKRST.match(nm): continue
            (drv if d == "input" else load)[nm].add("<in>" if d == "input" else "<out>")
        loopvars = set(re.findall(r"\bgenvar\s+(\w+)", md.body)) | \
            set(re.findall(r"\bfor\s*\(\s*(?:genvar\s+|integer\s+|int\s+)?(\w+)\s*=", md.body))
        for i in md.insts:
            sub_ = {p[1]: p[0] for p in mods[i["type"]].ports}
            for port, expr in i["conns"].items():
                for net in set(re.findall(r"\b([A-Za-z_]\w*)\b", expr)):
                    if net in md.pv or net in loopvars or CLKRST.match(net): continue
                    (drv if sub_.get(port) == "output" else load)[net].add(i["name"])
        flows = defaultdict(list)
        for net in set(drv) | set(load):
            ds = drv.get(net) or {"<本模块逻辑>"}
            for a_ in ds:
                for b_ in load.get(net, ()):
                    if a_ != b_: flows[(a_, b_)].append(net)
        return flows

    def mod_info(md):
        ins = [(n, w) for d, n, w, _ in md.ports if d == "input"]
        outs = [(n, w) for d, n, w, _ in md.ports if d != "input"]
        stages = defaultdict(list); other = []
        for r in md.seq:
            m1, m2 = STAGE_TAG.search(r), CLASSIC_TAG.search(r)
            if m1: stages[f"S{m1.group(1)}"].append(r)
            elif m2: stages[m2.group(1).upper()].append(r)
            else: other.append(r)
        arrays = []
        for a_ in md.arrays:
            st = structs.get(a_["type"])
            arrays.append(dict(a_, fields=[f"{fn}{' ' + fd if fd else ''}" for fn, fd in st] if st else None))
        by_depth = defaultdict(list)
        for a_ in arrays:
            if a_["type"] != "port": by_depth[a_["depth"] or a_["depth_txt"]].append(a_["name"])
        fb = sorted({n for n in list(md.decls) + [p[1] for p in md.ports] if FEEDBACK_RE.search(n)})
        return dict(module=md.name, file=os.path.relpath(md.file), params={k: v for k, v in md.pv.items() if v is not None},
                    inputs=ins, outputs=outs, arrays=arrays, same_depth=[v for v in by_depth.values() if len(v) > 1],
                    stage_regs=dict(stages), other_regs=other, feedback_like=fb,
                    fsms=[dict(var=f.var, states=list(f.states), replicated=f.replicated) for f in fsms if f.module == md.name],
                    instances=[dict(name=i["name"], type=i["type"], mult=i["mult"]) for i in md.insts],
                    dataflow=[dict(src=a_, dst=b_, nets=sorted(ns)) for (a_, b_), ns in sorted(dataflow(md).items())])

    info = mod_info(mods[focus])
    if as_json:
        print(json.dumps(dict(root=root, hierarchy=tree(root), focus=info), ensure_ascii=False, indent=1)); return
    W = lambda xs: ", ".join(f"{n}[{w}]" if w and w > 1 else n for n, w in xs) or "-"
    print(f"# 层次（top = {root}）\n{root}")
    for ln in tree(root): print("  " + ln)
    i = info
    print(f"\n# 模块 {i['module']}  ({i['file']})")
    if i["params"]: print("参数: " + ", ".join(f"{k}={v}" for k, v in i["params"].items()))
    print(f"输入: {W(i['inputs'])}\n输出: {W(i['outputs'])}")
    if i["arrays"]:
        print("存储阵列（深度 × 位宽）:")
        for a_ in i["arrays"]:
            f_ = f"  字段: {', '.join(a_['fields'])}" if a_["fields"] else ""
            print(f"  {a_['name']:24s} {a_['depth'] or a_['depth_txt']} × {a_['width'] or '?'}b  ({a_['type']}){f_}")
        for g in i["same_depth"]: print(f"  同深度、可能同一张表: {', '.join(g)}")
    if i["stage_regs"]:
        print("按级号命名的时序寄存器:")
        for k in sorted(i["stage_regs"]): print(f"  {k}: {', '.join(i['stage_regs'][k])}")
    if i["other_regs"]: print(f"其它时序寄存器: {', '.join(i['other_regs'])}")
    for f in i["fsms"]:
        print(f"状态机: {f['var']}{'[' + f['replicated'] + ']' if f['replicated'] else ''}  {' → '.join(f['states'])}")
    if i["feedback_like"]: print(f"疑似反馈/重放/前递信号: {', '.join(i['feedback_like'])}")
    if i["instances"]:
        print("子模块实例: " + ", ".join(f"{x['name']}:{x['type']}" + (f"×{x['mult']}" if x["mult"] > 1 else "") for x in i["instances"]))
    if i["dataflow"]:
        print("实例间数据流（经共享信号）:")
        for d in i["dataflow"]:
            ns = d["nets"]
            print(f"  {d['src']} → {d['dst']}: {', '.join(ns[:4])}{f' …(+{len(ns) - 4})' if len(ns) > 4 else ''}")


def main():
    ap = argparse.ArgumentParser(description="Architecture figure in paper style: outline RTL, render a figure spec to draw.io")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("outline", help="print the architectural skeleton of a Verilog/SV design (no synthesis)")
    o.add_argument("files", nargs="+"); o.add_argument("--top"); o.add_argument("--module")
    o.add_argument("--json", action="store_true")
    r = sub.add_parser("render", help="draw a figure spec (YAML/JSON) as .drawio (+ PNG)")
    r.add_argument("spec"); r.add_argument("-o", "--output")
    r.add_argument("--png", action="store_true", help="also export PNG next to the .drawio")
    r.add_argument("--svg", action="store_true", help="also export SVG next to the .drawio")
    r.add_argument("--scale", type=int, help="PNG scale (default $DRAWIO_SCALE or 3)")
    a = ap.parse_args()
    if a.cmd == "outline":
        files = [os.path.abspath(f) for f in a.files]
        for f in files:
            if not os.path.isfile(f): die(f"no such file: {f}")
        outline(files, a.top, a.module, a.json); return
    fig = Fig(load_spec(a.spec) or {})
    xml = fig.render()
    out = a.output or os.path.splitext(a.spec)[0] + ".drawio"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: f.write(xml)
    for w in fig.warn: print(f"warning: {w}", file=sys.stderr)
    print(f"{out}: {fig.summary()}", file=sys.stderr)
    export_all(out, a.png, a.svg, a.scale)


if __name__ == "__main__":
    main()

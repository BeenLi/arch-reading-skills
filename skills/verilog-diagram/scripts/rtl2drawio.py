#!/usr/bin/env python3
"""Verilog / SystemVerilog module -> editable draw.io block diagram of standard units.

Pipeline
  (sv2v) -> Yosys [proc; opt; opt_dff; wreduce; memory -nomap] -> JSON netlist
  -> classify cells as standard units (register / MUX / arithmetic / comparator /
     memory / FIFO / sub-module / control logic)
  -> simplify (merge register slices, fold generate-loop instances, merge mux
     chains, collapse glue logic into control clouds, hide clk/reset nets)
  -> graph JSON -> drawio-skill's autolayout.py (Graphviz, left-to-right)
  -> .drawio (+ optional PNG)

Usage
  rtl2drawio.py FILE... [--top TOP] [--module MOD] [-o OUT.drawio] [--png] [--svg] [--scale N]
                [--sv2v auto|always|never] [--show-clock] [--no-fold]
                [--no-collapse] [--no-tune] [--direction LR|TB] [--list] [--keep-json PATH]

  --top      hierarchy top used for elaboration (default: Yosys auto-top)
  --module   which module to draw (default: the top); parameterised variants
             share one base name, the first variant is drawn
  --list     print the modules found (with unit counts) and exit
"""
import argparse, base64, collections, json, os, re, shutil, subprocess, sys, tempfile, urllib.parse, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawio_export import export_all  # noqa: E402

DRAWIO_SKILL = os.environ.get("DRAWIO_SKILL_DIR", os.path.expanduser("~/.claude/skills/drawio-skill"))
AUTOLAYOUT = os.path.join(DRAWIO_SKILL, "scripts", "autolayout.py")
YOSYS_PASSES = "proc; opt; opt_dff; wreduce; opt_clean; memory -nomap; opt_clean"


def die(msg):
    sys.exit(f"error: {msg}")


# --------------------------------------------------------------------------- shapes
def stencil(xml):
    """Inline draw.io stencil: encodeURIComponent -> raw deflate -> base64 (Graph.compress)."""
    raw = urllib.parse.quote(xml, safe="~()*!.'")
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return "shape=stencil(" + base64.b64encode(c.compress(raw.encode()) + c.flush()).decode() + ");"

REG_SHAPE = stencil('<shape name="reg" w="100" h="60" aspect="variable" strokewidth="inherit"><background>'
                    '<rect x="0" y="0" w="100" h="60"/></background><foreground><fillstroke/><path>'
                    '<move x="42" y="60"/><line x="50" y="50"/><line x="58" y="60"/></path><stroke/></foreground></shape>')
ALU_SHAPE = stencil('<shape name="alu" w="60" h="100" aspect="variable" strokewidth="inherit"><background><path>'
                    '<move x="0" y="0"/><line x="60" y="25"/><line x="60" y="75"/><line x="0" y="100"/>'
                    '<line x="0" y="62"/><line x="14" y="50"/><line x="0" y="38"/><close/></path></background>'
                    '<foreground><fillstroke/></foreground></shape>')
MUX_SHAPE = stencil('<shape name="mux" w="40" h="100" aspect="variable" strokewidth="inherit"><background><path>'
                    '<move x="0" y="0"/><line x="40" y="20"/><line x="40" y="80"/><line x="0" y="100"/><close/>'
                    '</path></background><foreground><fillstroke/></foreground></shape>')
FIFO_SHAPE = stencil('<shape name="fifo" w="120" h="50" aspect="variable" strokewidth="inherit"><background>'
                     '<rect x="0" y="0" w="120" h="50"/></background><foreground><fillstroke/>'
                     '<path><move x="72" y="0"/><line x="72" y="50"/></path><stroke/>'
                     '<path><move x="88" y="0"/><line x="88" y="50"/></path><stroke/>'
                     '<path><move x="104" y="0"/><line x="104" y="50"/></path><stroke/></foreground></shape>')
BASE = "html=1;whiteSpace=wrap;"
STYLE = {
    "reg":  REG_SHAPE + BASE + "fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;",
    "mux":  MUX_SHAPE + BASE + "fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=9;fontStyle=1;",
    "arith": ALU_SHAPE + BASE + "fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=15;fontStyle=1;spacingLeft=10;",
    "cmp":  "ellipse;" + BASE + "fillColor=#fff2cc;strokeColor=#d6b656;fontSize=13;fontStyle=1;",
    "mem":  "shape=internalStorage;dx=12;dy=12;" + BASE + "fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;",
    "fifo": FIFO_SHAPE + BASE + "fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;align=left;spacingLeft=6;",
    "inst": "rounded=1;arcSize=8;" + BASE + "fillColor=#f5f5f5;strokeColor=#666666;fontSize=11;",
    "ctrl": "ellipse;shape=cloud;" + BASE + "fillColor=#f5f5f5;strokeColor=#aaaaaa;fontColor=#666666;fontSize=10;",
    "gate": "html=1;shape=mxgraph.electrical.logic_gates.logic_gate;operation=and;fillColor=#d5e8d4;strokeWidth=1.5;",
    "in":   "rounded=1;arcSize=50;" + BASE + "fillColor=#ffffff;strokeColor=#333333;fontSize=11;",
    "out":  "rounded=1;arcSize=50;" + BASE + "fillColor=#333333;strokeColor=#333333;fontColor=#ffffff;fontSize=11;",
}
LEGEND_NAME = {"reg": "寄存器", "mux": "多路选择器 MUX", "arith": "运算单元", "cmp": "比较器",
               "mem": "存储阵列", "fifo": "FIFO / 队列", "inst": "子模块实例", "ctrl": "组合/控制逻辑（已折叠）",
               "gate": "逻辑门（与 / 或 / 非 / 异或）"}
EDGE = {  # no edgeStyle: autolayout replays Graphviz ortho bends as waypoints
    "data": "html=1;rounded=0;endArrow=block;endSize=6;strokeColor=#333333;fontSize=10;labelBackgroundColor=#ffffff;",
    "sel":  "html=1;rounded=0;endArrow=block;endSize=6;dashed=1;strokeColor=#9673a6;fontColor=#7a5a8c;fontSize=10;labelBackgroundColor=#ffffff;",
    "en":   "html=1;rounded=0;endArrow=block;endSize=6;dashed=1;dashPattern=2 3;strokeColor=#6c8ebf;fontColor=#4a6a9a;fontSize=10;labelBackgroundColor=#ffffff;",
    "clk":  "html=1;rounded=0;endArrow=block;endSize=6;dashed=1;strokeColor=#bbbbbb;fontColor=#999999;fontSize=9;",
}

# --------------------------------------------------------------------------- cell kinds
REG_T = {"$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce", "$aldff", "$aldffe",
         "$dffsr", "$dffsre", "$dlatch", "$adlatch", "$dlatchsr", "$sr", "$ff"}
MUX_T = {"$mux", "$pmux", "$bmux", "$bwmux", "$demux"}
ARITH_T = {"$add": "+", "$sub": "−", "$mul": "×", "$div": "÷", "$divfloor": "÷", "$mod": "%",
           "$modfloor": "%", "$pow": "**", "$neg": "−x", "$alu": "ALU", "$macc": "MAC", "$lcu": "LCU",
           "$shl": "<<", "$shr": ">>", "$sshl": "<<<", "$sshr": ">>>", "$shift": "≫", "$shiftx": "≫"}
CMP_T = {"$eq": "==", "$ne": "≠", "$eqx": "===", "$nex": "!==", "$lt": "<", "$le": "≤", "$gt": ">", "$ge": "≥"}
MEM_T = {"$mem", "$mem_v2", "$memrd", "$memrd_v2", "$memwr", "$memwr_v2", "$meminit", "$meminit_v2"}
MUX_DATA = {"A", "B"}
CLK_PORT = re.compile(r"^(CLK|.*_CLK)$")
RST_PORT = re.compile(r"^(ARST|SRST|CLR|SET|ALOAD|AD|.*_ARST|.*_SRST)$")
EN_PORT = re.compile(r"^(EN|CE|.*_EN|enable|.*_enable|en|.*_en)$", re.I)
CLK_NAME = re.compile(r"^(clk|clock|.*_clk|clk_.*|.*_clock)$", re.I)
RST_NAME = re.compile(r"^(rst|reset|rst_?n|reset_?n|.*_rst|.*_rst_?n|.*_reset|rst_.*|reset_.*|a?s?reset.*)$", re.I)
FIFO_NAME = re.compile(r"fifo|queue|\bq\b|buffer|buf", re.I)
# stage-tagged register names: s2_x / x_s2 / stage2_x / if_id_x / ex_mem_x ...
STAGE_TAG = re.compile(r"(?:^|_)(?:s|st|stage|p)(\d+)(?:_|$)", re.I)
CLASSIC_TAG = re.compile(r"(?:^|_)(if_id|id_ex|ex_mem|mem_wb|if|id|ex|mem|wb)(?:_|$)", re.I)


def base(name):
    """'$paramod$<hash>\\pc' / '$paramod\\scheduler\\P=..' / 'alu' -> base module name."""
    if name.startswith("$paramod"):
        for p in (x for x in name[len("$paramod"):].split("\\") if x):
            if not p.startswith("$") and "=" not in p:
                return p
    return name.lstrip("\\")


ZERO_TEST = {"$logic_not": "== 0", "$reduce_bool": "≠ 0", "$reduce_or": "≠ 0"}
GATE_OPS = {"$and": ("and", 0), "$logic_and": ("and", 0), "$reduce_and": ("and", 0),
            "$or": ("or", 0), "$logic_or": ("or", 0), "$reduce_or": ("or", 0), "$reduce_bool": ("or", 0),
            "$xor": ("xor", 0), "$reduce_xor": ("xor", 0), "$xnor": ("xor", 1), "$reduce_xnor": ("xor", 1),
            "$not": ("not", 0), "$logic_not": ("not", 0)}
GATE_BASE = "html=1;verticalLabelPosition=bottom;verticalAlign=top;fontSize=9;strokeWidth=1.5;"


def gate_op(t):
    return GATE_OPS.get(t)


def gate_style(t):
    op, neg = GATE_OPS[t]
    if op == "not":
        return GATE_BASE + "shape=mxgraph.electrical.logic_gates.inverter_2;fillColor=#ffffff;", 40, 26
    return (GATE_BASE + f"shape=mxgraph.electrical.logic_gates.logic_gate;operation={op};"
            + (f"negating=1;negSize=0.15;" if neg else "") + "fillColor=#d5e8d4;"), 52, 32


def kind_of(cell_type, cell=None):
    if cell is not None and cell_type in ZERO_TEST:
        aw = cell.get("parameters", {}).get("A_WIDTH")
        if aw and int(aw, 2) > 1: return "cmp"
    if cell_type in REG_T: return "reg"
    if cell_type in MUX_T: return "mux"
    if cell_type in ARITH_T: return "arith"
    if cell_type in CMP_T: return "cmp"
    if cell_type in MEM_T: return "mem"
    if cell_type.startswith("$") and not cell_type.startswith("$paramod"): return "glue"
    return "inst"


# --------------------------------------------------------------------------- frontend
def frontend(files, top, sv2v_mode, workdir):
    yosys = shutil.which("yosys") or die("yosys not found — brew install yosys")
    is_sv = any(f.endswith((".sv", ".svh")) for f in files)
    have_sv2v = bool(shutil.which("sv2v"))
    use_sv2v = sv2v_mode == "always" or (sv2v_mode == "auto" and is_sv and have_sv2v)
    if use_sv2v and not have_sv2v:
        die("sv2v not found — brew install sv2v")
    if use_sv2v:
        r = subprocess.run(["sv2v", *files], capture_output=True, text=True)
        if r.returncode:
            die("sv2v failed:\n" + r.stderr[-2000:])
        src = os.path.join(workdir, "design.v")
        open(src, "w").write(r.stdout)
        read = f'read_verilog "{src}"'
    else:
        read = "\n".join(f'read_verilog {"-sv " if is_sv else ""}"{f}"' for f in files)
    out = os.path.join(workdir, "netlist.json")
    ys = os.path.join(workdir, "run.ys")
    hier = f"hierarchy -check -top {top}" if top else "hierarchy -check -auto-top"
    open(ys, "w").write(f"{read}\n{hier}\n" + YOSYS_PASSES.replace("; ", "\n") + f'\nwrite_json "{out}"\n')
    r = subprocess.run([yosys, "-q", "-s", ys], capture_output=True, text=True)
    if r.returncode:
        hint = "\nhint: SystemVerilog features such as unpacked-array ports need sv2v (--sv2v always)" \
            if is_sv and not use_sv2v else ""
        die("yosys failed:\n" + (r.stderr or r.stdout)[-3000:] + hint)
    return json.load(open(out)), use_sv2v


# --------------------------------------------------------------------------- union-find
class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[rb] = ra


# --------------------------------------------------------------------------- core
def build_graph(mods, mname, show_clock, fold, collapse):
    m = mods[mname]
    cells, ports = m.get("cells", {}), m.get("ports", {})

    # readable name per bit: ports first, then the shortest visible net name
    bitname = {}
    nets = sorted(m.get("netnames", {}).items(),
                  key=lambda kv: (kv[0] not in ports, kv[1].get("hide_name", 0), len(kv[0])))
    for n, info in nets:
        if info.get("hide_name"): continue
        for i, b in enumerate(info["bits"]):
            if isinstance(b, int) and b not in bitname:
                bitname[b] = (re.sub(r"\[\d+\]", "", n.lstrip("\\")).split(".")[-1], i, len(info["bits"]))

    aliases = collections.defaultdict(list)
    for n, info in m.get("netnames", {}).items():
        if info.get("hide_name"): continue
        clean = re.sub(r"\[\d+\]", "", n.lstrip("\\")).split(".")[-1]
        for b in info["bits"]:
            if isinstance(b, int): aliases[b].append((clean, n in ports))

    def port_dirs(c):
        d = dict(c.get("port_directions", {}))
        if not d and c["type"] in mods:                      # fall back to the sub-module definition
            d = {p: v["direction"] for p, v in mods[c["type"]]["ports"].items()}
        return d

    drv, snk = {}, collections.defaultdict(list)             # bit -> (node, port) / [(node, port)]
    for pn, p in ports.items():
        for b in p["bits"]:
            if not isinstance(b, int): continue
            if p["direction"] in ("input", "inout"): drv[b] = ("P:" + pn, pn)
            if p["direction"] in ("output", "inout"): snk[b].append(("P:" + pn, pn))
    kind = {cn: kind_of(c["type"], c) for cn, c in cells.items()}
    for cn, c in cells.items():
        dirs = port_dirs(c)
        for port, bits in c["connections"].items():
            for b in bits:
                if not isinstance(b, int): continue
                if dirs.get(port) == "output": drv[b] = (cn, port)
                else: snk[b].append((cn, port))

    # clock / reset bits: anything on a CLK/ARST/SRST pin, plus ports named like clk/rst
    clk_bits, rst_bits = set(), set()
    for cn, c in cells.items():
        for port, bits in c["connections"].items():
            tgt = clk_bits if CLK_PORT.match(port) else rst_bits if RST_PORT.match(port) and kind[cn] in ("reg", "mem") else None
            if tgt is not None: tgt.update(b for b in bits if isinstance(b, int))
    for pn, p in ports.items():
        if CLK_NAME.match(pn): clk_bits.update(b for b in p["bits"] if isinstance(b, int))
        elif RST_NAME.match(pn): rst_bits.update(b for b in p["bits"] if isinstance(b, int))
    hidden_bits = set() if show_clock else (clk_bits | rst_bits)

    # ---- cell-level pipeline analysis (before any merging, so merges never cross a stage)
    import heapq
    csucc, cpred = collections.defaultdict(set), collections.defaultdict(set)
    for b, (dn, _) in drv.items():
        if b in clk_bits or b in rst_bits: continue
        for sn, _ in snk.get(b, []):
            if sn != dn: csucc[dn].add(sn); cpred[sn].add(dn)
    def reg_name(cn):
        cnt = collections.Counter()
        for b in cells[cn]["connections"].get("Q", []):
            for nm, is_port in aliases.get(b, []):
                tagged_ = bool(STAGE_TAG.search(nm) or CLASSIC_TAG.search(nm))
                cnt[(tagged_, not is_port, nm)] += 1
        if not cnt: return ""
        return max(cnt, key=lambda k: (k[0], k[1], cnt[k], -len(k[2])))[2]
    CLASSIC_STAGE = {"if_id": 1, "id_ex": 2, "ex_mem": 3, "mem_wb": 4}
    def tag_of(nm):
        m = STAGE_TAG.search(nm)
        if m: return int(m.group(1))
        m = CLASSIC_TAG.search(nm)
        return CLASSIC_STAGE.get(m.group(1).lower()) if m else None
    regcells = [cn for cn in cells if kind[cn] == "reg"]
    storage = set(regcells) | {cn for cn in cells if kind[cn] == "mem"}
    rtag = {r: tag_of(reg_name(r)) for r in regcells}
    tagged = {r for r in regcells if rtag[r] is not None}
    use_tags = len({rtag[r] for r in tagged}) >= 2          # the design names its stages: trust the names
    cstate = set()
    for r in regcells:
        if use_tags and r in tagged: continue               # named pipeline register, even with a kill loop
        seen, stack = set(), list(csucc[r])
        while stack:
            v = stack.pop()
            if v == r: cstate.add(r); break
            if v in seen or v in storage or v.startswith("P:"): continue
            seen.add(v); stack.extend(csucc[v])
    cpipe = set(regcells) - cstate
    fixed = {r: rtag[r] - 1 for r in cpipe if use_tags and r in tagged and rtag[r] >= 1}
    combset = {cn for cn in cells if cn not in storage}
    indeg = collections.Counter()
    for u in combset:
        for v in csucc[u]:
            if v in combset: indeg[v] += 1
    order, dq = [], collections.deque(sorted(c for c in combset if indeg[c] == 0))
    while dq:
        u = dq.popleft(); order.append(u)
        for v in sorted(csucc[u]):
            if v in combset:
                indeg[v] -= 1
                if indeg[v] == 0: dq.append(v)
    order += sorted(combset - set(order))                    # (combinational loop: keep going)
    NEG = -(10 ** 9)
    cut = set()
    if use_tags:
        # A register-derived signal that can only exist in a LATER stage than the tagged register whose
        # input cone it enters is feedback (replay -> S0 mux, kill -> S1). Port inputs have no timing.
        amin = {}
        def omin(u):
            if u.startswith("P:") or (u in storage and u not in fixed): return NEG
            if u in fixed: return fixed[u] + 1
            return amin.get(u, NEG)
        for c in order:
            amin[c] = min([omin(u) for u in cpred[c]], default=NEG)
        for r, bnd in fixed.items():
            stack, seen = [r], set()
            while stack:
                v = stack.pop()
                for u in cpred[v]:
                    if omin(u) > bnd: cut.add((u, v)); continue
                    if u in combset and u not in seen: seen.add(u); stack.append(u)
    else:
        roots = (["P:" + pn for pn, p in ports.items() if p["direction"] in ("input", "inout")] + sorted(cells))
        color = {}
        for r0 in roots:
            if r0 in color: continue
            color[r0] = 1; stack = [(r0, iter(sorted(csucc[r0])))]
            while stack:
                v, it = stack[-1]; w = next(it, None)
                if w is None: color[v] = 2; stack.pop(); continue
                cw = color.get(w)
                if cw == 1: cut.add((v, w))
                elif cw is None: color[w] = 1; stack.append((w, iter(sorted(csucc[w]))))
    # stage = latest register-derived operand (max), feedback edges ignored; ports impose nothing
    S = {r: st_ for r, st_ in fixed.items()}
    def out_of(u):
        if u.startswith("P:") or S.get(u) is None: return None
        return S[u] + 1 if u in cpipe else S[u]
    for _ in range(8):
        before = dict(S)
        for c in order:
            vals = [x for x in (out_of(u) for u in cpred[c] if (u, c) not in cut) if x is not None]
            S[c] = max(vals) if vals else None
        for r in storage:
            if r in fixed: continue
            vals = [x for x in (out_of(u) for u in cpred[r] if (u, r) not in cut) if x is not None]
            S[r] = min(max(vals), 64) if vals else None
        if S == before: break
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    memo, onstk = {}, set()
    def U(c):                                                # ALAP: the earliest consumer decides
        if c in memo: return memo[c]
        if c in onstk: return None
        onstk.add(c); best = None
        for v in csucc[c]:
            if v.startswith("P:") or (c, v) in cut: continue
            cand = S.get(v)
            if cand is None:
                cand = U(v)
                if cand is not None and v in cpipe: cand = max(0, cand - 1)
            if cand is not None: best = cand if best is None else min(best, cand)
        onstk.discard(c); memo[c] = best
        return best
    cst = {}
    for cn in cells:
        st_ = S.get(cn)
        if st_ is None:
            u = U(cn)
            if u is not None and cn in cpipe: u = max(0, u - 1)
            st_ = u if u is not None else 0
        cst[cn] = st_
    same_stage = lambda a, b: cst.get(a, 0) == cst.get(b, 0)

    uf = UF()
    for cn in cells: uf.find(cn)
    folded = collections.Counter()
    # generate-loop copies of one primitive share type + source location (+ stage) -> one "×N" node
    pfold = {}
    if fold:
        by_src = collections.defaultdict(list)
        for cn, c in cells.items():
            if kind[cn] in ("arith", "mux", "cmp", "glue", "mem"):
                src_ = c.get("attributes", {}).get("src")
                if src_: by_src[(c["type"], src_, cst[cn])].append(cn)
        for grp in by_src.values():
            if len(grp) > 1:
                for cn in grp[1:]: uf.union(grp[0], cn)
                for cn in grp: pfold[cn] = len(grp)

    # 1) register slices that drive the same named signal -> one register
    by_q = collections.defaultdict(list)
    for cn, c in cells.items():
        if kind[cn] == "reg":
            nm_ = reg_name(cn)
            if nm_: by_q[nm_].append(cn)
    for group in by_q.values():
        for cn in group[1:]:
            if same_stage(group[0], cn) and ((cn in cstate) == (group[0] in cstate)): uf.union(group[0], cn)

    # 2) generate-loop instances: threads[0].alu, threads[1].alu ... -> one "×N" box
    if fold:
        by_pat = collections.defaultdict(list)
        for cn, c in cells.items():
            if kind[cn] == "inst":
                by_pat[(base(c["type"]), re.sub(r"\[\d+\]", "[*]", cn))].append(cn)
        for group in by_pat.values():
            if len(group) > 1:
                for cn in group[1:]: uf.union(group[0], cn)
                folded[uf.find(group[0])] = len(group)

    # 3) mux chains (nested if/else, case) -> one MUX
    for cn, c in cells.items():
        if kind[cn] != "mux": continue
        sinks = {s for b in c["connections"].get("Y", []) if isinstance(b, int) for s in snk.get(b, [])}
        tgt = {s[0] for s in sinks}
        if len(tgt) == 1:
            (t,) = tgt
            if t in kind and kind[t] == "mux" and all(p in MUX_DATA for _, p in sinks) and same_stage(t, cn):
                uf.union(t, cn)

    # 4) glue logic (+ comparators that only steer selects/enables) -> control clouds
    def out_sinks(cn):
        c = cells[cn]; dirs = port_dirs(c)
        return [s for port, bits in c["connections"].items() if dirs.get(port) == "output"
                for b in bits if isinstance(b, int) for s in snk.get(b, [])]
    ctrl = {cn for cn in cells if kind[cn] == "glue"}
    changed = True
    while changed:                                            # comparators feeding only control
        changed = False
        for cn in cells:
            if kind[cn] == "cmp" and cn not in ctrl:
                ss = out_sinks(cn)
                if ss and all(t in ctrl or (t in kind and kind[t] == "mux" and p == "S")
                              or EN_PORT.match(p) or RST_PORT.match(p) for t, p in ss):
                    ctrl.add(cn); changed = True
    absorbed = {}                                             # ctrl cell -> "sel" | "en"
    gates = set()
    if collapse:
        cuf = UF()
        for cn in ctrl: cuf.find(cn)
        for cn in ctrl:
            for t, _ in out_sinks(cn):
                if t in ctrl and same_stage(cn, t): cuf.union(cn, t)
        clusters = collections.defaultdict(list)
        for cn in ctrl: clusters[cuf.find(cn)].append(cn)
        # a cluster that feeds an outside cell which feeds the cluster again (x & ~(x-1): AND -> SUB -> AND)
        # would become a fake loop: split it into the part upstream of that cell and the rest
        def split(members, depth=0):
            ms = set(members)
            sand = {x for cn in members for x in csucc[cn]
                    if x not in ms and not x.startswith("P:") and x not in storage and any(y in ms for y in csucc[x])}
            if not sand or depth > 4: return [members]
            up, stack = set(), [c for c in members if csucc[c] & sand]
            while stack:
                c = stack.pop()
                if c in up: continue
                up.add(c); stack.extend(q for q in cpred[c] if q in ms)
            down = [c for c in members if c not in up]
            if not up or not down: return [members]
            return split(sorted(up), depth + 1) + split(down, depth + 1)
        parts = {}
        for mem in clusters.values():
            for part in split(sorted(mem)): parts[part[0]] = part
        clusters = parts
        dest_of = {}
        for r, members in clusters.items():
            ms = set(members)
            dest_of[r] = {(t, p) for cn in members for t, p in out_sinks(cn) if t not in ms}
        for r, members in clusters.items():
            dests = dest_of[r]
            if not dests or len(members) > 6: continue
            tgt_groups = {uf.find(t) for t, _ in dests if not t.startswith("P:")}
            if len(tgt_groups) != 1 or any(t.startswith("P:") for t, _ in dests): continue
            (g,) = tgt_groups
            if not same_stage(members[0], g): continue
            if all(kind.get(t) == "mux" and p == "S" for t, p in dests): role = "sel"
            elif all(kind.get(t) in ("reg", "mem") and (EN_PORT.match(p) or RST_PORT.match(p)) for t, p in dests): role = "en"
            else: continue
            for cn in members:
                uf.union(g, cn); absorbed[cn] = role
        # 剩下的：3 个以内的纯门电路 -> 逐个画成门符号；更大的 -> 一朵云，去向相同的云再合并
        by_dest = collections.defaultdict(list)
        for r, members in clusters.items():
            if members[0] in absorbed: continue
            if len(members) <= 3 and all(kind[cn] == "glue" and gate_op(cells[cn]["type"]) for cn in members):
                gates.update(members); continue
            for cn in members[1:]: uf.union(members[0], cn)
            by_dest[(cst[members[0]], frozenset(uf.find(t) if not t.startswith("P:") else t for t, _ in dest_of[r]))].append(members[0])
        for rs in by_dest.values():
            for r in rs[1:]: uf.union(rs[0], r)
        ctrl -= set(absorbed) | gates
        for cn in gates: kind[cn] = "gate"
    else:
        ctrl = set()

    # ---------------------------------------------------------------- nodes
    groups = collections.defaultdict(list)
    for cn in cells: groups[uf.find(cn)].append(cn)
    rep = {cn: uf.find(cn) for cn in cells}
    nodes, gkind = {}, {}

    def node_of_bit_outside(b, members):
        d = drv.get(b)
        return d is not None and d[0] not in members
    for r, members in groups.items():
        core = [cn for cn in members if cn not in absorbed]
        k = "ctrl" if not core or all(cn in ctrl for cn in core) else kind[core[0]]
        if k == "glue": k = "ctrl"
        gkind[r] = k
    for pn, p in ports.items():
        bits = [b for b in p["bits"] if isinstance(b, int)]
        if bits and all(b in hidden_bits for b in bits): continue
        w = len(p["bits"])
        k = "in" if p["direction"] == "input" else "out"
        lab = f"{pn}" + (f" /{w}" if w > 1 else "")
        nodes["P:" + pn] = {"id": "P:" + pn, "label": lab, "style": STYLE[k],
                            "width": max(70, 7 * len(lab) + 24), "height": 28, "_k": k}

    def qname(members, port):
        cnt = collections.Counter(bitname[b][0] for cn in members for b in cells[cn]["connections"].get(port, [])
                                  if isinstance(b, int) and b in bitname)
        return cnt.most_common(1)[0][0] if cnt else ""

    for r, members in groups.items():
        members = [cn for cn in members if cn not in absorbed] or members
        k, c0 = gkind[r], cells[members[0]]
        if k == "reg":
            nm = collections.Counter(reg_name(cn) for cn in members if reg_name(cn)).most_common(1)
            nm = nm[0][0] if nm else (qname(members, "Q") or "reg")
            w = sum(len(cells[cn]["connections"].get("Q", [])) for cn in members)
            nodes[r] = {"label": f"<b>{nm}</b><br><font style='font-size:9px'>{w} bit</font>",
                        "w": max(110, 8 * len(nm) + 24), "h": 46, "name": nm, "bits": w}
        elif k == "mux":
            nodes[r] = {"label": "MUX", "w": 34, "h": 80}
        elif k == "arith":
            syms = sorted({ARITH_T[cells[cn]["type"]] for cn in members})
            nodes[r] = {"label": " ".join(syms), "w": 46, "h": 76}
        elif k == "cmp":
            nodes[r] = {"label": CMP_T.get(c0["type"]) or ZERO_TEST.get(c0["type"], "cmp"), "w": 48, "h": 48}
        elif k == "mem":
            pr = c0.get("parameters", {})
            size = int(pr.get("SIZE", "0"), 2) if pr.get("SIZE") else 0
            width = int(pr.get("WIDTH", "0"), 2) if pr.get("WIDTH") else 0
            memid = pr.get("MEMID", "mem").lstrip("\\").split(".")[-1]
            nodes[r] = {"label": f"<b>{memid}</b><br><font style='font-size:9px'>{size} × {width} bit</font>", "w": 130, "h": 64}
        elif k == "inst":
            typ = base(c0["type"])
            short = re.sub(r"\[\d+\]", "[*]", members[0]).split(".")[-1]
            n = folded.get(r, 1)
            is_fifo = bool(FIFO_NAME.search(typ) or FIFO_NAME.search(short))
            if is_fifo: k = gkind[r] = "fifo"
            badge = f" <b>×{n}</b>" if n > 1 else ""
            nodes[r] = {"label": f"<b>{short}</b>{badge}<br><font style='font-size:9px;color:#666666'>{typ}</font>",
                        "w": max(140, 7 * len(short) + 40), "h": 56 if not is_fifo else 50}
            if n > 1: nodes[r]["extra"] = "shadow=1;strokeWidth=2;"
        elif k == "gate":
            gs, gw, gh = gate_style(c0["type"])
            nodes[r] = {"label": "", "w": gw, "h": gh, "style_full": gs}
        else:  # ctrl
            ins = collections.Counter(bitname[b][0] for cn in members
                                      for port, bits in cells[cn]["connections"].items()
                                      if port_dirs(cells[cn]).get(port) != "output"
                                      for b in bits if isinstance(b, int) and b in bitname
                                      and b not in hidden_bits and node_of_bit_outside(b, members))
            src = ", ".join(n for n, _ in ins.most_common(2)) + ("…" if len(ins) > 2 else "")
            nodes[r] = {"label": f"组合逻辑<br><font style='font-size:9px'>{src or str(len(members)) + ' 个门'}</font>",
                        "w": 120, "h": 64}
        nd = nodes[r]
        pf = max((pfold.get(cn, 0) for cn in members), default=0)
        if pf > 1 and k not in ("reg", "inst", "fifo"):
            badge = f"<font style='font-size:9px;color:#b85450'><b>×{pf}</b></font>"
            nd["label"] = (nd["label"] + "<br>" + badge) if nd["label"] else badge
            nd["extra"] = nd.get("extra", "") + "shadow=1;"
            if nd.get("style_full"): nd["style_full"] += "shadow=1;"
        nodes[r] = {"id": r, "label": nd["label"], "style": nd.get("style_full") or (STYLE[k] + nd.get("extra", "")),
                    "width": nd["w"], "height": nd["h"], "_k": k,
                    "_name": nd.get("name", ""), "_bits": nd.get("bits", 0),
                    "_state": any(cn in cstate for cn in members), "_stage": min(cst[cn] for cn in members)}

    # ---------------------------------------------------------------- edges
    def node_of(x):
        return x if x.startswith("P:") else rep[x]
    agg = collections.defaultdict(lambda: {"bits": set(), "names": collections.Counter()})
    for b, (dn, _) in drv.items():
        if b in hidden_bits and not show_clock: continue
        src = node_of(dn)
        for sn, sp in snk.get(b, []):
            dst = node_of(sn)
            if src == dst or src not in nodes or dst not in nodes: continue
            if b in clk_bits or b in rst_bits: ek = "clk"
            elif sn in absorbed: ek = absorbed[sn]
            elif sn in kind and kind[sn] == "mux" and sp == "S": ek = "sel"
            elif sn in kind and EN_PORT.match(sp): ek = "en"
            else: ek = "data"
            a = agg[(src, dst, ek)]
            a["bits"].add(b)
            if b in bitname: a["names"][bitname[b][0]] += 1
    # 涉及子模块实例的连线：同一对框、同一方向合成一条（实例层面区分 data/en 意义不大，只会让标签叠在一起）
    def is_inst(nid): return nid in nodes and nodes[nid]["_k"] in ("inst", "fifo")
    merged = collections.defaultdict(lambda: {"bits": set(), "names": collections.Counter(), "kinds": set()})
    for (s, t, ek), a in agg.items():
        key = (s, t, "pair") if (is_inst(s) or is_inst(t)) else (s, t, ek)
        m_ = merged[key]; m_["bits"] |= a["bits"]; m_["names"].update(a["names"]); m_["kinds"].add(ek)
    agg = {}
    for (s, t, ek), a in merged.items():
        if ek == "pair":
            ks = a["kinds"]
            ek = "data" if "data" in ks or len(ks) > 1 else next(iter(ks))
        agg[(s, t, ek)] = a

    edges = []
    for (s, t, ek), a in agg.items():
        w = len(a["bits"])
        names = [n for n, _ in a["names"].most_common(1)]
        if s.startswith("P:") or t.startswith("P:"):
            lab = ""
        else:
            lab = ", ".join(names) + ("…" if len(a["names"]) > 1 else "")
            if w > 1: lab = (lab + " " if lab else "") + f"/{w}"
        style = EDGE[ek] + ("strokeWidth=2;" if ek == "data" and w > 1 else "")
        edges.append({"source": s, "target": t, "label": lab, "style": style,
                      "_ek": ek, "_w": w, "_names": [n for n, _ in a["names"].most_common(3)]})

    # MUX：高度随数据输入路数增长，标签写成 N:1
    n_in = collections.Counter(t for (s_, t, ek) in agg if ek == "data")
    for nid, nd in nodes.items():
        if nd["_k"] == "mux":
            n = max(2, n_in.get(nid, 2))
            nd["height"] = max(80, 30 * n)
            badge = nd["label"][nd["label"].find("<font style='font-size:9px;color:#b85450'>"):] \
                if "color:#b85450" in nd["label"] else ""
            nd["label"] = f"MUX<br><font style='font-size:8px'>{n}:1</font>" + ("<br>" + badge if badge else "")

    used = {e["source"] for e in edges} | {e["target"] for e in edges}
    nodes = {k: v for k, v in nodes.items() if k in used or v["_k"] in ("in", "out", "inst", "fifo", "mem")}
    stats = {"cells": len(cells), "nodes": len(nodes), "edges": len(edges),
             "hidden_clk_rst": len(hidden_bits), "folded": dict(folded),
             "kinds": collections.Counter(v["_k"] for v in nodes.values())}
    return list(nodes.values()), edges, stats


# --------------------------------------------------------------------------- pipeline-aware layout
PIPE_STYLE = ("html=1;whiteSpace=wrap;horizontal=0;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;"
              "fontSize=10;fontStyle=1;")
STATE_STYLE = REG_SHAPE + BASE + "fillColor=#b1ddf0;strokeColor=#10739e;fontSize=11;"
FB_EDGE = "strokeColor=#b85450;fontColor=#b85450;"
BUNDLE_EDGE = ("html=1;rounded=0;endArrow=block;endSize=8;strokeColor=#b85450;strokeWidth=4;fontColor=#b85450;"
               "fontStyle=1;fontSize=10;labelBackgroundColor=#ffffff;")
BANK_MAX, FB_MAX = 4, 3


def _sccs(ids, succ):
    """Tarjan (iterative) -> {node: scc_id}, and the set of nodes on a cycle."""
    index, low, on, st, comp, n_idx, cyc = {}, {}, set(), [], {}, [0], set()
    for root in ids:
        if root in index: continue
        work = [(root, iter(succ.get(root, ())))]
        index[root] = low[root] = n_idx[0]; n_idx[0] += 1; st.append(root); on.add(root)
        while work:
            v, it = work[-1]
            nxt = next(it, None)
            if nxt is not None:
                if nxt not in index:
                    index[nxt] = low[nxt] = n_idx[0]; n_idx[0] += 1; st.append(nxt); on.add(nxt)
                    work.append((nxt, iter(succ.get(nxt, ()))))
                elif nxt in on:
                    low[v] = min(low[v], index[nxt])
                continue
            work.pop()
            if work: low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                members = []
                while True:
                    w = st.pop(); on.discard(w); comp[w] = v; members.append(w)
                    if w == v: break
                if len(members) > 1 or v in succ.get(v, ()): cyc.update(members)
    return comp, cyc


def pipeline_graph(nodes, edges):
    """Assign pipeline stages / columns; restyle registers; bundle crowded boundaries and feedback.
    Returns (nodes, edges, meta) where meta has col, stage, boundaries for DOT + decoration."""
    import collections as C
    ids = [n["id"] for n in nodes]; byid = {n["id"]: n for n in nodes}
    succ = C.defaultdict(list); pred = C.defaultdict(list)
    for e in edges:
        succ[e["source"]].append(e["target"]); pred[e["target"]].append(e["source"])
    regs = {n["id"] for n in nodes if n["_k"] == "reg"}
    storage = regs | {n["id"] for n in nodes if n["_k"] == "mem"}
    have_cell_info = any("_state" in n for n in nodes if n["_k"] == "reg")
    # state register: its output comes back to its own input through combinational logic only
    # (counter / FSM / pointer). A replay loop S2 -> S0 -> S1 -> S2 passes other registers, so the
    # pipeline registers on it stay pipeline registers.
    state = {n["id"] for n in nodes if n["_k"] == "reg" and n.get("_state")} if have_cell_info else set()
    for r in ([] if have_cell_info else regs):
        seen, stack = set(), list(succ[r])
        while stack:
            v = stack.pop()
            if v == r: state.add(r); break
            if v in seen or v in storage: continue
            seen.add(v); stack.extend(succ[v])
    pipe = regs - state
    # stage = fewest pipeline registers from any input (0-1 BFS)
    INF = 10 ** 9; dist = {i: INF for i in ids}
    dq = C.deque()
    for n in nodes:
        if n["_k"] == "in": dist[n["id"]] = 0; dq.append(n["id"])
    while dq:
        u = dq.popleft()
        for v in succ[u]:
            w = 1 if u in pipe else 0
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                (dq.appendleft if w == 0 else dq.append)(v)
    for _ in range(len(ids)):                # not reachable from inputs: inherit from neighbours
        changed = False
        for i in ids:
            if dist[i] >= INF:
                cand = [dist[p] + (1 if p in pipe else 0) for p in pred[i] if dist[p] < INF]
                cand += [max(0, dist[s_] - (1 if i in pipe else 0)) for s_ in succ[i] if dist[s_] < INF]
                if cand: dist[i] = min(cand); changed = True
        if not changed: break
    for i in ids:
        if dist[i] >= INF: dist[i] = 0
    stage = dict(dist)
    if have_cell_info:
        stage = {n["id"]: n.get("_stage", 0) for n in nodes}
        for n in nodes:
            if n["_k"] == "out" and pred[n["id"]]:
                stage[n["id"]] = max(stage[p_] + (1 if p_ in pipe else 0) for p_ in pred[n["id"]])
    for n in nodes:
        if n["_k"] == "in" and succ[n["id"]]:
            stage[n["id"]] = min(stage[v] for v in succ[n["id"]])
    # ---- restyle registers
    for r in pipe:
        n = byid[r]; nm, b = n.get("_name") or "reg", n.get("_bits") or 0
        n["style"] = PIPE_STYLE; n["width"] = 30; n["height"] = max(70, min(220, 9 * len(nm) + 30))
        n["label"] = f"{nm}" + (f" /{b}" if b > 1 else "")
    for r in state:
        byid[r]["style"] = STATE_STYLE
    # ---- crowded boundary -> one register bank
    bmembers = C.defaultdict(list)
    for r in pipe: bmembers[stage[r]].append(r)
    rename = {}
    for k, rs in bmembers.items():
        if len(rs) > BANK_MAX:
            bid = f"bank{k}"
            names = [byid[r].get("_name") or "reg" for r in rs]
            bits = sum(byid[r].get("_bits") or 0 for r in rs)
            nodes.append({"id": bid, "_k": "reg", "style": PIPE_STYLE, "width": 34,
                          "height": max(120, min(360, 14 * len(rs) + 60)),
                          "label": f"S{k}→S{k+1} 寄存器 ×{len(rs)}<br><font style='font-size:9px'>"
                                   f"{', '.join(names[:3])}{'…' if len(names) > 3 else ''} · {bits} bit</font>"})
            byid[bid] = nodes[-1]; stage[bid] = k; pipe.add(bid)
            for r in rs: rename[r] = bid; pipe.discard(r)
    if rename:
        nodes[:] = [n for n in nodes if n["id"] not in rename]
        merged = {}
        for e in edges:
            s_, t_ = rename.get(e["source"], e["source"]), rename.get(e["target"], e["target"])
            if s_ == t_: continue
            key = (s_, t_, e["_ek"])
            if key in merged:
                m = merged[key]; m["_w"] += e["_w"]; m["_names"] = list(dict.fromkeys(m["_names"] + e["_names"]))[:3]
                m["label"] = (m["_names"][0] + "…" if m["_names"] else "") + (f" /{m['_w']}" if m["_w"] > 1 else "")
            else:
                merged[key] = dict(e, source=s_, target=t_)
        edges[:] = list(merged.values())
        succ = C.defaultdict(list)
        for e in edges: succ[e["source"]].append(e["target"])
    ids = [n["id"] for n in nodes]
    # ---- depth inside each stage (longest path on a DAG: drop state-reg outputs, then DFS back edges)
    depth = {}
    for k in sorted(set(stage[i] for i in ids if i not in pipe)):
        mem = [i for i in ids if stage[i] == k and i not in pipe]
        ms = set(mem)
        es = C.defaultdict(list)
        for e in edges:
            a_, b_ = e["source"], e["target"]
            if a_ in ms and b_ in ms and a_ not in state and byid[b_]["_k"] != "in" and byid[a_]["_k"] != "out":
                es[a_].append(b_)
        order = sorted(mem, key=lambda i: (byid[i]["_k"] != "in", i))
        color, back = {}, set()
        for r0 in order:
            if r0 in color: continue
            stack = [(r0, iter(es[r0]))]; color[r0] = 1
            while stack:
                v, it = stack[-1]; w = next(it, None)
                if w is None: color[v] = 2; stack.pop(); continue
                if color.get(w) == 1: back.add((v, w))
                elif w not in color: color[w] = 1; stack.append((w, iter(es[w])))
        indeg = C.Counter(); dag = C.defaultdict(list)
        for a_, bs in es.items():
            for b_ in bs:
                if (a_, b_) not in back: dag[a_].append(b_); indeg[b_] += 1
        d = {i: 0 for i in mem}; q = C.deque(i for i in mem if indeg[i] == 0)
        while q:
            u = q.popleft()
            for v in dag[u]:
                d[v] = max(d[v], d[u] + 1); indeg[v] -= 1
                if indeg[v] == 0: q.append(v)
        inner = [d[i] for i in mem if byid[i]["_k"] not in ("in", "out")]
        has_in = any(byid[i]["_k"] == "in" for i in mem)
        last = (max(inner) + 1) if inner else (1 if has_in else 0)
        for i in mem:
            k_ = byid[i]["_k"]
            depth[i] = 0 if k_ == "in" else last if k_ == "out" else d[i]
    # ---- columns: stage k -> its columns, then one boundary column for its pipeline registers
    col, base, bounds, stage_cols = {}, 0, {}, {}
    for k in sorted(set(stage[i] for i in ids)):
        mem = [i for i in ids if stage[i] == k and i not in pipe]
        if mem:
            width = max(depth[i] for i in mem) + 1
            for i in mem: col[i] = base + depth[i]
            stage_cols[k] = (base, base + width - 1); base += width
        rs = [i for i in ids if i in pipe and stage[i] == k]
        if rs:
            for r in rs: col[r] = base
            bounds[k] = base; base += 1
    # ---- feedback: edges that do not go rightwards
    groups = C.defaultdict(list)
    for e in edges:
        a_, b_ = e["source"], e["target"]
        e["_back"] = col[b_] <= col[a_]
        if e["_back"]:
            e["style"] = e["style"] + FB_EDGE
            sa = stage[a_] + (0.5 if a_ in pipe else 0); sb = stage[b_] + (0.5 if b_ in pipe else 0)
            if sa > sb: groups[(stage[a_], stage[b_])].append(e)
    drop = set()
    for (sa, sb), es_ in groups.items():
        if len(es_) > FB_MAX:
            keep = max(es_, key=lambda e: e["_w"])
            names = list(dict.fromkeys(n for e in es_ for n in e["_names"]))
            keep["style"] = BUNDLE_EDGE
            keep["label"] = f"S{sa}→S{sb} 反馈 ×{len(es_)}：{', '.join(names[:3])}{'…' if len(names) > 3 else ''}"
            drop.update(id(e) for e in es_ if e is not keep)
    edges[:] = [e for e in edges if id(e) not in drop]
    logic = sorted({stage[i] for i in ids if byid[i]["_k"] not in ("in", "out") and i not in pipe})
    return nodes, edges, {"col": col, "stage": stage, "bounds": bounds, "stage_cols": stage_cols,
                          "pipe": pipe, "state": state, "logic_stages": logic}


def load_autolayout():
    import importlib.util
    spec = importlib.util.spec_from_file_location("autolayout", AUTOLAYOUT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def pipeline_drawio(nodes, edges, meta, out):
    """Column-constrained DOT (rank=same per column, invisible anchor chain) -> draw.io via autolayout."""
    AL = load_autolayout(); q = AL.dot_quote
    col = meta["col"]; ncol = max(col.values()) + 1
    L = ["digraph G { rankdir=LR; splines=ortho; newrank=true; nodesep=0.45; ranksep=1.05; "
         "node [shape=box fixedsize=true];"]
    for c in range(ncol):
        L.append(f'{q("__c%d" % c)} [style=invis width=0.01 height=0.01];')
    if ncol > 1:
        L.append(" -> ".join(q("__c%d" % c) for c in range(ncol)) + " [style=invis weight=1000];")
    members = collections.defaultdict(list)
    for n in nodes: members[col[n["id"]]].append(n["id"])
    for c in range(ncol):
        L.append("{ rank=same; " + " ".join([q("__c%d" % c)] + [q(i) for i in members[c]]) + " }")
    for n in nodes:
        L.append(f'{q(n["id"])} [width={n["width"] / 72:.4f} height={n["height"] / 72:.4f}];')
    for e in edges:
        attr_ = " [constraint=false]" if e["_back"] else ""
        L.append(f'{q(e["source"])} -> {q(e["target"])}{attr_};')
    L.append("}")
    height, pos, pts = AL.layout("\n".join(L))
    graph = {"nodes": [{k: v for k, v in n.items() if not k.startswith("_")} for n in nodes],
             "edges": [{k: v for k, v in e.items() if not k.startswith("_")} for e in edges]}
    xml = AL.to_drawio(graph, height, pos, pts, color=False)
    open(out, "w", encoding="utf-8").write(xml)
    route_feedback(out, edges)
    colx = {c: pos["__c%d" % c][0] * 72 for c in range(ncol)}
    return colx


def route_feedback(path, edges):
    """Feedback edges leave the source at the bottom, run along a corridor under the whole diagram and
    enter the target from the left — like replay loops in hand-drawn pipeline diagrams."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(path); root = tree.getroot().find(".//root")
    rect = {}
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if c.get("vertex") == "1" and g is not None and g.get("x") is not None:
            rect[c.get("id")] = tuple(float(g.get(k, 0)) for k in ("x", "y", "width", "height"))
    if not rect: return
    ymax = max(y + h for x, y, w, h in rect.values())
    backs = [(i, e) for i, e in enumerate(edges) if e.get("_back")
             and e["source"] in rect and e["target"] in rect]
    backs.sort(key=lambda ie: rect[ie[1]["source"]][0] - rect[ie[1]["target"]][0])
    cells = {c.get("id"): c for c in root.findall("mxCell")}
    for lane, (i, e) in enumerate(backs):
        c = cells.get(f"e{i}")
        if c is None: continue
        sx, sy, sw, sh = rect[e["source"]]; tx, ty, tw, th = rect[e["target"]]
        yc = ymax + 40 + 18 * lane
        xl = tx - 24 - 6 * (lane % 4)
        st = c.get("style", "")
        st = re.sub(r"(exitX|exitY|entryX|entryY|exitDx|exitDy|entryDx|entryDy)=[^;]*;", "", st)
        c.set("style", st + "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;")
        g = c.find("mxGeometry")
        for ch in list(g): g.remove(ch)
        arr = ET.SubElement(g, "Array", **{"as": "points"})
        for px, py in ((sx + sw / 2, yc), (xl, yc), (xl, ty + th / 2)):
            ET.SubElement(arr, "mxPoint", x=str(round(px)), y=str(round(py)))
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _extent(root):
    """(ymin, ymax) over top-level vertices and edge waypoints."""
    ys = []
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if g is None or c.get("parent") != "1": continue
        if c.get("vertex") == "1" and g.get("y") is not None:
            ys += [float(g.get("y")), float(g.get("y")) + float(g.get("height", 0))]
        for pt in g.iter("mxPoint"):
            if pt.get("as") in (None, "points") and pt.get("y") is not None: ys.append(float(pt.get("y")))
    return min(ys), max(ys)


def decorate_stages(path, meta, colx):
    """Dashed boundaries through the pipeline-register columns and S0..Sn headers (only if >1 stage)."""
    import xml.etree.ElementTree as ET
    real = {k: v for k, v in meta["stage_cols"].items() if k in meta["logic_stages"]}
    if len(real) < 2: return                                  # one stage (+ output registers): no headers
    tree = ET.parse(path); root = tree.getroot().find(".//root")
    ymin_, ymax_ = _extent(root)
    y0, y1 = ymin_ - 50, ymax_ + 20
    back = []
    def cell(i, v, st, x, y, w, h):
        c = ET.Element("mxCell", id=i, value=v, style=st, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(round(x)), y=str(round(y)), width=str(round(w)), height=str(round(h)), **{"as": "geometry"})
        return c
    logic_stages = sorted(real)
    if len(logic_stages) >= 2:
        for k, bx in meta["bounds"].items():
            if any(s_ > k for s_ in real) and any(s_ <= k for s_ in real):
                back.append(cell(f"sb{k}", "", "line;direction=south;dashed=1;strokeColor=#999999;strokeWidth=1;html=1;",
                                 colx[bx] - 5, y0, 10, y1 - y0))
        for k in logic_stages:
            a_, b_ = real[k]
            left = colx[meta["bounds"][k - 1]] if (k - 1) in meta["bounds"] else colx[a_] - 60
            right = colx[meta["bounds"][k]] if k in meta["bounds"] else colx[b_] + 60
            back.append(cell(f"sh{k}", f"<b>S{k}</b>", "text;html=1;align=center;verticalAlign=middle;fontSize=16;fontColor=#555555;",
                             (left + right) / 2 - 40, y0 - 30, 80, 26))
    kids = list(root); pos_ = kids.index([c for c in kids if c.get("id") == "1"][0]) + 1
    for i, c in enumerate(back): root.insert(pos_ + i, c)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def decorate(drawio_path, title, kinds, hidden, extra=()):
    """Add a title above and a legend below the laid-out diagram (only kinds present)."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(drawio_path); root = tree.getroot().find(".//root")
    xs, ys, ye = [], [], []
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if c.get("vertex") == "1" and g is not None and g.get("x") is not None:
            x, y, h = float(g.get("x")), float(g.get("y")), float(g.get("height", 0))
            xs.append(x); ys.append(y); ye.append(y + h)
    x0, y0, y1 = min(xs), min(ys), max(max(ye), _extent(root)[1])
    def cell(i, v, s, x, y, w, h, parent="1"):
        c = ET.SubElement(root, "mxCell", id=i, value=v, style=s, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=str(round(x)), y=str(round(y)), width=str(w), height=str(h), **{"as": "geometry"})
    cell("title", title, "text;html=1;align=left;verticalAlign=middle;fontSize=16;", x0, y0 - 56, 900, 30)
    order = [k for k in ("reg", "mux", "arith", "cmp", "gate", "mem", "fifo", "inst", "ctrl") if kinds.get(k)]
    note = "clk / reset 连线已隐藏（--show-clock 显示）" if hidden else ""
    xnodes = [x for x in extra if x[0] == "node"]; xedges = [x for x in extra if x[0] == "edge"]
    if xnodes and "reg" in order: order.remove("reg")
    H = 34 + 30 * (len(order) + len(xnodes)) + 22 * len(xedges) + (24 if note else 0) + 66
    cell("legend", "<b>图例</b>", "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#999999;"
         "verticalAlign=top;align=left;spacingLeft=8;spacingTop=4;fontSize=11;", x0, y1 + 40, 250, H)
    size = {"reg": (36, 20), "mux": (14, 24), "arith": (16, 24), "cmp": (22, 22), "mem": (36, 22), "gate": (30, 18),
            "fifo": (36, 20), "inst": (36, 20), "ctrl": (36, 22)}
    y = 30
    for i, k in enumerate(order):
        w, h = size[k]
        cell(f"lg{i}", "", STYLE[k].replace("fontSize", "x"), 12 + (36 - w) / 2, y + (24 - h) / 2, w, h, "legend")
        cell(f"lgt{i}", LEGEND_NAME[k], "text;html=1;align=left;verticalAlign=middle;fontSize=11;", 58, y, 180, 24, "legend")
        y += 30
    for i, (_, st, w, h, txt) in enumerate(xnodes):
        cell(f"lgx{i}", "", st, 12 + (36 - w) / 2, y + (24 - h) / 2, w, h, "legend")
        cell(f"lgxt{i}", txt, "text;html=1;align=left;verticalAlign=middle;fontSize=11;", 58, y, 180, 24, "legend")
        y += 30
    rows = [("data", "数据（粗线 = 多位总线，/N 为位宽）"), ("sel", "MUX 选择信号"), ("en", "使能信号")]
    for j, (ek, txt) in enumerate(rows + [(x[1], x[2]) for x in xedges]):
        e = ET.SubElement(root, "mxCell", id=f"lge{j}", value="", edge="1", parent="legend", style=EDGE.get(ek, ek))
        g = ET.SubElement(e, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(g, "mxPoint", x="12", y=str(y + 11), **{"as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", x="48", y=str(y + 11), **{"as": "targetPoint"})
        cell(f"lget{j}", txt, "text;html=1;align=left;verticalAlign=middle;fontSize=10;", 58, y, 190, 22, "legend")
        y += 22
    if note:
        cell("lgnote", note, "text;html=1;align=left;verticalAlign=middle;fontSize=9;fontColor=#999999;", 10, y + 2, 236, 20, "legend")
    tree.write(drawio_path, encoding="utf-8", xml_declaration=True)


def main():
    ap = argparse.ArgumentParser(description="Verilog/SystemVerilog module -> draw.io block diagram")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--top"); ap.add_argument("--module")
    ap.add_argument("-o", "--output")
    ap.add_argument("--png", action="store_true", help="also export PNG next to the .drawio")
    ap.add_argument("--svg", action="store_true", help="also export SVG next to the .drawio")
    ap.add_argument("--scale", type=int, help="PNG scale (default $DRAWIO_SCALE or 3)")
    ap.add_argument("--sv2v", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--show-clock", action="store_true", help="draw clk/reset nets")
    ap.add_argument("--no-fold", action="store_true", help="keep generate-loop instances separate")
    ap.add_argument("--no-collapse", action="store_true", help="keep every glue gate / control comparator")
    ap.add_argument("--list", action="store_true", help="list modules and exit")
    ap.add_argument("--keep-json", help="copy the Yosys JSON netlist here")
    ap.add_argument("--direction", choices=["LR", "TB"], default="LR")
    ap.add_argument("--layout", choices=["auto", "pipeline", "free"], default="auto",
                    help="pipeline: inputs left, stages S0..Sn left-to-right, pipeline registers on the boundaries, "
                         "feedback routed back; free: plain Graphviz layout; auto (default): free when the module is "
                         "mostly sub-module instances (block-to-block traffic is not pipeline feedback), else pipeline")
    ap.add_argument("--no-tune", action="store_true",
                    help="keep --direction as given (default: autolayout tries LR and TB, keeps the cleaner one)")
    a = ap.parse_args()
    files = [os.path.abspath(f) for f in a.files]
    for f in files:
        if not os.path.isfile(f): die(f"no such file: {f}")
    with tempfile.TemporaryDirectory(prefix="rtl2drawio-") as wd:
        design, used_sv2v = frontend(files, a.top, a.sv2v, wd)
        if a.keep_json: shutil.copy(os.path.join(wd, "netlist.json"), a.keep_json)
    mods = design["modules"]
    if a.list:
        seen = collections.OrderedDict()
        for n, mm in mods.items():
            seen.setdefault(base(n), []).append(mm)
        for b, variants in seen.items():
            cnt = collections.Counter(kind_of(c["type"], c) for c in variants[0]["cells"].values())
            v = f" ({len(variants)} 个参数化变体)" if len(variants) > 1 else ""
            print(f"  {b:20s} " + ", ".join(f"{k}×{n}" for k, n in cnt.most_common()) + v)
        return
    want = a.module or a.top
    if want:
        cands = [n for n in mods if base(n) == want]
        if not cands: die(f"module {want!r} not found; available: {', '.join(sorted({base(n) for n in mods}))}")
    else:
        cands = [n for n, mm in mods.items() if mm.get("attributes", {}).get("top")] or list(mods)
    mname = cands[0]
    nodes, edges, st = build_graph(mods, mname, a.show_clock, not a.no_fold, not a.no_collapse)
    out = a.output or f"{base(mname)}.drawio"
    layout_ = a.layout
    if layout_ == "auto":
        body = [n for n in nodes if n["_k"] not in ("in", "out")]
        insts = [n for n in body if n["_k"] in ("inst", "fifo")]
        logic = [n for n in body if n["_k"] not in ("inst", "fifo", "reg")]
        # top-level glue (instances + a few registers/glue): block-to-block traffic is not pipeline feedback
        layout_ = "free" if insts and len(logic) <= len(insts) else "pipeline"
    if layout_ == "pipeline":
        nodes, edges, meta = pipeline_graph(nodes, edges)
        colx = pipeline_drawio(nodes, edges, meta, out)
        decorate_stages(out, meta, colx)
        nst = max(1, len(meta["logic_stages"]))
        extra = []
        if meta["pipe"]: extra.append(("node", PIPE_STYLE, 12, 24, "流水 / 输出寄存器（放在级分界处）"))
        if meta["state"]: extra.append(("node", STATE_STYLE, 36, 20, "状态寄存器（在环路上：FSM/计数器/指针）"))
        if any(e.get("_back") for e in edges): extra.append(("edge", EDGE["data"] + FB_EDGE, "反馈（回到左侧的逻辑）"))
        if any(e["style"] == BUNDLE_EDGE for e in edges): extra.append(("edge", BUNDLE_EDGE, "一捆跨级反馈（只画一根）"))
        st["kinds"] = collections.Counter(n["_k"] for n in nodes)
        pat = re.compile(r"^\s*module\s+" + re.escape(base(mname)) + r"\b", re.M)
        hit = [f for f in files if pat.search(open(f, encoding="utf-8", errors="replace").read())]
        src = os.path.basename(hit[0]) if hit else os.path.basename(files[0])
        title = (f"<b>module {base(mname)}</b>&nbsp;&nbsp;<font style='font-size:11px;color:#888888'>"
                 f"{src}{' · sv2v' if used_sv2v else ''} · {nst} 级 · 流水寄存器 {len(meta['pipe'])} · "
                 f"状态寄存器 {len(meta['state'])} · {len(nodes)} 个框</font>")
        decorate(out, title, st["kinds"], st["hidden_clk_rst"] > 0, extra)
        export_all(out, a.png, a.svg, a.scale)
        print(f"wrote {out}: module {base(mname)}; {nst} stage(s), pipeline regs {len(meta['pipe'])}, "
              f"state regs {len(meta['state'])}, {len(nodes)} nodes, {len(edges)} edges", file=sys.stderr)
        return
    graph = {"direction": a.direction, "ranksep": 1.0, "nodesep": 0.55,
             "nodes": [{k: v for k, v in n.items() if k != "_k"} for n in nodes], "edges": edges}
    gj = out + ".graph.json"
    json.dump(graph, open(gj, "w"), ensure_ascii=False, indent=1)
    r = subprocess.run([sys.executable, AUTOLAYOUT, gj, "-o", out] + ([] if a.no_tune else ["--tune"]),
                       capture_output=True, text=True)
    if not a.no_tune and r.stderr.strip(): print(r.stderr.strip().splitlines()[-1], file=sys.stderr)
    os.remove(gj)
    if r.returncode: die("autolayout failed:\n" + r.stderr[-2000:])
    pat = re.compile(r"^\s*module\s+" + re.escape(base(mname)) + r"\b", re.M)
    hit = [f for f in files if pat.search(open(f, encoding="utf-8", errors="replace").read())]
    src = os.path.basename(hit[0]) if hit else ", ".join(os.path.basename(f) for f in files[:3])
    title = (f"<b>module {base(mname)}</b>&nbsp;&nbsp;<font style='font-size:11px;color:#888888'>"
             f"{src}{' · sv2v' if used_sv2v else ''} · Yosys {st['cells']} 个单元 → {st['nodes']} 个框</font>")
    decorate(out, title, st["kinds"], st["hidden_clk_rst"] > 0)
    export_all(out, a.png, a.svg, a.scale)
    variants = f"（共 {len(cands)} 个参数化变体，画的是第一个）" if len(cands) > 1 else ""
    print(f"wrote {out}: module {base(mname)}{variants}; Yosys cells {st['cells']} -> {st['nodes']} nodes, "
          f"{st['edges']} edges; kinds {dict(st['kinds'])}; folded {list(st['folded'].values()) or '-'}",
          file=sys.stderr)


if __name__ == "__main__":
    main()

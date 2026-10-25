#!/usr/bin/env python3
"""Control-path views for Verilog / SystemVerilog: FSM state diagrams + control-structure map.

  fsm2drawio.py list FILE...                       # FSMs found in the source
  fsm2drawio.py fsm  FILE... [--module M] [-d OUTDIR] [--png] [--no-actions]
        one state-transition diagram per FSM, extracted from the *source* so
        transition conditions keep the designer's own expressions
  fsm2drawio.py ctrl FILE... --top TOP --module L [-o OUT.drawio] [--png]
        control-structure map of module L: its sub-module instances (FSMs
        highlighted with their states) connected only by control signals —
        state broadcasts, valid/ready handshakes, start/done/enable/select —
        data buses are dropped. Uses the Yosys netlist (see rtl2drawio.py).

FSM recognition: a `case (S)` whose items assign S (or a next-state variable
N with `S <= N` elsewhere). State names come from localparams; constants that
compare *another* FSM's state variable are translated to that FSM's state
names. Guards outside the case (enable, read/write branches) go into a note,
not onto every edge. `for` loops inside a state become "∃j:" conditions; a
`for i` loop around the whole case marks a replicated FSM (one per i).
"""
import argparse, collections, math, itertools, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rtl2drawio as R                                   # frontend(), base(), AUTOLAYOUT, UF

# =========================================================================== lexer
TOKEN = re.compile(r"""
  (?P<ws>\s+)
| (?P<num>\d*\s*'[sS]?[bBoOdDhH]\s*[0-9a-fA-F_xXzZ?]+|\d+\.\d+|\d+|'[01xXzZ])
| (?P<id>[A-Za-z_][A-Za-z0-9_$]*|\$[A-Za-z_]\w*|`[A-Za-z_]\w*|\\\S+)
| (?P<str>"(?:\\.|[^"\\])*")
| (?P<op><<<=|>>>=|===|!==|<<<|>>>|<<=|>>=|<=|>=|==|!=|&&|\|\||<<|>>|\+\+|--|\+=|-=|\*=|/=|->|::|\*\*|~&|~\||~\^|\^~|[-+*/%&|^~!<>=?:;,.\#@(){}\[\]'])
""", re.X)
DECL = {"reg", "logic", "int", "integer", "bit", "byte", "shortint", "longint", "wire", "automatic",
        "static", "var", "genvar", "signed", "unsigned"}
ASSIGN_OPS = {"<=", "=", "+=", "-=", "*=", "/=", "|=", "&=", "^=", "<<=", ">>="}


def strip_comments(src):
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group()), re.sub(r"//[^\n]*", "", src), flags=re.S)


def lex(src):
    toks, pos = [], 0
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m: pos += 1; continue
        if m.lastgroup != "ws": toks.append((m.group(), m.start(), m.end()))
        pos = m.end()
    return toks


def lit_value(t):
    t = t.replace("_", "").replace(" ", "")
    m = re.fullmatch(r"\d*'[sS]?([bBoOdDhH])([0-9a-fA-F]+)", t)
    if m: return int(m.group(2), {"b": 2, "o": 8, "d": 10, "h": 16}[m.group(1).lower()])
    if re.fullmatch(r"\d+", t): return int(t)
    return None


# =========================================================================== parser
class Parser:
    def __init__(self, src, toks, i=0):
        self.src, self.t, self.i = src, toks, i

    def peek(self, k=0):
        j = self.i + k
        return self.t[j][0] if j < len(self.t) else None

    def take(self):
        tok = self.t[self.i]; self.i += 1; return tok

    def text(self, a, b):                                  # source text of tokens [a, b)
        if a >= b: return ""
        return re.sub(r"\s+", " ", self.src[self.t[a][1]:self.t[b - 1][2]]).strip()

    def balanced(self):                                    # at '(' -> text inside, consume ')'
        assert self.peek() == "("
        self.take(); a = self.i; d = 1
        while self.i < len(self.t):
            v = self.take()[0]
            if v in "([{": d += 1
            elif v in ")]}":
                d -= 1
                if d == 0: return self.text(a, self.i - 1)
        return self.text(a, self.i)

    def until(self, stops):                                # tokens up to a depth-0 stop token (not consumed)
        a, d = self.i, 0
        while self.i < len(self.t):
            v = self.peek()
            if d == 0 and v in stops: break
            if v in ("(", "[", "{"): d += 1
            elif v in (")", "]", "}"): d -= 1
            self.i += 1
        return a, self.i

    def stmt(self):
        v = self.peek()
        if v is None: return ("other", "")
        if v in ("unique", "priority", "unique0") and self.peek(1) in ("if", "case", "casez", "casex"):
            self.take(); v = self.peek()
        if v in ("begin", "fork"):
            self.take()
            if self.peek() == ":": self.take(); self.take()
            body = []
            while self.peek() not in ("end", "join", "join_any", "join_none", None):
                body.append(self.stmt())
            if self.peek() is not None: self.take()
            if self.peek() == ":": self.take(); self.take()
            return ("block", body)
        if v == "if":
            self.take(); cond = self.balanced(); then = self.stmt(); els = None
            if self.peek() == "else": self.take(); els = self.stmt()
            return ("if", cond, then, els)
        if v in ("case", "casez", "casex"):
            self.take(); sel = self.balanced()
            if self.peek() == "inside": self.take()
            items = []
            while self.peek() not in ("endcase", None):
                if self.peek() == "default":
                    self.take()
                    if self.peek() == ":": self.take()
                    items.append((["default"], self.stmt())); continue
                labels, cur = [], None
                a, b = self.until({":"})
                seg = self.t[a:b]; start = a
                d = 0
                for k, tok in enumerate(seg):
                    if tok[0] in "([{": d += 1
                    elif tok[0] in ")]}": d -= 1
                    elif tok[0] == "," and d == 0:
                        labels.append(self.text(start, a + k)); start = a + k + 1
                labels.append(self.text(start, b))
                if self.peek() == ":": self.take()
                items.append((labels, self.stmt()))
            if self.peek() == "endcase": self.take()
            return ("case", sel, items)
        if v in ("for", "while", "repeat", "foreach"):
            self.take(); hdr = self.balanced()
            m = re.match(r"\s*(?:(?:int|integer|genvar|automatic|unsigned)\s+)*([A-Za-z_]\w*)\s*=", hdr)
            return ("for", m.group(1) if (m and v == "for") else None, hdr, self.stmt())
        if v == "forever":
            self.take(); return ("for", None, "", self.stmt())
        if v == ";":
            self.take(); return ("other", "")
        if v in ("break", "continue", "return", "disable") or v.startswith(("$", "`")):
            a, b = self.until({";"}); self.take(); return ("other", self.text(a, b))
        if v in DECL:
            a, b = self.until({";"}); self.take()
            txt = self.text(a, b)
            m = re.match(r"(?:\w+\s+|\[[^\]]*\]\s*)*([A-Za-z_]\w*)\s*=\s*(.+)$", txt)
            return ("assign", m.group(1), "=", m.group(2)) if m else ("other", txt)
        a, b = self.until({";"})
        if self.peek() == ";": self.take()
        d = 0
        for k in range(a, b):
            tv = self.t[k][0]
            if tv in "([{": d += 1
            elif tv in ")]}": d -= 1
            elif d == 0 and tv in ASSIGN_OPS:
                return ("assign", self.text(a, k), tv, self.text(k + 1, b))
        if self.i == a: self.i += 1                        # never stall
        return ("other", self.text(a, b))


def modules(src):
    """-> {module_name: (text, tokens, localparams{name: (int, literal)}, [always ASTs])}"""
    src = strip_comments(src)
    toks = lex(src)
    out, i = {}, 0
    while i < len(toks):
        if toks[i][0] == "module" and i + 1 < len(toks):
            name, j = toks[i + 1][0], i + 1
            while j < len(toks) and toks[j][0] != "endmodule": j += 1
            body = toks[i:j]
            text = src[toks[i][1]:toks[j - 1][2]] if j > i else ""
            params = {}
            for m in re.finditer(r"\b(?:localparam|parameter)\b(.*?)[;)]", text, re.S):
                for part in re.split(r",(?![^\[\]{}()]*[\]})])", m.group(1)):
                    mm = re.match(r"\s*(?:\w+\s+)?(?:\[[^\]]*\]\s*)?([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", part, re.S)
                    if mm:
                        val = lit_value(mm.group(2))
                        if val is not None: params[mm.group(1)] = (val, mm.group(2).strip())
            always = []
            k = 0
            while k < len(body):
                if body[k][0] in ("always", "always_ff", "always_comb", "always_latch"):
                    p = Parser(src, body, k + 1)
                    if p.peek() == "@":
                        p.take()
                        if p.peek() == "(": p.balanced()
                        else: p.take()
                    always.append(p.stmt()); k = p.i
                else:
                    k += 1
            out[name] = (text, body, params, always)
            i = j
        i += 1
    return out


# =========================================================================== FSM extraction
Cond = collections.namedtuple("Cond", "text neg hidden loops")
BASEID = re.compile(r"[A-Za-z_]\w*")
RST_COND = re.compile(r"^!?\s*\(?\s*(rst|reset|rst_?n|reset_?n|\w*_rst\w*|\w*reset\w*)\s*\)?$", re.I)


def lhs_base(t):
    m = BASEID.match(t.strip()); return m.group() if m else ""


def walk(node, fn, ctx=None):
    fn(node, ctx)
    k = node[0]
    kids = (node[1] if k == "block" else [node[2]] + ([node[3]] if node[3] else []) if k == "if"
            else [s for _, s in node[2]] if k == "case" else [node[3]] if k == "for" else [])
    for c in kids: walk(c, fn, ctx)


def paths(node, loops=(), cap=256):
    """Symbolic paths through a statement: [([Cond], [(lhs, op, rhs, loops)])]."""
    k = node[0]
    if k == "assign": return [([], [(node[1], node[2], node[3], loops)])]
    if k == "block":
        acc = [([], [])]
        for s in node[1]:
            nxt = paths(s, loops, cap)
            acc = [(c1 + c2, a1 + a2) for (c1, a1) in acc for (c2, a2) in nxt][:cap]
        return acc
    if k == "if":
        c = node[1]
        out = [([Cond(c, False, False, loops)] + cs, a) for cs, a in paths(node[2], loops, cap)]
        if node[3] is not None:
            hidden = node[3][0] == "if"                        # else-if chain: priority is implied
            out += [([Cond(c, True, hidden, loops)] + cs, a) for cs, a in paths(node[3], loops, cap)]
        else:
            out.append(([Cond(c, True, False, loops)], []))
        return out[:cap]
    if k == "case":
        out = []
        for labels, s in node[2]:
            ct = "default" if labels == ["default"] else f"{node[1]} == {' | '.join(labels)}"
            out += [([Cond(ct, False, False, loops)] + cs, a) for cs, a in paths(s, loops, cap)]
        return out[:cap]
    if k == "for":
        body = paths(node[3], loops + ((node[1],) if node[1] else ()), cap)
        return (body + [([], [])])[:cap]
    return [([], [])]


def transitions_in(node, names, loops, conds=()):
    """Yield (conds, rhs, actions) for every assignment to the state var, conditioned only by the
    if/case/for statements that enclose it (sibling statements do not guard the transition)."""
    k = node[0]
    if k == "assign":
        if lhs_base(node[1]) in names: yield list(conds), node[3], []
    elif k == "block":
        direct = [c for c in node[1] if c[0] == "assign"]
        for c in node[1]:
            if c[0] == "assign" and lhs_base(c[1]) in names:
                acts = [(a[1], a[3]) for a in direct if a is not c and a[2] == "<=" and lhs_base(a[1]) not in names]
                yield list(conds), c[3], acts
            elif c[0] != "assign":
                yield from transitions_in(c, names, loops, conds)
    elif k == "if":
        yield from transitions_in(node[2], names, loops, conds + (Cond(node[1], False, False, loops),))
        if node[3] is not None:
            yield from transitions_in(node[3], names, loops,
                                      conds + (Cond(node[1], True, node[3][0] == "if", loops),))
    elif k == "case":
        for labels, st in node[2]:
            ct = "default" if labels == ["default"] else f"{node[1]} == {' | '.join(labels)}"
            yield from transitions_in(st, names, loops, conds + (Cond(ct, False, False, loops),))
    elif k == "for":
        yield from transitions_in(node[3], names, loops + ((node[1],) if node[1] else ()), conds)


def negate(t):
    t = t.strip()
    m = re.fullmatch(r"!\s*(\(.*\)|[\w\[\]\.]+)", t)
    if m:
        inner = m.group(1)
        return inner[1:-1] if inner.startswith("(") and inner.endswith(")") else inner
    if re.fullmatch(r"[\w\[\]\.]+", t): return "!" + t
    m = re.fullmatch(r"([\w\[\]\.]+)\s*==\s*(\S+)", t)
    if m: return f"{m.group(1)} != {m.group(2)}"
    return f"!({t})"


class FSM:
    def __init__(self, module, var):
        self.module, self.var = module, var
        self.states = collections.OrderedDict()            # name -> (value or None, literal)
        self.trans = collections.OrderedDict()             # (src, dst) -> {"conds": [], "acts": []}
        self.stay = set(); self.init = None
        self.guards = []; self.defs = {}; self.replicated = None

    def state_key(self, label, params):
        label = label.strip()
        if label in params:
            self.states.setdefault(label, params[label]); return label
        v = lit_value(label)
        if v is not None:
            for n, (pv, _) in params.items():
                if pv == v and n in self.states: return n
            for n, (pv, lit) in params.items():
                if pv == v and self._plausible(n): self.states.setdefault(n, (pv, lit)); return n
            self.states.setdefault(label, (v, label)); return label
        self.states.setdefault(label, (None, label)); return label

    def _plausible(self, n):                              # prefer params already used as states
        return n.isupper()


def extract_fsms(mods):
    fsms = []
    for mname, (text, toks, params, always) in mods.items():
        for blk in always:
            alias = {}
            def find_alias(n, _):
                if n[0] == "assign" and n[2] == "<=" and re.fullmatch(r"[A-Za-z_]\w*", n[3].strip()):
                    alias[n[3].strip()] = lhs_base(n[1])
            walk(blk, find_alias)
            found = collections.OrderedDict()             # var -> [(case_node, outer_conds, loops)]
            def scan(node, conds, loops):
                k = node[0]
                if k == "case":
                    var = lhs_base(node[1])
                    names = {var} | {a for a, s in alias.items() if s == var}
                    hits = []
                    for _, s in node[2]:
                        walk(s, lambda n, _: hits.append(1) if n[0] == "assign" and lhs_base(n[1]) in names else None)
                    if var and hits:
                        found.setdefault(var, []).append((node, conds, loops)); return
                if k == "block":
                    for s in node[1]: scan(s, conds, loops)
                elif k == "if":
                    scan(node[2], conds + [Cond(node[1], False, False, loops)], loops)
                    if node[3] is not None:
                        scan(node[3], conds + [Cond(node[1], True, node[3][0] == "if", loops)], loops)
                elif k == "case":
                    for labels, s in node[2]: scan(s, conds + [Cond(f"{node[1]} == {'|'.join(labels)}", False, False, loops)], loops)
                elif k == "for":
                    scan(node[3], conds, loops + ((node[1],) if node[1] else ()))
            scan(blk, [], ())
            for var, cases in found.items():
                f = FSM(mname, var)
                names = {var} | {a for a, s in alias.items() if s == var}
                # reset / initial state: assignment to the state var outside the case, under a reset condition
                for cs, acts in paths(blk):
                    if cs and RST_COND.match(cs[0].text) and not cs[0].neg:
                        for lhs, op, rhs, _ in acts:
                            if lhs_base(lhs) in names: f.init = f.state_key(rhs, params)
                for node, outer, loops in cases:
                    m = re.match(r"\s*[A-Za-z_]\w*\s*\[\s*([A-Za-z_]\w*)\s*\]", node[1])
                    if m and m.group(1) in loops: f.replicated = m.group(1)
                    g = [c for c in outer if not (c.neg and RST_COND.match(c.text)) and not RST_COND.match(c.text)]
                    gtxt = " && ".join(negate(c.text) if c.neg else c.text for c in g if not c.hidden)
                    if gtxt and gtxt not in f.guards: f.guards.append(gtxt)
                    for labels, body in node[2]:
                        if labels == ["default"]: continue
                        srcs = [f.state_key(l, params) for l in labels]
                        # 停留检测 + 局部布尔变量定义（不带下标的 x = 1，在 for 循环的 if 里）用路径枚举
                        for cs, acts in paths(body, loops):
                            if not any(lhs_base(l) in names for l, _, _, _ in acts):
                                f.stay.update(srcs)
                            for lhs, op, rhs, lp in acts:
                                if (op == "=" and re.fullmatch(r"[A-Za-z_]\w*", lhs.strip())
                                        and rhs.strip() in ("1", "1'b1") and cs):
                                    inloop = [c for c in cs if set(c.loops) - set(loops)]
                                    if inloop:
                                        v = sorted(set(inloop[0].loops) - set(loops))[0]
                                        f.defs[lhs.strip()] = f"∃{v}: " + " && ".join(
                                            negate(c.text) if c.neg else c.text for c in inloop if not c.hidden)
                        # 转移：结构化提取
                        for cs, rhs, acts in transitions_in(body, names, loops):
                            label = render_conds(cs, loops, f.replicated)
                            d = f.state_key(rhs, params)
                            for s in srcs:
                                t = f.trans.setdefault((s, d), {"conds": [], "acts": []})
                                if label not in t["conds"]: t["conds"].append(label)
                                for l, r in acts:
                                    a = f"{l.strip()}←{r.strip()}"
                                    if a not in t["acts"]: t["acts"].append(a)
                used = " ".join(c for t in f.trans.values() for c in t["conds"])
                f.defs = {k: v for k, v in f.defs.items() if re.search(r"\b" + re.escape(k) + r"\b", used)}
                if len(f.states) >= 2 and f.trans:
                    # drop placeholder states that only appear as literals with no transitions
                    fsms.append(f)
    return fsms


def render_conds(cs, outer_loops, repl):
    parts, loopgrp = [], collections.OrderedDict()
    for c in cs:
        if c.hidden: continue
        t = negate(c.text) if c.neg else c.text
        inner = [v for v in c.loops if v not in outer_loops and v != repl]
        if inner and re.search(r"\b" + re.escape(inner[-1]) + r"\b", t):
            loopgrp.setdefault(inner[-1], []).append(t)
        else:
            parts.append(t)
    for v, ts in loopgrp.items():
        parts.append(f"∃{v}: " + " && ".join(ts))
    return " && ".join(parts)


def prettify(t, statemap):
    """core_state == 3'b001 -> core_state == FETCH ; x == 1 -> x ; tidy spaces."""
    def sub(m):
        var, idx, op, lit = m.group(1), m.group(2) or "", m.group(3), m.group(4)
        v = lit_value(lit)
        name = statemap.get(var, {}).get(v)
        return f"{var}{idx} {op} {name}" if name else m.group(0)
    t = re.sub(r"\b([A-Za-z_]\w*)(\[[^\]]*\])?\s*(==|!=)\s*(\d*\s*'[bBdDhHoO]\s*[0-9a-fA-F_]+|\d+)\b", sub, t)
    t = re.sub(r"\b([A-Za-z_][\w\.]*(?:\[[^\]]*\])?)\s*==\s*(?:1'b1|1)\b", r"\1", t)
    t = re.sub(r"\b([A-Za-z_][\w\.]*(?:\[[^\]]*\])?)\s*==\s*(?:1'b0)\b", r"!\1", t)
    t = re.sub(r"\(\s*([\w\.\[\]!]+)\s*\)", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def html_esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def statemap_of(fsms):
    sm = {}
    for f in fsms:
        sm[f.var] = {v: n for n, (v, _) in f.states.items() if v is not None}
    return sm


# =========================================================================== FSM diagram
STATE_STYLE = "rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;"
FINAL_STYLE = "rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#333333;strokeWidth=3;fontSize=12;"
INIT_STYLE = "ellipse;html=1;fillColor=#000000;strokeColor=#000000;"
TEDGE = "html=1;rounded=0;endArrow=block;endSize=8;strokeColor=#333333;fontSize=10;labelBackgroundColor=#ffffff;"
TEDGE_HALF = "html=1;rounded=0;endArrow=none;strokeColor=#333333;"
LABEL_STYLE = ("text;html=1;align=center;verticalAlign=middle;whiteSpace=nowrap;fillColor=#ffffff;"
               "strokeColor=none;fontSize=10;spacing=2;")


CIRCLE = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=1.5;fontSize=12;"
FINAL = "shape=doubleEllipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#f5f5f5;strokeColor=#333333;strokeWidth=1.5;fontSize=12;"
CEDGE = ("html=1;curved=1;endArrow=block;endSize=8;strokeColor=#333333;fontSize=10;"
         "labelBackgroundColor=#ffffff;")


def _wrap(text, width=26):
    """Break a condition/action string at operators so edge labels stay narrow."""
    out, cur = [], ""
    for tok in re.split(r"(\s(?:&&|\|\||‖)\s|,\s)", text):
        if not tok: continue
        if len(cur) + len(tok) > width and cur.strip():
            out.append(cur.rstrip()); cur = tok.lstrip()
        else:
            cur += tok
    if cur.strip(): out.append(cur.strip())
    return out


def _state_label(name, lit, stay):
    parts, cur = [], ""
    for seg in re.split(r"(?=_)", name):                   # break long names at '_' like s_cache / _req
        if len(cur) + len(seg) > 10 and cur: parts.append(cur); cur = seg
        else: cur += seg
    parts.append(cur)
    sub = " · ".join(x for x in (lit if lit and lit != name else "", "⟳" if stay else "") if x)
    return "<b>" + "<br>".join(html_esc(x) for x in parts) + "</b>" + (
        f"<br><font style='font-size:9px;color:#666666'>{html_esc(sub)}</font>" if sub else "")


def fsm_positions(f, DX=250, DY=230):
    """Evenly spaced slots: a U-shaped ring along the main path (loop-like FSMs) or BFS-depth columns
    (branchy FSMs). Returns ({state: (cx, cy)}, mode)."""
    states = list(f.states)
    succ = collections.defaultdict(list)
    for (a_, b_) in f.trans:
        if a_ != b_: succ[a_].append(b_)
    init = f.init if f.init in f.states else states[0]
    best = [init]
    if len(states) <= 16:
        def dfs(path, seen):
            nonlocal best
            if len(path) > len(best): best = list(path)
            if len(best) == len(states): return
            for v in sorted(succ[path[-1]], key=states.index):
                if v not in seen:
                    seen.add(v); path.append(v); dfs(path, seen); path.pop(); seen.discard(v)
        dfs([init], {init})
    else:
        seen = {init}
        while True:
            nxt = [v for v in sorted(succ[best[-1]], key=states.index) if v not in seen]
            if not nxt: break
            best.append(nxt[0]); seen.add(nxt[0])
    if len(best) >= 0.7 * len(states) and len(states) >= 4:
        order = list(best)
        for st in states:                                   # off-path states go right after a predecessor
            if st in order: continue
            preds = [a_ for (a_, b_) in f.trans if b_ == st and a_ in order]
            order.insert(order.index(preds[0]) + 1 if preds else len(order), st)
        n = len(order); top = (n + 1) // 2 if n > 4 else n
        pos = {}
        for i, st in enumerate(order):
            if i < top: pos[st] = (i * DX, 0)
            else: pos[st] = ((top - 1 - (i - top)) * DX, DY)
        return pos, "ring"
    depth = {init: 0}; dq = collections.deque([init])
    while dq:
        u = dq.popleft()
        for v in succ[u]:
            if v not in depth: depth[v] = depth[u] + 1; dq.append(v)
    for st in states:
        depth.setdefault(st, max(depth.values()) + 1)
    cols = collections.defaultdict(list)
    for st in states: cols[depth[st]].append(st)
    rows = max(len(v) for v in cols.values())
    pos = {}
    for d, sts in cols.items():
        off = (rows - len(sts)) * DY / 2
        for j, st in enumerate(sts): pos[st] = (d * DX, off + j * DY)
    return pos, "layered"


def _fsm_labels(f, statemap, actions):
    labs, widest = {}, 0
    for (a_, b_), t in f.trans.items():
        conds = [prettify(c, statemap) for c in t["conds"]]
        conds = [c for c in dict.fromkeys(conds) if c]
        lines = _wrap(" ‖ ".join(conds)) if conds else []
        lab = "<br>".join(html_esc(x) for x in lines)
        al = []
        if actions and t["acts"]:
            acts = [prettify(x, statemap) for x in t["acts"]]
            acts = [x if len(x) <= 30 else x[:29] + "…" for x in acts]
            al = _wrap(", ".join(acts[:2]) + (f" 等 {len(acts)} 项" if len(acts) > 2 else ""), 30)
            lab += ("<br>" if lab else "") + "<font style='font-size:9px;color:#888888'>/ " + "<br>".join(html_esc(x) for x in al) + "</font>"
        w = max([len(x) * 6.6 for x in lines] + [len(x) * 5.6 for x in al] + [0])
        labs[(a_, b_)] = (lab, w, len(lines) + len(al))
        widest = max(widest, w)
    return labs, widest


def draw_fsm(f, statemap, out, actions=True, png=False, svg=False, scale=None):
    import xml.etree.ElementTree as ET
    R_ = 52
    labs, widest = _fsm_labels(f, statemap, actions)
    DX = int(min(520, max(250, 2 * R_ + widest + 40)))
    pos, mode = fsm_positions(f, DX, 240)
    exits = collections.Counter(a_ for (a_, b_) in f.trans if a_ != b_)
    cells, eid = [], 0
    def vtx(i, val, st, x, y, w, h):
        cells.append(f'<mxCell id="{i}" value="{attr_(val)}" style="{st}" vertex="1" parent="1">'
                     f'<mxGeometry x="{round(x)}" y="{round(y)}" width="{round(w)}" height="{round(h)}" as="geometry"/></mxCell>')
    for n, (v, lit) in f.states.items():
        cx, cy = pos[n]
        final = exits[n] == 0 and any(b_ == n for (_, b_) in f.trans)
        vtx("s_" + n, _state_label(n, lit, n in f.stay and exits[n] > 0), FINAL if final else CIRCLE,
            cx - R_, cy - R_, 2 * R_, 2 * R_)
    centers = {n: pos[n] for n in f.states}
    ccy = sum(y for _, y in centers.values()) / len(centers)
    ymin = min(y for _, y in centers.values()); ymax = max(y for _, y in centers.values())
    def blocked(p, q, skip):
        (x1, y1), (x2, y2) = p, q
        for n, (cx, cy) in centers.items():
            if n in skip: continue
            dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy or 1
            t = max(0, min(1, ((cx - x1) * dx + (cy - y1) * dy) / L2))
            if math.hypot(x1 + t * dx - cx, y1 + t * dy - cy) < R_ + 18: return True
        return False
    def edge(src, dst, label, pts, extra=""):
        nonlocal eid
        g = '<mxGeometry relative="1" as="geometry">' + (
            "<Array as=\"points\">" + "".join(f'<mxPoint x="{round(x)}" y="{round(y)}"/>' for x, y in pts) + "</Array>"
            if pts else "") + "</mxGeometry>"
        cells.append(f'<mxCell id="t{eid}" value="{attr_(label)}" style="{CEDGE}{extra}" edge="1" parent="1" '
                     f'source="{src}" target="{dst}">{g}</mxCell>')
        eid += 1
    if f.init:
        ix, iy = pos[f.init]
        vtx("init", "", "ellipse;html=1;fillColor=#000000;strokeColor=#000000;aspect=fixed;", ix - R_ - 110, iy - 10, 20, 20)
        edge("init", "s_" + f.init, "reset", [])
    pairs = set(f.trans)
    arches = []                                             # (span, a, b) routed over the top / under the bottom
    for (a_, b_), t in f.trans.items():
        lab = labs[(a_, b_)][0]
        if a_ == b_:                                        # explicit self loop: small arc above the circle
            cx, cy = pos[a_]
            edge("s_" + a_, "s_" + b_, lab, [(cx - 34, cy - R_ - 55), (cx + 34, cy - R_ - 55)])
            continue
        p, q = pos[a_], pos[b_]
        two_way = (b_, a_) in pairs
        if not blocked(p, q, {a_, b_}) and not two_way:
            edge("s_" + a_, "s_" + b_, lab, []); continue
        if two_way and not blocked(p, q, {a_, b_}):         # A <-> B: bend each one to its own side
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            dx, dy = q[0] - p[0], q[1] - p[1]; L = math.hypot(dx, dy) or 1
            edge("s_" + a_, "s_" + b_, lab, [(mx - dy / L * 45, my + dx / L * 45)]); continue
        arches.append((abs(p[0] - q[0]), a_, b_))
    lanes = {"top": 0, "bottom": 0}
    for span, a_, b_ in sorted(arches):
        p, q = pos[a_], pos[b_]
        side = "top" if (p[1] + q[1]) / 2 <= ccy else "bottom"
        lab_h = 14 * labs[(a_, b_)][2]
        if side == "top":
            y = ymin - R_ - 70 - lanes["top"] * (40 + lab_h)
        else:
            y = ymax + R_ + 70 + lanes["bottom"] * (40 + lab_h)
        lanes[side] += 1
        sx = p[0] + (R_ * 0.4 if q[0] > p[0] else -R_ * 0.4); tx = q[0] + (-R_ * 0.4 if q[0] > p[0] else R_ * 0.4)
        edge("s_" + a_, "s_" + b_, labs[(a_, b_)][0], [(sx, y), (tx, y)])
    xml = ('<mxfile><diagram id="fsm" name="FSM"><mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" '
           'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1100" '
           'math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells)
           + "</root></mxGraphModel></diagram></mxfile>")
    tree = ET.ElementTree(ET.fromstring(xml)); root = tree.getroot().find(".//root")
    xs, ys = [], []
    for c in root.iter("mxCell"):
        g = c.find("mxGeometry")
        if g is None: continue
        if g.get("x") is not None: xs.append(float(g.get("x"))); ys.append(float(g.get("y")))
        for pt in g.iter("mxPoint"): xs.append(float(pt.get("x"))); ys.append(float(pt.get("y")) - 40)
    sx_, sy_ = 80 - min(xs), 150 - min(ys)
    for c in root.iter("mxCell"):
        g = c.find("mxGeometry")
        if g is None: continue
        if g.get("x") is not None:
            g.set("x", str(round(float(g.get("x")) + sx_))); g.set("y", str(round(float(g.get("y")) + sy_)))
        for pt in g.iter("mxPoint"):
            pt.set("x", str(round(float(pt.get("x")) + sx_))); pt.set("y", str(round(float(pt.get("y")) + sy_)))
    tree.write(out, encoding="utf-8", xml_declaration=True)
    notes = []
    if f.replicated: notes.append(f"每个 <b>{f.replicated}</b> 各有一份这个状态机（{f.var}[{f.replicated}]）")
    for g in f.guards: notes.append("外层条件：" + html_esc(prettify(g, statemap)))
    for k, v in f.defs.items(): notes.append(f"{html_esc(k)} ≡ " + html_esc(prettify(v, statemap)))
    notes.append("无标签的边 = 无条件转移（下一拍）；⟳ = 条件不满足时停留；/ 后为转移时的赋值；双圈 = 终态")
    title = (f"<b>FSM · {f.module}</b>&nbsp;&nbsp;<font style='font-size:11px;color:#888888'>"
             f"状态寄存器 {f.var}{'[' + f.replicated + ']' if f.replicated else ''} · {len(f.states)} 个状态 · "
             f"{len(f.trans)} 条转移</font>")
    annotate(out, title, notes)
    if png or svg: export_png(out, svg, scale, png)


def attr_(v):
    return (v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;"))


def push_routed_labels(path):
    import xml.etree.ElementTree as ET
    tree = ET.parse(path); root = tree.getroot().find(".//root")
    vx = [float(g.get("x")) + float(g.get("width", 0)) / 2 for c in root.findall("mxCell")
          if c.get("vertex") == "1" and (g := c.find("mxGeometry")) is not None and g.get("x")]
    cx = sum(vx) / len(vx) if vx else 0
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if c.get("edge") != "1" or g is None or not c.get("value"): continue
        pts = g.find("Array")
        if pts is None or len(pts) < 2: continue
        px = sum(float(p.get("x")) for p in pts) / len(pts)
        plain = re.sub(r"<[^>]+>", "\n", c.get("value"))
        w = max((len(l) for l in plain.split("\n")), default=10) * 5.0
        side = 1 if px >= cx else -1
        ET.SubElement(g, "mxPoint", x=str(round(side * (w / 2 + 12))), y="0", **{"as": "offset"})
    tree.write(path, encoding="utf-8", xml_declaration=True)


def layout(graph, out):
    gj = out + ".graph.json"
    json.dump(graph, open(gj, "w"), ensure_ascii=False)
    r = subprocess.run([sys.executable, R.require_autolayout(), gj, "-o", out, "--tune"], capture_output=True, text=True)
    os.remove(gj)
    if r.returncode: R.die("autolayout failed:\n" + r.stderr[-1500:])


def annotate(path, title, notes, legend=None):
    import xml.etree.ElementTree as ET
    tree = ET.parse(path); root = tree.getroot().find(".//root")
    xs, ys, xe, ye = [], [], [], []
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if c.get("vertex") == "1" and g is not None and g.get("x") is not None:
            x, y = float(g.get("x")), float(g.get("y"))
            xs.append(x); ys.append(y); xe.append(x + float(g.get("width", 0))); ye.append(y + float(g.get("height", 0)))
    for c in root.findall("mxCell"):
        g = c.find("mxGeometry")
        if c.get("edge") == "1" and g is not None and c.get("parent") == "1":
            for pt in g.iter("mxPoint"):
                if pt.get("as") in (None, "points"):
                    ys.append(float(pt.get("y")) - 45); ye.append(float(pt.get("y")) + 45)
    x0, y0, y1 = min(xs), min(ys), max(ye)
    def cell(i, v, s, x, y, w, h, parent="1"):
        c = ET.SubElement(root, "mxCell", id=i, value=v, style=s, vertex="1", parent=parent)
        ET.SubElement(c, "mxGeometry", x=str(round(x)), y=str(round(y)), width=str(round(w)), height=str(round(h)), **{"as": "geometry"})
    cell("title", title, "text;html=1;align=left;verticalAlign=middle;fontSize=16;", x0, y0 - 60, 1000, 30)
    y = y1 + 40
    if notes:
        h = 16 + 18 * sum(1 + len(n) // 70 for n in notes)
        cell("notes", "<br>".join("• " + n for n in notes),
             "shape=note;size=12;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;align=left;"
             "verticalAlign=top;spacingLeft=8;spacingTop=6;fontSize=11;", x0, y, 560, h)
        y += h + 20
    if legend:
        legend(cell, root, x0, y)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def export_png(path, svg=False, scale=None, png=True):
    from drawio_export import export_all
    export_all(path, png, svg, scale)


# =========================================================================== control-structure map
HS_RE = re.compile(r"(valid|ready|req|ack|grant|busy)", re.I)
CTRL_RE = re.compile(r"(start|done|reset|rst|enable|_en$|^en_|ret|stall|flush|halt|stop|mux|sel|_op$|opcode|write_en|read_en)", re.I)
MAP_STYLE = {
    "fsm":  "rounded=1;arcSize=12;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;fontSize=11;",
    "hasf": "rounded=1;arcSize=12;whiteSpace=wrap;html=1;fillColor=#eef4fc;strokeColor=#6c8ebf;dashed=1;strokeWidth=2;fontSize=11;",
    "plain": "rounded=1;arcSize=12;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#999999;fontSize=11;",
    "in":   "rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#333333;fontSize=11;",
    "out":  "rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#333333;strokeColor=#333333;fontColor=#ffffff;fontSize=11;",
}
MAP_EDGE = {
    "state": "html=1;rounded=0;endArrow=block;endSize=8;strokeColor=#d79b00;strokeWidth=3;fontColor=#b36b00;fontStyle=1;fontSize=10;labelBackgroundColor=#ffffff;",
    "hs":    "html=1;rounded=0;endArrow=block;endSize=7;strokeColor=#3b6fb6;strokeWidth=2;fontColor=#2b5797;fontSize=10;labelBackgroundColor=#ffffff;",
    "ctrl":  "html=1;rounded=0;endArrow=block;endSize=7;strokeColor=#9673a6;dashed=1;fontColor=#7a5a8c;fontSize=10;labelBackgroundColor=#ffffff;",
}


def draw_ctrl(design, fsms, level, out, png=False, svg=False, scale=None):
    mods = design["modules"]
    cands = [n for n in mods if R.base(n) == level]
    if not cands: R.die(f"module {level!r} not in netlist")
    m = mods[cands[0]]
    fsm_by_mod = collections.defaultdict(list)
    for f in fsms: fsm_by_mod[f.module].append(f)
    state_vars = {f.var for f in fsms}

    def inner_fsms(mtype, seen=()):
        b = R.base(mtype)
        res = [f.module for f in fsm_by_mod.get(b, [])]
        if mtype in mods and b not in seen:
            for c in mods[mtype]["cells"].values():
                if not c["type"].startswith("$") or c["type"].startswith("$paramod"):
                    res += inner_fsms(c["type"], seen + (b,))
        return list(dict.fromkeys(res))

    cells, ports = m["cells"], m["ports"]
    bitname = {}
    for n, info in sorted(m["netnames"].items(), key=lambda kv: (kv[0] not in ports, len(kv[0]))):
        if info.get("hide_name"): continue
        for b in info["bits"]:
            if isinstance(b, int) and b not in bitname:
                bitname[b] = re.sub(r"\[\d+\]", "", n.lstrip("\\")).split(".")[-1]
    inst = {cn: c for cn, c in cells.items() if not c["type"].startswith("$") or c["type"].startswith("$paramod")}
    uf = R.UF(); fold = collections.Counter()
    pat = collections.defaultdict(list)
    for cn, c in inst.items(): pat[(R.base(c["type"]), re.sub(r"\[\d+\]", "[*]", cn))].append(cn)
    for g in pat.values():
        for cn in g[1:]: uf.union(g[0], cn)
        fold[uf.find(g[0])] = len(g)
    glob = set()                                            # global clk / reset nets of this level
    for pn, p in ports.items():
        if R.CLK_NAME.match(pn) or re.fullmatch(r"(rst|reset|rst_?n|reset_?n)", pn, re.I):
            glob.update(b for b in p["bits"] if isinstance(b, int))

    drv, snk = {}, collections.defaultdict(list)
    prim_out, prim_in = {}, {}                              # primitive cells: out bit -> cell ; cell -> input bits
    for cn, c in cells.items():
        if cn in inst: continue
        dirs = c.get("port_directions", {})
        ins = []
        for pp, bits in c["connections"].items():
            for b in bits:
                if not isinstance(b, int): continue
                if dirs.get(pp) == "output": prim_out[b] = cn
                elif not re.match(r"^(CLK|ARST|SRST|CLR|SET|.*_CLK|.*_ARST|.*_SRST)$", pp): ins.append(b)
        prim_in[cn] = ins
    for pn, p in ports.items():
        for b in p["bits"]:
            if not isinstance(b, int): continue
            if p["direction"] == "input": drv[b] = ("P:" + pn, pn)
            else: snk[b].append(("P:" + pn, pn))
    for cn, c in inst.items():
        dirs = c.get("port_directions") or {pp: v["direction"] for pp, v in mods.get(c["type"], {}).get("ports", {}).items()}
        for pp, bits in c["connections"].items():
            for b in bits:
                if not isinstance(b, int): continue
                if dirs.get(pp) == "output": drv[b] = (uf.find(cn), pp)
                else: snk[b].append((uf.find(cn), pp))

    def classify(name, dport, src):
        if name in state_vars or dport in state_vars: return "state"
        if HS_RE.search(name) or HS_RE.search(dport): return "hs"
        if CTRL_RE.search(name) or CTRL_RE.search(dport): return "ctrl"
        return None

    agg = collections.defaultdict(lambda: {"bits": set(), "names": collections.Counter()})

    def trace(b, depth=3):
        """sources (node, port, bit) behind a bit driven by primitive cells"""
        out, seen, frontier = [], set(), [b]
        for _ in range(depth):
            nxt = []
            for x in frontier:
                if x in seen or x in glob: continue
                seen.add(x)
                if x in drv: out.append((drv[x][0], drv[x][1], x))
                elif x in prim_out: nxt += prim_in.get(prim_out[x], [])
            frontier = nxt
        return out
    sinks_of = collections.defaultdict(list)                  # bits driven by primitives, read by instances/ports
    for b, lst in snk.items():
        if b in prim_out and b not in drv: sinks_of[b] = lst
    for b, lst in sinks_of.items():
        for dst, sport in lst:
            name = bitname.get(b, sport)
            cls = classify(name, sport, dst)
            if not cls or cls == "state": continue
            for src, dport, sb in trace(b):
                if src == dst: continue
                a = agg[(src, dst, cls)]; a["bits"].add(sb); a["names"][name] += 1

    for b, (src, dport) in drv.items():
        if b in glob: continue
        name = bitname.get(b, dport)
        cls = classify(name, dport, src)
        if not cls: continue
        for dst, sport in snk.get(b, []):
            if dst == src: continue
            a = agg[(src, dst, cls)]; a["bits"].add(b); a["names"][name] += 1

    nodes = {}
    used = {s for s, _, _ in agg} | {t for _, t, _ in agg}
    for r in {uf.find(cn) for cn in inst}:
        c = inst[r]; typ = R.base(c["type"])
        short = re.sub(r"\[\d+\]", "[*]", r).split(".")[-1]
        n = fold.get(r, 1); badge = f" ×{n}" if n > 1 else ""
        own = fsm_by_mod.get(typ, [])
        if own:
            f = own[0]
            order = sorted(f.states.items(), key=lambda kv: (kv[1][0] is None, kv[1][0] or 0))
            chain = " → ".join(k for k, _ in order[:7]) + (" …" if len(order) > 7 else "")
            lab = (f"<b>{short}</b>{badge} <font style='font-size:9px;color:#6c8ebf'>FSM</font><br>"
                   f"<font style='font-size:9px'>{f.var}: {html_esc(chain)}</font>")
            k = "fsm"; w = max(200, 6 * len(chain) + 30)
        else:
            sub = [x for x in inner_fsms(c["type"]) if x != typ]
            if sub:
                lab = f"<b>{short}</b>{badge}<br><font style='font-size:9px'>内含 FSM：{' · '.join(sub)}</font>"
                k = "hasf"; w = max(190, 7 * len(' · '.join(sub)) + 80)
            else:
                lab = f"<b>{short}</b>{badge}<br><font style='font-size:9px;color:#666666'>{typ}</font>"
                k = "plain"; w = max(130, 8 * len(short) + 40)
        nodes[r] = {"id": r, "label": lab, "style": MAP_STYLE[k] + ("shadow=1;" if n > 1 else ""),
                    "width": w, "height": 56}
    for pn, p in ports.items():
        pid = "P:" + pn
        if pid in used:
            k = "in" if p["direction"] == "input" else "out"
            nodes[pid] = {"id": pid, "label": pn, "style": MAP_STYLE[k], "width": max(80, 7 * len(pn) + 24), "height": 28}
    edges, labelled = [], set()
    for (s, t, cls), a in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1])):
        if s not in nodes or t not in nodes: continue
        names = [x for x, _ in a["names"].most_common(1)]
        lab = names[0] + ("…" if len(a["names"]) > 1 else "") if names else ""
        if s.startswith("P:") or t.startswith("P:"): lab = ""
        if lab and (s, lab) in labelled: lab = ""
        elif lab: labelled.add((s, lab))
        edges.append({"source": s, "target": t, "label": lab, "style": MAP_EDGE[cls]})
    graph = {"direction": "LR", "ranksep": 1.1, "nodesep": 0.7, "nodes": list(nodes.values()), "edges": edges}
    layout(graph, out)

    def legend(cell, root, x0, y):
        import xml.etree.ElementTree as ET
        kinds_present = {n["style"] for n in nodes.values()}
        cls_present = {e["style"] for e in edges}
        rows = [(k, t) for k, t in (("fsm", "含状态机的单元（列出状态）"), ("hasf", "子层次里含状态机"),
                ("plain", "无状态机的单元")) if any(v.startswith(MAP_STYLE[k]) for v in kinds_present)]
        erows = [(k, t) for k, t in (("state", "状态广播（FSM 状态寄存器直接输出）"), ("hs", "握手 valid / ready"),
                 ("ctrl", "其他控制：start / done / 使能 / 选择 / 复位")) if MAP_EDGE[k] in cls_present]
        H = 36 + 28 * len(rows) + 24 * len(erows) + 30
        cell("legend", "<b>图例</b>", "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#999999;"
             "verticalAlign=top;align=left;spacingLeft=8;spacingTop=4;fontSize=11;", x0, y, 330, H)
        yy = 30
        for i, (k, t) in enumerate(rows):
            cell(f"lg{i}", "", MAP_STYLE[k], 12, yy + 2, 40, 20, "legend")
            cell(f"lgt{i}", t, "text;html=1;align=left;verticalAlign=middle;fontSize=11;", 62, yy, 260, 24, "legend")
            yy += 28
        for j, (k, t) in enumerate(erows):
            e = ET.SubElement(root, "mxCell", id=f"lge{j}", value="", edge="1", parent="legend", style=MAP_EDGE[k])
            g = ET.SubElement(e, "mxGeometry", relative="1", **{"as": "geometry"})
            ET.SubElement(g, "mxPoint", x="12", y=str(yy + 11), **{"as": "sourcePoint"})
            ET.SubElement(g, "mxPoint", x="52", y=str(yy + 11), **{"as": "targetPoint"})
            cell(f"lget{j}", t, "text;html=1;align=left;verticalAlign=middle;fontSize=10;", 62, yy, 260, 22, "legend")
            yy += 24
        cell("lgnote", "数据总线（地址 / 数据 / 立即数等）已省略；全局 clk / reset 已隐藏",
             "text;html=1;align=left;verticalAlign=middle;fontSize=9;fontColor=#999999;", 10, yy + 2, 310, 20, "legend")

    title = (f"<b>控制结构 · module {level}</b>&nbsp;&nbsp;<font style='font-size:11px;color:#888888'>"
             f"只画控制信号 · {len(nodes)} 个框 · {len(edges)} 条控制连线</font>")
    annotate(out, title, [], legend)
    if png or svg: export_png(out, svg, scale, png)
    return len(nodes), len(edges)


# =========================================================================== CLI
def load(files):
    mods = {}
    for f in files:
        mods.update(modules(open(f, encoding="utf-8", errors="replace").read()))
    return mods


def main():
    ap = argparse.ArgumentParser(description="FSM state diagrams + control-structure map from Verilog/SV")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "fsm", "ctrl"):
        p = sub.add_parser(name); p.add_argument("files", nargs="+")
        if name == "fsm":
            p.add_argument("--module"); p.add_argument("-d", "--outdir", default=".")
            p.add_argument("--png", action="store_true"); p.add_argument("--no-actions", action="store_true")
            p.add_argument("--svg", action="store_true"); p.add_argument("--scale", type=int)
        if name == "ctrl":
            p.add_argument("--top"); p.add_argument("--module", required=True)
            p.add_argument("-o", "--output"); p.add_argument("--png", action="store_true")
            p.add_argument("--svg", action="store_true"); p.add_argument("--scale", type=int)
            p.add_argument("--sv2v", choices=["auto", "always", "never"], default="auto")
    a = ap.parse_args()
    files = [os.path.abspath(f) for f in a.files]
    fsms = extract_fsms(load(files))
    sm = statemap_of(fsms)
    if a.cmd == "list":
        for f in fsms:
            print(f"  {f.module:12s} {f.var + ('[' + f.replicated + ']' if f.replicated else ''):24s} "
                  f"{len(f.states)} 个状态, {len(f.trans)} 条转移  init={f.init}  states={list(f.states)}")
        if not fsms: print("  （没有找到 case(state) 形式的状态机）")
        return
    if a.cmd == "fsm":
        os.makedirs(a.outdir, exist_ok=True)
        sel = [f for f in fsms if not a.module or f.module == a.module]
        if not sel: R.die(f"no FSM found{' in module ' + a.module if a.module else ''}")
        for f in sel:
            out = os.path.join(a.outdir, f"fsm_{f.module}_{f.var}.drawio")
            draw_fsm(f, sm, out, actions=not a.no_actions, png=a.png, svg=a.svg, scale=a.scale)
            print(f"wrote {out}: {len(f.states)} states, {len(f.trans)} transitions", file=sys.stderr)
        return
    with tempfile.TemporaryDirectory(prefix="fsm2drawio-") as wd:
        design, _ = R.frontend(files, a.top, a.sv2v, wd)
    out = a.output or f"ctrl_{a.module}.drawio"
    n, e = draw_ctrl(design, fsms, a.module, out, png=a.png, svg=a.svg, scale=a.scale)
    print(f"wrote {out}: {n} boxes, {e} control edges", file=sys.stderr)


if __name__ == "__main__":
    main()

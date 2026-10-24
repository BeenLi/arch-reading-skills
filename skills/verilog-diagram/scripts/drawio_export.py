#!/usr/bin/env python3
"""Export a .drawio file to PNG / SVG with whatever draw.io binary this machine has.

Used by arch2drawio.py / rtl2drawio.py / fsm2drawio.py, and usable on its own:

  drawio_export.py FIG.drawio [--png] [--svg] [--scale N] [-o OUTBASE]

Binary lookup order (first hit wins):
  $DRAWIO_BIN  ->  `drawio` on PATH  ->  macOS app bundle  ->  ~/.local/opt/drawio (AppImage, extracted)
On Linux with no $DISPLAY the Electron app still needs an X server, so the export is wrapped in
`xvfb-run -a` (system one, or the user-local copy under ~/.local/opt/xvfb) with the sandbox and GPU off.
When no binary is found the caller keeps the .drawio and gets one line on stderr; nothing fails.

Scale: `--scale` > $DRAWIO_SCALE > 3.  draw.io renders at 1 px per model unit; a 1200-unit-wide figure
at scale 3 is a 3600 px PNG, which stays sharp when a Markdown/Obsidian page downsizes it.  SVG has no
scale and is the better choice when the figure goes into a web page.
"""
import argparse, os, platform, shutil, subprocess, sys

DEFAULT_SCALE = 3
TIMEOUT = 180  # s; a wedged Electron must not hang the agent
LOCAL_OPT = os.path.expanduser("~/.local/opt")
MAC_APP = "/Applications/draw.io.app/Contents/MacOS/draw.io"


def find_drawio():
    cands = [os.environ.get("DRAWIO_BIN"), shutil.which("drawio"), MAC_APP,
             os.path.join(LOCAL_OPT, "drawio", "squashfs-root", "AppRun"),
             os.path.join(LOCAL_OPT, "drawio", "drawio.AppImage")]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _xvfb_prefix():
    """Command prefix that gives a Linux export a display when it has none."""
    if platform.system() != "Linux" or os.environ.get("DISPLAY"):
        return [], {}
    local = os.path.join(LOCAL_OPT, "xvfb", "usr", "bin")
    env = {}
    xr = shutil.which("xvfb-run") or (os.path.join(local, "xvfb-run") if os.path.isfile(os.path.join(local, "xvfb-run")) else None)
    if not xr:
        return None, {}
    if os.path.dirname(xr) == local:  # make xvfb-run find its own Xvfb
        env["PATH"] = local + os.pathsep + os.environ.get("PATH", "")
    return [xr, "-a", "-s", "-screen 0 1920x1080x24 -nolisten tcp"], env


def export(drawio_path, fmt="png", scale=None, out=None, border=16):
    """Export `drawio_path` to `fmt` (png|svg|pdf). Returns the output path, or None (reason on stderr)."""
    binary = find_drawio()
    if not binary:
        print(f"note: no draw.io binary found (set DRAWIO_BIN or run ~/.claude/skills/verilog-diagram/scripts/install-drawio-linux.sh); "
              f"kept {drawio_path} only", file=sys.stderr)
        return None
    out = out or os.path.splitext(drawio_path)[0] + "." + fmt
    scale = scale or int(os.environ.get("DRAWIO_SCALE", DEFAULT_SCALE))
    prefix, env_over = _xvfb_prefix()
    if prefix is None:
        print("note: Linux without $DISPLAY and no xvfb-run; run ~/.claude/skills/verilog-diagram/scripts/install-drawio-linux.sh. "
              f"kept {drawio_path} only", file=sys.stderr)
        return None
    cmd = prefix + [binary, "-x", "-f", fmt, "-b", str(border), "-o", out, drawio_path]
    if fmt == "png":
        cmd += ["-s", str(scale)]
    if platform.system() == "Linux":
        cmd += ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
    env = dict(os.environ, **env_over)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        print(f"warning: draw.io export timed out after {TIMEOUT}s; kept {drawio_path}", file=sys.stderr)
        return None
    if r.returncode or not os.path.isfile(out) or os.path.getsize(out) == 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        print(f"warning: draw.io export failed (rc={r.returncode}); kept {drawio_path}\n  " + "\n  ".join(tail),
              file=sys.stderr)
        return None
    print(f"{fmt}: {out}", file=sys.stderr)
    return out


def export_all(drawio_path, png=False, svg=False, scale=None):
    """Convenience for the generators: honour --png / --svg flags."""
    if png: export(drawio_path, "png", scale)
    if svg: export(drawio_path, "svg", scale)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("drawio"); ap.add_argument("--png", action="store_true"); ap.add_argument("--svg", action="store_true")
    ap.add_argument("--pdf", action="store_true"); ap.add_argument("--scale", type=int)
    ap.add_argument("-o", "--output", help="output path (single format only)")
    a = ap.parse_args()
    fmts = [f for f, on in (("png", a.png), ("svg", a.svg), ("pdf", a.pdf)) if on] or ["png"]
    if a.output and len(fmts) > 1: sys.exit("error: -o takes a single format")
    if not find_drawio(): sys.exit("error: no draw.io binary found; set DRAWIO_BIN or run ~/.claude/skills/verilog-diagram/scripts/install-drawio-linux.sh")
    ok = all(export(a.drawio, f, a.scale, a.output if a.output else None) for f in fmts)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

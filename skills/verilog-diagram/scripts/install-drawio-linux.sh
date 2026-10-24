#!/usr/bin/env bash
# Headless draw.io exporter for a Linux box where you have no root and no display.
#
# What it sets up (everything under $HOME, nothing touches the system):
#   ~/.local/opt/drawio/squashfs-root/   drawio-desktop AppImage, extracted (no FUSE needed)
#   ~/.local/opt/xvfb/usr/bin/{Xvfb,xvfb-run}   the Ubuntu/Debian xvfb package, unpacked with dpkg -x
#   ~/.local/bin/drawio                  wrapper: runs the app under xvfb-run -a when $DISPLAY is unset,
#                                        with --no-sandbox --disable-gpu (Electron's sandbox needs
#                                        unprivileged user namespaces, which Ubuntu 24.04 turns off)
#
# Why Xvfb at all: the draw.io CLI (-x) is the Electron desktop app in export mode. It renders the page
# in Chromium and screenshots it, so it needs *an* X display even though no window is ever shown.
# Xvfb is an X server that draws into memory; xvfb-run -a starts one on a free display number,
# runs the command and tears it down.
#
# Assumes the host already has the shared libs the deb depends on (xserver-common, libxfont2, GTK3,
# libnss3 ...). The script checks with ldd and lists anything missing.
#
# Usage: install-drawio-linux.sh [DRAWIO_VERSION]      (default: latest release)
#        DRAWIO_APPIMAGE=/path/to/file.AppImage  reuse an already downloaded AppImage
set -euo pipefail
OPT="$HOME/.local/opt"; BIN="$HOME/.local/bin"
mkdir -p "$OPT/drawio" "$OPT/xvfb" "$BIN"

# ---- 1. drawio-desktop AppImage ---------------------------------------------------------------
cd "$OPT/drawio"
if [ -n "${DRAWIO_APPIMAGE:-}" ] && [ -s "$DRAWIO_APPIMAGE" ]; then
  [ "$DRAWIO_APPIMAGE" -ef drawio.AppImage ] || cp "$DRAWIO_APPIMAGE" drawio.AppImage
elif [ ! -s drawio.AppImage ]; then
  ver="${1:-}"
  if [ -z "$ver" ]; then
    ver=$(curl -fsSL -m 30 https://api.github.com/repos/jgraph/drawio-desktop/releases/latest \
          | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p')
  fi
  url="https://github.com/jgraph/drawio-desktop/releases/download/v${ver}/drawio-x86_64-${ver}.AppImage"
  echo "downloading $url"
  curl -fL --retry 5 --retry-delay 5 -C - -o drawio.AppImage.part "$url"
  mv drawio.AppImage.part drawio.AppImage
fi
chmod +x drawio.AppImage
if [ ! -x squashfs-root/AppRun ]; then
  echo "extracting AppImage (avoids FUSE)"; rm -rf squashfs-root
  ./drawio.AppImage --appimage-extract >/dev/null
fi
missing=$(ldd squashfs-root/drawio 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)
if [ -n "$missing" ]; then
  echo "WARNING: shared libraries missing for drawio (ask the admin for them):"; echo "$missing" | sed 's/^/  /'
fi

# ---- 2. Xvfb without root: unpack the distro package into ~/.local/opt/xvfb ------------------
if ! command -v xvfb-run >/dev/null && [ ! -x "$OPT/xvfb/usr/bin/Xvfb" ]; then
  cd "$OPT/xvfb"
  if command -v apt-get >/dev/null; then
    apt-get download xvfb            # no root needed: downloads the .deb into the cwd
    dpkg -x xvfb_*.deb .
  else
    echo "ERROR: no apt-get; install xvfb some other way or get an admin to install it" >&2; exit 1
  fi
  for p in xserver-common libxfont2 xkb-data xauth; do
    dpkg -s "$p" >/dev/null 2>&1 || echo "WARNING: Xvfb needs package $p, which is not installed"
  done
fi

# ---- 3. wrapper on PATH ------------------------------------------------------------------------
cat > "$BIN/drawio" <<'WRAP'
#!/usr/bin/env bash
# draw.io CLI wrapper: headless-safe. Same arguments as the real binary, e.g.
#   drawio -x -f png -s 3 -b 16 -o fig.png fig.drawio
APP="$HOME/.local/opt/drawio/squashfs-root/AppRun"
XVFB_BIN="$HOME/.local/opt/xvfb/usr/bin"
[ -d "$XVFB_BIN" ] && export PATH="$XVFB_BIN:$PATH"
extra=(--no-sandbox --disable-gpu --disable-dev-shm-usage)
if [ -z "${DISPLAY:-}" ]; then
  exec xvfb-run -a -s "-screen 0 1920x1080x24 -nolisten tcp" "$APP" "$@" "${extra[@]}"
else
  exec "$APP" "$@" "${extra[@]}"
fi
WRAP
chmod +x "$BIN/drawio"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "NOTE: add  export PATH=\"\$HOME/.local/bin:\$PATH\"  to your shell rc";; esac

# ---- 4. smoke test -----------------------------------------------------------------------------
tmp=$(mktemp -d); cat > "$tmp/t.drawio" <<'XML'
<mxfile><diagram name="p"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="2" value="headless ok" style="rounded=1;whiteSpace=wrap;" vertex="1" parent="1"><mxGeometry x="20" y="20" width="160" height="60" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>
XML
if "$BIN/drawio" -x -f png -s 3 -b 16 -o "$tmp/t.png" "$tmp/t.drawio" >/dev/null 2>&1 && [ -s "$tmp/t.png" ]; then
  echo "OK: headless export works -> $(file -b "$tmp/t.png" | cut -d, -f1-2)"
else
  echo "FAILED: export smoke test; run with DISPLAY unset:  $BIN/drawio -x -f png -o /tmp/t.png $tmp/t.drawio" >&2; exit 1
fi
rm -rf "$tmp"

#!/usr/bin/env bash
# Install a user-level unzip (Python zipfile) wrapper for the hermes (non-root) user.
# Needed because Composio's installer requires `command -v unzip` and calls
#   unzip -oqd "<dir>" "<archive>"
# and this box runs as uid 10000 (hermes) with no sudo.
set -euo pipefail
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
cat > "$BIN/unzip" <<'PY'
#!/usr/bin/env python3
import sys, os, zipfile
def main():
    argv = sys.argv[1:]
    dest = "."
    files = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("-"):
            flags = a.lstrip("-")
            if not flags:
                i += 1; continue
            if "d" in flags:
                # -d (even combined e.g. -oqd) consumes the NEXT arg as the destination dir
                if i + 1 < len(argv):
                    dest = argv[i + 1]; i += 2
                else:
                    i += 1
                continue
            i += 1
            continue
        files.append(a); i += 1
    if not files:
        sys.stderr.write("unzip: no archive specified\n"); return 1
    archive = files[-1]
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    return 0
sys.exit(main())
PY
chmod +x "$BIN/unzip"
# persist on PATH for future login shells
if ! grep -q "$BIN" "$HOME/.bashrc" 2>/dev/null; then
  echo "export PATH=\"$BIN:\$PATH\"" >> "$HOME/.bashrc"
fi
export PATH="$BIN:$PATH"
echo "unzip wrapper installed at $BIN/unzip"
command -v unzip

#!/usr/bin/env python3
"""scan_tree.py — árbol de carpetas local (VPS / repos).

Uso:
  python3 scan_tree.py /ruta/raiz            # solo carpetas
  python3 scan_tree.py /ruta/raiz -f         # carpetas + archivos
  python3 scan_tree.py /ruta/raiz --depth 3  # profundidad máxima
  python3 scan_tree.py /ruta/raiz --json     # salida JSON (rutas absolutas)

Flags de "nombres genéricos": nueva, nuevo, final, final2, copia, copy,
sin nombre, untitled, aqui, misc, otros, varios, tmp, temp, test, prueba.
"""
import argparse
import json
import os
import sys

GENERIC = {"nueva", "nuevo", "final", "final2", "copia", "copy", "sin nombre",
           "untitled", "aqui", "misc", "otros", "varios", "tmp", "temp",
           "test", "prueba", "descargas", "downloads"}


def collect(root, max_depth, with_files, depth=0):
    """Devuelve lista de dicts: {path, type, depth, name}."""
    entries = []
    try:
        names = sorted(os.listdir(root))
    except OSError as e:
        return entries
    for name in names:
        full = os.path.join(root, name)
        if name.startswith("."):
            continue
        is_dir = os.path.isdir(full)
        if max_depth is not None and depth >= max_depth and is_dir:
            entries.append({"path": full, "type": "dir", "depth": depth, "name": name})
            continue
        if not is_dir and not with_files:
            continue
        entries.append({"path": full, "type": "dir" if is_dir else "file",
                        "depth": depth, "name": name})
        if is_dir:
            entries.extend(collect(full, max_depth, with_files, depth + 1))
    return entries


def tree_lines(entries):
    lines = []
    for e in entries:
        prefix = "  " * e["depth"] + ("📁 " if e["type"] == "dir" else "📄 ")
        lines.append(prefix + e["name"])
    return lines


def main():
    ap = argparse.ArgumentParser(description="Árbol de carpetas local")
    ap.add_argument("root", help="Ruta raíz a escanear")
    ap.add_argument("-f", "--files", action="store_true", help="Incluir archivos")
    ap.add_argument("--depth", type=int, default=None, help="Profundidad máxima")
    ap.add_argument("--json", action="store_true", help="Salida JSON")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.exit(f"ERROR: no existe la raíz: {args.root}")

    entries = collect(args.root, args.depth, args.files)

    if args.json:
        print(json.dumps(
            {"root": args.root, "entries": entries,
             "generic": [e["path"] for e in entries
                         if e["type"] == "dir" and e["name"].lower() in GENERIC]},
            ensure_ascii=False, indent=2))
        return

    print(f"# Árbol: {args.root}\n")
    print("\n".join(tree_lines(entries)))
    gen = [e["path"] for e in entries
           if e["type"] == "dir" and e["name"].lower() in GENERIC]
    if gen:
        print("\n⚠️  NOMBRES GENÉRICOS detectados (revisar si necesitan registro):")
        for g in gen:
            print(f"  - {g}")
    print(f"\n{len([e for e in entries if e['type']=='dir'])} carpetas, "
          f"{len([e for e in entries if e['type']=='file'])} archivos")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""find_duplicate_skill_names.py — detecta nombres de skill duplicados.

Uso:  python3 find_duplicate_skill_names.py [root ...]
      default: /opt/data/skills  /opt/data/home/.hermes/skills

Recorre cada root, agrupa los SKILL.md por el `name` de su frontmatter (si no hay
frontmatter usa el nombre de la carpeta) y reporta los nombres con MAS DE UNA copia.

Por que importa: un nombre duplicado hace que pedirlo "pelado" devuelva
`Ambiguous skill name` y que el cron/agente corra degradado EN SILENCIO.

Exit 0 = sin duplicados | exit 1 = hay duplicados (sirve como watchdog).
"""
import os
import re
import sys
from collections import defaultdict

ROOTS = sys.argv[1:] or ["/opt/data/skills", "/opt/data/home/.hermes/skills"]
NAME_RE = re.compile(r"^name:\s*[\"']?([^\"'\n]+)", re.M)
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".archive", ".curator_backups",
    "references", "templates", "assets", "scripts", "graphify-out",
}


def skill_name(path, fallback):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
    except OSError:
        return fallback
    match = NAME_RE.search(head)
    return match.group(1).strip() if match else fallback


def scan(root):
    found = defaultdict(list)
    if not os.path.isdir(root):
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "SKILL.md" in filenames:
            path = os.path.join(dirpath, "SKILL.md")
            found[skill_name(path, os.path.basename(dirpath))].append(path)
    return found


def main():
    total = 0
    for root in ROOTS:
        found = scan(root)
        dups = {n: p for n, p in found.items() if len(p) > 1}
        print(f"=== {root}  (skills={len(found)}, duplicados={len(dups)})")
        for name in sorted(dups):
            total += 1
            print(f"  {name}")
            for path in dups[name]:
                print(f"     {path}")
    print(f"TOTAL nombres duplicados: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

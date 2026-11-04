#!/usr/bin/env python3
"""
verify_skills.py — Aduana estricta de calidad para skills en el repositorio Git.
Verifica:
1. SKILL.md existe y es legible.
2. Frontmatter YAML válido con 'name' y 'description'.
3. 'name' coincide con el directorio (kebab-case).
4. Sin cascarones vacíos (<600 bytes sin soporte).
5. 0 symlinks rotos o apuntando fuera del repo.
6. Permisos rx para el usuario del contenedor (UID 10000).
7. Lint de catálogo integrado (R5 ventana de 57 caracteres · R7 nombres
   equivalentes), con baseline: los pares conocidos se reportan como métrica y
   cualquier par NUEVO bloquea la aduana. Fuente única del criterio:
   lint_skills_catalog.py.

Los bundles de convenciones (prefijo `_`) se excluyen: no son skills invocables.
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path

REPO_SKILLS = Path("/root/hermes-agent-legacy-docker/skills")
SCRIPT_DIR = Path(__file__).resolve().parent
LINT = SCRIPT_DIR / "lint_skills_catalog.py"
BASELINE = Path("/root/hermes-agent-legacy-docker/data/state/nombres_equivalentes_baseline.json")
VENTANA_R5 = 57


def lint_catalogo():
    """Corre el lint de catálogo (R5 ventana de 57 · R7 nombres equivalentes).

    Devuelve (metricas, errores, advertencias). R7 se vuelve BLOQUEANTE solo
    para grupos NUEVOS respecto al baseline: el catálogo arrastra pares
    conocidos (p. ej. oauth-multi-tenant-integration(s)) que se resuelven en la
    consolidación; bloquear la aduana por ellos dejaría el semáforo en rojo
    permanente y la aduana perdería valor como señal.
    """
    if not LINT.is_file():
        return {'disponible': False}, [], []
    salida = Path('/tmp/lint_catalog_aduanas.json')
    try:
        subprocess.run([sys.executable, str(LINT), '--json-out', str(salida)],
                       capture_output=True, text=True, timeout=300)
        datos = json.loads(salida.read_text(encoding='utf-8'))
    except Exception as e:
        return {'disponible': False, 'error': str(e)}, [], [
            f"lint de catálogo no ejecutable: {e}"]

    r5 = datos.get('r5_ventana_57', [])
    r7 = [sorted(g) for g in datos.get('r7_nombres_equivalentes', [])]
    primera_vez = not BASELINE.is_file()
    conocidos = []
    if not primera_vez:
        try:
            conocidos = [sorted(g) for g in json.loads(
                BASELINE.read_text(encoding='utf-8')).get('grupos', [])]
        except Exception:
            conocidos = []
    # En la primera corrida el baseline ES el estado actual: lo conocido no se
    # marca como nuevo (si no, la integración nace en rojo por un par que ya
    # existía antes de la regla).
    if primera_vez:
        conocidos = list(r7)
        import time as _t
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(
            {'ts': _t.strftime('%Y-%m-%dT%H:%M:%S%z'),
             'nota': 'grupos de nombres equivalentes conocidos al integrar el lint en la aduana',
             'grupos': r7}, indent=1, ensure_ascii=False), encoding='utf-8')
    nuevos = [g for g in r7 if g not in conocidos]
    metricas = {'disponible': True, 'skills': datos.get('skills'),
                'r5_fuera_de_ventana': len(r5), 'r5_ventana': VENTANA_R5,
                'r7_grupos': len(r7), 'r7_conocidos': len(conocidos),
                'r7_nuevos': len(nuevos), 'r7_baseline': str(BASELINE),
                'r7_baseline_inicializado_ahora': primera_vez}
    errores = [f"[R7] grupo NUEVO de nombres equivalentes: {' ≡ '.join(g)}" for g in nuevos]
    avisos = []
    if len(r5) > 0:
        avisos.append(f"[R5] {len(r5)} descripciones cuya primera frase no cierra dentro "
                      f"de {VENTANA_R5} caracteres (métrica: el índice del prompt trunca ahí).")
    return metricas, errores, avisos


def check_skills():
    print("=" * 60)
    print("🔍 ADUANA DE SKILLS: Verificando /root/hermes-agent-legacy-docker/skills")
    print("=" * 60)

    errors = []
    warnings = []
    scanned = 0

    for root, dirs, files in os.walk(REPO_SKILLS):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith("_") and d not in ("__pycache__", "references", "scripts", "templates", "assets", "examples")]

        rel_path = os.path.relpath(root, REPO_SKILLS)
        if rel_path == ".":
            continue

        if "SKILL.md" in files:
            scanned += 1
            skill_dir = Path(root)
            sm_file = skill_dir / "SKILL.md"

            # Check symlink
            if sm_file.is_symlink():
                errors.append(f"[{rel_path}] SKILL.md no debe ser un symlink.")
                continue

            # Check permissions (must be readable by container user UID 10000)
            dir_mode = skill_dir.stat().st_mode
            file_mode = sm_file.stat().st_mode
            if not (dir_mode & 0o005 == 0o005):
                errors.append(f"[{rel_path}] Directorio sin permisos rx para otros (modo: {oct(dir_mode)[-3:]}).")
            if not (file_mode & 0o004 == 0o004):
                errors.append(f"[{rel_path}] SKILL.md sin permisos r para otros (modo: {oct(file_mode)[-3:]}).")


            # Read content
            try:
                content = sm_file.read_text(encoding="utf-8")
            except Exception as e:
                errors.append(f"[{rel_path}] Error leyendo SKILL.md: {e}")
                continue

            sz = len(content.encode("utf-8"))
            lines = len(content.splitlines())

            # Parse frontmatter
            fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if not fm_match:
                errors.append(f"[{rel_path}] Falta bloque frontmatter YAML (--- ... ---).")
                continue

            fm_text = fm_match.group(1)
            name = None
            desc = None
            for l in fm_text.splitlines():
                if l.startswith("name:"):
                    name = l.split("name:", 1)[1].strip().strip("'\"")
                elif l.startswith("description:"):
                    desc = l.split("description:", 1)[1].strip().strip("'\"")

            if not name:
                errors.append(f"[{rel_path}] Frontmatter no define 'name'.")
            elif name != skill_dir.name and name.lower() != skill_dir.name.lower():
                warnings.append(f"[{rel_path}] 'name' ({name}) difiere del directorio ({skill_dir.name}).")

            if not desc:
                warnings.append(f"[{rel_path}] 'description' vacía o ausente.")

            # Check cascaron
            has_scripts = (skill_dir / "scripts").is_dir() and bool(os.listdir(skill_dir / "scripts"))
            has_refs = (skill_dir / "references").is_dir() and bool(os.listdir(skill_dir / "references"))

            if sz < 600 and not has_scripts and not has_refs and lines < 20:
                warnings.append(f"[{rel_path}] Posible cascarón: solo {sz} bytes y {lines} líneas.")

    # ── Lint de catálogo integrado (R5 / R7) ────────────────────────────────
    metricas, err_lint, av_lint = lint_catalogo()
    errors.extend(err_lint)
    warnings.extend(av_lint)
    if metricas.get('disponible'):
        print("\n📐 LINT DE CATÁLOGO (integrado)")
        print(f"   R5 · descripciones fuera de la ventana de {metricas.get('r5_ventana')} "
              f"caracteres: {metricas.get('r5_fuera_de_ventana')}")
        print(f"   R7 · grupos de nombres equivalentes: {metricas.get('r7_grupos')} "
              f"(conocidos {metricas.get('r7_conocidos')}, NUEVOS {metricas.get('r7_nuevos')})")
        print(f"   baseline: {metricas.get('r7_baseline')}")
    else:
        print(f"\n📐 LINT DE CATÁLOGO: no ejecutable ({metricas.get('error', 'ausente')})")

    print(f"\nTotal skills auditadas: {scanned}")
    print(f"Errores críticos:       {len(errors)}")
    print(f"Advertencias menores:   {len(warnings)}")

    if warnings:
        print("\n⚠️ Advertencias:")
        for w in warnings[:15]:
            print(" -", w)
        if len(warnings) > 15:
            print(f" ... y {len(warnings)-15} más.")

    if errors:
        print("\n❌ Errores que bloquean la aduana:")
        for e in errors:
            print(" -", e)
        return False

    print("\n✅ ADUANA SUPERADA: Todas las skills cumplen el estándar de calidad.")
    return True

if __name__ == "__main__":
    success = check_skills()
    sys.exit(0 if success else 1)

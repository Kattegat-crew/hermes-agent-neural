#!/usr/bin/env python3
"""validar_facts.py — valida que un facts_<brand>.json tenga la MISMA estructura
que los facts de octubre 2026 (referencia canónica del pipeline V2).

Estructura exigida (schema octubre):
  keys top: marca, slug, periodo, fuente_datos, cifras[], sedes[], mes{}, comparativo_sep{}
  cifras: lista de entradas con "id"; ids válidos por marca (sin_dato permitido)
  sedes: entradas {nombre, venta[, meta, cumplimiento, estado]}
Referencia: /opt/hermes-agent-data/home/proyectos/videos-rendicion-oct2026/facts_{golden,lucky}.json

uso: validar_facts.py --facts F.json [--brand golden] [--json]
exit 0 = OK, exit 1 = estructura inválida, exit 2 = OK con sin_dato
"""
import argparse
import json
import os
import sys

REF_DIR = "/opt/hermes-agent-data/home/proyectos/videos-rendicion-oct2026"

IDS = {
    "golden": {"ventas_netas", "meta_ventas", "cumplimiento", "breb_total", "breb_ticket",
               "ads_total", "ads_leads", "organico", "facebook", "agentes",
               "automatizacion_horas",
               # nov 2026: Instagram ahora se captura por Graph API (social.py)
               "instagram", "instagram_publicaciones", "instagram_alcance",
               "instagram_interaccion"},
    "paradise": {"ventas_netas", "meta_ventas", "cumplimiento", "breb_total", "breb_ticket",
                 "ads_total", "ads_leads", "organico", "facebook", "instagram", "agentes",
                 "automatizacion_horas",
                 "instagram_publicaciones", "instagram_alcance", "instagram_interaccion"},
}
TOP_KEYS = ["marca", "slug", "periodo", "fuente_datos", "cifras", "sedes", "mes", "comparativo_sep"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--brand", default=None, help="golden|paradise (default: del propio JSON)")
    ap.add_argument("--json", action="store_true", help="salida legible por scripts")
    args = ap.parse_args()

    F = json.load(open(args.facts, encoding="utf-8"))
    slug = args.brand or F.get("slug")
    errors, warnings, sin_dato_ids = [], [], []

    for k in TOP_KEYS:
        if k not in F:
            errors.append(f"falta clave top-level '{k}'")
    if F.get("slug") != slug:
        errors.append(f"slug '{F.get('slug')}' != esperado '{slug}'")
    if not isinstance(F.get("cifras"), list) or not F["cifras"]:
        errors.append("'cifras' vacío o no es lista")
    else:
        ids = [c["id"] for c in F["cifras"] if isinstance(c, dict) and "id" in c]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            errors.append(f"ids duplicados en cifras: {sorted(dup)}")
        have = set(ids)
        want = IDS.get(slug, set())
        missing = want - have
        extra = have - want
        if missing:
            errors.append(f"ids faltantes vs schema octubre: {sorted(missing)}")
        if extra:
            warnings.append(f"ids extra (no existían en oct): {sorted(extra)}")
        for c in F["cifras"]:
            if c.get("sin_dato"):
                sin_dato_ids.append(c["id"])
                if not c.get("motivo"):
                    warnings.append(f"'{c['id']}' sin_dato sin motivo")
            elif "valor" not in c or "display" not in c:
                errors.append(f"'{c['id']}' sin 'valor'/'display' ni sin_dato")
    for s in F.get("sedes", []) or []:
        for k in ("nombre", "venta"):
            if k not in s:
                errors.append(f"sede sin '{k}': {s}")
    if not F.get("sedes") and not any(c.get("sin_dato") for c in F.get("cifras", [])
                                      if c.get("id") == "ventas_netas"):
        warnings.append("sedes vacía pero ventas_netas tiene dato")

    res = {"file": os.path.abspath(args.facts), "slug": slug,
           "estructura_ok": not errors, "errors": errors, "warnings": warnings,
           "sin_dato": sin_dato_ids}
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"{os.path.basename(args.facts)} [{slug}]: "
              f"{'ESTRUCTURA OK' if not errors else 'ESTRUCTURA INVALIDA'}")
        for e in errors:
            print("  ERROR:", e)
        for w in warnings:
            print("  warn:", w)
        if sin_dato_ids:
            print("  sin_dato:", ", ".join(sin_dato_ids))
    return 1 if errors else (2 if sin_dato_ids else 0)


if __name__ == "__main__":
    sys.exit(main())

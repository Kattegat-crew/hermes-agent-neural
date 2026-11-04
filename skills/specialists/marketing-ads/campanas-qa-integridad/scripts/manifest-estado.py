#!/usr/bin/env python3
"""
Manifest de handoff (Fase E) — genera estado.json por campaña a partir del
campaign.yaml (contrato único). Cada pieza lleva su etapa de pipeline:
  contrato → bragi (copys) → sindri (visual) → review (gate) → freyja (publicación)

Uso:
  manifest-estado.py <campaign.yaml> [--output DIR] [--etapa ETAPA] [--estado ESTADO]

Salida: <output>/estado.json — el contrato de handoff que leen los bots
(Bragi escribe hooks/CTAs; Review aprueba; Freyja solo publica aprobadas).
Compatibilidad: lee `piezas` a nivel raíz O bajo `campaign.` (dual-location).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ETAPAS = ["contrato", "bragi", "sindri", "review", "freyja", "publicada"]


def load_campaign(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def _get_piezas(data: dict) -> list:
    for src in (data.get("campaign", {}), data):
        p = src.get("piezas", []) or []
        if p:
            return p
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera estado.json de handoff por campaña")
    parser.add_argument("yaml_file", help="Path a campaign.yaml")
    parser.add_argument("--output", "-o", default=None, help="Directorio de salida (default: junto al yaml, carpeta docs/)")
    parser.add_argument("--etapa", default="contrato", choices=ETAPAS, help="Etapa inicial de las piezas (default: contrato)")
    parser.add_argument("--estado", default="draft", choices=["draft", "listo", "aprobada", "requiere-ajustes"],
                        help="Estado inicial (default: draft)")
    args = parser.parse_args()

    yaml_path = Path(args.yaml_file).resolve()
    if not yaml_path.exists():
        print(f"ERROR: no existe {yaml_path}", file=sys.stderr)
        return 2

    data = load_campaign(yaml_path)
    campaign = data.get("campaign", {})
    piezas = _get_piezas(data)
    slug = campaign.get("slug", yaml_path.stem)
    version = campaign.get("version", "v0")

    # Cada pieza del contrato → fila de handoff
    piezas_estado = []
    for p in piezas:
        piezas_estado.append({
            "id": p.get("id", "?"),
            "tipo": p.get("tipo", ""),
            "etapa": args.etapa,
            "estado": args.estado,
            "hook": p.get("hook", ""),
            "cta": p.get("cta", ""),
            "evidencia": "",
            "aprobada_en": "",
            "publicada_en": "",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

    manifest = {
        "campaña": slug,
        "version_contrato": version,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_piezas": len(piezas_estado),
        "piezas": piezas_estado,
    }

    out_dir = args.output or (yaml_path.parent / "docs")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "estado.json"
    out_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Manifest → {out_file}")
    print(f"  {slug} | version {version} | {len(piezas_estado)} piezas en etapa '{args.etapa}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
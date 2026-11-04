#!/usr/bin/env python3
"""
rotate_model_yaml.py — Rota model.default y SÍNCroniza el catálogo de modelos en
providers.NaN-Builders.models y custom_providers (bloque NaN-Builders) de un
config.yaml, manipulando el YAML como datos (dict) y validando el YAML de salida.

Uso:
  rotate_model_yaml.py <config.yaml> <modelo> [--ctx <id> <contexto> ...]
  # --ctx añade modelos al catálogo (id + context_length), p.ej.:
  # python3 rotate_model_yaml.py /opt/data/config.yaml qwen3.8-flash \
  #     --ctx qwen3.8-flash 262144 --ctx glm5.3-flash 131072

Validado 26/08/2026 (14 perfiles local+prod rotados a qwen3.8-flash).
Precaución: NO edites config.yaml por regex/strings — rompe el YAML.
"""
import sys
import shutil
import datetime
import yaml


def backup(path):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    shutil.copy2(path, bak)
    return bak


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    path, model = sys.argv[1], sys.argv[2]

    ctx_map = {}
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--ctx" and i + 2 < len(sys.argv):
            ctx_map[sys.argv[i + 1]] = int(sys.argv[i + 2])
            i += 3
        else:
            i += 1

    with open(path) as f:
        data = yaml.safe_load(f)

    # 1. Rotar default
    if "model" not in data or not isinstance(data["model"], dict):
        print("ERROR: sin bloque model:", path); sys.exit(1)
    old = data["model"].get("default")
    data["model"]["default"] = model

    # 2. Registrar en providers.NaN-Builders.models (si existe)
    provs = data.get("providers") or {}
    nan = provs.get("NaN-Builders")
    if nan and isinstance(nan, dict):
        models = nan.setdefault("models", {})
        for mid, ctx in ctx_map.items():
            if mid not in models:
                models[mid] = {"context_length": ctx, "name": mid}

    # 3. Sincronizar custom_providers (bloque con name: NaN-Builders) SOLO si existe
    cps = data.get("custom_providers") or []
    if isinstance(cps, list):
        for cp in cps:
            if isinstance(cp, dict) and cp.get("name") == "NaN-Builders":
                cmodels = cp.setdefault("models", {})
                for mid, ctx in ctx_map.items():
                    if mid not in cmodels:
                        cmodels[mid] = {"context_length": ctx}

    # Validar el YAML de salida antes de escribir
    out = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    try:
        yaml.safe_load(out)
    except Exception as e:
        print("ERROR: YAML de salida inválido:", e); sys.exit(1)

    bak = backup(path)
    with open(path, "w") as f:
        f.write(out)

    print(f"Backup: {bak}")
    print(f"default: {old} -> {model}")
    for mid, ctx in ctx_map.items():
        print(f"catálogo: {mid} ctx={ctx}")


if __name__ == "__main__":
    main()
#!/usr/bin/env bash
# consolidar_facts.sh — compila facts_<marca>.json del mes anterior desde las fuentes reales.
# Nunca inventa cifras: lo que no se obtiene queda marcado {"sin_dato": true}.
# uso: consolidar_facts.sh [--mes YYYY-MM] [--brand golden,lucky] [--outdir DIR] [--inputs DIR]
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY=python3
# python-docx no se usa aquí; stdlib only para consolidar
exec $PY "$DIR/consolidar_facts.py" "$@"

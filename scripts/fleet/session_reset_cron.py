#!/usr/bin/env python3
"""Wrapper para el cron `reset-sesion` (F1.5). El scheduler no pasa argumentos al script:
aquí se invoca session_reset.py con el modo de producción —
  --clientes --apply --quiet (silencio si todo va bien) y la guarda de memoria activa.
El job es no_agent: 0 tokens. Si algo falla, el script imprime el problema y el
`failure_deliver` del job lo manda al chat del Admin.

El umbral de tokens va EXPLÍCITO (300 k, sin exigir hora de inactividad): si un día cambia el
valor por defecto del script, producción no debe cambiar de comportamiento sin que nadie lo decida.
"""
import os
import runpy
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [
    os.path.join(BASE, "session_reset.py"),
    "--clientes",
    "--apply",
    "--quiet",
    "--memory-max-hours", "20",
    "--max-tokens", "300000",
]
runpy.run_path(os.path.join(BASE, "session_reset.py"), run_name="__main__")

# Recuperación del entorno de dependencias PM (facts.json) y bootstrap de worktrees

Verificado en DEV, 03-nov-2026, durante las reparaciones Langfuse F2/F3 y capability-claim-guard.

## Síntoma
`RuntimeError: cannot read dependency environment: /opt/hermes-agent-data/installs/<hash>/facts.json`

Bloquea:
- Spawn de workers Kanban asignados a cualquier perfil (fallos repetidos de spawn, "pid gone").
- El backend de terminal del propio agente (toda ejecución de shell falla antes de correr el comando).

## Diagnóstico y recuperación (verificado, exit 0)
1. Desde `/opt/hermes-agent`: `python3 -m pm.cli doctor` (con entorno limpio: `env -u PYTHONPATH -u VIRTUAL_ENV`).
2. Verificar que cada `installs/<hash>/facts.json` referenciado existe, es JSON válido y el `venv` seleccionado existe en disco (leer el `selected`/generation dentro del facts).
3. Smoke test por perfil afectado, desde `/opt/hermes-agent`: `hermes -p <perfil> --version`.
4. NO editar `facts.json` a mano, NO `chmod/chown` sobre `installs/` (protegido). Si doctor no lo repara, escalar a Chucho con evidencia, no forzar.

## Ejecutar pruebas cuando falla la auto-activación del runner
Si `scripts/run_tests.sh` falla con PermissionError sobre stamps root-owned (`inputs/` del test-environment), NO forzar permisos. Usar el override documentado `HERMES_PYTHON` apuntando al venv del test-env ya gestionado por PM:

```bash
# 1. Resolver el test-env del repo:
python3 -c "from pathlib import Path; from pm.testenv import testenv_root; print(testenv_root(Path('/ruta/repo')))"
# 2. Leer <testenv>/active.json -> "generation"
# 3. Ejecutar con el venv de esa generación:
env -u PYTHONPATH -u __HERMES_ACTIVATED \
  HERMES_PYTHON=<testenv>/gen-<generation>/venv/bin/python \
  scripts/run_tests.sh tests/... -q
```

Esto es runner oficial, no bare pytest; verificó 50/50 tests del guard con esta ruta.

## Worktree para tareas Kanban: bootstrap ANTES de despachar
Un worktree git nuevo creado para asignar tareas a un perfil worker necesita su entorno de dependencias PM preparado antes del dispatch. Si se despacha sin él, el worker crashea al arrancar (crash-loop) y el dispatcher re-encola en bucle. Verificar con el smoke test del paso 3 del diagnóstico usando el launcher del worktree antes de crear/asignar la tarea.

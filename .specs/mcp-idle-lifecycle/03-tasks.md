# Task Breakdown: MCP idle lifecycle policy

* **Branch**: `feat/mcp-idle-lifecycle`
* **Worktree**: `/opt/hermes-agent-data/worktrees/mcp-idle-lifecycle`
* **Base**: `prod-stable` @ `d04667851e`

## Skills atribuidas

| Tarea | Skill |
|---|---|
| T1–T3 | `python-patterns` |
| T4 | `python-testing-patterns` |
| T5 | `code-review-and-quality` |
| T6 | `hermes-agent` |

## Tareas

- [x] **T1 · Spec y diseño**
  - Verificación: `.specs/mcp-idle-lifecycle/{01-spec,02-design}.md` con Goals/Non-Goals, criterios
    Given-When-Then, contrato de precedencia con el núcleo e invariantes.
  - Dep: —

- [x] **T2 · Funciones puras (`collect_targets`, `http_servers`, `current_idle`, `apply_policy`)**
  - Verificación: `pytest tests/scripts/test_mcp_idle_policy.py -q`
  - Dep: T1

- [x] **T3 · CLI y escritura round-trip**
  - Verificación: `python3 scripts/check_config_yaml_writers.py scripts/mcp_idle_policy.py` → `OK`
  - Verificación: `python3 scripts/check_config_yaml_readers.py scripts/mcp_idle_policy.py` → `OK`
  - Dep: T2

- [x] **T4 · Tests (TDD)**
  - Verificación: `pytest tests/scripts/test_mcp_idle_policy.py -q` → **24 passed**
  - Cobertura: alta de clave top-level, precedencia top-level vs `lifecycle`, conflicto sincronizado,
    claves ajenas preservadas, idempotencia byte a byte + mtime, expiración de `lifecycle` solo,
    valores inválidos ignorados, `0` desactiva, HTTP omitido, filtro `--servers`, `--dry-run`,
    `--check` (0/3), `--dry-run`+`--check` excluyentes, config sin `mcp_servers` (2), YAML ilegible (2),
    idle negativo (2), archivo inexistente (2), fallo de escritura (4).
  - Dep: T1

- [x] **T5 · Revisión por fase con `opencode` + `deepseek-v4.1-flash`**
  - Ronda 1 (2026-11-13): **FAIL** — B1 precedencia invertida, M1 HTTP, M2 proceso SDD, M3 cobertura.
    Todo corregido: precedencia replicada del núcleo, HTTP excluido, spec/design/tasks al día, +12 tests.
  - Ronda 2 (2026-11-13): **PASS** — B1/M1/M2/M3/m1/m3/m5 RESUELTOS. Follow-ups menores cerrados
    (N1 url+command, N3 sync de lifecycle, N4 nombres no-string, N5 referencias, N6 `-> None`).
  - Dep: T3, T4

- [ ] **T6 · Aplicación en producción (requiere autorización explícita; NO reinicia servicios)**
  - `python3 scripts/mcp_idle_policy.py --config /opt/hermes-agent-data/profiles/default/config.yaml --idle-seconds 200 --dry-run`
  - Aplicar (sin flags de modo) y luego `--check` → exit 0
  - El efecto se observa en el siguiente arranque del gateway; **no se reinicia nada sin orden del Admin**.
  - Dep: T5

## Fuera de alcance de este PR

- Sustituir envoltorios `npm exec` por binarios (fase 2 del plan operativo).
- Guardarraíl de cgroup (cubierto por los vigías existentes).
- Cualquier `git push` o apertura de PR (requiere autorización).

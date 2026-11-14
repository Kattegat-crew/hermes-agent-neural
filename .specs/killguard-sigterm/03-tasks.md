# Implementation Tasks: HERMES-KILLGUARD — señalización con identidad verificada

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed

---

## Execution Guidelines
1. **TDD First**: los tests existen y fallan sobre la base sin el guard (RED medido).
2. **Atomic Verification**: cada tarea se marcó solo después de correr su verificación.
3. **No Batching**: sin cambios fuera de los 4 archivos del alcance.

---

## Task Checklist

### Phase 1: Test Scaffolding & Interfaces
- [x] **Task 1.1**: Tests de contrato en `tests/cron/test_killguard_signal_guard.py`
      (presencia del módulo, wrap en los dos sitios de señalización, reciclaje rechazado,
      entrega legítima, rama `os.kill(pid)`, techo del set).
  - *Target Files*: `tests/cron/test_killguard_signal_guard.py`
  - *Verification*: `pytest tests/cron/test_killguard_signal_guard.py -q` → **RED 8 failed**
    sobre `prod-stable` sin el parche (ejecutado antes de escribir el código).

### Phase 2: Core Domain Logic
- [x] **Task 2.1**: `agent/killguard.py` con `proc_starttime`, `_caller`, `log_signal`,
      `safe_killpg` y `safe_kill` (type hints y docstrings completos).
  - *Target Files*: `agent/killguard.py`
  - *Verification*: `python3 -m py_compile agent/killguard.py` + los tests → exit 0.
- [x] **Task 2.2**: Wrap en `cron/scheduler_script.py` (`_terminate_process_group`,
      `_terminate_cron_script_tree`) y en `agent/deadline.py` (`kill_process_tree`, ramas
      `killpg` y `os.kill(pid)`).
  - *Target Files*: `cron/scheduler_script.py`, `agent/deadline.py`
  - *Verification*: `grep -c HERMES-KILLGUARD` → 1 / 3 / 3 en los tres archivos.

### Phase 3: Integration & System Wiring
- [x] **Task 3.1**: Auditoría `HERMES-SIGTERM-AUDIT` en el bloque de `-15`, con registro de
      pids señalados acotado (`_PIDS_SENALADOS_MAX`) y solo tras entregar la señal.
  - *Target Files*: `cron/scheduler_script.py`
  - *Verification*: `pytest tests/cron/test_killguard_signal_guard.py -q` → **GREEN 9 passed**.

### Phase 4: Final Quality Gates & Cleanup
- [x] **Task 4.1**: Compilación y suite de regresión comparada contra la base:
      `pytest` sobre los 10 archivos que tocan `scheduler_script`/`deadline` → mismos
      FAILED/ERROR que `prod-stable` (50 ids, `diff` vacío), 162 → 170 passed.
- [x] **Task 4.2**: `git status --short` → solo los 4 archivos esperados (sin `.bak`, sin
      artefactos).
- [x] **Task 4.3**: Especificación en `.specs/killguard-sigterm/` con `Status: Completed`.

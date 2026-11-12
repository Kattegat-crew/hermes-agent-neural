# Diseño técnico: guard `read-before-patch`

## 1. Punto de enganche (verificado en el código, no supuesto)

Hermes ya despacha hooks de shell en `pre_tool_call` y `post_tool_call`
(`agent/shell_hooks.py`, `_TOOL_EVENTS`), con contrato:

- **entrada** (stdin JSON): `{hook_event_name, tool_name, tool_input, session_id, cwd, extra}`
- **salida** (stdout JSON opcional): `{"decision": "block", "reason": "..."}`
- **bloqueo**: `exit 2` (funciona incluso sin JSON)
- **registro**: `/opt/hermes-agent-data/config.yaml` → `hooks:` con `matcher` (regex), `command`,
  `timeout`, `fail_closed`; `hooks_auto_accept: true` ya está activo en este perfil.

Los scripts desplegados viven en `/opt/hermes-agent-data/hooks/`; su fuente versionada, en
`scripts/hooks/` de este repo (patrón que ya usan `guard_config_model_mutation.py` y
`guard_autoskill_create.py`).

## 2. Componentes

```
scripts/hooks/guard_read_before_patch.py     # hook único, dos eventos
scripts/hooks/read_before_patch_state.py     # ledger + huellas (importable y testeable)
scripts/hooks/read_before_patch_report.py    # replay sobre state.db -> informe (CA11)
tests/hooks/test_guard_read_before_patch.py  # contrato, sin red, sin tocar el ledger real
```

### 2.1 Ledger por sesión

`/opt/hermes-agent-data/state/hooks/read-before-patch/<session_id>.jsonl`, una línea por evento:

```json
{"t":"2026-11-12T20:41:03Z","ev":"post_tool_call","tool":"read_file","path":"/abs/x.py","mtime_ns":1762… ,"size":4211,"ok":true}
```

- `flock` exclusivo por escritura (hay turnos concurrentes), lectura completa con tolerancia a
  líneas corruptas (se ignoran, no rompen el hook).
- Retención: 7 días o 5.000 líneas por sesión, lo que llegue primero; limpieza oportunista en el
  propio hook (1 de cada 50 invocaciones, bajo el mismo lock).
- Última entrada por `path` gana.

### 2.2 Decisión (pre_tool_call)

```
si tool ∉ {patch, edit_file}            -> allow
path = realpath(join(cwd, tool_input.path))
si no existe                            -> allow            (CA5)
huella_actual = (st_mtime_ns, st_size)
última = ledger.última_entrada(path)
si última y última.huella == huella_actual -> allow         (CA2, CA4)
si no                                     -> BLOCK con reason:
   «read_file <path> antes de editarlo: cambió desde la última lectura (o no la hubo).
     Huella registrada: <mtime/size>. Actual: <mtime/size>.»
```

El bloqueo ocurre **antes** de tocar el archivo: no hay edición parcial.

### 2.3 Registro (post_tool_call)

- `read_file` con resultado: registra `(path, huella actual)`.
- `write_file` / `patch` / `edit_file` correctos: registra `(path, huella posterior)` — el agente
  sabe lo que escribió, así que puede seguir editando mientras nadie más toque el archivo (CA4).
- Cualquier otro tool: nada.

### 2.4 Modos y seguridad operativa

| Control | Implementación | Default |
|---|---|---|
| Modo | env `READ_BEFORE_PATCH_MODE=shadow|enforce` (leída del payload/entorno), o archivo `MODE` junto al ledger | `shadow` |
| Kill switch | archivo `DISABLED` en el directorio del ledger | ausente |
| Error interno | `except Exception: exit 0` + línea `{"ev":"error"}` en el ledger | siempre |
| `fail_closed` | **false** en config: un bug del guard no puede dejar la flota sin editar | explícito |
| Sesión desconocida | sin `session_id` → allow + log (no se puede atribuir la lectura) | — |

En `shadow` el hook escribe `{"ev":"would_block"}` y sale 0: sirve para medir durante 24-48 h
antes de apretar.

### 2.5 Replay (CA11)

`read_before_patch_report.py --db state.db --last N` reconstruye, por sesión, la secuencia de
`read_file`/`write_file`/`patch` con las mismas reglas y emite:

- `patch_total`, `would_block`, `would_block_pct`, `sessions_affected`
- `path_form_suspects` (mismo basename leído con otra forma de ruta → falso positivo potencial)
- top 10 sesiones por bloqueos

Ya ejecutado a mano para dimensionar: **404/2.526 (16%)** en **83/299** sesiones, con **45**
sospechosos de forma de ruta. El script debe reproducir esa cifra (test de regresión del número).

## 3. Registro en config (una sola entrada, no dos)

```yaml
hooks:
  pre_tool_call:
    - matcher: ^(patch|edit_file)$
      command: /opt/hermes-agent-data/hooks/guard_read_before_patch.py
      timeout: 10
      fail_closed: false
  post_tool_call:
    - matcher: ^(read_file|write_file|patch|edit_file)$
      command: /opt/hermes-agent-data/hooks/guard_read_before_patch.py
      timeout: 10
      fail_closed: false
```

## 4. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Bloquea trabajo legítimo tras `cp`/`scp`/subagente | ese es justo el caso que debe bloquear; el mensaje pide un `read_file` (1 llamada) |
| Ruta relativa vs absoluta dispara falsos bloqueos | `realpath` + `cwd` del payload; el replay mide cuántos quedan |
| Lectura parcial cuenta como lectura | límite declarado en la spec; v2 evalúa rangos |
| Turnos concurrentes corrompen el ledger | `flock` + tolerancia a líneas rotas |
| Bug del guard tumba la edición | `fail_closed: false` + `except → exit 0` + kill switch |
| Coste por llamada | lectura de un JSONL por sesión; < 5 ms medido en el prototipo del replay |

## 5. Rollback

1. Quitar las dos entradas de `hooks:` en `config.yaml` (o renombrar el `command` a `.off`).
2. Borrar el directorio de estado del ledger (no hay dato crítico).
3. Si el guard está en `enforce` y algo se atasca: crear `DISABLED` (efecto inmediato, sin recargar).

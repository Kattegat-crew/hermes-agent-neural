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
- **Ronda 7 (H-A): el ledger jamás contiene contenido de archivo** (solo huellas
  `(mtime_ns, size)`, hexdigests sha256 y rutas). El contenido previo que el pre captura para la
  certificación del post vive en un **snapshot efímero fuera del ledger**:
  `<root>/snapshots/<session>/<call_id>.snap` con directorio 0700 y archivo 0600; el post lo borra
  al consumirlo y la poda barre huérfanos con TTL corto (`SNAP_TTL_S` = 10 min).

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
- `write_file` correcto: certifica por INTENCIÓN — `sha256(tool_input['content'])`
  debe coincidir con el sha256 del disco al llegar el post; si difiere (otro
  proceso escribió entre la tool y el post), NO registra nada y anota
  `write_concurrent` en el ledger (fail-closed: mejor falso bloqueo que falso
  permiso). Payload legacy sin `content` conserva la huella de disco de antes.
- `patch` / `edit_file` correctos: certificación por RECONSTRUCCIÓN (ronda 6, sobre el
  snapshot efímero del pre; ronda 7 H-A: el snapshot vive en
  `<root>/snapshots/<session>/<call_id>.snap`, 0700/0600, nunca en el ledger). El
  post reconstruye el contenido ESPERADO desde `tool_input` (old→new para
  str_replace; hunks del `patch_text` V4A para Update/Delete; bloque literal '+'
  para Add File) y SOLO registra si `extra.result` reporta éxito y
  `sha256(esperado)` coincide con el disco al llegar el post. **Ronda 7 (H-B),
  fail-closed real:** con pendiente viva, si la reconstrucción/verificación no es
  posible (hunk no aplicable — p. ej. un hunk V4A que no empieza en la primera
  línea —, snapshot ausente para ese path, pendiente ambigua o snapshot no
  escribible en el pre) NO registra nada y anota `write_unverifiable` en el
  ledger: el fallback legacy (huella de disco) certificaba una versión
  potencialmente ajena. El fallback legacy queda SOLO para payloads sin
  pendiente (post sin pre, imposible en producción).
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
    - matcher: ^(read_file|patch|edit_file)$
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
| Fuga de secretos vía el ledger (ronda 7 / H-A) | El ledger JSONL jamás contiene contenido de archivo: solo huellas `(mtime_ns, size)`, hexdigests y rutas. El contenido previo que el pre captura para la certificación del post va a un snapshot EFÍMERO fuera del ledger (`<root>/snapshots/<session>/<call_id>.snap`, directorio 0700, archivo 0600); el post lo borra al consumirlo y la poda oportunista barre huérfanos con TTL corto (`SNAP_TTL_S` = 10 min). Si el snapshot no se puede escribir (permisos/ENOSPC) el post cae fail-closed: NO certifica (`write_unverifiable`) en vez de certificar la huella de disco |
| Certificación de una versión ajena tras un patch 'exitoso' (ronda 7 / H-B) | Fail-closed real: con pendiente viva del pre, reconstrucción no verificable (hunk no aplicable, snapshot ausente para ese path, pendiente ambigua) ⇒ NO registra y anota `write_unverifiable`; el fallback legacy (huella de disco) queda solo para payloads sin pendiente (post sin pre, imposible en producción) |
| Coste por llamada | lectura de un JSONL por sesión; el sha256 se guarda SOLO como hexdigest (nunca contenido del archivo), con cap de 32 MB (archivos mayores no se hashean: quedan protegidos solo por huella mtime+size). Rango medido del `sha256` en esta máquina: ~0,02 ms (10 KB) / ~0,08 ms (100 KB) / ~1,4 ms (1 MB). Se calcula en CADA `record()` (post_tool_call) y en el pre ÚNICAMENTE cuando `(mtime_ns, size)` coinciden con la huella registrada — si la huella ya difiere, no hay digest y la decisión de bloquear es inmediata. `record()` completo típico: ~0,1 ms (fingerprint + digest + append con `flock`); con ledger de ~4.900 líneas, ~5 ms (lectura + conteo de líneas de la poda oportunista, sin reescritura); en el tope de 5.000 líneas, ~11 ms (reescritura inherente del recorte FIFO) |

## 5. Rollback

1. Quitar las dos entradas de `hooks:` en `config.yaml` (o renombrar el `command` a `.off`).
2. Borrar el directorio de estado del ledger (no hay dato crítico).
3. Si el guard está en `enforce` y algo se atasca: crear `DISABLED` (efecto inmediato, sin recargar).

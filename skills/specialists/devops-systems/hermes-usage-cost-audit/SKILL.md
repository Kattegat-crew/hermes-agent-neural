---
name: hermes-usage-cost-audit
description: "Use when auditing where LLM tokens go across a Hermes fleet."
tags: [coste, tokens, uso, cuota, state-db, auditoria, flota]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cost, tokens, usage, quota, billing, profiles, sqlite, model-routing]
    related_skills: [context-monitoring, hermes-gateway-ops, hermes-desktop-plugins]
prerequisites:
  commands: [python3]
---

# Hermes Usage & Cost Audit

Medir **dónde se van los tokens** en una flota Hermes (multi-perfil) usando la
propia base de sesiones, antes de proponer o aplicar cualquier cambio de modelo,
compresión o reset. No cubre el límite del proveedor (eso es cuota; ver
`devops/hermes-desktop-plugins → references/nan-builders-quota-api.md`).

## When to Use

- «Se me está agotando la cuota», «¿por qué gasto tanto?», «cambia los modelos
  auxiliares a uno más barato», o cualquier pedido de *optimización de coste*.
- ANTES de escribir una recomendación de ruteo de modelos. Sin medición, la
  recomendación se basa en la lista del bloque `auxiliary` de `config.yaml`, que
  **no dice cuánto consume cada tarea** — y esa intuición falla (ver Pitfalls).
- Después de aplicar un cambio: re-medir a las 24 h y 72 h para probarlo.

## Quick Reference — cómo se cuenta el consumo

`<HERMES_HOME>/state.db` **y uno por perfil** (`profiles/<perfil>/state.db`; 12 en
DEV). Dos tablas importan:

| Tabla | Qué da |
|---|---|
| `sessions` | acumulados por sesión: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`, `model`, `source` (`desktop`/`telegram`/`whatsapp`/`discord`/`tui`/**`subagent`**), `title`, `api_call_count`, `end_reason` |
| `session_model_usage` | desglose por **(modelo, `task`)** dentro de la sesión: `task` vacío = **conversación principal**; valores como `compression`, `vision`, `approval`, `title_generation`, `background_review` = auxiliares |

Dos hechos que casi nadie tiene presentes:

1. **Los caps de proveedor suelen contar `cache_read_tokens`.** En la flota DEV del
   sep-2026 el cache read era **~92 %** del total contabilizado: el gasto no está en
   lo que se pregunta, está en **reenviar el historial cacheado en cada llamada**.
   `cache_read / api_calls` = prefijo medio (≈137k tokens/llamada medido).
2. **El consumo se concentra en pocas sesiones.** Medido: 14 sesiones de 251 = 71 %
   del total; casos tipo «Saludo amistoso» con 97M acumulados en una sola sesión.

## Procedure

1. Correr `scripts/audit_token_usage.py` (`--days 30`, `--since AAAA-MM-DD`, `--json`).
   Descubre solo los `state.db` del `HERMES_HOME` y de `profiles/*/`, en **solo lectura**.
2. Leer las tres salidas en este orden: **por tarea** → **por modelo+tarea** → **top sesiones**.
3. Decidir con las reglas de la tabla siguiente; nada de «mover las auxiliares obvias».
4. Proponer el cambio con palancas concretas (config exacta + efecto esperado en tokens/periodo).
5. Aplicar, y **re-medir** con el mismo script a las 24 h y 72 h. Sin re-medición no hay prueba.

| Hallazgo | Acción |
|---|---|
| `cache_read` ≫ input/output (~90 %) | Reducir **llamadas × prefijo**: compresión más temprana (`compression.threshold`), `session_reset.idle_minutes` menor, `/new` por tema. No es cambiar de modelo. |
| Conversación principal ~85 % del total | La palanca es la disciplina de sesión, no el ruteo auxiliar. |
| Una auxiliar ~15 % (p. ej. `background_review`) | Rutearla a un modelo con cap holgado; sí mueve la aguja. |
| `compression` + `title_generation` + `approval` + `vision` < 0,5 % | No tocar: es ruido, y tocar configuración tiene su propio riesgo. |

## Palancas nativas de contexto (lo que baja el consumo de verdad)

Antes de tocar modelos, revisar estas dos llaves de la raíz `compression:`: en esta
instalación (v0.20.4, verificado en código) están **apagadas por defecto**.

| Llave | Default | Qué hace |
|---|---|---|
| `proactive_prune_tokens` | `0` (apagado) | Enciende `prune_tool_results_only()` (`agent/context_compressor.py`): poda **sin LLM** los resultados de herramientas viejos — dedup byte-idéntico, resumen de lo que queda fuera del tramo protegido, truncado de argumentos gigantes. Su docstring describe el caso exacto: con ventana grande `should_compress()` casi nunca dispara, así que esas salidas viajan en el historial y se reenvían cada turno. |
| `threshold_tokens` | ausente | Tope **absoluto** en tokens: el disparo es `min(ratio × ventana, cap)`. Con `threshold: 0.5` sobre un modelo de 1M nada se comprime hasta ~500k; el cap (p.ej. 70k) es lo que mantiene pequeño el prefijo. |

Complementarias: `proactive_prune_min_result_chars` (8000), `proactive_prune_min_reclaim_tokens`
(4096 — la poda sólo se confirma si recupera al menos eso, para no romper el contrato de caché),
`protect_last_n` (12), `hygiene_hard_message_limit` (400).

Receta base cuando el auditor mide ~137k de prefijo por llamada:

```yaml
compression:
  threshold: 0.5
  threshold_tokens: 70000
  proactive_prune_tokens: 40000
```

Efecto esperado: prefijo por llamada a ~50-70k ⇒ −40/50 % en la conversación principal
(84,7 % del gasto). Nada de esto usa LLM ni pierde contenido único.

## Pitfalls

- **La disponibilidad de las llaves depende de la versión.** `threshold_tokens` está
  cableado en la 0.20.4 (`agent/agent_init.py` → `threshold_tokens_cap`,
  `compression.threshold_tokens`), mientras la hermana `devops/hermes-fleet-model-ops`
  lo da por *legacy* en 0.21. En una flota con dos instalaciones (host y contenedor)
  verificar EN EL CÓDIGO que sirve a ese perfil antes de prometer el efecto:
  `grep -n "threshold_tokens\|proactive_prune_tokens" agent/agent_init.py`.
- **Los subagentes no son gratis.** Aíslan contexto y son la palanca más grande cuando
  el patrón es «leer mucho → devolver poco», pero si el resultado que vuelve es grande
  el overhead se come el ahorro (la industria reporta **+200-500 %** en flujos
  subagent-heavy). Regla: subagente sólo si el resultado es pequeño; medido en la
  flota, los subagentes eran 3,5 % del gasto — no eran el problema.
- **Las lecturas pesadas no van al hilo principal.** Pasarlas por `execute_code`
  (turno sin coste de contexto) o por subagente y devolver sólo el hallazgo:
  benchmark de Anthropic, el mismo dato en contexto $0,68 vs vía `code_execution`
  $0,14 (−79 %).
- **La recomendación que parecía obvia y era falsa (11-sep-2026):** proponer mover
  compresión, títulos, `session_search` y aprobación a otro modelo. Medido: esas
  cuatro sumaban **0,15 %** del consumo, mientras `background_review` (el curador de
  skills) se llevaba **15,1 %** y las sesiones eternas **84,7 %**. Regla: la lista de
  `auxiliary` no es un ranking de gasto; se mide.
- **`background_review` no suele estar declarado en `auxiliary`**: hereda el runtime
  del padre con caché caliente (`routed=False` en `_resolve_review_runtime`). Para
  moverlo hay que declarar explícitamente
  `auxiliary.background_review.{provider,model,base_url,api_key}`.
- **Los perfiles son islas**: no heredan la config del perfil `default`. Un cambio
  «global» exige patchear `config.yaml` **y** cada `profiles/*/config.yaml`.
- **`session_model_usage` puede no existir** en una DB vieja (se crea al primer
  registro): tratarla como «desglose no disponible», nunca como cero.
- **DBs vivas**: abrirlas siempre con `sqlite3.connect('file:...?mode=ro', uri=True)`
  para no bloquear el agente que está escribiendo.
- `input_tokens` de la tabla `sessions` es **acumulado de la vida de la sesión**
  (incluye ciclos de compresión), no el contexto actual: no confundirlo con
  «tamaño del prompt».
- Los crons leen la config en cada tick (no necesitan reinicio); los procesos vivos
  (gateway de mensajería, `serve` por perfil) **sí** para recargar `config.yaml`.

## Verification

- El script imprime TOTAL, % por tarea, top de sesiones y prefijo medio por llamada;
  un cambio de ruteo está probado solo si el % de la tarea objetivo bajó **y** el
  modelo receptor sigue con holgura de cap.
- Cruzar con la cuota del proveedor (`GET cloud-api.nan.builders/api/usage/quota`,
  gratis, sin consumir tokens): la proyección al reset debe quedar < 90 %.
- Baseline real y cifras de referencia: `references/consumo-flota-dev-2026-09.md`.

## Output Contract — cómo entregar la medición (preferencia del Admin)

- **Números con fuente, nunca adjetivos.** Cada cifra con su origen: qué DBs, qué
  `task`, qué periodo. El Admin audita el dato, no la narración.
- **Separar medido de inferido**, explícitamente. Lo medido lleva la consulta o el
  script que lo produjo; lo inferido se etiqueta como tal (él no acepta «100 %
  verificado» de mis propias pruebas).
- **UNA acción recomendada** con su efecto esperado (config exacta + tokens/periodo
  que mueve). No una lista de alternativas sin ganador.
- **Corregir en voz alta la recomendación previa si los datos la contradicen.**
  Pasó el 11-sep-2026 (ver Pitfalls): presentar la corrección con las cifras fue lo
  que orientó la conversación; recomendaciones «de intuición» cuestan credibilidad.
- **Sin re-medición no hay claim.** El cierre es el mismo script a las 24 h y 72 h, y
  la proyección de cuota al reset como testigo externo.
- **Acción desacoplada = avisar en el mismo mensaje que se dispara.** Cuando el paso
  se lanza con retardo/`setsid`/background (p. ej. el reinicio del backend que sirve
  al Desktop), decir ahí: qué se lanzó, el handle/PID, cuántos segundos faltan y qué
  verá el Admin. Y nunca cerrar un turno con el lanzador **escrito pero no disparado**
  dando a entender que ya ocurrirá: el 11-sep-2026 el Admin tuvo que preguntar «¿ya?»
  por exactamente eso.

## Support files

- `scripts/audit_token_usage.py` — auditoría multi-perfil (tareas, modelo+tarea, sesiones, cache).
- `references/consumo-flota-dev-2026-09.md` — baseline medido de la flota DEV (sep-2026) para comparar mes contra mes.
- `references/context-economics-research-2026-09.md` — digesto de la investigación externa (Anthropic, LangChain, Faros AI, preprint) con cifras de referencia, las cuatro prácticas que aplica la industria y el plan por fases de la flota DEV.

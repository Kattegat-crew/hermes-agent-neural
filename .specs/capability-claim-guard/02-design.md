# 02 — Diseño técnico: Capability Claim Guard (CCG)

**Fase:** F1 (diseño; sin código). Referencias file:line verificadas vivas en el
worktree @ `cd397afc64`.

## 1. Arquitectura de alto nivel

```
                 ┌───────────────────────────────────────────────────────┐
                 │ agent/capability_claim_guard.py  (NUEVO, ~1 módulo)   │
                 │  capture_evidence(agent, turn_id, tool_defs)          │
                 │  scan_published_text(agent, text, surface) -> Verdict │
                 │  arm_repair(agent, verdict) / truthful_close(agent)   │
                 └───────┬───────────────────────┬───────────────────────┘
      S1 deltas          │                       │        S2 interim
  (delta sink)           │                       │     (_deliver_interim /
                         ▼                       ▼      _emit_interim_assistant_message)
   publicados ✔ ── detección + registro de contradicción (jamás retrata frames)
                         │
                         ▼  sello final / finish(final_text)
   S3 final: extend apply_llm_output_transform  ──(reparación acotada)──► salida veraz
```

Un solo módulo, tres call sites. El detector es determinista y offline (R6); la
evidencia es por turn_id (E5 prohíbe el global). Sin modelos auxiliares.

## 2. Superficies exactas (hook/transport mínimos)

| Seam | Punto exacto | Mecanismo | Justificación Footprint Ladder |
|---|---|---|---|
| S1 | Delta sink del core: `agent/stream_delivery.py::_deliver_to_stream_callbacks` (l.33) y el punto de emisión de deltas en `chat_completion_helpers` (donde se acumula `_current_streamed_assistant_text`, cf. `agent_init.py:647`) | Llamada interna directa al detector en el sink, ANTES de entregar a callbacks/superficies | No existe hoy ningún hook por-delta; un hook genérico per-delta vía plugin host añadiría latencia a cada token. Gate interno en el punto de publicación es el mismo patrón de los filtros `_visible_commentary`. |
| S2 | `agent/stream_delivery.py::_deliver_interim` (l.176) + `_emit_interim_assistant_message` (l.197) | Llamada interna directa; si el texto NO fue ya streamed → suprimible; si ya streamed → solo registrar contradicción | E3: commentary sale antes del final. Reusa la noción existente de `_interim_text_was_delivered`. |
| S3 | `agent/turn_finalizer.py::apply_llm_output_transform` (l.483) vía el hook existente `transform_llm_output` (o seam directo del mismo punto) | Extensión del seam existente | Regla "extender seam existente antes de añadir core hooks": S3 reutiliza el hook de plugins; un plugin YA podría implementar S3 hoy. Lo que ningún plugin puede cubrir es S1/S2 → por eso el gate interno, no "plugin solamente". |
| Cobertura API server | `gateway/platforms/api_server_openai_routes.py::_iter_stream_items` (los deltas llegan del stream_q alimentado por S1) | Sin cambio propio; `_post_stream_transform` (l.91) queda como última capa de append para transforms post-finales | E2: el gate en el sink corre ANTES de que los deltas entren a la cola → cobertura heredada. |
| Cobertura TUI/Desktop/Gateway | `tui_gateway` y plataformas consumen los mismos callbacks/stream hooks | Sin cambio | E4: un gate en el sink cubre todas las superficies (narrow waist). |

Transport surfaces NUEVOS: ninguno. Hooks nuevos genéricos: ninguno (se rechaza
`transform_output_delta` per-delta: sobrecosto por token sin consumidor más concreto).

## 3. Evidence Snapshot (CES) — evidencia por sesión/turno, sin globals

- **Fuente de la capacidad (corrección de review ronda 1, hallazgo 1):** la lista de
  herramientas NO se re-resuelve por turno. `agent.tools` se fija UNA vez al construir
  el agente en `agent/agent_init.py:1117`
  (`agent.tools = model_tools.get_tool_definitions(enabled_toolsets, disabled_toolsets,
  quiet_mode=agent.quiet_mode)`, con memoización en `model_tools.py`) y luego se refina
  en ese mismo bloque (`prune_oneshot_tools`, `agent_tool_drops`,
  `agent.valid_tool_names` derivado en las líneas siguientes). El turno solo decide si
  el payload la incluye: `agent/turn_request_assembly.py` NO llama a
  `get_tool_definitions()`; en `turn_request_assembly.py:204-210`,
  `should_decouple_tools_for_turn` (`agent/tool_guardrails.py:828`) vacía
  `tools_for_api = []` en turnos conversacionales o deja `tools_for_api = agent.tools`.
- **Captura:** del atributo de sesión `agent.tools` (y `agent.valid_tool_names`) al
  arrancar el turno, guardar en el agente `agent._ccg_evidence = {turn_id,
  direct: set[str], deferred: set[str], aliases: dict, observed_errors: dict[tool, err],
  seq: n}`. Ciclo de vida = turno; reset en el mismo punto donde hoy se resetea
  `_current_streamed_assistant_text`.
- **DIRECT:** capacidad de la SESIÓN (`agent.tools` / `agent.valid_tool_names`,
  propiedad de la sesión según `tools/AGENTS.md` § Surface capability, E8) — NO los
  schemas `tools=` del request actual. En turnos decoupled
  (`turn_request_assembly.py:205-210`) el payload omite las schemas pero la capacidad
  persiste → una negativa de herramienta presente en `agent.tools` sigue siendo
  CONTRADICTION(direct); el corpus §6 de 01-spec y la matriz de pruebas cubren esa
  clase (AC11).
- **DEFERRED:** catálogo expuesto por el puente tool_search de este ensamblado
  (`model_tools.py:524-535`): nombres alcanzables con `tool_search`/`tool_describe`.
- **Aliases:** mapa de alias de toolsets del registro (`tools/registry.py::register_toolset_alias`).
- **Errores observados:** `handle_function_call` ya registra fallos reales del turno;
  el snapshot REFERENCIA ese registro (no lo duplica) para R3/AC8.
- **Prohibido:** leer `_last_resolved_tool_names` como evidencia (E5: stale en delegación);
  re-probar `check_fn` con efectos (solo se reutilizan resultados ya cacheados, E7);
  cachear por proceso (multi-perfil: la evidencia se keyea por `turn_id` y vive en la
  instancia del agente, cuyo scope ya es el del perfil servido).

## 4. Detector (determinista, ES/EN)

1. **Segmentación:** el texto se analiza por segmentos publicables (frontera de
   oración/párrafo), tolerando claims partidos entre deltas: S1 mantiene una ventana
   de retraso acotada (`holdback_chars`, default ~200) + escaneo en fronteras de
   oración; jamás buffering ilimitado ni espera de fin de turno.
2. **Exenciones primero (R4):** bloques de código/fences, comillas, marcadores de
   hipótesis ("si tuviera", "as if"), envolturas `tool_call`, y frases que referencian
   un `observed_errors[tool]` del turno → no-scan del segmento.
3. **Patrones de speech-act de negativa** (ES/EN): "no tengo (ninguna(s)) herramienta(s)
   de X", "no existe la herramienta X", "no puedo enviar/leer/ejecutar X", "I don't have
   access to X", "there's no tool for X", "no cuento con X", etc. — tabla declarativa
   ES/EN, ampliable, con tests por clase del corpus (§6 de 01-spec).
4. **Extracción de la capacidad referida:** matching contra `direct ∪ deferred ∪ aliases`
   (exacto, alias y sinónimos de familia: mensajería/messaging/send, tareas/tasks/kanban,
   etc. — tabla corta, mantenida en el módulo, sin red neuronal).
5. **Veredicto:** `CLEAN` | `CONTRADICTION(direct)` | `CONTRADICTION(deferred)` |
   `ALLOWED(absent|exempt|observed_error)`.

## 5. Acciones por veredicto

### S1 (deltas)
- `CONTRADICTION`: NO se retrata lo publicado (prefix-stability, R9). Se marca el turno
  como tainted (`agent._ccg_tainted = turn_id`) y se agenda la corrección para el sello
  final (invariante 2 del streaming contract: la post-augmentación viaja en
  `finish(final_text)`). Si el repair budget lo permite y el turno aún no terminó, se
  arma UNA ronda de reparación (§5.3). Log WARN con veredicto y evidencia.
- Resto: pasa intacto.

### S2 (interim)
- `CONTRADICTION` y el texto NO fue streamed: se suprime la entrega interim (la mínima
  intervención posible: no publicar commentary falso), cuenta como evento de claim y
  agenda corrección de sello. Log WARN.
- `CONTRADICTION` ya streamed: igual que S1 (registro + sello).

### S3 (final)
- `CONTRADICTION` y turno tainted o claim nuevo: se intenta reparación acotada.
- Sin presupuesto (2 intervenciones gastadas) o discovery imposible: NO se bloquea la
  salida (R7); se APENDA una cláusula veraz explícita con la evidencia disponible
  ("Verificación: kanban_* consta en la lista de herramientas de esta sesión; si un
  intento falla, comunica el error real") y WARN. Nunca falsa promesa, nunca inventar
  herramientas, nunca suprimir un blocker comprobado.

### 5.3 Reparación acotada
- Inyección única como **tool result o user message** (jamás system prompt, R9):
  "Contradicción detectada: declaraste que no existen herramientas de X, pero
  {tool_1, tool_2…} están DIRECT en esta sesión / DEFERRED vía tool_search. Usa
  tool_describe para confirmar o reformula con veracidad." Luego una continuación del
  loop existente (no un sub-loop nuevo): el mecanismo es el mismo estilo de las
  rondas de stall/repair ya existentes en `turn_tool_validation`/recovery.
- Contador por `turn_id` en el agente; al agotarse, modo "solo sello veraz" (§5-S3).
- Condiciones seguras: snapshot ausente / catálogo vacío / excepción del guard →
  fail-open (R7/AC7). El guard jamás lanza hacia el turn loop.

## 6. Config (aislada, default apagado)

```yaml
agent:
  capability_claim_guard:
    enabled: false            # default: runtime actual byte-idéntico (AC1)
    holdback_chars: 200       # ventana de retraso S1
    repair_limit: 2           # intervenciones máx por turn_id
    # activación canaria solo en entorno AISLADO DEV (F3+), jamás perfiles operativos/PROD
```

Resolución por la config estándar (`hermes_cli/config`, lecturas defensivas `.get`),
sin env vars de comportamiento (regla raíz: `.env` solo secrets).

## 7. Trade-offs y riesgos

- **Falsos positivos del léxico:** mitigado por exenciones primero (R4), lista corta de
  patrones por speech-act (no matching de tema), y fail-open. El corpus ES/EN de tests
  es el presupuesto de precisión; cualquier caso nuevo entra como test, no como tweak
  ad-hoc.
- **Latencia S1:** ventana acotada (~200 chars ≈ una oración); el retraso máximo es
  acotado por diseño y no depende del proveedor. Alternativa descartada: escanear solo
  el final (viola E1/E2).
- **Riesgo de bucle:** repair_limit + contador por turn + fail-open → sin bucles (AC6).
- **Riesgo multi-perfil:** evidencia en instancia de agente (scope del turno), cero
  globals nuevos; el global existente queda intocado (E5).
- **Compatibilidad de plugins:** S3 vía hook existente es estable; S1/S2 son seam
  interno no-documentado como API (no rompe contrato de plugins).

## 8. Telemetría/observabilidad

Logs estructurados locales (`hermes_logging.py`): nivel WARN por veredicto
CONTRADICTION (surface, turn_id, tools involucradas, acción) y DEBUG por scan CLEAN.
Sin telemetría saliente (regla opt-in). Métricas opcionales futuras NO se especifican
aquí para no crear superficie muerta.

## 9. Rollback

1. Config: `enabled: false` (default) — apagado lógico inmediato, sin redeploy de config.
2. Código: revert de 1 módulo nuevo + 3 call sites + campos de estado en `agent_init`
   (`_ccg_evidence`, `_ccg_tainted`, `_ccg_repairs`) — diffs pequeños y ortogonales;
   ningún cambio de esquema, transcript, ni persisted state.
3. Sin migraciones: nada persiste fuera del turno. El sello veraz es texto publicado
   (no retractable, y correcto por diseño).

## 10. Cumplimiento de invariantes (matriz resumida; detalle en 04-matrix.md)

| Invariante | Cumplimiento |
|---|---|
| Prompt caching | Reparación viaja como user/tool message; system prompt intacto |
| Prefix-stability streaming | S1 jamás retrata frames; corrección por sello |
| Narrow waist | 1 módulo + 3 call sites; 0 herramientas core nuevas |
| Perfil/secret scope | Evidencia por instancia/turno; sin env reads; sin globals |
| Fail-safe | Fail-open siempre; jamás bloquea salida total |

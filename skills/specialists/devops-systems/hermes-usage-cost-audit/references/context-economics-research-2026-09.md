# Economía de contexto en agentes — digesto (sep-2026)

Recopilado el 11-sep-2026 a pedido del Admin («investiga online, X, reddit, github, qué
está implementando la gente») para resolver el caso de la flota DEV: 92 % del consumo
contabilizado eran **cache reads** y ~137k de prefijo reenviado por llamada.

## 1. Las cuatro prácticas que la industria aplica en 2026

| Práctica | Qué es | Cifra de referencia |
|---|---|---|
| **Compaction** | Resumir la historia pasada un umbral y continuar con el resumen | −16 % de coste en el benchmark de Anthropic |
| **Context editing / tool-result clearing** | Borrar resultados de herramientas viejos dejando constancia de la llamada | Ventana de 154k → **~16k** tras cada edición |
| **Isolating context (subagentes)** | Trabajo pesado en ventana propia; vuelve sólo el resumen | **−78 %** (pero +200-500 % si el resultado que vuelve es grande) |
| **Ejecución programática (`execute_code`)** | El dato grande se filtra en código y nunca entra al contexto | Mismo CSV: $0,68 en contexto vs **$0,14** vía code_execution (**−79 %**) |

Complementaria: **escribir fuera de la ventana** (scratchpad/memoria) en vez de cargar todo
el historial — taxonomía Karpathy/LangChain: *write / select / compress / isolate*.

## 2. El error más caro (y el que teníamos)

- «Una sola conversación por proyecto/días» es el gasto número uno: **cada turno reenvía el
  historial completo**. Medido en la flota: «Saludo amistoso» (Telegram) = 97,4M en una sesión;
  top-14 de 251 sesiones = 71 % del total.
- Faros AI lista las cinco fugas: *tool output bloat*, rework por prompts vagos, subagentes mal
  usados, planes de equipo, thinking extendido.
- Preprint «Context Compression for Long-Horizon AI Agents»: 40-50 % del gasto típico es
  acumulación de contexto; casos de 230k tokens reenviados **por mensaje**. Cita a Hermes Agent
  como buen ejemplo por sus subagentes aislados y turnos Python-RPC ("zero-context-cost").

## 3. Matiz de facturación que cambia el cálculo

En Anthropic el cache read cuesta ~0,1× el input (por eso sus ahorros parecen pequeños: 12-16 %).
En el proveedor de la flota (NaN) **el cache read cuenta completo contra el cap** ⇒ limpiar
contexto vale proporcionalmente mucho más que lo que reportan esos benchmarks. Cómo comprobarlo
en cualquier proveedor: comparar `SUM(input+output+cache_read)` de `session_model_usage` contra el
`tokensUsed` que reporta la API de cuota. Si coinciden, el cache read cuenta.

## 4. Cómo se ve en las herramientas del mercado

- **Anthropic API**: `context_management: { edits: [{ type: clear_tool_uses_20250919, trigger: {input_tokens: 30000-50000}, keep: {tool_uses: 3-5}, clear_at_least, exclude_tools }] }`, `clear_thinking_20251015`, compactación server-side y `memory_20250818`. Hermes implementa el equivalente nativo con `compression.proactive_prune_tokens`.
- **Claude Code**: `/compact` y `/context` (muestran qué está cargado y se reenvía), subagentes Explore/Plan, y `CLAUDE.md` corto (es un impuesto por turno).
- **GitHub/cursor.directory**: organizar `scratch/tool_outputs/`, `scratch/plans/`, `memory/` y usar subagentes con workspace propio.

## 5. Plan por fases que salió de esto (flota DEV, 12 configs)

1. **Fase 1 — knobs nativos**: `threshold_tokens: 70000` + `proactive_prune_tokens: 40000` (el 80 % del resultado).
2. **Fase 2 — curador**: `auxiliary.background_review.{provider,model,base_url,api_key}` = glm5.3-flash (15,1 % del gasto medido).
3. **Fase 3 — higiene**: `session_reset.idle_minutes` 120→60, `compression.threshold` 0,75→0,5 en los 11 perfiles, y regla operativa de lecturas pesadas (execute_code / subagente).
4. **Fase 4 — rollout**: script idempotente (`--dry`, backup por archivo, `--revert`), piloto sólo en `default` 24 h, luego el resto con reinicio escalonado (los crons no requieren reinicio).
5. **Fase 5 — verificación**: re-medir `session_model_usage` a 24/72 h + `GET /api/usage/quota` como testigo externo; buscar `[prune]` en `agent.log` para confirmar que la poda actúa.

Criterio de éxito acordado: proyección al reset < 80 % (hoy 114,8 %) y prefijo medio < 70k.
Documento completo en el Brain: `plans/plan-consumo-nan-dev-2026-09-11.md`.

## 6. Fuentes

- Anthropic · Cost Optimization Cookbook · https://platform.claude.com/cookbook/cost-optimization-cost-optimization
- Anthropic · Context editing (`clear_tool_uses`) · https://platform.claude.com/docs/en/build-with-claude/context-editing
- Anthropic · Effective context engineering for AI agents · https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic · Context engineering: memory, compaction, tool clearing · https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools
- LangChain · Context Engineering (write/select/compress/isolate) · https://www.langchain.com/blog/context-engineering-for-agents
- Faros AI · Monitoring de gasto de agentes · https://www.faros.ai/blog/claude-code-token-usage
- Preprint · Context Compression for Long-Horizon AI Agents · https://www.preprints.org/manuscript/202607.0924
- Debate en X/Reddit (Avi Chawla, TheValueist, CJ Avilla; r/ClaudeCode, r/AI_Agents): «context rot», compactar con caché caliente, sesiones eternas.

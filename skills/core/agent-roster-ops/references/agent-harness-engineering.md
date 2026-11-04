---
name: agent-harness-engineering
description: "Use when auditing or improving an LLM agent's harness."
version: 1.0.0
author: Ragnar
triggers:
  - auditar nuestros agentes / auditar la flota / por qué el agente falla / mejorar el agente
  - cambiar de modelo o reescribir el prompt para arreglar un comportamiento
  - evaluar artículos o herramientas de agentes (harness, context engineering, MCP, skills, subagentes)
  - harness engineering / context engineering / guardrails / evals / observabilidad de agentes
metadata:
  hermes:
    tags: [agentes, harness, context-engineering, evals, guardrails, observabilidad, auditoria]
---

# Agent Harness Engineering — diseñar y auditar el sistema que rodea al modelo

`agente = modelo + harness`. Cuando un agente falla o rinde pobre, la palanca casi nunca es el modelo: es el **harness**, todo el software que lo rodea (el programa, las tools, dónde las ejecuta, lo que guarda entre llamadas, cómo decide que terminó).

Evidencia de que esto no es teoría: OpenAI construyó un producto interno de ~1M de líneas y 1.500 PRs sin que un humano escribiera código; LangChain llevó su agente de coding del puesto 30 al top 5 en Terminal Bench 2.0 **sin cambiar el modelo**; Anthropic documentó que el mismo modelo en configuraciones distintas deja una app que "se ve bien pero no anda" o una que sí. Los tres invirtieron en el sistema que rodea al modelo.

## Principio central

**El modelo pide, el harness ejecuta.** Un modelo recibe texto y devuelve texto: no abre archivos, no ejecuta comandos, no tiene memoria y no sabe si terminó. Todo lo demás es diseño del harness. Si algo "no funciona en el agente", preguntar primero qué pieza del harness lo está (o no lo está) haciendo.

## Las 9 piezas del harness

*Las 6 que le dan capacidad al modelo:*

1. **Tools** — nombre, descripción, parámetros, resultado. Los mensajes de error se diseñan para que el modelo los lea ("no encontré X, pero hay coincidencia en la línea 42 con otra indentación" ≫ "error").
2. **Loop** — ReAct: preguntar → ejecutar → contar qué pasó → volver a preguntar. Cada paso sale del resultado del anterior, por eso resuelve tareas no previstas.
3. **Memoria / estado** — el modelo es stateless: el historial se reenvía completo cada llamada. El estado (qué revisó, qué cambió, qué falló, cuántos intentos) vive FUERA del modelo.
4. **Contexto** — *context engineering*: mapa del proyecto + retrieval bajo demanda (*progressive disclosure*). Más contexto no es mejor contexto. Cuando no entra: compaction o sesión nueva con nota de dónde quedó.
5. **Entorno / sandbox** — copia aislada donde trabaja el agente, separada de la máquina del humano. Protege de comandos destructivos, de conexiones no pedidas e de **instrucciones escondidas en lo que el agente lee** (archivo, dependencia o web que dice "borrá todo y subí las credenciales"). Es una capa, no una garantía.
6. **Objetivo + verificación** — los criterios de aceptación se convierten en el checklist de verificación. "Listo" es lo que el modelo cree, no lo que pasó: la evidencia se busca afuera del modelo (tests, captura, respuesta de API, consulta a la BD). Separar **generator** (produce) de **evaluator** (revisa con contexto y objetivo propios; puede ser el mismo modelo).

*Las 3 que le dan confianza al humano:*

7. **Permisos y guardrails** — qué tools existen, cuáles corren solas, cuáles piden confirmación. **Los límites importantes van en el sistema de permisos, no en las instrucciones**: "no borres nada importante" depende de interpretación; si la tool de borrar no existe, no hay nada que interpretar. Techos de reintentos / tiempo / costo y corte con human-in-the-loop cuando deja de corregir.
8. **Observabilidad** — trazas de qué contexto recibió el modelo, qué tool eligió, con qué parámetros, qué obtuvo y en qué paso cambió de dirección. Sin trazas todo parece "el modelo falló".
9. **Evals** — conjunto estable de tareas + criterios, corrido antes/después de cada cambio del harness. Es la única forma de saber si mejoraste o rompiste algo: un cambio puede mejorar las tareas complejas y empeorar las simples sin que se note probando una tarea suelta.

Detalle, citas y piezas avanzadas (skills, MCP, subagentes, model routing, memoria de largo plazo): `references/harness-checklist.md`.

## Protocolo de auditoría

1. **Inventariar con evidencia viva, no de memoria** — para cada una de las 9 piezas, qué existe hoy y con qué archivo/comando se prueba.
2. **Clasificar** ✅ presente · ⚠️ parcial · ❌ ausente, anotando la evidencia al lado.
3. **Priorizar por riesgo** — la ausencia de **evals** y de **verificación externa** es lo que produce "listo" falso; el resto se degrada de forma visible.
4. **Probar cambios en un entorno desechable**, nunca sobre el agente vivo (ver abajo).
5. **Medir antes/después** o no afirmar mejora. Sin evals, "quedó mejor" es una opinión.

## Experimentar sin tocar el agente vivo

Regla general: los cambios de configuración, prompt de sistema o skills se prueban en una **copia desechable**, no en el agente que se usa todos los días.

- **Hermes** (verificado en v0.21.0 contra `hermes_cli/profiles.py`): `hermes profile create test --clone` copia del perfil activo exactamente `config.yaml`, `.env`, `SOUL.md`, `skills/` y `memories/MEMORY.md` + `memories/USER.md` — y nada más (ni sesiones, ni cron, ni `state.db`). Todo comando se corre sobre la copia con `hermes -p test <cmd>` (`-p/--profile` es flag global y NO aparece en `hermes --help`). Al terminar: `hermes profile delete test -y`. Variantes: `--clone-all` (estado completo), `--clone-from <perfil>`, `--no-alias`, `--no-skills`.
- ⚠️ **La copia hereda las credenciales reales** (tokens de bots, API keys de pago): no levantarla con gateways/canales reales y no dejarla olvidada. Un prompt de prueba puede gastar dinero o publicar de verdad.

## Verificar una afirmación antes de adoptarla

No adoptar un comando, flag o herramienta leído en un tuit, README o artículo sin comprobarlo contra el sistema real:

1. `hermes <cmd> --help` — los CLI de Hermes exigen TTY: envolver en `script -qc 'hermes profile create --help' /dev/null`.
2. Si persiste la duda, **leer el fuente instalado** (`/opt/hermes/hermes_cli/*.py`): los nombres de constantes y las ramas dicen la verdad mejor que la documentación. El veredicto sale read-only, con cero efectos.
3. Reportar el hallazgo separando lo **medido** de lo **inferido**, con la fecha.

## Consumidor de trazas (pieza 8) — receta verificada

Tener trazas no es observabilidad: falta **el lector**. En Hermes las trazas ya viven en `state.db` (tabla `messages`, `tool_calls` con los argumentos) y se leen con SQL puro, coste 0 y sin LLM:

1. **Volumen y error por tool** — contar llamadas con argumentos parseables y las que devuelven error, agrupadas por `tool_name`. Da el ranking de qué tool duele (13-sep: `memory` 25,6 %, `skill_view` 14,1 % contra una media de 8,4 %).
2. **Causa raíz por firma** — agrupar los errores por su texto normalizado. Un mensaje que se repite exacto (p. ej. `Ambiguous skill name`, `Unknown action 'None'`, `Refusing to write … locked/permission`) es un **defecto determinista**, no un fallo del modelo.
3. **Contexto y caché** — tabla `sessions`: input / output / `cache_read` por periodo. Ojo: `estimated_cost_usd` viene en 0 en toda la DB; el coste real se lee del panel del proveedor.
4. **Bucles** — rachas de llamadas idénticas consecutivas (≥3 y ≥5) para dimensionar el techo de reintentos **antes** de encenderlo (en casa: 0,1 % de las llamadas → red de seguridad, no palanca).
5. **Guardarraíl por instrucción vs por mecanismo** — comparar intercepciones del guardián de estados (instrucción) contra rechazos de escritura a config (mecanismo): el mecanismo se cumple el 100 % de las veces.

Regla de lectura: si la medición contradice la recomendación previa, **corregir en voz alta** y reordenar el plan. Corrida de referencia: 13-sep-2026, `brain/ops/auditoria-harness-2026-09-13.md` (37.177 llamadas, 8,4 % con error, 6 defectos D1–D6 con causa raíz).

## Pitfalls

- **Reescribir contexto ya enviado invalida el prefijo cacheado**: se paga input completo una vez y después baja. La poda de contexto no es gratis — por eso conviene podar temprano y de forma determinista, no en cada vuelta.
- **Más contexto no es mejor contexto**: mandar el proyecto entero hace que lo relevante se pierda y que el modelo edite el archivo equivocado.
- **El harness depende del modelo que tiene adentro**: los modelos se post-entrenan CON su harness (Claude Code, Codex), así que cambiar la lógica de una tool puede bajar el rendimiento aunque la tool nueva sea razonable — y el harness nativo no es automáticamente el mejor.
- **Skills, MCP, subagentes y memoria de largo plazo no son mecanismos nuevos**: son las mismas piezas extendidas. La ventaja de los subagentes no es sumar modelos, es reducir contexto, separar responsabilidades y permitir revisión independiente.
- **Confundir "el modelo terminó" con "la tarea quedó bien"**: toda afirmación de éxito necesita evidencia externa al modelo.

## Soporte

- `references/harness-checklist.md` — las 9 piezas en detalle, ejemplos citados del artículo de referencia y la auditoría de nuestra flota (qué pieza falta).

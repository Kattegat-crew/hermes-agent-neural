---
name: context-recovery
description: "Use when recovering context after a provider error."
tags: [contexto, recovery, provider-error, litellm, brain, sesiones, continuidad]
---

# Context Recovery

## Overview

Cuando el provider (qwen3.6, etc.) tira un error de JSON corrupto o 400 y se pierde el hilo de la conversación, este skill permite recuperar el contexto leyendo archivos locales. **La memoria de la conversación NO es confiable después de un error del provider.**

## Cuándo usar

- Error `litellm.BadRequestError` con JSON corrupto
- `Unterminated string starting at`
- El agente "pierde memoria" y vuelve a un punto anterior
- HTTP 400 del provider
- Cualquier error que rompa el hilo de la conversación
- El usuario dice "correr context recovery"

## Workflow

1. **No confiar en la memoria de la conversación** — está corrupta
2. **Leer archivos locales como fuente de verdad** — Brain Wiki, tareas, config
3. **Identificar el último punto válido** — qué se estaba haciendo antes del error
4. **Continuar normalmente** — retomar desde ahí

## Pasos

1. `session_search(limit=3)` — ver últimas sesiones (sin query para ver todas)
2. `read_file('/opt/data/brain/index.md')` — ver estado de la Wiki
3. `read_file('/opt/data/brain/tasks/pending.md')` — ver estado de tareas
4. `read_file('/opt/data/brain/entities/hermes_messaging.md')` — si estaba en medio de algo
5. Reconstruir contexto y continuar

## Archivos clave para recuperar contexto

| Archivo | Qué contiene |
|---------|-------------|
| `/opt/data/brain/index.md` | Índice de la Wiki, estructura del conocimiento |
| `/opt/data/brain/tasks/pending.md` | Estado de tareas (qué está en curso, qué está listo) |
| `/opt/data/brain/entities/` | Últimas entradas creadas (Wiki pages, configs) |
| `/opt/data/brain/SOUL.md` | Identidad del agente |
| `/opt/data/config.yaml` | Configuración actual de Hermes |

## Señales de que el provider falló

- Mensaje incompleto o cortado
- Repetición del mismo contenido
- Pérdida de contexto (pregunta lo que ya respondió)
- El usuario dice "¿qué estabas haciendo?" o "correr context recovery"

## Pitfalls

- **NO** intentar corregir el error del provider — simplemente saltar al siguiente paso
- **NO** confiar en lo que "recuerdas" de la conversación — leer archivos
- **NO** hacer session_search con queries específicas — empezar con query vacía para ver TODO
- El Brain Wiki es la fuente de verdad — si está actualizado, el contexto se recupera en 30 segundos
- Después de recuperar, **siempre confirmar** al usuario qué estado encontraste

## Turno cortado: intención declarada sin tool call (2026-09-25)

Síntoma: la respuesta anterior anuncia una acción ("Voy a revisar X") pero murió ANTES de ejecutar cualquier tool call — no hay outputs de tools en el historial. El usuario lo percibe como cuelgue y reclama («¿por qué te cuelgas???»). Es un corte del provider silencioso, no un error visible.

Protocolo inmediato:
1. NO re-anunciar la acción ni disculparse a lo largo — una sola línea ("Tuve un corte; lo hago ahora").
2. Disparar la tool call anunciada EN LA MISMA respuesta, sin re-planificar.
3. Continuar la tarea original como si el turno no se hubiera cortado.

Pitfall: repetir el anuncio sin tool call duplica la frustración (cuelgue × 2). La recuperación se mide en tool calls emitidos, no en explicaciones.

## Verificación

- Confirmar que los archivos locales están actualizados
- Verificar que el último punto válido se recuperó correctamente
- Decirle al usuario: "Recuperado. Estaba haciendo X, continúo desde ahí."
- Continuar la tarea original desde ese punto

## Ejemplo de uso

Cuando el provider falla:

```
1. session_search(limit=3) — ver últimas sesiones (sin query)
2. read_file('/opt/data/brain/index.md') — ver estado de la Wiki
3. read_file('/opt/data/brain/tasks/pending.md') — ver estado de tareas
4. Decir al usuario: "Recuperado. Estaba en X, continúo."
5. Continuar desde ahí
```

## Lecciones aprendidas (2026-04-29)

- **Los loops se generan cuando:** browser falla → intento fallback → repito fallback → provider falla → pierdo contexto
- **Solución:** Tener un protocolo claro de fallback (ver skill `browser-fallback`)
- **Obscura:** Se analizó el repo pero nunca se instaló — quedó pendiente por falta de confirmación del usuario
- **Brain Wiki actualizado:** Después de cada sesión larga, verificar que index.md y tasks/pending.md estén al día

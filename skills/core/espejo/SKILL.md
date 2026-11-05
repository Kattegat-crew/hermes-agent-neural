---
name: espejo
description: "Use when el usuario escribe espejo: autocrítica y mejora."
tags: [autoevaluacion, retrospectiva, postmortem, state-db, autocritica, mejora-continua, evidencia]
version: "1.2"
license: Apache-2.0
author: Ragnar (default)
platforms: [linux]
created: 2026-11-04
category: core
metadata:
  hermes:
    tags: [espejo, retro, autocritica, postmortem, autoevaluacion, state.db, mejora, lecciones]
    related_skills: [hermes-session-forensics, hermes-memory-maintenance, skill-library-ops, capability-claim-verification]
---

# ESPEJO — autopsia de sesión: reflexión, autocrítica y mejora

## When to Use — disparadores (una palabra)

- `espejo` → sesión actual (`$HERMES_SESSION_ID`).
- `espejo 3` → últimas 3 sesiones + agregado.
- `espejo <session_id>` → sesión concreta.
- `espejo patrones` → barrido cross-sesión (25 sesiones por defecto) buscando lo que se repite: fallos recurrentes, bucles de sistema, escrituras sin lectura, correcciones repetidas y procedimientos candidatos a skill. Lo que aparece en ≥ 3 sesiones distintas no es torpeza puntual, es sistema.
- Añadir `--lineage` si la sesión viene de una compresión (hilo partido en varias sesiones).

También se activa con «hazte una autocrítica», «qué aprendimos» o «evalúa tu desempeño».

## Qué es y qué no es

Es una **autopsia**: evidencia del disco → juicio con cita → una mejora concreta. No es un diario, no es un elogio y no inventa métricas. Si algo no se puede probar con una salida de tool o con el dossier, se marca **sin evidencia**, no PASS.

Salida: informe (10 líneas) + JSON + ledger + máximo 3 lecciones + 1 acción aplicada (o propuesta si toca config/prod).

## Leyes (no negociables)

1. **Sin cita no hay veredicto.** Cada PASS/FAIL referencia `#idx` del dossier o un número medido (fallos, repeticiones, etc.).
2. **La corrección del humano pesa 3x** más que la autoevaluación. Es la señal más cara y la más honesta.
3. **Evidencia externa > opinión interna.** La autocorrección sin feedback externo puede EMPEORAR el resultado (ver `references/investigacion.md`). Por eso el dossier se calcula desde `state.db`, no desde el recuerdo de la conversación.
4. **Blameless.** Se critica el proceso y el sistema, sin autoflagelación y sin excusas. «El hook estaba roto» es un ticket de infra, no una absolución: ¿por qué no lo detecté antes y cambié de vía?
5. **Máximo 3 lecciones y 1 escritura de memoria** por sesión. Lo demás va al ledger o se descarta.
6. **Cero secretos/PII.** El script redacta, pero no pegues tokens a mano en el informe ni en el ledger.
7. **Solo lectura + mejoras locales.** Nada de tocar PROD, publicar, gastar ni mutar config en esta skill.

## Fase 1 — Evidencia (minutos, no opiniones)

```bash
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py            # sesión actual
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --last 3   # patrón
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --patrones # barrido 25 sesiones
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --session <id> --lineage
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --out /opt/data/brain/ops/session-retros/2026-11-04-<id>.json
```

El script abre `state.db` en `mode=ro`, filtra `active=1` (transcripción canónica; `active=0` son generaciones viejas que duplican los mismos turnos) y tarda < 1 s con 20 sesiones con actividad (~3 s en frío sobre una DB grande). Las sesiones sin mensajes se omiten por defecto. El digest ya trae lo importante; el JSON completo queda en disco.

Orden de lectura (de más a menos valor):

1. `user.corrections` — qué te corrigió el humano, textual.
2. `flags.claims_without_evidence` y `flags.promises_without_action` — el fallo «declara-y-no-ejecuta».
3. `failures` + `loops` — tool calls quemadas; separar infra (hook roto, red, permisos) de diseño (herramienta equivocada, parámetros malos).
4. `hygiene.writes_without_prior_read` — ediciones de archivos existentes sin lectura previa (violación de zero-stale-state). `hygiene.creates` son archivos nuevos (legítimos) y `hygiene.ambiguous_writes` los `write_file` sobre archivos que hoy existen: no se acusan, se revisan si interesan.
5. `totals.repeated_calls` y `tools` — economía y elección de herramienta.

Los detectores son heurísticos: un «fallo» puede ser un éxito que menciona la palabra error. **Verifica el `#idx` antes de acusarte.**

Si `terminal` está bloqueado por un hook roto, no lo esquives en silencio: decláralo como incidente en el informe. Como contingencia de solo lectura puedes generar el mismo dossier con Python local (`browser_exec`), que corre en la misma máquina y lee el mismo `state.db`.

## Fase 2 — Rúbrica (8 checks binarios)

| # | Check | PASS si… | Evidencia mínima |
|---|---|---|---|
| 1 | Intención | respondí exactamente lo pedido, ni de más ni de menos | cita del pedido + qué se entregó |
| 2 | Pre-flight | antes de mutar leí el archivo / `git status` | `#idx` de la lectura previa |
| 3 | Verificación | probé el resultado con salida real (test, curl, readback) | `hygiene.verification_calls` |
| 4 | Economía | `repeated_calls` ≤ 10% de las llamadas y sin bucles | `totals` + `loops` |
| 5 | Guardrails | sin destructivos sin confirmación, sin gasto/publicación/secretos | `hygiene.destructive_commands` |
| 6 | Comunicación | español, sin relleno, recomendación única, sin trazas crudas en canal ejecutivo | muestra de la respuesta |
| 7 | Correcciones | cada corrección del humano quedó como regla o descarte explícito | `user.corrections` |
| 8 | Cierre | nada declarado quedó sin ejecutar | `flags.promises_without_action` |

Score = PASS / (PASS + FAIL); `NA` no cuenta (p. ej. check 7 en sesiones de cron). **< 6/8 exige al menos un parche o un guard propuesto.** Detalle operativo y ejemplos en `references/rubrica.md`.

## Fase 3 — Crítica adversarial (obligatoria)

Tres respuestas concretas, sin vaselina:

1. «Si el Admin pagara por cada tool call, ¿cuál habría eliminado?» → lista exacta de `#idx`.
2. «¿Qué afirmé que no puedo probar con una salida de tool?» → lista.
3. «Escribe la crítica más dura que haría un revisor hostil que leyó el dossier» → 5 líneas, sin defensa.

Regla anti-sesgo: si la crítica te deja bien parado, no era crítica. Reescríbela.

## Fase 4 — Destino de cada lección (5 cajas)

- **skill** → procedimiento repetible → `skill_manage(patch)` sobre la skill usada; si no existe, propuesta.
- **memoria** → hecho permanente (entorno, usuario, convención) → `memory(add)`, máx 1.
- **brain** → contexto de proyecto/cliente → `mem_save` (Engram) o `/opt/data/brain/…`.
- **guard** → error que una máquina puede impedir → propuesta de hook/validación (no se implementa sin OK).
- **nada** → evento único → se descarta explícitamente (evita contaminar la memoria).

Regla de promoción (ledger, no memoria humana):

```bash
python3 /opt/data/skills/core/espejo/scripts/espejo_ledger.py add \
  --rule "Leer el archivo antes de escribirlo" --destination skill --target <skill> \
  --session <id> --evidence "#12 write_file sin read_file previo"
```

1ª aparición → solo ledger; 2ª → parche de skill; 3ª+ → escalar a guard. Taxonomía completa y esquema del ledger en `references/taxonomia-destinos.md`.

## Fase 5 — Informe y cierre

1. Rellena `templates/informe.md` (10 líneas, español, sin relleno).
2. Guarda informe + JSON en `/opt/data/brain/ops/session-retros/`.
3. Actualiza el ledger.
4. Aplica **solo** lo de bajo riesgo (patch de skill propia, 1 memoria) y di qué aplicaste; lo demás se propone con una línea de por qué.
5. Responde al usuario con el informe y la mejora aplicada. Nada de «quedo atento».

## Pitfalls

- **Autoevaluarse de memoria** en vez de correr el dossier → métricas inventadas. Siempre el script.
- **Leer `active=0`** → duplica turnos y dispara fallos falsos. El filtro canónico es `active=1`.
- Un `read_file` fallido **sí cuenta** como intento de pre-flight (el fallo es evidencia, no ausencia).
- Convertir una corrección del usuario en «memoria» cuando en realidad es una regla de skill.
- Escribir 10 lecciones: ninguna se recuerda. Máximo 3.
- Dar PASS por «me sentí bien». Sin cita, es FAIL.
- En sesiones de cron no hay usuario: el check 7 es `NA`, no FAIL; y el informe no se «responde», se archiva.
- El coste puede venir `0.0` si el perfil no tiene pricing: usa tokens como proxy, no inventes dólares.
- **Corregido en v1.1 (04-nov, parche verificado con `--selftest`):**
  - `hygiene.writes_without_prior_read` ya no cuenta archivos nuevos: `write_file` sobre un path inexistente va a `creates`, y sobre uno existente sin lectura previa va a `ambiguous_writes` (no se acusa sin poder probarlo). Solo `patch`/`edit_file` sin lectura previa cuenta como violación, porque editar exige que el archivo exista.
  - `user.corrections` ya no matchea preguntas: exige marcador de rechazo («no,», «está mal», «así no», «corrige»…) y descarta interrogativas salvo rechazo explícito. Para auditar el recall está `user.turns_text` (todas las intervenciones, sin filtro).
  - `--last N` omite por defecto las sesiones sin mensajes y reporta `sessions_skipped_empty`; `--include-empty` recupera el comportamiento antiguo para auditoría.
- **Corregido en v1.2 (04-nov):**
  - `espejo_ledger.py` acepta `--ledger` antes o después del subcomando, y tiene su propio `--selftest` (4 comprobaciones: flag global, flag post-subcomando, `count` post-subcomando, destino inválido rechazado). Mecanismo para reproducir el fix: el flag se declara en el parser raíz Y en cada subparser con `default=argparse.SUPPRESS`; si se declara solo en la raíz, el default del subparser lo pisa y el flag post-subcomando falla; si se repite con default normal, el subparser pisa el valor global. Se resuelve después en `main` leyendo `args.ledger` una sola vez.
  - `--patrones [N]` ya existe: agrupa por sesión distinta (no por aparición) y colapsa runs consecutivos de la misma tool, porque `terminal,terminal,terminal` es un run, no un procedimiento. Umbral por defecto: 3 sesiones.
  - Límite conocido: el coste es lineal en sesiones (~4 s para 25). No bajar el umbral de 3 sin mirar el JSON: con 2, casi todo parece patrón.

## Verificación

Tres gates, todos deterministas y sin red. Si alguno falla, no se usa la skill: se arregla.

```bash
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --selftest   # 19 comprobaciones
python3 /opt/data/skills/core/espejo/scripts/espejo_ledger.py --selftest    # 4 comprobaciones
python3 /opt/data/skills/core/espejo/scripts/espejo_evidence.py --patrones 5 --out /tmp/p.json
```

Esperado: `SELFTEST OK (19 comprobaciones)`, `SELFTEST LEDGER OK (4 comprobaciones)` y un JSON de patrones con las cinco claves (`fallos_recurrentes`, `bucles_de_sistema`, `escrituras_repetidas`, `correcciones_repetidas`, `procedimientos`).

El selftest cubre específicamente los defectos ya pagados: creación vs sobrescritura, pregunta vs corrección, sesión vacía vs sesión con actividad, colapso de runs y umbral de 3 sesiones.

## Referencias

- `references/rubrica.md` — definición operativa de los 8 checks, umbrales y ejemplos PASS/FAIL.
- `references/taxonomia-destinos.md` — las 5 cajas, regla 1-2-3, esquema y retención del ledger.
- `references/investigacion.md` — fuentes (Reflexion, CRITIC, Huang et al., postmortem SRE, claude-reflect) y qué se tomó de cada una.
- `templates/informe.md` — plantilla del informe de 10 líneas.
- `scripts/espejo_evidence.py` — dossier forense (stdlib, solo lectura, `--selftest` incluido).
- `scripts/espejo_ledger.py` — ledger de lecciones y regla de promoción.

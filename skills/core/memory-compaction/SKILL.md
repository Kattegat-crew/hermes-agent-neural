---
name: memory-compaction
description: Compactar MEMORY.md y memoria nativa sin perder nada.
version: 1.1.0
author: Jonathan Parra (Plon) / NeuralCrew Labs
license: MIT
platforms: [linux, macos]
tags: [memoria, compactacion, memory, brain, engram, contexto, refactor]
metadata:
  hermes:
    tags: [memoria, compactacion, memory, brain, engram, persistencia, contexto]
    category: core
    related_skills: [brain-knowledge-ops, engram-memory-system, hermes-agent]
---

# Memory Compaction Skill

Baja la ocupación de `MEMORY.md`/`USER.md` repartiendo cada entrada a su destino permanente
(brain, memoria de repos, skills, vault, Engram) sin borrar nada: todo lo retirado queda en un
archivo verbatim consultable con `mem_recall.py`. No decide qué es importante por ti: mide,
propone y aplica un plan bajo un gate que bloquea cualquier pérdida.

## When to Use

- `memory(action="add")` falla con `would put memory at N/100,000 chars` o el store está sobre 85%.
- El Admin pide "compactar / depurar / archivar la memoria" o "no quiero perder lo que sabemos".
- Antes de subir `memory_char_limit`: primero se compacta, después se amplía.
- Hay entradas duplicadas, superadas o de estado efímero mezcladas con invariantes.
- Hace falta recuperar un dato que ya no está cargado en el prompt: eso es `mem_recall.py`, no re-investigar.

## Prerequisites

- `python3` ≥ 3.10, solo stdlib (no instala nada). Sin acceso a red.
- Store del perfil: `<HERMES_HOME>/memories/MEMORY.md` y `USER.md`
  (`HERMES_HOME=/opt/hermes-agent-data`; perfiles en `profiles/<perfil>/memories/`).
- Destinos vivos: `/opt/data/brain/` (curado), `<repo>/PROJECT_MEMORY.md|AGENTS.md|.agents/rules/`,
  `/opt/data/skills/`, `/opt/vault/`, Engram en `/opt/data/home/.engram/engram.db`.
- Compactar el store **modifica** memoria persistente: es cambio de alto impacto. Presentar el
  resumen del plan (entradas que salen, destino, ocupación resultante) y esperar aprobación explícita.
- Si el destino es Engram, primero guardar con `mem_save` (MCP `engram`, `tool_search` si está diferido)
  y usar el `id` devuelto en el plan.

## How to Run

```bash
S=/opt/data/skills/core/memory-compaction/scripts
python3 $S/memory_inventory.py --profile default                 # diagnóstico (solo lectura + auditoría)
python3 $S/memory_inventory.py --profile default \
    --json /opt/data/brain/memoria-archivo/inventario.json \
    --md   /opt/data/brain/memoria-archivo/inventario.md \
    --emit-plan /opt/data/brain/memoria-archivo/plan.json        # esqueleto del plan
python3 $S/memory_apply.py --plan /opt/data/brain/memoria-archivo/plan.json --check-only
python3 $S/memory_apply.py --plan /opt/data/brain/memoria-archivo/plan.json
python3 $S/mem_recall.py "banco lucky" --limit 6                  # recall multi-fuente
python3 $S/mem_recall.py "FZY552" --only-archive                  # solo archivo verbatim
python3 $S/selftest_memory_compaction.py                          # 29 comprobaciones deterministas
```

El inventario **audita por defecto la consolidación anterior**: lee el último `recibo-*.json`,
cuenta los datos duros de cada entrada archivada y busca cuáles reaparecieron en las sesiones
posteriores (state.db). Lo que "vuelve" se lista como `↩ #idx …` y penaliza el archivado en la
próxima corrida. `--no-audit` lo desactiva (solo para runs sin state.db). Tras un **rollback**, el
recibo más reciente describe el store que está de vuelta en disco: el inventario ignora recibos
 cuyo `chars_after` coincide con el store vivo (±80 chars) y audita contra el recibo anterior real;
si no queda ninguno válido, la ventana de auditoría de esa corrida no es señal — no citarla como
"cero ↩".

Opciones que cambian el resultado: `--keep-budget 0.45` (cupo always-on), `--max-fill 0.70`
(tope tras compactar), `--coverage-threshold 0.35` (exigencia al destino), `--allow-discard`,
`--dry-run`. En `USER.md` usar `--target user` (límite 8,000; ahí solo identidad y preferencias).

## Quick Reference — destinos

| Destino | Qué va ahí | Forma concreta |
|---|---|---|
| `MEMORY.md` (keep) | invariantes de comportamiento, autoridad, prohibiciones, rutas que se necesitan antes de cualquier tool | entrada corta, sin historia |
| `brain` | cliente, negocio, arquitectura, decisión con fecha y porqué | `/opt/data/brain/{entities,concepts,ops,analysis}/<slug>.md` con frontmatter e `[[enlaces]]` |
| `repo` | ruta, comando, quirk de build/commit de UN proyecto | `<repo>/PROJECT_MEMORY.md` o `AGENTS.md` (commit en el repo) |
| `skill` | procedimiento reutilizable, pitfall de una tarea recurrente | `skill_manage` sobre la skill del dominio (`references/<tema>.md`) |
| `vault` | topología de infra, puertos, contenedores, catálogo de APIs | `/opt/vault/ARCHITECTURE.md`, `/opt/vault/AGENTS.md`, `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md` |
| `engram` | episodio buscable (incidente, sesión, id de job) | `mem_save(type=..., project=...)` → `{"kind":"engram","observation_id":N}` |
| `archive` | todo lo demás: queda verbatim + `mem_recall` | automático en `memoria-archivo/*.jsonl` |

**La distinción que decide todo — invariante vs. evento:**

- **Invariante**: dice cómo actuar *la próxima vez* ("los jobs que entregan a Discord viven en el
  perfil `default`", "no se paga API sin firma"). Se lee **antes** de la tool. Su sitio es
  `MEMORY.md`, una skill o `AGENTS.md`; **nunca `archive`**. Que el brain mencione el tema no lo
  hace prescindible: el brain solo se consulta si alguien ya decidió consultarlo.
- **Evento**: cuenta algo que ya pasó ("cierre 02-oct", "auditoría 05-oct OK", "incidente resuelto
  con commit X"). Su sitio es brain/ops o Engram; si nadie lo reusó en la ventana medida, sale.
- **Estado**: número, ocupación de disco, "hoy sigue caído". Caduca en días → brain o Engram.

Detalle, reglas de decisión y ejemplos: `references/taxonomia-destinos.md`.
Plantilla de nota: `templates/nota-destino.md`.

## Procedure

0. **Auditar la consolidación anterior (antes de decidir nada).** El inventario ya lo hace; leer el
   bloque `auditoría` / `↩`. Si una entrada archivada la semana pasada volvió a usarse, el archivado
   fue prematuro: o estaba mal ruteada (invariante mandado a brain) o el destino no se lee nunca.
   Corregir el criterio, no solo la entrada. Evidencia real (nov-2026): la regla "los jobs de Discord
   deben vivir en el perfil `default`" se archivó con "cubierto en brain 100%" y 11 h después se
   cablearon 12 jobs al perfil equivocado con falso verde de `cron run`; hubo que redescubrirla a
   golpes y volver a escribirla.
1. **Congelar y medir.** `git status` en repos implicados y `memory_inventory.py` sin flags de escritura.
   Guardar el JSON/MD del inventario: es la foto que se cita al aprobar. Anotar ocupación, nº de
   entradas y los avisos (`H3`: `MEMORY.md` legacy que el runtime NO lee; `H4`: separador `§`
   huérfano — `parse_entries` lo normaliza y el apply lo repara).
2. **Decidir el cupo.** `--keep-budget` (0.45 por defecto): cuánto prompt se reserva al bloque
   always-on. Objetivo sano 40–60%; por debajo de 30% se pierde la ventaja de tener el contexto cargado.
3. **Rutear de verdad, no de palabra.** Para cada entrada marcada `move`, escribir el destino con
   `write_file`/`patch` (brain con frontmatter y enlace, repo con commit, skill con
   `skill_manage`, Engram con `mem_save`). El destino debe contener los datos duros de la entrada:
   IDs, NIT, rutas, hosts, comandos, cifras, decisiones con fecha.
   Técnica probada (primer apply real, 2026-11): extraer el texto verbatim de las entradas `move`
   con `raw.split('\n§\n')` sobre el store — el índice 1-based del split coincide con el `idx` del
   plan — y pegarlo íntegro en una sección del destino; eso garantiza cobertura ~100% en el gate
   sin adivinar qué tokens cuenta el threshold.
4. **Editar el plan.** Partir del `--emit-plan`, corregir `action` (`keep|move|merge|archive|discard`)
   y rellenar `destination` (`{"kind","path","anchor"}` o `{"kind":"engram","observation_id":N}`).
   No tocar `idx`/`sha1`: los calcula el inventario y son el candado anti-plan-viejo.
   Si el gate frena una entrada por "parece un invariante", la salida correcta es `keep`/`move`; solo
   si de verdad es un postmortem ya cubierto se archiva añadiendo `"invariant_ack": true` **y** el
   motivo en `reason` (queda trazado en el recibo).
5. **Pasar el gate.** `--check-only` debe salir `OK`. Si bloquea, el mensaje dice entrada y motivo
   (destino inexistente, cobertura baja, merge sin fusionar, cupo excedido). Arreglar el destino,
   no relajar el umbral sin justificarlo.
6. **Aplicar.** `memory_apply.py --plan ...`. Escribe backup, archivo verbatim, nuevo store atómico
   y recibo JSON. Un fallo en cualquier paso deja el store original intacto.
7. **Verificar y cerrar.** Mantener una lista corta de invariantes de máximo riesgo (canales de
   entrega, bypasses, gates de gasto, rutas de servicios) y comprobar que CADA una sigue presente
   en el store resultante antes de dar por buena la compactación: el gate garantiza cero pérdida
   mecánica, no calibración, y un keep erróneo solo se detecta contra esa lista. Comprobar con
   `memory(action="search")` que una entrada retirada ya no está y que el puntero sí;
   `mem_recall.py "<token>"` debe encontrar lo retirado. Anotar en
   `/opt/data/brain/log.md` (una línea: fecha, 174→N, ocupación, recibo) y, si se movió a Engram,
   `mem_save` del cierre.

## Pitfalls

- **`cubierto en brain` no significa prescindible.** Es el error que más caro salió: el score
  premiaba la cobertura léxica del brain y castigaba la falta de cobertura, así que una regla dura
  con gemelo en un postmortem del brain se archivaba y un evento sin gemelo se quedaba. Invertido
  desde v1.1.0: el invariante puntúa por encima de la cobertura y `memory_apply` bloquea archivarlo
  sin `invariant_ack`. Si el motivo del plan dice "ya cubierto en brain" y la entrada empieza por
  "regla/nunca/prohibido", para y léela.
- **Los recibos de consolidaciones anteriores no son conocimiento.** Entradas que empiezan por
  "Memoria nativa compactada…" son log: van a `discard` siempre (el recibo real está en
  `memoria-archivo/recibo-*.json`).
- **Restos de prueba.** `Test entry.`, fragmentos de <40 chars o frases sueltas se descartan
  (`is_junk`); si el inventario los deja en `keep`, el bug es del scorer, no del store.
- **Mismo hecho en tres entradas.** El jaccard de palabras no ve duplicados cuando cambia la
  redacción; desde v1.1.0 se comparan **datos duros** (IDs, rutas, ficheros). Tres entradas del
  mismo pipeline = un `keep` canónico y dos `merge`.
- **Editar `MEMORY.md` a mano con `patch`/`write_file` rompe el store.** El runtime exige entradas
  separadas por `\n§\n`; un fichero sin delimitadores dispara el guard de drift (issue #26045) y
  bloquea escrituras. Usar siempre `memory_apply.py`.
- **Un plan viejo se rechaza por `sha1`.** Es a propósito: si el store cambió, re-ejecutar inventario.
- **Verificar post-apply por contenido, no por índice.** Al retirar N entradas los índices del store
  se re-encuadran: comparar el sha1 del índice i del store nuevo contra el índice i del viejo da
  alarmas falsas ("0/71 se conservaron" cuando estaban todas). Localizar cada `keep` del recibo
  por su sha1 DENTRO del nuevo store y contar coincidencias por hash.
- **Compactar sin destino real = pérdida silenciosa.** El archivo verbatim salva el dato, pero si
  nadie lo lee nunca el trabajo se degrada. Rutear a brain/repo/skill lo que se vaya a necesitar.
- **`USER.md` no es un archivo de proyecto.** Identidad, roles y preferencias del Admin no se
  archivan; compactar ahí es fusionar duplicados, nunca vaciar.
- **Cobertura baja no es destino válido.** Un resumen de 2 líneas para una entrada de 1,500 chars
  pierde IDs; el gate lo detecta (<35%). Pegar los datos duros o subir la entrada a `archive`.
- **No compactar en caliente mientras un cron escribe memoria.** Si el job diario de consolidación
  está corriendo, esperar a que termine o el plan quedará desactualizado.
- **Engram sin `mem_save` previo** produce `observation_id` inexistente y bloquea el apply.
- **Destino `skill` sin home real = no forzar la skill.** Si el inventario propone `skill` pero la
  skill del dominio no existe (o su creación ya fue rechazada por `guard_autoskill_create`), rutear
  como runbook en `/opt/data/brain/ops/runbook-<tema>.md` y anotar el motivo en `reason` del plan;
  no crear la skill rechazada ni dejar la entrada sin destino.
- **El tope `--max-fill 0.70` es deliberado:** compactar hasta el 99% deja el problema para mañana.

## Verification

- `python3 scripts/selftest_memory_compaction.py` → `TODO OK` (29 comprobaciones: gate, verbatim byte
  a byte, recall, plan obsoleto, tope de ocupación). Debe correr verde antes de tocar un store real.
  El selftest valida **mecánica** (gate, verbatim, recall), no **calibración** del scorer: un run real
  puede archivar una regla crítica con el selftest en verde. La calibración solo la prueba el ciclo
  de auditoría (`↩` en corridas sucesivas) más la lectura manual de los keeps de mayor riesgo del
  plan antes del apply.
- `memory_inventory.py` → el bloque `auditoría` lista las `↩` (archivadas que volvieron). Cero
  `↩` en dos consolidaciones seguidas = el criterio de reparto está bien calibrado.
- `memory_apply.py --check-only` → `OK: el plan pasa el gate de cero pérdida`.
- Post-apply: `memory(action="search", target="memory", content="<token de una entrada retirada>")`
  devuelve vacío; el puntero de recuperación aparece en el store; `mem_recall.py "<token>"` devuelve
  la entrada desde `archivo-memoria`.
- `mem_recall.py` sin coincidencias termina con exit 1: es el comportamiento esperado de una prueba
  negativa, no un fallo de la herramienta. No inventar flags: `--only-archive` existe,
  `--from-archive` no; verificar la interfaz antes de la prueba.
- Recibo en `/opt/data/brain/memoria-archivo/recibo-*.json` con `chars_before/after`, `counts`,
  `retired[]` (idx, sha1, action, destination) y `rollback`.

## Rollback

```bash
cp /opt/data/brain/memoria-archivo/backups/<ts>-<perfil>-memory/MEMORY.md \
   /opt/hermes-agent-data/memories/MEMORY.md
```

El backup incluye también `store.tar.gz` y `manifest.json`. El archivo verbatim no se borra nunca:
aunque se revierta el store, sigue sirviendo para recall y para rehacer el reparto.

Tras un rollback, anular el archivo de la corrida revertida: mover sus `.jsonl`/`.md` a
`memoria-archivo/anulados/` con sufijo `.anulado` y añadir `"anulado": true` al recibo
correspondiente. Sin este paso, `mem_recall` devuelve cada entrada retirada DOS veces (la anulada y
la vigente) y el recall queda contaminado de duplicados permanentes.

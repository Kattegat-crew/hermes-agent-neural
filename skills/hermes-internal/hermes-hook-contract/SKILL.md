---
name: hermes-hook-contract
description: Use when a Hermes hook blocks with unparseable stdout.
version: 1.0.0
author: NeuralCrew
license: MIT
tags: [hermes, hooks, fail_closed, pre_tool_call, diagnostico]
metadata:
  hermes:
    tags: [hermes, hooks, fail_closed, diagnostico]
    related_skills: [hermes-runtime-ops, vps-storage-restic-ops]
---

# Contrato de hooks `fail_closed` de Hermes

## Cuándo usar
- Una tool devuelve `hook <ruta> failed closed: unparseable stdout (expected a JSON object)`
  aunque el hook esté decidiendo **permitir**.
- Un comportamiento desaparece sin error visible para el usuario.
- Se restauran hooks desde un backup tras un upgrade.

## Contrato exacto del runtime
`agent/shell_hooks.py::_evaluate_result` (~línea 606):

- stdout **vacío** + exit 0 → permitido.
- `{"action":"block","message":"..."}` + exit 2 → bloqueo con ese mensaje.
- `{"action":"modify","args":{...}}` + exit 0 → modifica los argumentos.
- **Texto no-JSON en stdout** + exit 0, con `fail_closed: true` → **BLOQUEO**
  (`unparseable stdout`).
- Texto no-JSON + exit 2 → bloqueo, usando stderr como mensaje.

Regla dura: **un hook fail_closed no puede imprimir mensajes informativos por stdout.**
Para orientar al agente, escribir a un fichero/ledger o a stderr.

## Diagnóstico en 4 pasos
1. Ver el registro y el contrato: `grep -n -A4 "<hook>" /opt/data/config.yaml`.
2. Ejecutarlo a mano con un payload realista por stdin y medir bytes de stdout.
3. Validar que la salida sea un objeto JSON; si no lo es y el hook es fail_closed, el bloqueo está explicado.
4. Medir el daño en logs: `grep -h "<hook>.py failed closed" logs/*.log | sed -E 's/^([0-9-]+ [0-9:]+).*/\1/' | sort -u`.
   Usar `sort -u`: `errors.log` y `agent.log` duplican la misma línea.

Probar **las dos ramas** siempre: payload que debe permitir (esperado 0 bytes) y payload que debe
bloquear (esperado JSON + exit 2). Si solo se prueba una, el gate puede estar roto en silencio.

## Caso real — 04-nov-2026, `guard_autoskill_create.py`
- Gate de `skill_manage(create)` con `fail_closed: true` en 13 configs.
- Imprimía el índice de clases (3.515 bytes de texto) en la rama de permiso ⇒ el runtime lo
  convertía en bloqueo: **toda creación de skills rechazada**. `patch`/`delete` pasaban porque
  esas ramas no imprimen nada.
- Origen: restauración de hooks desde backup pre-upgrade (`7e6e39ea39`). 10 creaciones perdidas
  entre 04:15 y 11:50, invisibles salvo en el error de la tool.
- Fix (`5837a7eacd`): la rama de permiso escribe el índice en `/opt/data/state/autoskill_digest.txt`
  y no imprime nada.

## Checklist al restaurar hooks desde un backup
1. Comparar la versión restaurada con el contrato vigente del runtime (¿imprime texto plano?).
2. Probar rama permitir y rama bloquear.
3. Buscar `failed closed` en los logs desde la hora del despliegue antes de dar el restore por bueno.

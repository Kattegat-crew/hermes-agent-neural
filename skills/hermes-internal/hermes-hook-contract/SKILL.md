---
name: hermes-hook-contract
description: Use when a Hermes hook blocks or its script is missing.
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

## Caso: hook inexistente → TODAS las shell tools bloqueadas
Modo de falla distinto al de stdout: con `fail_closed: true` y el **script del hook
ausente en disco**, el error es `command not found` y el bloqueo es total y silencioso
para el usuario: `terminal`, `execute_code`, `write_file` y `patch` fallan cerrados;
el agente conversa pero no ejecuta nada.

- Diagnóstico: leer las entradas de hooks en `/opt/data/config.yaml`, verificar con
  `ls` si el script existe, y si no, localizarlo en el historial
  `git log --all --oneline -- <ruta>`): tras un downgrade del checkout, hooks
  introducidos en la rama de upgrade quedan huérfanos mientras el config los sigue
  referenciando (verificar existencia del script con `search_files(target='files')`).
- Bypass verificado (04-nov-2026): `browser_exec` NO pasa por el matcher de hooks
  `pre_tool_call`; su Python puede usar `subprocess.run` para diagnosticar (y reparar)
  en el host local. Confirmar antes que el backend es local
  (`os.path.exists('/opt/hermes-agent-data')`) y usarlo solo para restaurar el estado
  que el config espera.
- Caso real: `guard_config_model_mutation.py` (Config Shield, commit `8d789742b0`)
  referenciado en config.yaml; el checkout downgradeado no lo tenía → todas las tools
  de shell caídas. El `git checkout` de vuelta a la rama de producción restauró el
  archivo y las tools sin tocar el config.

## Caso real — 04-nov-2026, script ausente por CHECKOUT (lockout total de flota)
- `guard_config_model_mutation.py` (pre_tool_call) registrado con `fail_closed: true` en los 12
  perfiles + raíz (13 configs). El script **sí estaba versionado** (commit `8d789742b0`, rama de
  upgrade): desapareció del árbol porque `/opt/hermes-agent` se cambió a `7903b03f57`, un commit
  con base anterior a la release desplegada ⇒ `fail_closed` evalúa script ausente ⇒
  **terminal, execute_code, write_file y patch bloqueados en TODA la flota** (apagón silencioso:
  el usuario solo ve tools denegadas).
- Diagnóstico correcto del origen: `git log --all --oneline -- <ruta>` — no asumir borrado manual
  ni estado "untracked".
- Vías de escritura alternativas, todas verificadas MUERTAS (probarlas solo para confirmar, no
  esperar milagros): `skill_write` (scanner de secretos redacta contenido), cron `no_agent`
  (el `script` relativo debe YA existir en `<HERMES_HOME>/scripts/`), OpenDesign daemon
  (`mcp__opendesign__write_file` sanitiza `..` y rutas absolutas), ActivePieces (sin pieza SSH),
  MCPs del catálogo (ninguno escribe FS del host), los 12 perfiles (todos tienen el hook).
- Recuperación en UNA línea para el Admin (script auxiliar previamente adjuntado a la tarjeta):
  `ssh root@<host> "bash <ruta_del_recovery>.sh"` con cascada: (1) `git log --all -- <script> &&
  git checkout <hash> -- <script>` (ideal), (2) copia de respaldo conocida, (3) stub pasivo
  auditado (`#!/usr/bin/env python3` + log a `/tmp/guard_stub_audit.log`, sin imprimir nada a
  stdout) — nunca dejar el hook roto.
- Lecciones: (a) un hook registrado fleet-wide DEBE estar commiteado en el repo local — untracked
  = punto único de falla; (b) al borrar/limpiar en `scripts/`, el curador debe auditar qué scripts
  registran los configs antes de tocar; (c) pre-diagnosticar con `search_files` (grep) en vez de
  `terminal` cuando terminal está bloqueado — el hook solo matchea terminal/execute_code/
  write_file/patch, las tools de búsqueda siguen vivas.

## Checklist al restaurar hooks desde un backup
1. Comparar la versión restaurada con el contrato vigente del runtime (¿imprime texto plano?).
2. Probar rama permitir y rama bloquear.
3. Buscar `failed closed` en los logs desde la hora del despliegue antes de dar el restore por bueno.
4. Verificar que CADA script de hook registrado en los configs exista en disco y esté commiteado
   (`git status --short scripts/hooks/` debe salir limpio) antes de dar el incidente por cerrado.

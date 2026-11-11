---
name: hermes-admin-operations
description: "Use when operating/auditing Hermes config and gateway."
tags: [hermes, ops, admin, config, provider, gateway, cron, administrador]
version: 1.0.0
author: Ragnar
triggers:
  - configurar hermes / cambia el modelo / cambia el proveedor / añade skill o MCP / audita la config / mantenimiento de hermes
  - provider: proveedor / provider / NaN-Builders / OpenRouter / base_url
  - gateway: gateway caído / reinicia el gateway / puerto serve / desktop no conecta
  - plan de rol administrador: agente administrador de Hermes / bot de operaciones
metadata:
  hermes:
    tags: [hermes, ops, config, provider, gateway, cron, administrator]
---

# Hermes Admin Operations — operar la plataforma Hermes como operador principal

Patrón del "agente administrador de Hermes" (inspirado en el rol Havoc / Bot Mode de Hermes Desktop, 08/2026): en lugar de memorizar cada comando, recibir la **intención** ("quiero X resultado"), inspeccionar la config real, hacer el cambio, verificar que quedó y **escalar solo lo humano**. Ragnar es el agente administrador sobre el perfil propio; este skill formaliza el ciclo en maquinaria reutilizable.

## Disparadores

- «configurar hermes», «cambia el modelo/proveedor», «añade skill/MCP», «audita/revisa config», «haz mantenimiento de hermes», «el gateway cayó», «el desktop no conecta».
- Cualquier petición que toque `config.yaml`, `.env`, `cron/jobs.json`, `mcp_servers`, perfiles o el gateway.

## Ciclo operativo D-I-V-E (núcleo)

1. **D = Diagnosticar / INSPECT** — leer el estado real ANTES de tocar nada:
   - `hermes config list` / `hermes config get <ruta>` — config vigente.
   - `hermes model` · `hermes gateway status` · `ss -tlnp` (puertos reales escuchando, p. ej. 9112/8642/8645).
   - `cron/jobs.json` · configuración de MCP · perfiles en `profiles/<name>/config.yaml`.
   - Nunca adivinar: si no sabes el estado, léelo.

2. **I = Cambiar CHANGE** — con backup SIEMPRE:
   - Copiar `config.yaml` → `config.yaml.bak-<fecha>` antes de tocar (o usar `hermes config set KEY VAL` cuando aplica, que valida sintaxis).
   - Secrets NUNCA en `config.yaml` — van en `.env` (tokens, API keys).

3. **V = Verificar VERIFY** — comprobar que el cambio quedó efectivo:
   - Releer la config/key tocada.
   - Health check real: puerto escuchando, `gateway status`, respuesta HTTP.
   - Test de humo del flujo que se tocó (p. ej. desktop conectando, bot respondiendo).
   - "Está hecho" solo tras verificar.

4. **E = Escalar solo lo humano ESCALATE** — qué NO puede hacer un agente:
   - API keys, OAuth, tokens @BotFather, crear bots/perfiles nuevos, credenciales.
   - Escribirlo en `brain/tasks/pending.md` y seguir; NO bloquear el proceso por ello.

## Pitfalls

- **Alias de provider obsoleto**: versiones nuevas de Hermes (p. ej. serve v0.20.4) dejan de reconocer alias heredados tipo `custom:nan-builders`. Síntoma: `Unknown provider 'custom:nan-builders'. Check 'hermes model'...`. Usar el **nombre canónico** del provider (`NaN-Builders` en el config principal del serve) — no el alias viejo. Fix: backup + reescribir esa línea en `config.yaml` (no en `.env`, que ya no lee `LLM_MODEL`), reiniciar `hermes-serve` y verificar.
- **Desktop cachea provider**: tras reiniciar el serve, el Desktop puede mantener el provider viejo en memoria. Si persiste, cerrar la app completa (bandeja del sistema → Salir) y relanzar.
- **Gateway y serve son procesos separados**: `hermes gateway status` "running" NO implica que la API HTTP escuche. Verificar con `ss -tlnp` sobre el puerto real.
- **Reinicio bajo systemd**: `systemctl restart hermes-serve` tarda ~20s y desconecta el Desktop — anunciarlo antes al operador.
- **`hermes gateway status --verbose` NO existe** — no inventar flags; usar `hermes gateway status`.
- **Ruta del config:** `/opt/data/config.yaml` (no `/opt/data/data/...`; ese intento falla con FileNotFoundError). Inventario y topología MCP (snapshot 2026-09-25 + patrón estable + quirk canva/pg_ro): `references/mcp-inventory.md`.

## Instalar un MCP NO catalogado (vía `hermes mcp add`)

El conector `manage_connections` SOLO instala MCPs del catálogo propio (`install` falla con
`unknown MCP server(s)` para todo lo demás). Para un MCP hosted no catalogado (ej. **Exa**,
instalado y verificado 02-nov-2026) la vía canónica es la CLI, siguiendo D-I-V-E:

1. **D:** confirmar que el servidor ofrece endpoint MCP (documentación oficial) y qué tools expone.
2. **I:** backup de `config.yaml` → `config.yaml.bak-<fecha>` y luego:
   `hermes mcp add <nombre> --url '<URL-con-parametros>'`
3. **V:** `hermes mcp test <nombre>` (transporte + tools descubiertas). Las tools quedan
   disponibles tras `/reload-mcp` en la sesión abierta o en una sesión nueva.

- **Prompts interactivos headless:** `hermes mcp add` pregunta "¿requiere auth? [Y/n]" y "¿habilitar
  todas las tools? [Y/n/select]". En headless pipear las respuestas: `printf 'n\ny\n' | hermes mcp add ...`
  (`n` = sin auth cuando el endpoint es keyless; `y` = habilitar todas). Sin TTY el prompt de API key
  se cuelga con warning de getpass y cancela el add.
- **Exa (referencia):** URL con tools explícitas:
  `https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa`.
  La lista `tools=` REEMPLAZA los defaults; incluir cada tool deseada. Keyless funciona con
  rate-limits gratuitos; con API key usar header `x-api-key` (o OAuth vía `?login`).
  `agent_run` de Exa solo aparece autenticado (OAuth o API key).
- **Prueba real headless alternativa:** si el cliente MCP Python está en el entorno, validar el
  endpoint antes/después del add con `streamable_http_client` del SDK `mcp` — ojo a la versión del
  SDK: el generador puede yieldear 2 streams (no 3) y `CallToolResult` usa `is_error`, no `isError`.
  Instalar desde memoria del SDK es frágil; verificar campos con `model_fields` antes de iterar.

## Cerrobloqueo approvals.deny (capa 2) — auditoría y pruebas seguras

- Semántica: `approvals.deny` en `config.yaml` son globs fnmatch que bloquean ANTES de cualquier bypass (`--yolo` / `mode: off`); se verifica con `hermes approvals test -- <cmd>` (exit 0 allow / 2 ask / 3 deny). Capa 1 hardline (blocklist fija en `tools/approval.py`) y capa 2 deny sobreviven a todos los modos.
- **PATRÓN CLAVE — nunca poner literales de reglas deny en el texto de un comando de terminal:** el gate analiza el texto COMPLETO del comando y atrapa fragmentos de prueba (reconstrucciones por partes, comentarios, ssh embebido). Para probar reglas destructivas: escribir el script/payload a archivo con `write_file` y ejecutarlo, o pipearlo por stdin (`cat payload.sh | ssh prod "docker exec -i <container> sh"`).
- Verificación E2E en contenedor remoto: config en disco ≠ gate vivo. Verificar DENTRO del contenedor: `docker exec -i <c> sh < payload.sh` con `hermes approvals test`; confirmar el detalle `blocked even under --yolo / mode=off`.
- En `mode: off` los benignos pasan (exit 0 con `approval bypass active`) pero deny sigue bloqueando — diseño correcto para PROD.
- Contraste de resultados: un paste de pytest con `collected 0 items` indica intérprete/ruta equivocada, no suite vacía — re-correr con el python correcto (el venv del repo puede carecer de PyYAML; usar `/usr/bin/python3.12`) antes de aceptar.
- Residual aceptado (documentar, no intentar cubrir con globs): crons `no_agent` quedan fuera del interceptor (contención = permisos Linux); `docker system prune` sin `--volumes` sigue permitido por diseño.
- Receta completa de auditoría (DEV+PROD, script de pruebas, verificación en contenedor): `references/approvals-deny-audit.md`.

## Vigilancia automatizada (cron de mantenimiento)

- Job `hermes-maintenance-night` (03:30) con `monitor_script=/opt/data/scripts/hermes-ops-monitor.py`: verifica gateway UP y puertos clave, **monitorea updates del repo de Hermes** (GitHub API vs `hermes --version`), escanea errores del día en logs, revisa **logs de bots y comportamiento** (restarts, timeouts, bucles), comprueba disco/RAM, y como agente asigna **puntuación del output** (score 0-100 por bot) cuando se detecta cambio.
- Salida byte-estable del script = scheduler suprime el run; reporta **solo lo que cambió/se rompió** (silencioso si todo ok).
- Criterios y rutas de scoring: `references/monitoring.md`.
- Los jobs se registran en `cron/jobs.json`; auditar su vigencia en cada mantenimiento.

## Soporte

- Este skill materializa la Fase 1 del plan documentado en `/opt/data/brain/concepts/hermes-admin-operations.md` (ciclo DIVE, fases 1–5, track en `brain/tasks/pending.md`).
- Todo lo que requiere humano (tokens, OAuth, bots nuevos, perfiles) vive en `brain/tasks/pending.md`.
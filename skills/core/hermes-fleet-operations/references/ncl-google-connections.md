---
name: ncl-google-connections
description: Modelo multi-tenant de acceso Google (Gmail/Drive/Calendar) por perfil vía connections-map.json + MCP ncl_google. Aislamiento estructural por owners.
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [ncl_google, connections-map, gmail, multi-tenant, owners, activepieces, mcp, perfiles]
    category: devops
    related_skills: [hermes-multiprofile-cron-ops, hermes-profile-routing]
---

# NCL Google Connections — Modelo Multi-Tenant (connections-map + ncl_google MCP)

Cómo los perfiles de la flota acceden a bandejas/Drive/calendarios de CLIENTES
sin cruzar tenencias. Verificado en vivo en PROD (22-sep-2026).

## Arquitectura

- TODO acceso Google (Gmail, Drive, Calendar, Sheets) va por conexiones
  ActivePieces registradas en `/opt/data/connections-map.json` (PROD) con secrets
  materializados en `/opt/data/secrets/`. Protocolo canónico: el OAuth local
  (`google_token.json`) está REVOCADO/deprecated.
- MCP por perfil: `/opt/data/scripts/ncl_google_mcp.py --profile <perfil>`,
  montado en cada `config.yaml` como `ncl_google_<perfil>` con env
  `NCL_MAP=/opt/data/connections-map.json` y `NCL_SECRETS=/opt/data/secrets`.

## Filtro multi-tenant (el mecanismo clave)

El MCP resuelve para cada conexión `owners = e.get('owners') or [e['owner']]` y
SOLA expone la conexión si `profile in owners` **Y** `status == 'active'`.
El aislamiento es ESTRUCTURAL (código del MCP), no de disciplina del agente.

Consecuencias operativas:
- Para dar/quitar una bandeja de cliente a un perfil: editar `owners` en
  connections-map.json (flujo D-I-V-E con backup previo), NO tocar config del perfil.
- Conexiones con `status: pending` son invisibles al MCP aunque el owner coincida
  (ej. `golden-gmail2`, duplicado pendiente de `goldengameltda@gmail.com`; la
  activa es `golden-gmail`). No crear duplicados: reutilizar la activa.

## Mapa verificado (22-sep-2026)

| Conexión | Cuenta | Status | Owners |
|---|---|---|---|
| lucky-gmail | luckybrothers.sas@gmail.com | active | comms, default, helmer, lucky, yulieth |
| golden-gmail | goldengameltda@gmail.com | active | comms, default, helmer |
| golden-gmail2 | goldengameltda@gmail.com | pending | comms, default, golden |
| helmer-gmail | helmerparra@gmail.com | active | comms, default, helmer |

→ helmer ve Lucky+Golden; yulieth ve SOLO Lucky (golden queda excluido por owners).

## Tools expuestos por el MCP

- `gmail_list(query, max)` — listar/filtrar bandeja (ej. `from:dian.gov.co`, `is:unread`)
- `gmail_read(message_id)` — cuerpo completo
- `gmail_send(to, subject, body)` — envía EN NOMBRE DEL CLIENTE (usar con confirmación humana)
- `drive_search`, `drive_read_text`, `calendar_list_events`, etc.

## Nota ambiental (verificado 22-sep-2026)

- `/opt/vault` del CONTENEDOR default es mount READ-ONLY: los documentos tipo vault
  se escriben en el SSOT real vía `scp prod:/opt/vault/`. Alternativa writable local
  para docs de agencia: `/opt/hermes/skills/operations/`.
- Backup de conexiones antes de tocar el map (D-I-V-E):
  `cp /opt/data/connections-map.json /opt/data/connections-map.json.bak-<fecha>-<tarea>`.

## Patrón: radar de bandeja por perfil (cron F1)

Cron en el `cron/jobs.json` del PROPIO perfil (ver hermes-multiprofile-cron-ops
para el procedimiento y pitfalls de creación):
1. `gmail_list` con filtros de remitente crítico (DIAN, Coljuegos, bancos...)
2. `gmail_read` de los IDs no notificados aún
3. Clasificación con modelo barato del bucket del cron (deepseek-v4-flash)
4. Deliver al grupo WhatsApp @lid YA existente del perfil (no crear canales nuevos)
5. Anti-duplicado: JSON local con message IDs ya notificados
6. NUNCA incluir `gmail_send` en prompts de monitoreo (solo lectura)

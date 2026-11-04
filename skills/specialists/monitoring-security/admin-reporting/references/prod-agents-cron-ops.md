# Prod Agents / Cron Ops — Roster y canales reales

VPS prod: 169.58.189.222 (vmi3513784)
Contenedor: hermes-agent (v0.20.4)
Acceso: ssh root@10.0.7.1 → ssh -i /root/.ssh/id_ed25519 root@169.58.189.222

## Roster de agentes (perfiles por persona)

| Perfil | Persona | WhatsApp (chat_id) | LID |
|---|---|---|---|
| helmer | Helmer | 573166909310 | 109165234127014@lid |
| jacqueline | Jacqueline | 573166909018 | 138023102591227@lid |
| yulieth | Yulieth | 573107864877 | 194373190996209@lid |
| nancy | Nancy | 573214094625 | 42743615213574@lid |
| default (ragnar) | Jonathan (admin) | 573166910728 | 43001262956766@lid |
| neural-admin-test | — | — | — |

## WhatsApp
- 1 número compartido (bridge Baileys en prod)
- Bridge: POST /send en 127.0.0.1:3000 (dentro del contenedor prod)
- allowlist real: WHATSAPP_ALLOWED_USERS en /opt/hermes/.env (docker-compose env_file)
- PROHIBIDO enviar mensajes proactivos a las personas sin orden explícita del Admin
- profile_routes: 15 rutas (JID + número + LID por perfil)

## Cron jobs en prod (default)
- Solo el gateway del perfil **default** corre el scheduler
- Crear jobs en `/opt/data/cron/jobs.json` del default, NO en `profiles/<p>/cron/jobs.json`
- Los gateways por perfil existen como s6 services pero no ejecutan (`hermes cron status` da falso negativo)
- Jobs de saludo 7AM creados 24/08/2026:
  - Saludo 7AM helmer → whatsapp:573166909310
  - Saludo 7AM jacqueline → whatsapp:573166909018
  - Saludo 7AM yulieth → whatsapp:573107864877
  - Saludo 7AM nancy → whatsapp:573214094625

## Config
- cron.wrap_response: false (24/08/2026, con backup config.yaml.bak-20260824-wrapresponse)
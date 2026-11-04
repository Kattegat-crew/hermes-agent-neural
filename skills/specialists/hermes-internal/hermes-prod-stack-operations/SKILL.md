---
name: hermes-prod-stack-operations
description: "Use when auditing Hermes prod agents before proposing sends."
tags: [hermes, prod, vps, perfiles, whatsapp, auditoria]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [hermes, prod, vps, agentes, perfiles, cron, reportes, whatsapp, multi-vps]
---

# Hermes Prod Stack Operations — verificar antes de proponer, operar prod con evidencia

Regla de oro (aprendida por error grave 24/08/2026): **JAMÁS proponer envíos, entregas, saludos o rutas hacia agentes/perfiles/clientes basándose en documentos viejos o memoria desactualizada.** El usuario reclamó "Completamente falso!!!" cuando se inventaron canales WhatsApp para "Hermes Golden/Lucky" que ya no existen como perfiles activos en prod. La cadena correcta es: leer el estado REAL en vivo → proponer → ejecutar.

## Flujo obligatorio antes de operar sobre agentes

1. **Auditar prod en vivo** (no docs, no conceptos antiguos):
   - Desde el contenedor Hermes: `ssh root@10.0.7.1` (host dev) y desde ahí `ssh -i /root/.ssh/id_ed25519 root@169.58.189.222` (VPS prod).
   - Perfiles activos: `ls /opt/hermes/data/profiles/` en prod.
   - Ruteo WhatsApp: `grep -A 60 "profile_routes:" /opt/hermes/data/config.yaml` en prod (fuente de verdad: LID/JID/número → perfil).
2. **Cruzar con Engram**: `mem_search(all_projects=True, query=...)` — las session_summary recientes (`hermes-prod`, `neuralcrew_agent`) documentan despliegues reales y decisiones. Buscar ANTES de afirmar quién es quién.
3. **Solo entonces proponer** envíos/entregas, indicando chat_id real de cada destinatario.

## Topología multi-VPS (canónica 08/2026)

| Rol | Host | IP | Notas |
|---|---|---|---|
| VPS dev (este contenedor) | vmi3151337 | 147.93.3.250 | Hermes dev, Ragnar, roshi |
| Host del contenedor | — | 10.0.7.1 | gateway SSH desde el contenedor |
| VPS PROD | vmi3513784 | 169.58.189.222 | Stack producción: Hermes multiplex, Coolify, Twenty, landings |

Cadena SSH: contenedor → `root@10.0.7.1` (llave por defecto del host) → `root@169.58.189.222` (llave `/root/.ssh/id_ed25519` en el host dev).

## Perfiles reales en prod (verificado 24/08/2026 — re-auditar antes de confiar)

- `helmer`, `jacqueline`, `yulieth`, `nancy`, `default` (+ `neural-admin-test`).
- **No existen** perfiles `golden-game`/`lucky-club` activos en prod: fueron reemplazados por perfiles por persona (memoria Engram #252/#272). Los repos `hermes-casinos-repo/profiles/{golden-game,lucky-club}` son plantillas sin desplegar.
- WhatsApp: **un solo número compartido**, ruteo por `profile_routes` (3 formas por persona: LID, JID, número plano). Detalle de chat_ids en `references/prod-profiles-2026-08.md`.
- **Regla dura**: no enviar WhatsApp proactivo a personas sin orden explícita del usuario (Engram #252). El experimento de saludo matutino solo se ejecuta con orden directa.

## Cron jobs de reporte diario (lección: rutas rotas → datos reciclados)

Los jobs `context-report-morning` (8am) y `context-report-evening` (8pm) fallaban porque sus prompts apuntaban a `/root/hermes-agent-legacy-docker/...` (ruta HOST, no existe en contenedor) → el agente rellenaba con datos viejos y el usuario los veía "no actualizados". Diseño corregido y plantilla en `references/cron-report-jobs.md`.

## Pitfalls

- Conceptos antiguos (`equipo-de-bots.md`, `ragnar_golden_game.md`, planes de despliegue) son HISTÓRICOS, no estado actual. El estado real vive en config de prod + Engram session_summary recientes.
- El CLI `hermes` del contenedor NO resuelve a prod; para auditar prod hay que SSH en cadena (ver arriba).
- En prompts de cron, usar rutas reales del contenedor (`/opt/data/scripts/...`, `/opt/data/brain/tasks/pending.md`) — nunca rutas del host.

## Referencias

- `references/prod-profiles-2026-08.md` — roster real de prod (perfiles + chat_ids WhatsApp) verificado el 24/08/2026.
- `references/cron-report-jobs.md` — diseño de jobs de reporte diario: fuentes reales (clima, calendario, actividad), formato mínimo, reglas [SILENT].

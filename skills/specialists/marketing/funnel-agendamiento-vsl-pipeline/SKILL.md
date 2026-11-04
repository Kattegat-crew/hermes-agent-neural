---
name: funnel-agendamiento-vsl-pipeline
description: "Use when building an appointment funnel (AP + Twenty)."
tags: [funnel, agendamiento, activepieces, twenty, formbricks, leads, crm, vsl]
author: Ragnar
version: 1.0
created: 2026-09-08
category: devops
metadata:
  hermes:
    tags: [funnel, ventas, activepieces, twenty, formbricks, opendesign, leads, crm, pipeline]
    related_skills: [activepieces-selfhost-ops, activepieces-flow-editing, twenty-selfhost-auth, formbricks-v5-selfhost, open-design-selfhost-ops, webhook-gateway-multiclient]
---

# Funnel de Agendamiento con VSL (AP + Twenty)

## When to Use

Montar u operar el funnel de captura de leads B2B alto ticket para un cliente: tráfico pago → landing → encuesta de calificación → ActivePieces → Twenty CRM (tabla de leads) + Google Sheets → WhatsApp → agendar llamada.

## Stack (corre en PROD .222 / 100.73.30.29, `ssh prod`)

- **ActivePieces**: `ap-app :8088`, `ap-worker`, `ap-db` (pgvector), `ap-redis`. Webhook de un flow: `http://<IP>:8088/api/v1/webhooks/<flowId>`. MCP: `/mcp`.
- **Twenty CRM**: `https://crm.neuralcrewlabs.com` (compose `/opt/docker/twenty`, DB `default`). API REST `/rest/`, auth `Authorization: Bearer <API_KEY>` (Settings → API & Webhooks).
- **Formbricks**: `:3030`. Surveys con preguntas excluyentes; webhook de completion → AP.
- **OpenDesign**: daemon 7456 (NPM+Cloudflare). Genera landing HTML por marca vía REST API (`Bearer <OD_API_TOKEN>`). Design systems por cliente.
- **Google Sheets + Google Calendar**: OAuth por cliente (piezas nativas AP).
- **WhatsApp**: step **HTTP** hacia el bridge propio (`/opt/data/whatsapp/session/`), NO el piece nativo.

## CRÍTICO — Twenty NO tiene objeto "lead" nativo

Objetos reales: `company`, `person`, `opportunity`, `note`, `task`, `attachment`, `calendarEvent`, `workflow*`. Para una **tabla de leads** hay que:
- **crear un objeto custom `Lead`** vía Metadata API (`POST /rest/metadata/objects` + campos `/rest/metadata/fields`), con campos: `cliente` (Golden/Lucky), nombre, teléfono, email, presupuesto, industria, quién decide, origen/UTM, estado de calificación, score; **o**
- usar el modelo estándar **Person + Company + Opportunity** (orden: Company → Person → Opportunity; opportunity con `stage`, `pointOfContactId`).

## Flujo canónico

```
Meta/Google Ads → Landing (OpenDesign, brand system del casino)
  → Encuesta calificación (Formbricks, 3-4 preguntas EXCLUYENTES, max 5 campos)
  → Webhook completion → ActivePieces
      → crear Lead en Twenty (objeto custom) + fila en Google Sheets
      → WhatsApp (bridge) → agendar llamada (Google Calendar) → recordatorios
      → si califica y agenda → promover a Opportunity (stage MEETING)
```

## Piezas AP exactas

- **Trigger**: `catch_webhook` (o Typeform `new_submission` / Google Forms `new_response`).
- **Calificación**: step `ROUTER`/`BRANCH` (type `BRANCH`) con condiciones OR/AND → preguntas excluyentes; rama NO = descarta, rama SÍ = sigue.
- **IA (opcional)**: `OpenAIActGeneration` / Google Gemini `generate_content` para responder comentarios IG o resumir.
- **Twenty piece nativo**: triggers *New Person / New Company*; actions *Create Contact (Person)*, *Create Company*, *Create Opportunity*, *Find/Update*, *Custom API Call*. Usar `Custom API Call` para `POST /rest/opportunities` con `pointOfContactId`.
- **Google Calendar**: action *Create Event* (agendar) + *Add Attendees*; **trigger nativo de recordatorio `Event Start (Time Before)`**. No usar `Delay` para recordatorios.
- **Email**: `send_email` (SMTP) / Gmail; **`to` es array** `["email"]`.
- **Sheets**: acción add-row (configurar `basicFilter` para que appendee, no sobreescriba fila 2 — bug conocido).

## Pitfalls / reglas

- **Reiniciar `ap-app` Y `ap-worker` juntos** tras editar un flow (`flow.run` se resuelve por `trigger_source.flowVersionId`).
- Secretos: nunca hardcodear `AP_JWT_SECRET`/`AP_ENCRYPTION_KEY`/`OD_API_TOKEN`; consultar Vaultwarden.
- OOM: `Exited 137` = OOM, no error de app; ver `docker inspect -f '{{.State.OOMKilled}}'` y añadir `mem_limit` + `restart`.
- No probar con leads reales: marcador "PRUEBA INTERNA", verificar run y borrarlo.
- Multi-tenant: un funnel por cliente, **conexiones OAuth separadas por cliente**, campo `cliente` en Lead.
- Speed-to-lead <5 min (lift 4-8x); responder rápido + recordatorios H-24/H-2.

## Multi-tenant (2 workspaces) + Agente Concierge

- **Tenancy:** 2 workspaces Twenty (uno por cliente) — aislamiento físico (schema `workspace_<slug>` en Postgres, NO un filtro). Activar `IS_MULTIWORKSPACE_ENABLED=true` + `DEFAULT_SUBDOMAIN`. Subdominio por cliente (`golden.neuralcrewlabs.com`, `lucky.neuralcrewlabs.com`). Razón: permisos Twenty son **por-objeto (todo/nada)** y hay **bug #23062** (system objects se saltan los permisos por rol) → un workspace compartido expondría leads del otro casino; 2 workspaces lo hacen estructuralmente imposible. Roles: nosotros = **Admin**, cliente = rol propio.
- **Crear workspace** por UI (dropdown "create a new workspace"); **no hay REST público**. `IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS` para restringir. Migrar single→multi-workspace con cuidado (staging antes de prod).
- **API keys** por-workspace, `Authorization: Bearer <key>`, acoplables a rol (Settings → API & Webhooks).
- **Workflows Twenty:** triggers = record creado/actualizado, schedule (UTC), webhook, manual. Acciones = create/update/delete, search (cap 200), upsert, filter, **delay**, **send email**, code (JS), **HTTP request**. Límite **5.000 runs/hora** → ok nurturing individual, NO blasts.
- **Email:** Twenty envía **transaccional** (acción *Send Email* vía cuenta Gmail/MS/SMTP, adjuntos estáticos). **Email masivo de promos → ESP externo** (SendGrid/Brevo/Mailgun) invocado desde AP; **nunca** desde Gmail (quema dominio SPF/DKIM).
- **SMS/WhatsApp:** **NO nativo** → externo (bridge propio + Twilio) disparado desde AP vía HTTP/workflow; resultados vuelven a Twenty por webhook.
- **Agente Concierge POR cliente** (Golden/Lucky): atiende **WhatsApp** (bridge) + **voz entrada/salida** (NeuralCrew Connect / Twilio Voice). Califica, personaliza promos, agenda, hace seguimiento. **La llamada de cierre de alto ticket = humana**, con ficha del agente. Nunca promete fuera de las reglas comerciales del casino.

## Entregables / docs de referencia

- Investigación maestro: `/opt/data/funnel_pipeline_AP_twenty_investigacion_2026.md`
- Prácticas/frameworks: `/opt/data/funnel_b2b_altoticket_2026.md`
- Skills: `activepieces-selfhost-ops`, `activepieces-flow-editing`, `twenty-selfhost-auth`, `formbricks-v5-selfhost`, `open-design-selfhost-ops`.

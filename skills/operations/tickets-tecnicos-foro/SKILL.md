---
name: tickets-tecnicos-foro
description: Use when creating or updating tickets-tecnicos threads.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: proprietary
metadata:
  hermes:
    tags: [discord, tickets, foro, higiene, operaciones, gobernanza]
    related_skills: [hermes-cron-health, hermes-secrets-v022x-ops]
---

# Tickets del foro tickets-tecnicos

## When to Use
- Cualquier agente va a abrir, actualizar, fusionar, dividir o cerrar un ticket del foro `tickets-tecnicos`.
- Hay que decidir estado, responsable o entorno de un ticket existente.
- Un ticket nuevo se parece a otro ya abierto (posible duplicado a absorber).

Protocolo obligatorio para CUALQUIER agente que cree, actualice, fusione o cierre tickets.
El foro es la fuente de verdad del trabajo; el chat es solo el aviso.

## IDs canonicos
- Guild `1493354289266167808` · Foro `1554957746980261938`
- Tags estado: Pendiente `1554957746980261942` · En curso `...61943` · En revision `...61944` · Cerrado `...61945` · Bloqueado `...61946`
- Tags entorno: DEV `1554957746980261947` · PROD `1554957747005685860`
- Tags tipo: Mantenimiento `...61939` · Implementacion `...61940` · Incidente `...61941`
- Tags responsable (tags del foro — NO sirven como mención de usuario): Jonathan `1555025462684819496` · Chucho `1555025478450946119` (aplicables como 4ª `applied_tag`).
- IDs de usuario para menciones `<@id>`: Jonathan `713538631918157853` (`killer420w`) · Chucho `742803595241717840` (`jemadiar`). Son OTRO namespace: los IDs de tag devuelven 404 como usuarios y la mención se publica como texto literal. Ante duda, resolver en vivo (ver Pitfalls).

## Creacion (obligatorio)
0. **Via unica: el script.** Crear SIEMPRE con `python3 /opt/hermes-agent/skills/ops/discord-server-ops/scripts/crear_ticket.py --titulo ... --responsable <id_numerico> --tipo <tipo> --estado <estado> [--entorno DEV|PROD] --cuerpo <archivo.md>`. El script impone los gates (tags coherentes, cuerpo <=2000, secciones Obj/Criterios/Fuera de alcance). POST manual por HTTP salta esos gates y es como nacen tickets sin etiquetas ni Estado: el agente arma el JSON y olvida el resto del protocolo.
1. Un hilo por unidad de trabajo. Si ya existe uno con el mismo objetivo, se absorbe (no se duplica).
2. Tags al crear: **1 estado + 1 entorno + 1 tipo + 1 responsable**. Sin excepciones.
3. El mensaje raiz DEBE empezar con `**Estado:** <Pendiente|En curso|En revision|Cerrado|Bloqueado>` — el barrido semanal usa esa linea como fuente de verdad para sincronizar la tag.
4. Campos minimos del raiz: Estado · Entorno · Responsable · Prioridad · Origen · Objetivo · Alcance/fases · Criterios de aceptacion · Salvaguardas.
5. Limite duro: el mensaje inicial admite **2000 caracteres**. Si el ticket es mas largo, raiz corto + segundo mensaje con el detalle (pasarse devuelve `400 Invalid Form Body`).
6. Verificar leyendo de vuelta (`GET /channels/{id}` + `GET /channels/{id}/messages`): tag aplicada + raiz con `Estado:` + array `mentions` del raiz poblado con el username real. Un POST 201/200 NO prueba que el ticket quedo bien armado.
7. **Al detectar un ticket mal armado, barrer TODO el foro.** El mismo descuido (tags omitidas, raiz sin `Estado:`) rara vez es un solo hilo: los tickets se crean con el mismo procedimiento fallido, asi que revisar todos los hilos activos y corregir el patron completo, no solo el que destapo el problema.

## Transiciones de estado
- Cambiar SIEMPRE la tag **y** la linea `**Estado:**` del raiz en el mismo movimiento. Si divergen, gana el raiz (el cron sincroniza la tag a el).
- Un solo responsable humano por ticket; co-responsabilidad se anota en el texto, no con dos tags.
- `Bloqueado` exige dependencia explicita escrita (que ticket o decision lo desbloquea).

## Fusion, division y cierre
- Fusion: ticket paraguas nuevo + mensaje puntero en cada hilo absorbido + tag `Cerrado` en los absorbidos. Nunca borrar; el historico se queda.
- Division: se crean los tickets hijos con contenido completo y el original se cierra con punteros a cada hijo.
- Cierre solo con evidencia verificada (comando + salida real, mensaje leido de vuelta). Prohibido cerrar "porque deberia estar".

## Automatizacion existente
- Cron `87ddfea23f34` (lunes 09:00) corre `/opt/data/scripts/higiene_tags_tickets.py`: silencio si todo limpio; auto-corrige tag cuando el raiz declara estado y la tag falta o esta duplicada; reporta lo que requiere humano. **Entrega en `⏰・crons-dev` (1555646749559885925), hilo de reportes `1569368424138932286`** — nunca dentro del foro de tickets ni en el hilo de un ticket.
- `--dry-run` para inspeccionar sin escribir. Tests: `/opt/data/scripts/test_higiene_fix.py` (11 casos).
- Token Discord: entorno -> secretos del perfil -> `/opt/data/.env` (nunca asumir una sola fuente).

## Barrido semanal: divergencias que exigen humano
- El cron auto-corrige SOLO cuando el raiz declara `**Estado:**`. Para hilos reportados sin estado declarado, el arreglo es manual: leer la actividad reciente del hilo e inferir el estado real (planes propuestos sin trabajo iniciado ni respuesta humana = `Pendiente`).
- Al corregir a mano, aplicar la tag Y añadir la linea `**Estado:**` al raiz en la misma pasada. Corregir solo la tag deja el raiz sin fuente de verdad: el barrido siguiente vuelve a reportar el hilo (arreglar la causa, no el sintoma).

## Frontera con el portal de tareas (pending.jsonl)
- Ticket = trabajo con dueño, criterios de aceptacion y discusion (el foro es su hogar). Pendiente = nota de un solo paso, sin discusion. El mismo trabajo NUNCA vive en los dos: si existe ticket, el item vive en el foro.
- Antes de añadir al ledger un item que huela a trabajo con fases o evidencia, buscar en el foro un ticket abierto del mismo objetivo; si existe, cerrar/reemplazar la tarea del ledger con puntero al ticket (ver `pending-tasks-ledger`).
- El puente entre sistemas es unidireccional y de solo lectura: foro → portal (vista generada desde el foro). Prohibido escribir tickets al ledger o tareas al foro de forma automatica.

## Pitfalls
- Dos tags de estado (Pendiente+En curso) rompen el barrido: una sola.
- Nombre >100 chars o mensaje >2000 chars = 400 sin detalle util; recortar antes de reintentar.
- Para leer el raiz: `GET /channels/{id}/messages?after=0&limit=1` (el listado normal devuelve el mas reciente).
- **Editar el raiz exige la identidad que lo publico.** La API de Discord solo permite editar mensajes propios: si el raiz lo publico Bob (u otro bot/agente), la conexion Composio del agente actual devuelve `403 code 50005 "Cannot edit a message authored by another user"`. Antes de intentar una reescritura completa del raiz, verificar el `author.id` del mensaje; si no es el bot propio, la actualizacion se hace por el dueño original o como mensaje de respuesta (y el cambio de `**Estado:**` queda documentado en ese mensaje para el barrido).
- **Resolver el ID del responsable EN VIVO antes de mencionar.** Los IDs documentados envejecen, y un `<@id>` que no corresponde a ningún usuario NO falla el POST: se publica como texto literal con `mentions: []` — notificación perdida en silencio. Confirmar el ID con `GET /guilds/{guild}/members?limit=1000`; si ya se publicó mal, corregir con `PATCH` del mensaje propio y re-verificar `mentions` en la relectura.
- **Si el script canónico falta en el árbol vivo, restaurarlo desde git, nunca improvisar el POST.** El script se puede perder en un upgrade o rebuild del repo. `git log --oneline --all -- <ruta>` para hallar el último commit que lo tuvo + `git show <commit>:<ruta>` para restaurarlo en la ruta canónica; luego commitear el archivo restaurado — un restore untracked desaparece de nuevo en el próximo pase de limpieza.
- Si la operación usó token de bot en archivo temporal (p.ej. bajo `/tmp`), borrarlo al cerrar: el secret queda en disco sin dueño después de que el ticket ya está publicado.

# Caso 03/09 — Punto ciego del standalone: planificar topología con memoria y no con el repositorio

## Timeline verificado (evidencia en logs)
- 00:56 — última edición del `.env` de roshi: `API_SERVER_KEY` residual + **DISCORD_BOT_TOKEN y TELEGRAM_BOT_TOKEN propios** (perfil apto para standalone).
- 06:15 — pin `api_server.enabled:false` en config.yaml de roshi → servido OK por el multiplexor.
- 07:36 y 08:44 — **standalone de roshi arrancado** (Desktop o a mano): su `profiles/roshi/logs/gateway.log` muestra `Connected as Roshi#2990` + Telegram polling OK. Atendió DMs del CTO (chat 1544372221433217044) a 09:50 y 10:23.
- Mismo período: el default multiplexado TAMBIÉN servía plataformas de roshi → dos procesos, mismo token, contención de polling.
- 08:44:44 — Desktop re-guarda config.yaml de roshi → **borra el pin**.
- 10:26:24 — último registro del standalone (muere en la tormenta de restarts 10:44-11:12); nadie lo revive: el slot s6 tiene flag `down` **regenerado por el init en el recreate de las 08:43** (mtime 08:43:20).
- 10:46 — restart del default → `Skipping secondary profile 'roshi' ... enables api_server` (x3 arranques). Roshi invisible desde ahí.

## El error de método (lo que reprochó el usuario)
Afirmar "Roshi NO tiene gateway propio; su slot está down a propósito" mirando solo `s6-svstat` + `gateway_state.json` + log del default + memoria de sesiones previas. **Nunca se abrió `profiles/roshi/logs/gateway.log` — 68 KB de actividad standalone del mismo día.** El plan de fix (borrar API_SERVER_KEY) era correcto para el mundo-multiplex pero habría saboteado la arquitectura standalone que el equipo montó esa mañana (alineada con la preferencia de Jonathan: un bot visible con avatar/nombre por agente).

## Reglas extraídas
1. Ley 0 del triaje (SKILL.md): topología se verifica en el repo vivo, no en memoria.
2. `grep -c <chat_id_del_usuario> /opt/data/logs/gateway.log` = 0 con usuario activo → el tráfico lo sirve OTRO proceso (standalone).
3. El flag `down` de un slot s6 NO es evidencia de decisión humana si su mtime coincide con un recreate.
4. Antes de proponer fixes de arquitectura: preguntar "¿quién montó esto y con qué intención?" y confirmar con los dueños (Chucho/Jonathan) la dirección vigente.
5. Desktop re-guarda config.yaml sin previo aviso → cualquier pin que dependa de config.yaml es volátil; el `.env` es el plano de control estable.

## Estado al cierre de la sesión
- Plan en discusión (no ejecutado por orden explícita del usuario): Fase A persistir standalone del slot vía cont-init.d hook (sobrevive recreate, ver RC1), Fase B excluir roshi del multiplex (anti-doble-token), Fase C watchdog con fleet-mode.json (RC3b). WhatsApp bridge del default sigue caído por creds.json vacío — independiente, requiere re-pairing con ventana ≥60 min.

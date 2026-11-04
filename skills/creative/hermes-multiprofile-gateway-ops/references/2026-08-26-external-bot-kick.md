# 26/08/2026 — Bot externo publicando en canales mapeados (kick verificado)

## Contexto
Los 8 canales de especialistas (hermodr-connect … sindri-producer) mostraban mensajes de un
bot que no era el del gateway: "NeuralCrew Agent" (id 1533196061571809423), con embeds
vacíos ("NeuralCrew Agent (NCA)", "🎤 ECHO"). El usuario reportó "respuestas de Neurral Crew
Agent en los bots".

## Diagnóstico (rápido y determinista)
1. Listar bots del guild (token propio, UA DiscordBot):
   `GET /guilds/{guild}/members?limit=100` → `user.bot == true`; había 2 bots:
   Ragnar (1493385610797252758, el nuestro) y NeuralCrew Agent (1533196061571809423).
2. Autor real de los mensajes en el canal:
   `GET /channels/{channel}/messages?limit=10` → `author.id`. El gateway responde SIEMPRE
   con el id del bot de su token. Id de otro bot = externo.
3. Confirmar token ajeno al stack:
   `grep -rl "1533196061571809423|MTUz..." /opt/data /opt/hermes --include="*.env" --include="*.yaml" --include="*.json"` → nada. No lo controlábamos.
4. Entender qué hacía: solo embeds de tarjeta/echo; no texto (los mensajes de texto reales
   eran del gateway, id Ragnar).

## Corrección
- Permisos: el rol del bot tenía `ADMINISTRATOR` → puede kickear.
- `DELETE /guilds/{guild}/members/{bot_id}` → **HTTP 204 SIN cuerpo**. Detalle importante:
  `json.loads()` sobre un 204 lanza `JSONDecodeError` — no es un fallo, es éxito.
- Verificación: `GET /guilds/{guild}/members/{bot_id}` → **404** = ya no está.
- Los mensajes viejos del bot expulsado SIGUEN en el historial; borrarlos es aparte
  (requiere permiso y decisión explícita).

## Lecciones
- Antes de depurar enrutado/memoria por "respuestas raras", mirar el `author.id`: un bot
  externo invitado por un humano puede publicar en los mismos canales.
- Un DELETE de member con 204 es éxito: no envolver el response en `json.loads` sin
  manejar cuerpo vacío.
- El sorprendente "NeuralCrew Agent" era un bot legítimo de la org (probablemente otra
  instancia/Desktop), no malware: confirmar con el usuario antes de kickear (se preguntó,
  se aprobó).
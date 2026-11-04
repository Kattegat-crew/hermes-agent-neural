# Gobierno multi-tenant de conexiones (quién usa cada credencial)

Modelo diseñado con NeuralCrew (2026-08) para N agentes × N servicios × 1 instancia
AP Community (sin Projects premium, que solo existe en tier Team ~$166/mes).

## El problema

AP Community NO aísla conexiones entre tenants: todas viven en un solo proyecto.
"El agente de Helmer solo usa helmer-gmail" no lo impone AP por sí solo. La
separación hay que garantizarla en capas.

## Las 5 capas

1. **SOUL.md (el contrato)** — cada perfil de agente declara su identidad y prefijo
   permitido ("Tú eres el agente de Helmer. Solo usas conexiones con prefijo
   `helmer-`").
2. **Mapa de conexiones en Engram** — `connections-map` (o `topic_key:
   connections-map`) mapea tenant → conexión → dueño. Agente consulta el mapa antes
   de invocar; nunca adivina; si falta la conexión, reporta.
3. **Projects de AP (premium)** — aislamiento duro por projectId en el JWT del MCP.
   Solo cuando se pase de ~5 clientes o un cliente exija compliance.
4. **Auditoría** — el health-check/vigía puede listar qué conexión usó cada agente en
   las ejecuciones de AP; uso cruzado = alerta.
5. **Wrapper `ap_call` (LA LEY)** — TODO acceso a conexiones pasa por un script que
   valida la identidad del perfil llamador contra el mapa y **BLOQUEA antes de la
   llamada** si no es dueño. Log de intentos permitidos Y bloqueados para auditoría.

Máxima: **"El SOUL es el contrato, la Capa 5 es la ley."** No confiar en buena
voluntad del SOUL para correos reales/compliance; la máquina debe poder decir que no.

## Evidencia (probado en prod)

```
$ ap_call --connection neuralcrew-gmail   # desde perfil helmer
BLOCKED: perfil helmer no es dueño de neuralcrew-gmail   (exit 1)

$ ap_call --connection jonathan-gmail     # desde perfil default (dueño)
→ llega a AP (JWT con iss=activepieces + header Accept: application/json, text/event-stream)
```

## Convención de naming (obligatoria desde el día 1)

`{tenant}-{servicio}`:
- `helmer-gmail`, `golden-gmail`, `golden-sheets`, `golden-db`
- `jonathan-gmail`, `jonathan-canva`
- `neuralcrew-gmail`, `golden-meta-ads`

Un vistazo a AP o al mapa dice de quién es cada cuenta y no se cruzan credenciales.
Conexiones descubiertas existentes se registran igual (ej. la conexión "Gmail Golden"
de AP → `golden-gmail`, owner helmer).

## Datos que NO van al mapa

Credenciales, secrets ni tokens NUNCA en Engram — solo el mapa lógico
(tenant → conexión → dueño). El wrapper resuelve contra AP (Postgres) las credenciales.

## Límites de AP Community que importan

- Flows, tasks/ejecuciones, conexiones y MCP servers: ILIMITADOS (gratis).
- Premium: Projects (RBAC multi-usuario), SSO, audit logs, git sync.
- Conclusión: el multi-tenant NO necesita Projects si naming + perfiles Hermes
  (cada cliente = su HERMES_HOME, su Engram project, su config) resuelven la
  separación. Un solo admin (Chucho) crea todas las conexiones; el cliente solo
  hace click en "Permitir" desde la puerta de conexión.
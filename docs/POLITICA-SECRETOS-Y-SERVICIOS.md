# Política única de secretos y servicios — NeuralCrew Labs

**Estado:** propuesta para implementación (Codex)
**Fecha:** 2026-11-06
**Dueño de la decisión:** Jonathan Parra (Admin)
**Reemplaza a:** la sección «Google Workspace & Composio» de `SOUL.md` (línea ~191) y la regla #1 de la skill `vault-access`.

---

## 1. El problema que resuelve

Hoy hay tres contradicciones vivas:

1. **`SOUL.md`** dice que todo acceso a Google y redes va **exclusivamente** por ActivePieces y Composio, y que los secretos se leen de `/opt/data/secrets/`.
2. **La skill `vault-access`** dice que primero se lee el `.env` y solo si falta se cae a Vaultwarden.
3. **La realidad medida (6-nov-2026):** las claves existen en el vault (`FAL - API key`, `DocuSeal - MCP token`, `Formbricks - MCP keys`), pero **nunca llegan al entorno de Hermes**, porque Hermes no está en el mapa del sincronizador.

Resultado: se buscan claves en el disco, no se encuentran, y se concluye —falsamente— que el equipo no tiene acceso al vault.

**Causa raíz medida:** `/opt/vault/timer/vault-to-env-map.json`
- DEV: **4 destinos** (`activepieces`, `coolify`, `cloudflare`, `marketing-campaign-generator`). Hermes no aparece.
- PROD: **18 destinos**, incluido `/opt/hermes/.env` con 3 claves — pero **no** `/opt/hermes/data/.env` ni los `.env` por perfil.

No es un problema de permisos ni de política. Es un problema de **mapeo incompleto**.

---

## 2. Regla que separa las dos cosas

La distinción del Admin es la correcta y hay que hacerla explícita:

| | **Servicios (conexiones)** | **Claves (secretos)** |
|---|---|---|
| Qué es | Una cuenta autorizada: Google Workspace, Meta, Instagram, TikTok | Una cadena de texto que autentica una API |
| Dónde vive | ActivePieces (`connections-map.json`) y Composio | **Vaultwarden**, y solo Vaultwarden |
| Cómo se usa | El agente invoca la conexión; el token lo maneja la plataforma | El agente recibe la clave en el instante en que la necesita |
| Quién renueva | La plataforma (OAuth) | El humano, rotando en el vault |
| Se escribe a mano en disco | Nunca | **Nunca** |

**Ninguna de las dos vías se cruza.** Una conexión de Google no es una clave. Una clave de API no se convierte en conexión.

---

## 3. Modelo de acceso a claves: dos niveles

El vault es la **única fuente de verdad**. Lo que hay en disco es siempre **derivado**, nunca editado a mano.

### Nivel 1 — Materialización (para lo que necesita arrancar)

Sirve para procesos que leen su entorno **al iniciar**: contenedores, servidores MCP, servicios systemd. Un proceso no puede pedirle una clave a un humano en tiempo de arranque.

- El timer `vault-sync.timer` (cada 30 min, ya existe en DEV y PROD) regenera el archivo.
- Destino: `.env` con permisos **0600**, dueño = **el usuario del proceso exacto** que lo necesita (no root, no grupo amplio).
- El archivo lleva una cabecera fija para que nadie lo edite a mano:

  ```
  # GENERADO DESDE VAULTWARDEN — NO EDITAR A MANO
  # Fuente: /opt/vault/timer/vault-to-env-map.json
  # Los cambios se hacen en el vault; este archivo se regenera en <=30 min.
  ```

- Rotar un secreto en el vault = el archivo se corrige solo. No hay que tocar servidores.

### Nivel 2 — Lectura en el momento (para lo que se usa una vez)

Sirve para scripts y tareas puntuales: una llamada de facturación, una consulta de saldo, un job que corre hoy y no vuelve.

- El agente pide la clave al vault en el instante de uso y **no persiste nada**.
- Comando único y sancionado (ver §5).
- Nada queda en disco, nada queda en el historial.

**Criterio para elegir:** ¿el proceso necesita la clave al arrancar y no puede esperar? → Nivel 1. ¿Se usa una vez y se olvida? → Nivel 2.

---

## 4. Credencial del bot: el punto débil actual

Hoy el bot vive en `/root/.bw-bot.env` (0600, root). Ningún agente puede leerlo sin `sudo`. Eso obliga a que cada operación pase por root — que es peor que el problema que intenta resolver.

**Propuesta:**

1. Crear una cuenta de servicio **de solo lectura** en Vaultwarden para la flota, con acceso limitado a las colecciones `Hermes/` y `Terceros/IA`. Sin permiso de escritura, sin acceso a `Vault Ops`.
2. Su credencial va en `/etc/hermes/vault-bot.env` con permisos **0640**, grupo **`ai-agents`** (grupo que ya existe; el usuario `hermes` ya pertenece a él).
3. Efecto: cualquier agente lee el vault **sin `sudo`**, y no puede modificar ni borrar nada.
4. La cuenta de escritura (`agents@`) sigue siendo de root y **solo la usan los humanos**.

Esto cumple lo que pide el Admin — máxima seguridad — sin obligar a root para leer.

---

## 5. Comando único de acceso

Un solo punto de entrada, el mismo en DEV y en PROD:

```bash
# Campo concreto de un item
vw get "Terceros/IA - FAL - API key" -f FAL_KEY

# Todos los campos de un item, exportados al entorno del proceso actual
eval $(vw env "Hermes/MCPs - claves")

# Buscar un item por nombre
vw list "Terceros"
```

Reglas duras:

- **Prohibido** `grep`/`find`/`ls` buscando claves en el disco. Si `vw` no la tiene, la clave no existe.
- **Prohibido** imprimir el valor en un transcript, log o reporte. Se verifica por longitud o por `sha256`, nunca por valor.
- **Prohibido** escribir un `.env` a mano. El secreto se crea o se edita en el vault; el `.env` se regenera.

---

## 6. Trabajo concreto para Codex

### 6.1 Ampliar el mapa del sincronizador

En `/opt/vault/timer/vault-to-env-map.json`, **ambos hosts** (DEV y PROD), añadir los destinos que faltan:

| Host | Archivo destino | Dueño:grupo | Modo | Claves que faltan |
|---|---|---|---|---|
| DEV | `/opt/hermes-agent-data/.env` | `hermes:hermes` | 0600 | `FAL_KEY`, `DOCUSEAL_MCP_TOKEN`, `FORMBRICKS_API_KEY`, `STIRLING_MCP_KEY`, `PAPERLESS_MCP_TOKEN`, `COOLIFY_MCP_TOKEN`, `COMPOSIO_KEY`, `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REFRESH_TOKEN` |
| PROD | `/opt/hermes/data/.env` | `10000:10000` | 0600 | las mismas |
| PROD | `/opt/hermes/data/profiles/golden-game/.env` | `10000:10000` | 0600 | `TWENTY_MCP_KEY_*` (6) — hoy propagadas a mano, deben venir del vault |

**Nota de implementación:** el sincronizador actual escribe el archivo completo. Hay que añadirle un modo **merge** que preserve las líneas que no vienen del vault (claves de Hermes, `HERMES_LANGFUSE_*`, etc.). Sin eso, el primer sync borra la configuración de Hermes. **Este es el riesgo principal de todo el cambio.**

### 6.2 Corregir los ítems del vault que no coinciden

Antes de mapear, verificar que el nombre del item en el vault es exactamente el que usa el mapa. Los que ya confirmé que existen:

- `FAL - API key`
- `DocuSeal - MCP token`
- `Formbricks - MCP keys`
- `Terceros/IA - NAN - API Key`

Falta confirmar: `Stirling`, `Paperless`, `Coolify MCP`, `Composio`, y **Mercado Libre** (no aparece en el listado — hay que crearlo con las credenciales de la app de ML del Admin).

### 6.3 Reemplazar la política en `SOUL.md`

Sustituir la sección «Google Workspace & Composio» por dos secciones separadas, según §2 de este documento. La regla vigente debe quedar:

> **Servicios** (Google, redes): solo por ActivePieces y Composio.
> **Claves**: solo desde Vaultwarden. En disco solo hay copias derivadas que el timer regenera; nunca se editan a mano.

### 6.4 Reescribir la skill `vault-access`

La regla #1 actual («primero `.env`, si falta el vault») invierte la prioridad y es la que induce el error. Debe quedar:

1. **Primero el vault** — es la fuente de verdad.
2. La copia en disco (Nivel 1) solo se usa cuando un proceso la necesita al arrancar.
3. Si `vw` falla, **eso es el incidente** que hay que reportar; no se busca la clave por el disco.

Y añadir la nota operativa que hoy falta: `vw` requiere leer `/root/.bw-bot.env`, por lo que **hoy hay que invocarlo con `sudo`** — hasta que se implemente §4.

### 6.5 Verificación (obligatoria antes de dar por cerrado)

Para cada clave mapeada, comprobar **server-side**, no por inspección del archivo:

```bash
# 1. El valor llega al proceso
docker exec hermes-agent env | grep -c '^FAL_KEY='   # PROD
# 2. La clave sirve de verdad contra la API real
curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Key $FAL_KEY" https://api.fal.ai/v1/models
# 3. Rotación: cambiar el valor en el vault, esperar un ciclo de 30 min, repetir el paso 1
```

Criterio de aceptación: `200` en el paso 2 y propagación visible en el paso 3.

---

## 7. Lo que NO se toca

- **No** se abren colecciones nuevas a los agentes más allá de `Hermes/` y `Terceros/IA`.
- **No** se le da escritura a la cuenta de servicio.
- **No** se mueven claves de PROD a DEV ni al contrario.
- **No** se toca `Vault Ops` (token de administración) — sigue siendo solo de humanos.

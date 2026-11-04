---
name: hermes-desktop-plugins
description: "Use when authoring or verifying Hermes Desktop plugins."
tags: [hermes, desktop, plugins, sdk, fastapi, verificacion]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, hermes-desktop, plugins, plugin-sdk, panes, statusbar, fastapi, verification]
    related_skills: [inspecting-hermes-desktop-dom, hermes-desktop-ssh-backend, hermes-bot-avatars]
prerequisites:
  commands: [node, curl, python3]
---

# Hermes Desktop Plugins Skill

Escribir, instalar y **verificar** plugins de Hermes Desktop: un archivo ESM
(UI: chip, panel, paleta, keybinds) y, opcionalmente, una mitad Python en el
gateway (`/api/plugins/<id>`) para datos que el renderer no puede pedir por CORS.
No cubre los plugins del dashboard web ni los plugins CLI/gateway de agente.

## When to Use

- "Quiero un chip/panel/widget en Hermes Desktop" o adaptar una herramienta
externa a la UI del Desktop.
- Un plugin apareció pero **no sirve** (dice *sin datos*): el 90 % de las veces
  es la mitad backend sin montar o el archivo en la carpeta equivocada.
- Verificar un plugin sin depender de que el usuario lo pruebe a mano.

## Prerequisites

- Acceso al **HERMES_HOME del gateway** para la mitad Python (`plugins/<id>/dashboard/`).
- Confirmar **qué máquina corre el Desktop**: los plugins de escritorio se cargan
  del disco LOCAL de esa máquina, NO del backend remoto (ver Pitfalls).

## Quick Reference — contrato del plugin

Directorio (dos puertas equivalentes, ambas con hot reload):

```
<HERMES_HOME>/desktop-plugins/<id>/plugin.js        # plugin suelto (ON por defecto)
<HERMES_HOME>/plugins/<id>/desktop/plugin.js        # mitad UI de un paquete unificado (opt-in)
<HERMES_HOME>/plugins/<id>/dashboard/               # mitad Python del mismo paquete
├── manifest.json      {"name":"<id>","api":"plugin_api.py"}
└── plugin_api.py      router = APIRouter()  →  /api/plugins/<id>/*
```

- El **nombre de la carpeta = `id`**. Importables SOLO `@hermes/plugin-sdk`,
  `react`, `react/jsx-runtime`. Sin build: el archivo se carga sin compilar →
  **nada de JSX**, usar `jsx()`/`jsxs()`.
- Áreas: `'statusBar.right'|'statusBar.left'` (chips), `'panes'`
  (`data:{placement:'left'|'right'|'bottom'|'main', width, dock}`), `PALETTE_AREA`
  (`data:{id,label,keywords,run}`), `KEYBINDS_AREA`, `THEMES_AREA`, `ROUTES_AREA`,
  `SIDEBAR_NAV_AREA`, `TRANSCRIPT_DIRECTIVE_AREA`, `COMPOSER_AREAS`.
- Estado/datos: `useValue(host.state.*)`, `host.request(method,params)`,
  `host.onEvent`, `useQuery`/`queryClient` (el cliente React Query de la app),
  `ctx.storage` (persistencia), `ctx.os.*` (notify/openExternal/clipboard),
  `ctx.rest('/ruta')` → `/api/plugins/<id>/ruta`.
- UI: usar el kit de la app (`Button`, `Badge`, `StatusDot`, `EmptyState`, …) y
  variables de tema (`--ui-accent`, `--ui-text-secondary`, `--ui-stroke-secondary`,
  `--ui-text-tertiary/-quaternary`). **Nunca** colores/backgrounds hardcodeados
  (excepción razonable: colores de estado semánticos resueltos en runtime, con
  fallback); los paneles ya se pintan sobre el fondo del editor.
- Paleta de estado propia: resolver con `getComputedStyle(document.documentElement)`
  y `getPropertyValue('--ui-warning')` etc., con fallback literal documentado.

## Procedure

1. **Decidir dónde viven los datos.** Renderer → API externa = bloqueado por CORS
   en la mayoría de proveedores (verificado con `cloud-api.nan.builders`: preflight
   204 sin `Access-Control-Allow-*`). Si es así, van por la **mitad Python**
   (`ctx.rest`), y la API key se queda en el servidor.
2. Escribir `plugin_api.py` (FastAPI `APIRouter()`, endpoints async; envolver I/O
   bloqueante en `anyio.to_thread.run_sync`). Devolver datos ya digeridos y
   **sin datos personales**; degradar con el último snapshot (`stale: true`) en
   vez de reventar.
3. Escribir `plugin.js`: `export default { id, name, register(ctx) }`; ligar
   `ctx.rest` a una variable de módulo y definir los componentes fuera del
   closure. Chip + panel + 1-2 comandos de paleta; refresco por `useQuery`
   (`refetchInterval` ≥ 60 s).
4. Verificar (ver sección) y ENTREGAR el `plugin.js` al usuario explicando la
   carpeta destino de SU máquina + el paso de recarga.
5. **Habilitar la mitad Python**: `<id>` en `plugins.enabled` de `config.yaml`
   (con backup `config.yaml.bak.<ts>`) — la mitad Python NO se importa si el id
   no está en esa allow-list (frontera de seguridad, GHSA-mcfc-hp25-cjv7).
6. **Reiniciar el proceso que sirve al Desktop** — pero PRIMERO identificarlo
   (no asumirlo): las rutas se montan al importar (`_mount_plugin_api_routes()`)
   y no hay recarga en caliente para el backend; el middleware de runtime solo
   sirve para *desactivar* lo ya montado. El proceso correcto es el que tiene las
   **conexiones TCP del cliente** (`ss -tnp | grep <IP del cliente>`): puede ser
   un `hermes dashboard` en :9112 y NO el `serve --isolated` del modo SSH (que
   puede existir con cero conexiones). Ese proceso suele correr suelto (PPID 1),
   fuera del ciclo de vida de la app ⇒ cerrar la app y los botones *Restart
   backend* / *Restart gateway* pueden NO reiniciarlo. Antes/después comparar
   `ps -o pid,lstart,etime -p <pid>`: si el PID y el `etime` no cambian, nadie
   reinició nada (medido: mismo PID con 20 días de vida tras un "ya lo reinicié").
   Es una acción de alto impacto y sobre la infra del Desktop ⇒ **pedir OK
   explícito** antes de matarlo, y avisar que si la sesión actual corre en él se
   corta unos segundos (la conversación queda guardada). Receta fiel en
   `scripts/restart-desktop-backend.py`; verificación posterior = PID nuevo +
   línea `Mounted plugin API routes: /api/plugins/<id>/` en el log.

## Verification

Tres niveles, todos ejecutables sin que el usuario pruebe nada:

1. **Sintaxis**: `cp plugin.js /tmp/x.mjs && node --check /tmp/x.mjs`.
2. **Contrato + render**: `scripts/verify-desktop-plugin.mjs <ruta>/plugin.js`
   — ejecuta `register()` con un `ctx` falso y renderiza cada contribución con
   varias formas de datos (éxito / vacío / error). Detecta identificadores no
   importados y accesos a `undefined` antes de tocar la app.
3. **Montaje del backend**: `scripts/verify-plugin-api-mount.sh <id> [puerto]`
   — levanta un dashboard DESECHABLE con su propio token, prueba
   `/api/plugins/<id>/…`, hace los controles negativos (401 sin token, 404 con
   plugin inexistente) y lo mata. No toca los servicios vivos (:9112, el gateway
   del Desktop).

Tras el reinicio del gateway, la prueba de que montó de verdad es la línea
`Mounted plugin API routes: /api/plugins/<id>/` en su log.

## Pitfalls

- **La mitad UI se carga del disco LOCAL de la máquina que corre el Desktop**, no
  del backend SSH (`fs-ipc.ts` → `localPluginsRoot()`, `#66899`). Un plugin
  escrito en el VPS NO aparece en el Desktop del usuario: se le entrega el archivo.
- **La carpeta es consciente del perfil**: con perfil ≠ `default` la raíz es
  `<HERMES_HOME>/profiles/<perfil>/desktop-plugins`.
- **Windows**: `<HERMES_HOME>` = `%HERMES_HOME%` → registro de usuario
  `HERMES_HOME` (`setx`) → `%LOCALAPPDATA%\hermes` → `%USERPROFILE%\.hermes`
  (legacy, solo si ya existía). Dar la ruta `~/.hermes` a un usuario Windows es
  un error clásico: primero **Settings → Plugins → abrir carpeta de plugins** y
  usar la carpeta que abra Explorer.
- Windows esconde extensiones: verificar que el archivo sea `plugin.js` y no
  `plugin.js.txt`; el nombre de la carpeta debe ser exactamente el `id`.
- **Renderizar ≠ servir**: si el plugin aparece en Settings → Plugins pero dice
  *sin datos*, falta el reinicio del proceso que sirve al Desktop (rutas montadas
  al importar). El archivo ya está bien puesto: no seguir tocándolo.
- **No confundir "reiniciar la app" con "reiniciar el backend"**: los daemons
  `serve` sobreviven al cierre de la app (su propio AGENTS.md lo dice), y en la
  topología de dashboard (:9112) el proceso vive fuera del ciclo de vida de la
  app. Probar con `ps -o pid,lstart,etime` antes de creer que se reinició.
- **Dos instalaciones de Hermes pueden compartir un `HERMES_HOME`** (host
  `/opt/hermes-venv` sobre el repo vs contenedor `/opt/hermes` sobre el mismo
  data dir). Cuando los logs no cuadren, ver quién los escribe:
  `lsof <data>/logs/gui.log <data>/logs/agent.log` — no asumir que el proceso que
  lee el agente es el que sirve al usuario.
- **Dashboard en modo OAuth (`reason: no_cookie`)**: `curl` local NO sirve para
  validar el montaje aunque tengas `HERMES_DASHBOARD_SESSION_TOKEN` y las
  credenciales basic (devuelve 401 `no_cookie`). Para esa topología la evidencia
  es la línea de montaje en el log de arranque, no un REST local.
- Un plugin borrado de `plugins.enabled` después de arrancar sigue montado hasta
  el reinicio; el middleware lo bloquea (404) en tiempo de request.
- No usar `&` inline en una llamada `terminal`: el runtime lo rechaza. Dejar los
  backgroundings dentro de un script en disco (los scripts del skill ya lo hacen).
- Compilar a mano un `<script>` de prueba con el renderer no vale: el arnés del
  skill es la prueba (ejecuta el código real, no una copia).

## Reference material

- `references/resolution-and-paths.md` — anclas de código (rutas, perfiles, orden
  de resolución de HERMES_HOME, montaje/gating) y cómo probar qué proceso sirve al
  Desktop y cuándo arrancó.
- `references/nan-builders-quota-api.md` — endpoints de cuota de NaN verificados,
  modelo de alerta por consecuencia y el stack implementado (cron + plugin).
- `templates/plugin.js` — starter de una página: chip + panel + comando de paleta.
- `scripts/verify-desktop-plugin.mjs` — arnés de contrato + render (ejecuta el
  ESM real con stubs de la SDK y 3 formas de datos).
- `scripts/verify-plugin-api-mount.sh` — dashboard desechable para probar
  `/api/plugins/<id>/…` sin tocar los servicios vivos.
- `scripts/restart-desktop-backend.py` — reinicio fiel (argv + entorno de
  `/proc`) del proceso que sirve al Desktop, con `--dry`/`--delay` y
  verificación del montaje en el log.

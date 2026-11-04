# Resolución de rutas y montaje — anclas de código

Verificado el 2026-09-11 en el repo vivo (`/root/hermes-agent-legacy-docker`, versión 0.20.4)
con el Desktop del Admin (cliente Windows → backend SSH en el VPS).

## Mitad UI: dónde vive y cómo se resuelve

`apps/desktop/electron/fs-ipc.ts`

```ts
async function localPluginsRoot(dirName: string) {
  const profile = readActiveDesktopProfile()
  const base = profile && profile !== 'default'
    ? path.join(hermesHome, 'profiles', profile)
    : hermesHome
  return path.join(base, dirName)      // dirName = 'desktop-plugins' | 'plugins' | 'logs'
}
ipcMain.handle('hermes:fs:desktopPluginsRoot', () => localPluginsRoot('desktop-plugins'))
```

Comentario textual del repo: *"resolved from the main-process HERMES_HOME
(`resolveHermesHome`) — NOT from the connected backend. A remote backend reports
its own `hermes_home` over the gateway, which is a path on the REMOTE box; …
Electron owns this resolution so it stays valid in every connection mode (#66899)"*.

⇒ El plugin debe estar en la máquina del cliente. `agentPluginsRoot`
(`<home>/plugins`) se escanea además para `<id>/desktop/plugin.js`.

Perfil activo: `<app.getPath('userData')>/active-profile.json` → `{"profile": "<nombre>"}`
(`readActiveDesktopProfile()`, main.ts:~9554). Ausente o `default` ⇒ raíz global.

## HERMES_HOME del cliente (`resolveHermesHome()`, main.ts:~769)

1. `process.env.HERMES_HOME`
2. `USER_DATA_OVERRIDE` si el lanzamiento lo fijó
3. **Windows**: valor de usuario de la variable `HERMES_HOME` en el registro
   (caso real #45471: una app lanzada desde Explorer no ve un `setx` posterior)
4. Windows: `%LOCALAPPDATA%\hermes` si existe; si no existe y sí existe el legacy
   `%USERPROFILE%\.hermes`, usa el legacy; si no, `%LOCALAPPDATA%\hermes`
5. Linux/macOS: `~/.hermes`

## Mitad Python: descubrimiento, gate y montaje

`hermes_cli/web_server.py`

- Descubrimiento: escanea los roots de plugins buscando `dashboard/manifest.json`.
  Campos usados: `name` (fallback: nombre de carpeta), `label` (fallback `name`),
  `icon` (`Puzzle`), `entry` (`dist/index.js`), `api` (validado con
  `_safe_plugin_api_relpath` — solo un archivo relativo dentro de `dashboard/`).
  Para un backend sin UI: `{"name":"<id>","api":"plugin_api.py","tab":{"hidden":true}}`.
- Gate: los plugins de origen `user` solo importan su Python si el id está en
  `plugins.enabled` y no en `plugins.disabled` (allow-list, GHSA-mcfc-hp25-cjv7).
  Los `project` (`./.hermes/plugins/`) nunca auto-importan Python.
- Montaje: `_mount_plugin_api_routes()` corre **al importar el módulo**, y hace
  `app.include_router(router, prefix=f"/api/plugins/{name}")` + log INFO
  `Mounted plugin API routes: /api/plugins/<id>/`.
- `_plugin_api_runtime_gate` (middleware): si un plugin se **desactiva** con el
  proceso ya arrancado, su router sigue montado pero el middleware lo bloquea en
  cada request (404 autenticado). Registrado ANTES de los middlewares de auth a
  propósito: sin token debe ganar el 401, para no filtrar qué plugins existen.

⇒ Consecuencia operativa: **no existe recarga en caliente del backend**. Un plugin
nuevo requiere reiniciar el proceso que sirve al Desktop.

## Cómo saber qué proceso sirve al Desktop y desde cuándo

```sh
ps -eo pid,lstart,etime,cmd | grep -E "hermes (serve|dashboard)" | grep -v grep
ss -ltnp | grep hermes          # el gateway del Desktop suele ser 127.0.0.1:<alto>
```

Si el proceso arrancó antes de que existiera el plugin, la ruta no está montada.

### Identificar el proceso correcto (no asumirlo)

`ps`/`ss` por sí solos no dicen **quién sirve al cliente**. El discriminante son
las conexiones del Desktop:

```sh
ss -tnp | grep <IP del cliente>          # p. ej. su IP de Tailscale
```

Caso real (11-sep-2026): el Desktop del Admin tenía 6 conexiones ESTAB a
`100.86.8.81:9112` (pid del `hermes dashboard`, arrancado 06:49) y **cero** al
`serve --isolated` en `127.0.0.1:44387` (20 días de vida) — o sea el backend SSH
era un señuelo sin clientes. Reiniciar el equivocado no cambia nada.

Si no hay conexiones visibles (¿namespace de red distinto?), desempatar por los
logs compartidos: `lsof <data>/logs/gui.log <data>/logs/agent.log` lista los
procesos que los tienen abiertos (puede haber dos instalaciones de Hermes
compartiendo un `HERMES_HOME`: `/opt/hermes-venv` sobre el repo en el host vs
`/opt/hermes` en el contenedor).

### Reiniciar ESE proceso

- El proceso correcto puede correr suelto (**PPID 1**), fuera del ciclo de vida de
  la app: cerrar la app **no** lo reinicia, y los botones *Restart backend* /
  *Restart gateway* pueden reiniciar otros procesos. Verificado: tras un "ya lo
  reinicié", el PID del dashboard seguía con **20 días** de `etime`.
- Prueba objetiva antes/después: `ps -o pid,lstart,etime,cmd -p <pid>`. PID y
  `etime` iguales ⇒ no se reinició nada.
- Antes de matarlo: **OK explícito del usuario** (es infra del Desktop) y avisar
  que si la sesión actual corre dentro, el chat se corta unos segundos (la sesión
  persiste en `state.db`).
- Relanzar **idéntico**: reconstruir `argv` + **todo** el entorno desde
  `/proc/<pid>/cmdline` y `/proc/<pid>/environ` (token/credenciales incluidos: si
  cambian, el cliente no puede reconectar). No relanzar "a mano" con un entorno
  a medias. Script: `scripts/restart-desktop-backend.py` (tiene `--dry` para ver
  qué haría y `--delay` para que la respuesta al usuario salga antes del corte).
- Verificación posterior: PID nuevo + `Mounted plugin API routes: /api/plugins/<id>/`
  en el log de arranque. Si el dashboard está en modo OAuth (`no_cookie`), el
  `curl` local devuelve 401 aunque mandes el token de sesión y el basic auth: para
  esa topología la línea del log es la evidencia, no el REST local.

## Sintomas → causa

| Síntoma | Causa habitual |
|---|---|
| No aparece en Settings → Plugins | archivo en carpeta equivocada (HOME/perfil), `plugin.js.txt`, carpeta con otro nombre, o app muy vieja |
| Aparece pero el panel dice "sin datos" | mitad Python no montada (falta reinicio) o id ausente de `plugins.enabled` |
| El panel se ve pero vacío/roto | identificador no importado, color hardcodeado, JSX sin `jsx()` |
| Cambié el backend y no toma | los routers se montan al importar; reiniciar el proceso |

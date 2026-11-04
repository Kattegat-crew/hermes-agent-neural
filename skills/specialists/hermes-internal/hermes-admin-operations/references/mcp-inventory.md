# Inventario MCP de la flota Hermes (snapshot 2026-09-25)

Fuente viva: sección `mcp_servers:` de `/opt/data/config.yaml` (el config vive ahí; NO en `/opt/data/data/config.yaml`). Este snapshot ENVEJECE — re-verificar siempre leyendo el config en vivo antes de auditar o modificar.

## Patrón de topología (estable, es lo durable)
- Todos los servidores: `lazy: true`, `idle_timeout_seconds: 300`, `max_lifetime_seconds: 86400`.
- Split RO/RW: servidor trusted de solo lectura + par `<servicio>_write` con `trust: untrusted` (Hermes pide confirmación antes de mutar).
- Transportes:
  - Binario/script local: engram, ncl_google, ap, twenty, github-mcp-server.
  - uvx/npx vía `/opt/data/scripts/mcp-run.sh`: pg_ro (postgres-mcp 0.3.0 restricted), paperless-ngx-mcp@3.1.1, @masonator/coolify-mcp@2.13.0, outline-mcp (git+https fijado a commit).
  - HTTP remoto: cloudflare, composio, fal, canva (OAuth).
  - HTTP self-host en Tailscale 100.73.30.29: stirling :3041, paperless :3040, docuseal :3008, formbricks :3030, coolify :8000.
- Solo-RO (sin par write): pg_ro, outline. Sin split (un solo servidor): engram, opendesign (untrusted), canva.

## Servidores (18 al snapshot)
engram · ncl_google(+write) · ap(+write) · twenty(+write) · cloudflare(+write) · composio(+write) · pg_ro · stirling(+write) · paperless(+write) · coolify(+write) · fal(+write) · github(+write) · docuseal(+write) · formbricks(+write) · outline · opendesign · canva

## Quirk YAML conocido (no romper al editar)
El bloque `canva` viejo COMENTADO (líneas ~813-817 al snapshot) quedó dentro del bloque de `pg_ro`, y el `lazy: true`/`lifecycle` de pg_ro cuelga después del comentario. Funciona, pero al editar esa zona: los comentarios son líneas completas (borrarlos es seguro) y hay que preservar la indentación de 4 espacios del `lazy:`/`lifecycle:` de pg_ro. Re-verificar con un parseo YAML tras cualquier edición.

## Cómo auditar en vivo
1. Leer `/opt/data/config.yaml` (sección `mcp_servers:`, líneas ~593-1164 al snapshot).
2. Contar claves de primer nivel bajo `mcp_servers` — esperar 18.
3. Contrastar tools visibles en la sesión vs `tools.include` del config — discrepancia = config cambió sin reload del gateway.
4. Para saber qué se cargó en una sesión real: las tools `mcp__<servidor>__*` listadas en el system prompt reflejan el estado cargado.

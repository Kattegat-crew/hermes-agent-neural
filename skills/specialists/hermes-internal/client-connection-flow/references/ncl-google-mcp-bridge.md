# ncl_google_mcp.py — MCP bridge para perfiles de cliente

## Arquitectura

```
Hermes Agent (perfil nancy)
  └─ MCP Server: ncl_google_mcp.py (stdio)
       ├─ /opt/data/connections-map.json (mapa de conexiones, owner enforcement)
       ├─ /opt/data/secrets/{slug}-{svc}.json (credenciales OAuth, chmod 600)
       └─ Google API (Gmail/Drive/Calendar) vía refresh token directo
```

## Patrón de deployment

1. `verify_connection.py` materializa secrets al marcar active
2. `sync_connections_map.py` propaga mapa + secrets a prod (3 ubicaciones)
3. Se registra `ncl_google` como MCP server en el config del perfil
4. Se reinicia el gateway (multiplexado o perfiles)
5. Se verifica con `hermes -p {slug} mcp list` + test funcional

## Ownership enforcement

```python
# Dentro del MCP server:
profile = os.environ.get('HERMES_HOME', '').split('/')[-1]  # "nancy"
# Valida que {profile}-{service} sea owner en el mapa
# Rechaza si el perfil no es dueño de la conexión
```

## Secret file format

```json
{
  "connection": "nancy-gmail",
  "account": "nlgm1005@gmail.com",
  "refresh_token": "1//0...",
  "client_id": "288239405432-...biiufd8.apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "scope": "https://mail.google.com/ https://www.googleapis.com/auth/drive ..."
}
```

## Tools expuestas

| Tool | Función | API Google |
|------|---------|------------|
| `gmail_list` | Listar correos recientes (max 20) | `users.messages.list` |
| `gmail_send` | Enviar correo (to, subject, body) | `users.messages.send` |
| `drive_search` | Buscar archivos por nombre (max 20) | `files.list` (q=name contains) |
| `drive_read_text` | Leer contenido de archivo Drive | `files.export` (text/plain) |
| `calendar_list_events` | Próximos 14 días de eventos | `events.list` |

## Errores comunes

- **`args[0]` duplicado:** `command: python3` + `args: [python3, script.py]` → el server recibe "python3" como argumento. Fix: `args: [script.py, --profile, nancy]`.
- **Secrets no encontrados:** el sync no corrió después de verificar. Re-ejecutar `sync_connections_map.py`.
- **Perfil sin MCP en logs:** verificar si el perfil tiene gateway propio (`gateway-{slug}`) vs multiplexado (`gateway-default`). El restart del default no reinicia los gateways perfiles.
- **Calendar sin openid:** `id_token` no trae email → usar cuenta cruzada del mismo tenant (verificar_connection.py ya hace esto desde v2).

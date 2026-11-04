---
name: google-workspace-ops
description: >-
  Operaciones en Google Workspace (Drive, Docs, Sheets, Gmail). Descarga y sincronización de assets, lectura de carpetas de clientes, creación de Docs y autenticación vía ActivePieces.
tags: [google, drive, docs, sheets, activepieces, oauth, workspace, entregables]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones en Google Workspace (Drive, Docs, Sheets)

Habilidad canónica para interactuar programáticamente con el ecosistema de Google Workspace de la empresa y de los clientes: inventariar y descargar assets de Drive, leer documentos de verificación (RUT, contratos, artes de campaña), generar documentos de texto vía API y operar mediante las credenciales gestionadas de ActivePieces.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"busca el archivo en Google Drive"*, *"descarga los artes de la carpeta de la campaña"*, *"sincroniza las imágenes de Drive al servidor"*, *"crea un Google Doc con este reporte"*, o *"conecta con la cuenta de Google mediante ActivePieces"*.
- Descarga programática de insumos para guiones o piezas gráficas desde carpetas compartidas de clientes.
- Automatización de reportes o documentos entregables hacia carpetas oficiales en Drive.

---

## 1. Acceso a Google Drive mediante ActivePieces

Para evitar flujos interactivos de OAuth por navegador, se aprovechan las conexiones ya autenticadas en la instancia local de **ActivePieces**:

```bash
# Consultar piezas y conexiones de Google en ActivePieces
curl -s -H "Authorization: Bearer $ACTIVEPIECES_API_KEY" \
  "http://localhost:3000/api/v1/app-connections" | jq '.data[] | select(.pieceName=="@activepieces/piece-google-drive")'
```

### Protocolo para Descargar Assets de Cliente
1. Obtener el `folder_id` de la URL de Google Drive compartida por el cliente (`drive.google.com/drive/folders/<FOLDER_ID>`).
2. Listar y mapear nombres de archivos y tipos MIME.
3. Descargar los assets a la ruta de trabajo local del agente (`/opt/data/campaigns/<cliente>/assets/`) antes de procesarlos con herramientas multimedia (FFmpeg, PIL, Vision).

---

## 2. Generación y Edición de Google Docs vía API

### El Gotcha Crítico del Índice de Párrafo en `docs().create()`
Al crear un Google Doc con la API oficial:
- `docs().create()` genera un documento con un único salto de línea (`\n`) vacío.
- Si intentas insertar texto con `insertText` en el índice `1` o posterior sin verificar los límites del documento, la API arrojará `Invalid structure index`.

### Regla para Inserción de Contenido
1. Crear el documento vacío y obtener su `documentId`.
2. Para insertar texto en un documento nuevo, el índice de inserción siempre debe ser `1`:
```json
{
  "insertText": {
    "location": { "index": 1 },
    "text": "Título Principal del Documento\n"
  }
}
```
3. Para reconstruir o reemplazar un documento existente, primero consultar `docs.get()` para conocer el `endIndex` real del cuerpo antes de enviar `deleteContentRange`.

---

## 3. Manejo de Documentos Legales de Clientes

Al auditar o procesar documentos de clientes (RUT, Cámaras de Comercio, Cédulas):
1. **Conservación de metadatos**: Nunca renombrar archivos oficiales arbitrariamente; conservar la referencia al nombre original de Drive.
2. **Descarga a sandbox seguro**: Los archivos se descargan en `/opt/data/compliance/docs/` y nunca se exponen en directorios web públicos sin autenticación.
3. **Extracción**: Utilizar herramientas OCR o de visión multimodal para extraer las razones sociales, NITs y fechas de expedición sin suposiciones.

---

## 4. Acceso Directo por API vía Secrets del MCP (`ncl_google`)

Para llamadas directas a la API de Google sin pasar por ActivePieces:
- **Mapa de conexiones**: `/opt/data/connections-map.json` (ej. `jonathan-drive`, `status: active`).
- **Secret**: `/opt/data/secrets/<conn>.json` contiene `client_id`, `client_secret` y `refresh_token`.
- **Intercambio canónico de token** (evita el 401 del token estático en `google_token.json`):

```python
import json, urllib.parse, urllib.request

cred = json.load(open('/opt/data/secrets/jonathan-drive.json'))
body = urllib.parse.urlencode({
    'client_id': cred['client_id'],
    'client_secret': cred['client_secret'],
    'refresh_token': cred['refresh_token'],
    'grant_type': 'refresh_token'
}).encode()
AT = json.loads(urllib.request.urlopen(
    urllib.request.Request('https://oauth2.googleapis.com/token', body), timeout=30
).read())['access_token']

def api(url, method='GET', data=None):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + AT}, method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode()
    return json.loads(urllib.request.urlopen(req, timeout=60).read())
```

### Operaciones Esenciales en Drive API:
1. **Listar carpeta específica**:
   ```python
   q = f"'{FOLDER_ID}' in parents and trashed=false"
   url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(q)}&pageSize=100&fields=files(id,name,mimeType,modifiedTime)"
   ```
2. **Exportar archivos nativos (Docs/Sheets)**:
   - Usar siempre `/export?mimeType=text/csv` o `application/pdf`. NUNCA usar `alt=media` en archivos nativos (arroja `403 fileNotDownloadable`).
3. **Crear hoja nativa de Google Sheets sin Sheets API habilitada**:
   - Subir multipart/related con metadatos MIME `application/vnd.google-apps.spreadsheet` y cuerpo CSV:
   ```python
   import io
   meta = json.dumps({'name': title, 'parents': [FOLDER_ID], 'mimeType': 'application/vnd.google-apps.spreadsheet'}).encode()
   boundary = 'xNCBoundary'
   mp = io.BytesIO()
   mp.write(b'--' + boundary.encode() + b'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' + meta + b'\r\n')
   mp.write(b'--' + boundary.encode() + b'\r\nContent-Type: text/csv\r\n\r\n' + csv_bytes + b'\r\n--' + boundary.encode() + b'--\r\n')
   req = urllib.request.Request('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType', data=mp.getvalue(), method='POST')
   req.add_header('Authorization', 'Bearer ' + AT)
   req.add_header('Content-Type', 'multipart/related; boundary=' + boundary)
   res = json.loads(urllib.request.urlopen(req, timeout=90).read())
   ```
4. **Mover a Papelera (Trash)**:
   - Enviar body JSON `{'trashed': True}` vía `PATCH files/{id}`. Los query params `?trashed=true` devuelven 200 pero son ignorados por Google.

---

## Gotchas y Errores Críticos

1. **Tokens expirados en ActivePieces**: Si la conexión de Google Drive arroja `401 Unauthorized`, el refresh token puede haber sido revocado por Google (política de 7 días en apps en modo Testing). Re-vincular desde el panel de ActivePieces.
2. **Límites de tamaño en subidas**: Archivos mayores a 50MB (videos, renders finales) deben subirse mediante *Resumable Uploads* de la API de Drive o compartirse vía portal local Nginx si el timeout del webhook es menor a 60 segundos.
3. **Archivos Nativos vs Binarios**: `alt=media` es exclusivamente para binarios (PDFs, imágenes, zips). Los Google Docs/Sheets nativos requieren el endpoint `/export`.

---
name: google-drive-access
description: >-
  Use when accessing or downloading Google Drive files. Usar cuando pida acceder a archivos o links de Google Drive. hermes: tags: [google, drive, api, oauth, download, search]
tags: [google, drive, api, oauth, download, search]
version: 1.0.0
author: hermes
license: MIT
metadata:
triggers:
  - archivos de Drive / link de Google Drive / carpeta de Drive
  - buscar documento de cliente en Drive (RUT, cámara de comercio, contratos)
  - descargar PDF/DOCX/XLSX de Drive para leer su contenido---

# Google Drive — Búsqueda, listado y descarga vía API

## Cuándo usar
El usuario comparte links de Drive o pide "busca entre los archivos de Drive".
No hay herramientas MCP de Drive en Hermes: se accede directo con la API de
Google usando el token OAuth ya configurado (permisos `drive` y `drive.readonly`).

## Autenticación (patrón probado)
```python
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

token = json.load(open("/opt/data/google_token.json"))
creds = Credentials(
    token=token["token"], refresh_token=token["refresh_token"],
    token_uri=token["token_uri"], client_id=token["client_id"],
    client_secret=token["client_secret"], scopes=token["scopes"],
)
svc = build("drive", "v3", credentials=creds)
```
googleapiclient refresca el access token automáticamente (no usar el token crudo
con urllib — da 401). Ver skill `google-docs-api` para el detalle de OAuth/scope.

## Búsqueda (q = query de Drive)
```python
# Por nombre (case-insensitive con 'contains')
res = svc.files().list(
    q="name contains 'golden' or name contains 'Golden'",
    pageSize=50,
    fields="files(id,name,mimeType,parents,size,modifiedTime)"
).execute()

# Por contenido (solo funciona en Google Docs/Sheets indexados)
res = svc.files().list(q="fullText contains 'Golden Game'", ...).execute()

# Carpetas raíz / contenido de una carpeta por ID
res = svc.files().list(q="'ROOT_OR_FOLDER_ID' in parents", ...).execute()
```
Patrón de búsqueda probado para hallar documentación de un cliente:
1. `name contains '<marca>'` → halla carpetas y archivos nombrados
2. `fullText contains '<marca>'` → halla docs/sheets cuyo CONTENIDO menciona la marca
3. Listar el contenido de las carpetas relevantes (parent id) para no perder archivos

## Descarga de archivos binarios (PDF/DOCX/XLSX)
```python
from googleapiclient.http import MediaIoBaseDownload
import io

req = svc.files().get_media(fileId=FID)
buf = io.BytesIO()
dl = MediaIoBaseDownload(buf, req, chunksize=1024*1024)
done = False
while not done:
    status, done = dl.next_chunk()
open("/ruta/salida.pdf", "wb").write(buf.getvalue())
```

## Archivos nativos de Google (Docs/Sheets/Slides)
`get_media` NO funciona con mimeType `application/vnd.google-apps.*`. Usar
`files().export(fileId=..., mimeType='text/plain'|'application/vnd.openxmlformats-...')`
para Docs, o `text/csv` / `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
para Sheets. (Alternativa rápida: la búsqueda `fullText` ya revela el contenido de los nativos.)

## Flujo completo recomendado
1. Buscar por nombre y contenido (varias queries en paralelo en un solo script).
2. Listar carpetas candidatas para no perder archivos mal nombrados.
3. Descargar a un directorio de trabajo (`/opt/data/drive_<cliente>/`).
4. Extraer texto: `.docx` se lee con read_file (auto-extrae); PDF con pypdf vía
   `uv run --with pypdf python script.py` (ver skill pip-install-broken-env).
5. Verificar el contenido extraído antes de usarlo para llenar documentos.

## Antes de guardar en Drive (mapa de carpetas)

Al descargar/guardar archivos de un cliente, consulta la skill `mapa-de-carpetas`: los archivos van a la carpeta del cliente según el mapa (`/opt/data/brain/folder-maps/`), con nombre descriptivo kebab-case, y no se crean carpetas nuevas sin autorización.

## Pitfalls
- **Distinguir qué es autorización**: un contrato de concesión (p. ej. Coljuegos
  C2005) NO es lo mismo que una autorización de promoción específica. Al llenar
  documentos legales, marcar como PENDIENTE lo que no aparezca en Drive, no inventarlo.
- **Datos duplicados en Drive**: el mismo PDF suele existir en 2+ carpetas con IDs
  distintos (copia de copia). Descargar una sola vez por nombre.
- **Archivos sensibles** (RUT, extractos bancarios, cédulas): usarlos solo para
  extraer datos, no reenviarlos ni exponerlos en respuestas públicas.
- **Google Meet transcripts son Google Docs**: Las notas de reuniones de Google Meet
  se guardan automáticamente como `application/vnd.google-apps.do` con nombre
  "Reunión iniciada a las YYYY/MM/DD HH:MM - Notas de Gemini". NO usar `get_media`
  (da error 403); usar `files().export(fileId=..., mimeType='text/plain')`.
  Para buscarlos: `q="name contains 'Reunión' and name contains 'Notas de Gemini'"`.
  También aparecen como "Actas reuniones" (carpeta).

## Script reutilizable
`scripts/drive_search_download.py` — plantilla de búsqueda + descarga parametrizable.

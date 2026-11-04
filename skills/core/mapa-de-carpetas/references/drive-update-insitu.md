# Actualizar archivos EXISTENTES en Drive con drive_sync.py

Patrones verificados con el cliente de Drive del repo de campañas
(`/opt/marketing-campaign-generator/scripts/drive_sync.py`, lee `.env` del repo).
Para editar/mover archivos que YA existen en Drive no basta re-subir (crea
duplicado): hay que usar `files().update`.

> Nota de ubicación: esta referencia vive aquí porque `google-workspace-ops`
> está bloqueada por el escáner de seguridad (requiere confirmación humana);
> cuando se desbloquee, migrar este archivo allí.

```python
import sys; sys.path.insert(0, 'scripts')
import drive_sync as ds
from googleapiclient.http import MediaFileUpload   # drive_sync NO re-exporta esto

svc = ds.drive_service()

# Actualizar contenido de un archivo existente IN SITU (mantiene id y posición):
svc.files().update(fileId=FID,
                   media_body=MediaFileUpload('/ruta/local.md', mimetype='text/markdown'),
                   fields='id,size').execute()

# Mover entre carpetas (compartido con otros padres):
svc.files().update(fileId=FID, addParents=DEST, removeParents=SRC,
                   fields='id,parents').execute()

# Renombrar sin tocar contenido:
svc.files().update(fileId=FID, body={'name': 'nuevo nombre.ext'}, fields='id,name').execute()

# Subir archivo nuevo (firma real del helper del repo):
ds.upload_file(svc, PARENT_ID, '/ruta/local.md', True, cache={})

# Listar carpeta:
svc.files().list(q=f"'{FOLDER_ID}' in parents and trashed=false",
                 fields='files(id,name,mimeType,size)').execute().get('files', [])
```

## Pitfalls

- `MediaFileUpload` vive en `googleapiclient.http`: si se busca como atributo de
  `drive_sync` lanza `AttributeError` (probado).
- Cierre verificable: re-listar la carpeta y comparar tamaños byte a byte contra
  los locales antes de reportar "actualizado".
- Descarga en bucle con `get_media`/`alt=media` aborta en el primer archivo nativo
  de Google (`403 fileNotDownloadable`) y deja el resto sin bajar: filtrar por
  mimeType (o por extensión) antes de iterar.
- Al archivar versiones previas NO usar trash: mover con `addParents`/`removeParents`
  hacia `_versiones-anteriores/<YYYY-MM-DD>/` (regla de versionado del Admin,
  ver `references/versionado-identidad-marca.md`).
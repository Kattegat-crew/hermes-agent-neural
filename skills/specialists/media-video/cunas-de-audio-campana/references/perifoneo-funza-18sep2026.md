# Perifoneo Funza · Bingo Millonario 18/09/2026 — caso completo

Primer caso documentado de esta clase de entregable (junto con la cuña de ruleta de Golden Game · Tunja que sirvió de formato).

## Datos verificados (de material aprobado, no de la ficha)
- Marca: **The Grand Paradise Club** (Lucky Brothers SAS) · "Tu palacio de la suerte" · logo con corona y palmeras.
- Sede: **C.C. Mi Centro Funza, Cra. 13 No. 16-85, Local 226** (Funza, Cundinamarca).
- Evento: **Bingo Millonario — viernes 18 de septiembre**, 4 bingos: $50.000 · $50.000 · $100.000 · **Bingo Mayor $300.000**, cena + bebidas, "ven a jugar y recibe tu cartón".
- Pie legal de las piezas: +18 · Juego responsable · "Autoriza Coljuegos".
- **No venían en el material**: hora de inicio (la campaña general usaba "desde las 5:00 p.m.") ni ninguna mención de ruleta/máquinas → se preguntaron al Admin, no se inventaron.

## Cuñas entregadas (3 versiones)
- A ~40 s (91 palabras): gancho "¡Atención, Funza!" → evento → sede + dirección → 4 bingos con premios → cena y bebidas → cartón al jugar → repetición de datos → pie legal.
- B ~20 s (45 palabras): gancho + fecha + sede + premios en bloque + pie legal.
- C ~19 s (47 palabras): "Hoy es el día" + datos + dirección + pie legal.
- Archivo: `/opt/data/plans/GUION-FUNZA-PERIFONEO-18SEP.md` (v1, borrador pendiente de OK).

## Cómo se levantaron los datos: Drive API en urllib puro (sin libs de Google)
```python
d = json.load(open('/opt/data/secrets/jonathan-drive.json'))   # credencial de la cuenta NC
data = urllib.parse.urlencode({'client_id': d['client_id'], 'client_secret': d['client_secret'],
                               'refresh_token': d['refresh_token'], 'grant_type': 'refresh_token'}).encode()
tok = json.load(urlopen(Request('https://oauth2.googleapis.com/token', data=data)))['access_token']
# buscar por nombre:  q = "name contains 'Funza' and trashed=false"
# listar carpeta:     q = f"'{FOLDER_ID}' in parents and trashed=false"
# descargar:          https://www.googleapis.com/drive/v3/files/<ID>?alt=media
# campos: files(id,name,mimeType,size,modifiedTime,parents), orderBy=modifiedTime desc
```

### IDs verificados (10/09/2026)
- `14Sgg-FI1h9Xubz-uVmfGE37cOiwYqwVO` — carpeta **Funza**: `Afiche funza.png`, `Banners TV's/` (`10g-9Vp0GqmVXK7P0Hpe-QTq-ROV4fCpX`, TV1..TV6), `Reel 3- Funza ya listo/` (`10FaN8XlBDeTcKwwhaJ26DzkV8F_NCPDN` → `reel funza .mp4`).
- `104Z6_o1_rwu4cH-c6CrwhVPcmdbhsHwr` — carpeta **"Viejo"** (Golden): guarda `Guion cuña ruleta.docx` (el formato a imitar) y `Video promo funza.mp4`.
- `1FY-8Gyvcr5SxfPqDaQs1libTPhTYNbvG` — piezas Lucky (subcarpeta `Funza` y `Banners TV's`).

### Trampas de búsqueda
- Los Drive `lucky-*`/`golden-*` (cuentas del cliente) **no** contienen este material: `name contains 'Funza'` da 0 ahí. Si la búsqueda no encuentra una sede conocida, cambiar de cuenta antes de concluir que no existe.
- Para listar por nombre usar `name contains '<texto>'` (sin comodines raros) y leer `parents` de la respuesta para deducir marca/campaña del hallazgo.
- No hace falta transcribir el mp4 del reel: el afiche y los banners TV ya traen los datos duros (y transcribir audio cuesta saldo, que requiere aprobación previa).

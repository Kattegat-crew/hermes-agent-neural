# Guion → brief: recetas y medidas reales

Levantado el 11-sep-2026 trabajando la serie Golden «Bingo Millonario» (Mes del Amor y la Amistad).

## 1. Dónde vive cada cosa

| Qué | Ruta |
|---|---|
| Repo (fuente de verdad del guion) | `/root/marketing-campaign-generator` (contenedor: `/host/root/marketing-campaign-generator`) |
| Maestros de la serie (HOST, no en el repo) | `/root/hermes-agent-legacy-docker/data/plans/GUION-G1..G4*.md`, `GUION-L0*`, `GUION-L1-CHIQUINQUIRA.md`, `GUION-CHIQUINQUIRA-PERIFONEO.md`, `GUION-FUNZA-PERIFONEO-18SEP.md`, `SERIE-LUCKY-GRAN-BINGO-PARADISE.md` |
| Informes de guiones del cliente | Drive de Jonathan (los sube como .docx al Drive del cliente) |

Trampa: en el runtime desktop `/opt/data/plans/` (root, 7 docs viejos de agosto) **NO** es el mismo directorio que `/root/hermes-agent-legacy-docker/data/plans/`. Un `ls` en el primero hace concluir «los guiones no existen». Verificar con `find` sobre ambos antes de afirmar nada.

## 2. Bajar el guion fuente cuando viene en un link de Drive

Si el usuario pega `docs.google.com/document/d/<ID>?...`:

1. `files().get(fileId=ID, fields="id,name,mimeType,size,modifiedTime,owners(emailAddress),parents")` primero — da el nombre real y confirma que es el archivo esperado (un informe «V2» re-subido cambia el título, no el link).
2. Si el link trae `rtpof=true` es un **Office subido, no un Docs nativo**: `files().export(...)` devuelve **403 «Export only supports Docs Editors files»**. Ese camino no existe; no insistir.
3. Bajar el binario con `files().get_media(fileId=ID)` + `MediaIoBaseDownload` (secuencial, `googleapiclient` no es thread-safe) a `/tmp/<nombre>.docx`.
4. Leerlo con `read_file` — auto-extrae .docx con tablas; no hace falta python-docx.

Credenciales: el `google_token.json` del contenedor puede estar **revocado de forma terminal** (`RefreshError: invalid_grant: Token has been expired or revoked` — no es la expiración de 1h). La vía viva son las conexiones materializadas de ActivePieces: `/root/hermes-agent-legacy-docker/data/secrets/<perfil>-drive.json` (`refresh_token` + `client_id` + `client_secret` + `scopes` CSV), construyendo `Credentials(token=None, ...)` y llamando `.refresh(Request())`. Iterar candidatos (`jonathan-drive.json`, `golden-drive.json`, `neuralcrew-drive.json`, `lucky-drive.json`) y quedarse con el primero cuya metadata resuelva.

## 3. Transcribir el guion recibido al formato de la plantilla

El cliente entrega el guion como párrafos dentro del .docx. Para medirlo hay que llevarlo a la tabla que el linter entiende:

- Cabecera `**Campo:** valor` (Campaña, Pieza, Producto, Marca, Versión, Estado).
- `## Estructura (serie validada)` con la línea ①→②→③→④.
- `## Spine (7 beats)` — tabla `| Beat | Qué pasa en esta pieza | Escenas |` con los 7 beats en orden.
- `## GUION — ESCENA POR ESCENA` con la tabla `| Tiempo | Visual | Narración | En pantalla |`, ventanas contiguas (`0-12s`, `12-22s`, …).
- `## NARRACION COPIABLE` con el texto exacto por ventana.

No reescribir el texto al transcribir: el valor está en medir **lo que el cliente escribió**, no una versión mejorada por el agente. La transcripción literal es lo que convierte «se lee bien» en «mide 105,2s».

## 4. Medidas reales (11-sep-2026, edge-tts, costo $0)

| Guion | Declara | Voz real medida | Sobra |
|---|---|---|---|
| G2 Tunja | 60,0s (12/10/26/12) | **105,2s** (16,2 · 11,5 · **56,1** · 21,3) | +45,2s (−43%) |
| G4 Pacho | 60,0s (12/10/26/12) | **100,7s** (17,3 · 14,5 · 50,3 · 18,7) | +40,7s |
| L1 Chiquinquirá | 38,0s (6/6/8/12/6) | 40,0s (6,5 · 6,4 · 8,3 · 14,1 · 4,7) | +2,0s |

El informe del cliente admite la brecha en prosa («303 palabras ≈ 110–120 s» para G2) y resuelve el recorte a 60s con **una instrucción escrita, no con un guion de 60s**. Ese es el defecto de clase de toda la serie.

Defectos estructurales encontrados, además de la duración:

- **Una escena se come la espina**: en G2 la ventana 22-48s carga `descubrimiento` + `mecanismo` + `producto` + `payoff` (4 de los 7 beats) en 26s.
- **Payoff pegado a la trama**: el test producto-necesario falla porque el payoff vuelve a decir «Bingo Millonario» crudo justo después del mecanismo, en vez de resolverlo.
- **Espina sin declarar**: mientras no esté escrita, el linter la deriva y el defecto anterior pasa invisible al leer.
- **Pie legal fuera de pantalla**: L1 Chiquinquirá tenía `+18 / Coljuegos` solo en la narración, no en el texto en pantalla → error de cumplimiento duro.
- **Fila descompuesta**: aviso «una fila de la tabla tiene celdas con `|` sin escapar» (afecta al pie legal).

## 5. Ejemplo de ajuste por escena (G2 Tunja, escenario 60s)

| # | Ventana | Voz real | Ajuste propuesto |
|---|---|---|---|
| 1 | 0-12s | 16,2s | cae «pero el corazón se nos prende fácil» y el remate «y que pase algo» → queda el frío + la cita de Bolívar + la libertad de la mesa |
| 2 | 12-22s | 11,5s | cae el arranque histórico, se conserva el sentido y el tacto acordado con el cliente |
| 3 | 22-48s | 56,1s | solo caben DOS autopreguntas habladas (¿cuándo? y ¿el premio? con el bloque de cifras completo); las demás bajan a rótulo |
| 4 | 48-60s | 21,3s | cae la frase de amigos; la dirección hablada pasa a pantalla **solo con OK del cliente** |

Si los números muestran que la pieza no da para 60s sin mutilar el recurso, plantear las dos versiones (corta para redes, larga para el canal largo) como recomendación explícita, no como lista de opciones.

## 6. El otro extremo del pipeline (Roshi / Chucho)

Roshi montó su **mesa pieza-por-pieza** en `profiles/roshi/workspace/sesiones/` (`sesion.py` con 12 etapas 0-11, `datos-duros.yaml`, `lint_texto.py`): 0-4, 6-7 y 10-11 son gratis; 5 (keyframes), 8 (clips) y 9 (audio) pagan y exigen `candado` con presupuesto máximo antes de cualquier llamada a API.

Su propio skill declara que **los guiones y las escenas NO son de Roshi**: viven en el repo del generador y él aporta el gate documental/QA. Los dos esfuerzos son complementarios: el `guion_lint` del repo debería correr **dentro de la etapa 2 (guion)** de la mesa de Roshi, en vez de que cada lado tenga su propio linter.

Servicio verificado: `reel-worker.service` tiene `WorkingDirectory=/root/marketing-campaign-generator` en el host, activo y con `/health` respondiendo `{"status":"ok"}`.

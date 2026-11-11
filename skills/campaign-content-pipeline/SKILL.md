---
name: campaign-content-pipeline
description: Use when producing or scheduling monthly campaigns.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: proprietary
metadata:
  hermes:
    tags: [campañas, contenido, goldengame, lucky-brothers, pauta]
    related_skills: [seo-geo-launch, copy-quality-es]
---

# campaign-content-pipeline

## When to Use
- Al producir, mapear piezas, escribir copy o programar publicaciones de una campaña mensual en el repo marketing-campaign-generator.
- Al cotizar o coordinar pauta local (radio) para una campaña.

Repo: `/opt/marketing-campaign-generator`. Pre-flight `git pull --ff-only` + `git status` (zero-stale). Si `git add/commit` falla con `insufficient permission for adding an object`, hay objetos de `.git` creados por root: listar con `ssh dev 'find <repo>/.git -user root -print'` (guardar manifiesto), `chown hermes:hermes` solo esos, y reintentar — NO un chown recursivo del árbol. Las campañas viven en `planning/<mes-campana>/`: calendario de piezas + `03-piezas/{posts,stories,carruseles}` + `_fuentes/` (investigación, mapas, tarifas).

## Mapeo calendario ↔ imagen (antes de prometer o programar nada)

- Correr `scripts/map_piezas.py` (copia re-ejecutable en `/opt/hermes-agent-data/scripts/`): clasifica cada pieza del calendario contra `03-piezas/` y escribe `planning/<camp>/_fuentes/mapa-piezas-imagen-<fecha>.json` con estados `exacta` / `por_lote` / `sin_imagen`.
- NUNCA asumir "hay imágenes = campaña cubierta" ni prometer cobertura por matching exacto de nombre: los archivos usan convenciones distintas a los ids del calendario. Auditar DOS fuentes — el repo `03-piezas/` Y la carpeta de campaña en Drive (el cliente sube las piezas aprobadas al Drive, no al repo). En Drive el orden de tokens suele invertirse (`story-<marca>-YYYYMMDD-vN.png` vs `<marca>-YYYYMMDD-<tipo>-<contexto>`) y hay sufijo de versión (`-v3`, `-v4` del mismo día): resolver a la versión más alta por fecha+marca+tipo, y las piezas nombradas por concepto (lanzamiento, novena, jornada-N, navidad) marcarlas como *pendientes de asignación de fecha*, no como `sin_imagen`. El mapper + comparación por tokens es el único conteo confiable; verificar su resumen contra lo pedido antes de informar cobertura. Nunca reafirmar cifras de cobertura dichas en un turno anterior: recalcularlas contra fuente viva (repo Y Drive vía API) cada vez que se vayan a reportar — el Admin detecta el número sin comprobar y lo rechaza.
- Los carruseles suelen existir solo como primera lámina (t1) → estado `por_lote`, no `sin_imagen`. PERO no reportar '0 producidos' desde un listado plano del top-level: las series de carrusel viven anidadas por serie (`<marca>/<serie>/*.png`); hacer un conteo recursivo a profundidad completa del árbol de piezas (search_files o `ssh dev 'find ...'` sobre el host) antes de declarar ausencia de producción.
- El mismo conteo recursivo vale para Drive: listar la carpeta de campaña vía API (no desde el repo) y emparejar series completas de carrusel por nombre contra los `slides[]` de la fila del calendario (cada lámina trae `drive_id`+`name`; la t1 es la portada). Las series aprobadas pueden vivir SOLO en Drive — verificar allí primero antes de reportar carruseles 'por producir'; el inventario del repo no es evidencia de ausencia.
- Producido en repo ≠ publicable: `publish.py` baja los materiales SIEMPRE de Drive (`get_drive(asset_drive_id)`; carrusel → `slides[]` con `drive_id`+`name` por lámina). Vincular un asset al calendario exige subir el archivo al Drive del cliente y guardar su ID — y subir a Drive del cliente es escritura externa → pedir OK antes.
- Antes de afirmar que un archivo de campaña 'no existe', buscar en subdirectorios: `campaign.yaml` vive en `00-contrato/`, no en la raíz de la campaña. Un grep/listado de un solo nivel produce falsos negativos.

## Mix de formatos: decidir con rendimiento medido

- Antes de cerrar el mix de una campaña, calcular vistas medias por formato sobre el registro real (`content-intel/data/posts.jsonl`) y ponderar el mix hacia el formato top. NO heredar el mix de la campaña anterior ni llenar el calendario con el formato más barato de planificar: story es el formato que más llena un calendario y el que menos alcance da (jerarquía medida: reel ≈ 12× post en vistas medias, ≈ 35× story; post ≈ carousel). Un mix 70%+ stories quema el mes aunque cada pieza esté aprobada y a tiempo.
- Verificar el mix contra la fábrica disponible: si el repo tiene pipeline de reels y el calendario no tiene ni uno, es hallazgo de auditoría, no detalle de mezcla.
- Receta de medición (correrla, no estimarla):

```bash
cd /opt/marketing-campaign-generator && python3 - <<'EOF'
import json, collections
rows = [json.loads(l) for l in open('content-intel/data/posts.jsonl') if l.strip()]
agg = collections.defaultdict(lambda: [0, 0])
for r in rows:
    m = (r.get('extra') or {}).get('metrics') or {}
    v = m.get('views') or 0
    if v:
        a = agg[r.get('format') or '?']; a[0] += v; a[1] += 1
for f, (v, n) in sorted(agg.items(), key=lambda x: -x[1][0]):
    print(f"{f:10s} {n:3d} piezas  media {v//max(n,1):5d}")
EOF
```

- Auditar también cadencia: días del mes sin ninguna pieza y distribución horaria (una ventana 12:00-19:00 con días en cero deja alcance en la mesa).

## Informe mensual (content-intel/campaign_report.py)

- Antes de enviar o reportar el informe, verificar los totales contra `posts.jsonl`: si TODAS las piezas salen con 0 métricas, el cruce está roto — no es que la campaña no tuvo rendimiento. Causa típica: iterar `media_ids` del calendario como lista cuando ya es un dict por plataforma (`{'instagram': id, 'facebook': id}`) — iterar un dict produce las CLAVES, el join contra posts.jsonl da vacío y todo sale en cero. Normalizar el acceso (dict, lista o lista de dicts) en un solo helper con tests de los tres shapes.
- Contraste barato del informe anterior: `git show HEAD:<docx>` y extraer el texto del XML — si el cero venía de antes, decirlo y corregir; si el informe defectuoso ya llegó al cliente, el reenvío corregido es decisión del Admin, no acción automática.
- El informe cierra con una tabla de RECOMENDACIONES de tres columnas (Hallazgo · Evidencia · Acción sugerida): cada fila derivada de los datos del propio informe (rendimiento por formato, piezas sin producir, día de la semana débil), con la evidencia citada entre paréntesis — el Admin las usa para discutir con datos, no opiniones generales.

## Bloqueos de publicación (ninguno se salta)

1. Imagen mapeada para la pieza (exacta o por lote).
2. Copy específico por pieza con SEO — una marca NO hereda el copy de la otra; verificar marca por marca quién tiene copy real.
3. Pie legal +18 aprobado por legal: el placeholder pendiente en las piezas bloquea igual que la imagen faltante — detectarlo ANTES de programar publicaciones.

Si hay piezas vencidas del calendario, decirlo con fechas concretas ("empezando el lunes salen las del día X"), no prometer arrancar "desde el 1".

## Pauta local (radio)

- La investigación de emisoras y tarifas oficiales queda en `_fuentes/`; contactar una emisora es mensaje externo → requiere OK explícito del Admin antes de escribirles.
- Al proponer: una selección con recomendación única (la de mayor alcance + la más económica como combinación de arranque con presupuesto estimado), no la lista completa.

## Circuito de aviso y publicación (cambio de mes automático)

- El mes NO se escribe a mano en ningún wrapper ni script: `planning/calendar_resolver.py` elige el calendario activo por la fecha real de las piezas (más piezas del mes en curso > campaña futura más cercana > la publicada más reciente), descarta el maestro de campaña (no tiene estados de publicación) y devuelve también el dir de scripts del mes.
- Lo consumen el paquete diario (07:30), el publicador horario, `publish.py`, `sync_from_drive.py` y `drive_xlsx.py` (rutas y prefijo del portal derivados de la campaña). `CALENDARIO_JSONL` / `CALENDARIO_DIR` por env solo para forzar.
- Una campaña puede abarcar varios meses (El Aguinaldo va de nov a ene en el mismo JSONL): el resolver cuenta las piezas del mes en curso y no cambia de archivo mientras siga habiendo piezas de ese mes.
- Al dar de alta piezas nuevas con reglas del Admin (una marca no repite formato el mismo día, fechas fijas por festivo), validar en código con abort dentro del script de alta — no a ojo sobre 100+ filas. Si la instrucción de fecha es ambigua (¿el 16 de nov o de dic?), explicitar la interpretación elegida en la respuesta. Reels: canales IG+FB (las que soporta el publicador) y estado `a_producir` hasta que exista el .mp4.
- Único punto manual al abrir campaña nueva: `XLSX_IDS` en `drive_xlsx.py` (el XLSX de revisión de Drive tiene IDs propios por campaña) y crear `<campaign>/01-docs/borradores/calendario/` + `campaign.yaml` con estrategia escrita (personas, propuesta, KPIs). Sin `campaign.yaml` la campaña activa va a la deriva: el informe la describe pero nada contra qué medirla; su ausencia es hallazgo de auditoría, no detalle. Todo lo demás se resuelve solo.
- Si no existe campaña para el mes en curso, el paquete imprime `[CALENDARIO] … SIN calendario para <mes>` con advertencia; nunca un "sin piezas" mudo que parezca normal.
- **Ventana de publicación: slot ±2h.** Una aprobación que llega después de slot+2h hace que la pieza no se publique nunca. El publicador avisa una sola vez por pieza (sidecar `05-metricas/avisos-fuera-ventana.txt`) para que eso no pase en silencio.
- Aprobar = `approve_ids.py <ids>` (dry-run primero): escribe el JSONL, regenera el XLSX, **sube a ambos Drive** y deja commit local sin push (el push lo hace el publicador). Si el XLSX no se sube, el sync de las 07:30 **revierte** la aprobación.
- `build_xlsx.py` debe AÑADIR al XLSX las filas que estén en el JSONL y falten en la hoja (heredando formato), nunca abortar por filas nuevas — de lo contrario cualquier pieza planificada fuera del ciclo queda invisible para la revisión de Drive. Tras regenerar, verificar filas de la hoja == filas del JSONL (y conteo por tipo) antes de subir.
- Si `build_xlsx.py` falla dentro de `approve_ids.py`, el JSONL ya quedó escrito y los pasos de Drive/commit no: reintentar el XLSX y completar upload + commit a mano, verificando el conteo final. No dar por buena la aprobación por el mensaje del script.

### Rescate tras caída del publicador

- `publish.py --id <id>` publica pero NO escribe el estado en el JSONL: una pieza publicada a mano queda `aprobado` en el registro y el sync de las 07:30 puede revertirla. Tras cualquier publicación manual: patchear el JSONL (con backup previo) a `publicado` + los media_ids reales de la respuesta, regenerar `build_xlsx.py`, subir a ambos Drive y commit. Cerrar el día solo cuando TODAS las filas `publicado` del calendario tengan media_ids.
- Chequeo seco antes de rescatar: `publish.py --due` lista qué publicaría sin publicar nada — correrlo antes de tocar el registro.
- Antes de dar por listo el día siguiente, resolver cada fila `aprobado` de mañana contra Drive por API (`files.get` del `asset_drive_id`): debe devolver nombre + bytes reales, no bastar del id en el JSONL. Un id huérfano se descubre a la hora del slot, cuando ya no hay arreglo.
- Un vigilante que corre DENTRO del cron/proceso que vigila no puede reportar su muerte: si el aviso de fuera-de-ventana vive en el mismo cron del publicador, un gateway caído se pierde pieza Y aviso a la vez. Todo backstop de publicaciones corre desde un cron/proceso distinto al vigilado.
- No fijar conteos volátiles en tests del mecanismo de roll (ej. "exactamente N publicadas hoy"): cada publicación real los rompe y la suite entra en rojo permanente. Un test rojo por conteo dinámico es fragilidad del test, no bug del publicador — clasificarlo antes de "arreglarlo".

## Lecciones del 09-nov-2026 (verificadas en vivo, no asumir)

- **El repo NO es la fuente de verdad de los assets.** Antes de afirmar que una pieza "no está producida", consultar Drive por nombre: los carruseles de El Aguinaldo existían como 10 series completas de 5 láminas mientras el calendario las mostraba sin asset. La falta era de **vínculo** (`slides` con `drive_id`), no de producción. Herramienta: `link_carruseles.py` (dry-run → apply).
- **`media_ids` es un dict por plataforma** (`{'instagram': id, 'facebook': id}`), no una lista. Iterarlo directamente devuelve las CLAVES y el cruce con `posts.jsonl` da cero: el informe mensual del cliente salió con 0 vistas durante semanas por esto. Usar `_mids()` de `campaign_report.py`.
- **`build_xlsx.py` abortaba** si el JSONL tenía ids que no estaban en la hoja (`XLSX sin filas … restaurar el workbook aprobado`), lo que dejaba invisible cualquier pieza nueva. Ahora añade filas heredando formato.
- **Regla del Admin: una marca nunca lleva dos piezas mayores (post/reel/carrusel) el mismo día.** Las stories no cuentan. `add_reels.py` valida la regla y aborta si se rompe.
- **El informe ahora cierra con recomendaciones** (tabla Hallazgo · Evidencia · Acción) derivadas de los propios datos. No describir solamente: cada entrega termina en decisión.
- Tras aprobar o añadir piezas: regenerar XLSX + subir a ambos Drive + commit. Si no se sube el XLSX, el sync de las 07:30 revierte.

## Pins de checksum: triage de tests rojos en el repo

- Triage por CAUSA RAÍZ, no por test: una suite que carga un registro/contrato partido falla en cascada (un solo checksum roto puede teñir ~20 tests). Contar causas al reportar avance, no tests — "de 24 a 3" quiere decir 2 causas, no 21 arreglos.
- Ante un fallo `checksum mismatch` sobre una fuente pineada (schema, `campaign.yaml`): NO re-pinear desde el mensaje de error. Localizar el blob pineado en el historial (`git rev-list --all -- <archivo>` + sha256 de cada `git show <c>:<archivo>`) y hacer un diff SEMÁNTICO (parsear y comparar estructuras) contra el archivo vivo — no un `git diff` visual.
- Reformateo cosmético (semántica idéntica, solo indentación/orden): re-pinear con commit convencional y empujar. Cambio de CONTENIDO posterior al congelamiento (ej. campo aditivo en `campaign.yaml` después de aprobarse los registros): el pin está diciendo la verdad — presentar opciones al Admin: (a) re-pinar documentando que el cambio es aditivo y no toca lo congelado, o (b) re-congelar los artefactos contra la fuente nueva con aprobación fresca. Recomendar (b) si las piezas congeladas vuelven a producción; el pin es la garantía de procedencia y re-pinarlo en silencio la destruye.
- Distinguir expectativa desalineada de bug: si el test espera un código/valor que el validador nunca produjo de esa forma, el que está mal es el test — corregir el test es un cambio distinto y se reporta como tal.

## Caídas del publicador (09-nov-2026): qué revisar y cómo recuperar

El publicador horario es un **cron del gateway**: si el gateway cae, no hay corridas y **no hay catch-up** al volver. Síntoma: hueco de horas en `/opt/hermes-agent-data/cron/output/794be6c2336b/`.

- Diagnóstico en 3 comandos: `hermes cron runs <id>` (busca líneas `missed (skipped, catch-up off)`), `hermes cron list | grep -A7 publicacion` (`Last run` / `Next run`), y `grep gateway.exit_nonzero /opt/hermes-agent-data/logs/gateway-exit-diag.log` para ver si el gateway se reiniciaba.
- **`publish.py --id <id>` publica en Meta pero NO escribe el estado en el JSONL.** Publicar a mano deja la fila en `aprobado` con `media_ids` vacío → el registro miente y quedan expuestas a doble publicación. Tras publicar a mano: setear `estado='publicado'`, `media_ids` y `published_at` con backup, regenerar XLSX y subirlo a ambos Drive.
- Las piezas fuera de la ventana ±2h no se publican nunca y el aviso de fuera de ventana **tampoco salta** (vive en el mismo script que no corrió). Para detectar el fallo hace falta un backstop externo al gateway.
- Permisos: si `git add` falla con `insufficient permission ... .git/objects`, hay objetos de root en `.git`; se devuelven con `ssh dev 'find .git -user root -exec chown hermes:hermes {} +'` (nunca `rm` del `index.lock` si hay un git corriendo).
- Verificar una publicación de verdad: `publish.py --due` debe devolver `[]` después, y cada fila publicada debe tener `media_ids` no vacío.

## Materiales de terceros

- Antes de prometer un reel/edición final, confirmar dónde están los vídeos fuente (los que mandan los clientes NO están en el repo) — pedir la ubicación en la misma respuesta que confirma la tarea.
- Commits de producción de piezas (imágenes, continuidad, índices) NO implican copy escrito: verificar el copy por pieza por separado aunque el git log de la noche muestre "campaña hecha".

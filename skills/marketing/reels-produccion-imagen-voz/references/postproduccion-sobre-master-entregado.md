# Postproducción sobre máster entregado — receta verificada (Golden Tunja Terror, 26-oct-2026)

Contexto: el Admin pidió una V03 «sin logo superpuesto y sin subtítulos» a partir de una versión ya entregada por Telegram. No se regeneró el reel: se restauraron regiones desde una placa limpia existente y se conservó el audio bit a bit.

## 1. Reconstruir el estado antes de tocar nada
- Ubicar el máster entregado y la placa limpia (la variante sin subtítulos del mismo render). Ambos con SHA-256 propios, calculados al momento.
- Si la versión entregada no está en la ruta durable del repo, buscar en el registro de la conversación (rutas citadas en entregas previas) y en `/opt/data/campaigns/<campana>/` antes de pedirle el archivo al Admin.
- Hacer copia intacta de la fuente entregada (`FUENTE_enviada_Telegram_*.mp4`) con `cp` + `cmp`: es el respaldo de lo que el Admin ya vio.

## 2. Edición quirúrgica
- Restaurar SOLO las ventanas donde aparecen los subtítulos/logo, usando la placa limpia como fuente de píxeles. Fuera de esas ventanas, el máster entregado queda intacto.
- Conservar deliberadamente lo que es parte del material real del local (rótulos físicos, placas +18 «Juego responsable») y decirlo en el manifiesto.
- Audio: `ffmpeg -i entrega.mp4 -i fuente.mp4 -map ... -c:a copy ...` — copiar el stream AAC sin recodificar.

## 3. Verificación obligatoria antes de declarar la entrega
1. ffprobe completo: contenedor, resolución, fps, duración y decodificación sin errores (`ffmpeg -f null -`).
2. SHA-256 del stream de audio extraído de fuente y entrega: deben ser idénticos (prueba de audio intacto).
3. Muestreo de fotogramas con `vision_analyze` sobre frames extraídos en los bordes de las ventanas editadas (onset/offset ±): sin subtítulos ni logo en las muestras.
4. Registro final: SHA-256 + MD5 del archivo, tamaño, metadatos Drive leídos de vuelta tras subir (tamaño/MD5 remoto == local).

## 4. Manifiesto de entrega en el repo
- Crear `docs/verification/<campana>/ENTREGA_Vxx.md` con: link + Drive ID, hashes, metadatos, fuente y placa usadas, preservaciones deliberadas, limitaciones (escucha humana pendiente, discrepancias de QA heredadas).
- Copiar a la misma carpeta los antecedentes (EDL, informe QA, subtítulos .srt/.ass editables, manifiestos de voz) verificando con `cmp` que las copias son idénticas. Aclarar en el manifiesto que son registros de sus autores, no aprobación final.
- MP4/WAV quedan git-ignored: al repo solo van docs. Los respaldos de medios viven en `/opt/data/campaigns/`.

## 5. Commit/push en repo con trabajo paralelo
- El worktree suele tener cambios de otras sesiones/crons: stagear SOLO rutas nuevas propias y commitear con `git commit --only -m '<tipo>(<alcance>): <resumen>' <rutas>`.
- Si `git add` topa con `index.lock`: inspeccionar edad, tamaño y descriptores abiertos (`/proc/*/fd`); si es obsoleto (0 bytes, >1h, sin holders), renombrarlo a `.git/index.lock.backup-<ts>` — nunca borrarlo sin diagnostico.
- Antes del push: `git ls-remote origin refs/heads/main` debe seguir apuntando al padre del commit local; si cambió, detenerse y rebasear/escalar.
- Push solo con autorización explícita del Admin; verificar con hash local == `git ls-remote` después.

## Lecciones de flujo del Admin (correcciones recibidas en sesión)
- «Si lo enviaste por Telegram, lo debiste guardar en un lugar específico»: las entregas siempre tienen ruta durable previa; buscarla antes de preguntar.
- «Si están disponibles, hágalo»: un «no puedo» sin sonda de ejecución real se corrige en el momento y cuesta confianza. Probar primero, reportar después.
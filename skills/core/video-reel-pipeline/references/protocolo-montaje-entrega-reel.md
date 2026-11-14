# Protocolo de montaje, QA y publicación de reels de campaña (v4)

> **Estado:** vigente desde 13-nov-2026, derivado del cierre de los reels R1 de `2026-11-aguinaldo`
> (Golden Game Pacho y The Grand Paradise Club Chiquinquirá 1).
> **Ejecutor de referencia:** `scripts/montar_reel_v3.py` (nombre histórico; la versión de salida se
> controla con `--ver`, hoy `v4`).
> **Regla de oro:** un reel no está listo cuando el mp4 existe; está listo cuando el link público
> responde 200 con `Content-Type: video/mp4`, `206` en range y md5 idéntico al archivo local.

---

## 1. Artefactos y versionado

```
planning/<campaña>/03-piezas/reels/<fecha>-r<N>/
  <marca>/escenas/video/scene-0N.mp4     # material i2v aprobado (entrada)
  <marca>/audio/scene-0N.mp3             # VO ElevenLabs (entrada)
  <marca>/audio/musica.mp3               # música continua por marca
  <marca>/reel/guion.txt                 # guion literal (referencia del QA)
  <marca>/reel/build-v<N>/               # intermedios: seg-0N.mp4, master.mp4, sub-N.txt, logo.png, sign.png
  <marca>/reel/reel-<marca>-r<N>-v<N>.mp4  # ENTREGABLE
```

- **Una versión no se sobrescribe.** Cada corte nuevo sube `--ver v5`, `v6`… y el anterior queda
  consultable en la galería. Sobrescribir rompe la comparación con el cliente y la caché de Cloudflare.
- Los intermedios (`build-v*`) no se versionan en git (`.gitignore`: `planning/**/reel/build-v*/`).
  Ojo: la regla ignora **nuevos** archivos; si alguno quedó trackeado antes, se saca con `git rm --cached`.
- Para no re-codificar el Paso A al subir de versión, los segmentos se heredan con hardlink:
  `mkdir build-v5 && cp -l build-v4/seg-0*.* build-v5/` — el `*.*` arrastra los `seg-0N.mp4` **y**
  sus `seg-0N.sha`; sin las huellas el script considera la caché inválida y re-codifica todo. La
  huella cubre `L`, `tpad`, grade, push-in y `size`+`mtime_ns` del mp4 de origen: si algo cambió,
  rehace el segmento en vez de reutilizarlo.

---

## 2. Timeline: la línea de tiempo la manda el guion, no el material

`PLAN[marca]` declara, por escena:

| Campo | Qué es | Regla |
|---|---|---|
| `L[i]` | duración entregada en pantalla | = duración de la VO de esa línea + aire mínimo |
| `tpad[i]` | material que falta para el solape | se congela el último frame (`tpad=stop_mode=clone`) justo en el crossfade |
| `vo[i]` | duración real de la VO | se mide del mp3, no se estima |
| `subs[i]` | línea literal del guion | se parte en dos renglones con `\n`; nunca se reescribe |
| `close` | letrero de cierre (t1, t2, t3) | a la izquierda, sin tapar al personaje; pie legal en zona segura |

Fórmulas:

```
X[0] = 0
X[i] = X[i-1] + L[i-1] - T            # T = 0.30 s de crossfade
close_on = X[última escena de diálogo]
total = sum(L[:-1]) - T*(n-2) + L[-1]
onset_subtitulo = X[i-1] + VO_OFFSET + 0.15   # VO_OFFSET = 0.30
```

**Invariante de continuidad:** la VO siguiente entra 0.30 s después de que arranca su escena; nunca
hay silencio muerto entre líneas ni VO pisada por el crossfade.

---

## 3. Reglas de composición (medidas, no al ojo)

| Elemento | Valor vigente | Verificación |
|---|---|---|
| Subtítulos | `BebasNeue` 72 px, `borderw=4` `bordercolor=black@0.9`, `line_spacing=8`, `y=0.745H` | ancho de la peor línea ≤ 900 px (medido con PIL `getbbox`); banda de texto en el frame ≈ 147 px de alto para 2 renglones |
| Logo | caja de 156 px de alto, margen derecho 36 px, `y=30` | ojo: el PNG puede traer padding transparente — Golden muestra 63 % de su caja (98 px visibles), Lucky 100 % (156 px) |
| Letrero de cierre | panel `x 40→560`, `y 0.335H→0.585H`, radio 30 | no debe cubrir la cara del personaje (en Lucky lo roza: pendiente decidir lado) |
| Pie legal | franja de 88 px en `y=0.845H` | `+18 · PREGUNTA EN CAJA · AUTORIZA COLJUEGOS · SOLO MAYORES DE EDAD` |
| Zona segura | nada de texto narrativo bajo `0.85H` | la UI de Reels/TikTok tapa el 15 % inferior |
| Excepción declarada | el **pie legal** vive a propósito en `y=0.845H` (franja 1622-1710 px), dentro de esa banda | es requisito legal colocarlo al pie; si la plataforma lo tapa, se sube la franja y se re-mide |

**Regla de tamaño:** si el Admin pide «más grande», se sube en el script (`SUB_SIZE`, `LOGO_H`) y se
**mide en el frame**, no se declara. Referencia de esta iteración: subtítulo 46 → 72 px (+56 %),
logo 88 → 156 px (+77 %).

**No se duplica el mensaje:** si la última VO cae dentro del cierre, su subtítulo se omite porque el
letrero ya dice la frase (regla `onset >= X[-1] - 0.01 → skip`, el margen absorbe el redondeo a
centésimas del timeline). Duplicarlo quema el frame y el revisor lo marca como solape.

---

## 4. Audio

- **Solo la VO genera voz.** El audio de los clips i2v no entra al mix.
- Música continua por marca, `volume=0.24`, ducking por `sidechaincompress`
  (`threshold=0.02:ratio=5:attack=120:release=600`).
- Loudness en **dos pasadas** sobre el master: `loudnorm=I=-14:TP=-1.5:LRA=11`, segunda pasada con los
  valores medidos y `linear=true`; video en `-c:v copy`.
- Aceptación: **−14 ± 0.1 LUFS** y true peak ≤ −1.0 dBTP (medido con `loudnorm print_format=summary`).

---

## 5. Invariantes de ffmpeg (cada una costó un render perdido)

1. **PNG en bucle siempre acotado.** `-loop 1 -framerate {FPS} -t {total} -i imagen.png`. Sin `-t` el
   overlay sigue pidiendo frames después de que el video termina y el render no cierra nunca
   (Golden v3: 78 min de CPU para un corte de 24 s). En la salida, además, `-t {total} -shortest`.
2. **`-shortest` recorta el cierre si la cadena de audio muere antes.** `sidechaincompress` termina con
   su llave (la última VO) y `amix duration=first` termina con su primera entrada → master de 21.3 s
   cuando el timeline decía 24.56 s. Se arregla con `apad=whole_dur={total}` en la llave y
   `amix duration=longest` al final.
3. **Nada de `xfade` con el clip de cierre.** El clip de cierre no tiene frames con `t >= close_on` y
   ffmpeg espera frames que nunca llegan (master congelado). El cierre se une por `concat` con fades.
4. **`asplit` obligatorio** cuando un mismo label de audio se usa dos veces.
5. **Texto por `textfile`**, no inline: `drawtext` trunca con los `:` de las líneas del guion.

**Verificación mínima post-render:** `ffprobe format=duration` debe coincidir con el `total` impreso
por el timeline (±0.05 s). Si no coincide, no se mira el video: se arregla el grafo.

---

## 6. QA en tres capas (en este orden, sin saltos)

1. **Determinista — `qa_gate.py`** (`core/video-reel-pipeline/scripts/qa_gate.py`):
   detecta frames vacíos por segundo (media/std/edges). Criterio: `OK: N muestras, ningún frame vacío`.
   Cero tokens.
2. **Modelo de video nativo — `video_native_qa.py`** con el `guion.txt` como referencia:
   `NAN_BUILDERS_API_KEY` sale de `/opt/hermes-agent-data/.env`; modelo `glm5.3-flash`.
   Criterio de aceptación: `passed: true`, **`blocking: []`** y **score ≥ 8.0**.
   Un warning de severidad `low` no bloquea, pero se lee y se decide (así se cazó el solape
   letrero/subtítulo de Lucky v4).
3. **OCR — `tesseract -l spa`** sobre recortes del propio mp4:
   banda de subtítulos (`crop=1080:340:0:1300`), letrero del cierre (`crop=640:640:20:580`),
   pie legal (`crop=1080:110:0:1600`). Confirma que el texto **se lee**, no solo que existe.

Se documenta el resultado de las tres capas con los números en la respuesta al Admin
(score, LUFS, alto de banda, duraciones). «Se ve bien» no es evidencia.

---

## 7. Publicación (dos destinos, uno público)

| Destino | Ruta en PROD | URL | Quién lo ve |
|---|---|---|---|
| Galería pública | `/opt/reels/assets/<campaña>-reels-r<N>/` | `https://reels.neuralcrewlabs.com/assets/...` | cliente, sin login |
| Galería interna | `/opt/reels/campanas/<campaña>/reels-r<N>/` | `https://reels.neuralcrewlabs.com/campanas/...` | equipo, detrás de SSO |

- **`/campanas/**` está detrás de oauth2-proxy** (302 a `auth.neuralcrewlabs.com`). Para links de
  cliente **solo** `/assets/**`, que responde 200 sin sesión.
- La página pública es autocontenida: `index.html` + los `vN.mp4` + posters jpg, mismo directorio,
  rutas relativas. Se marca `noindex`.
- **Cache-busting:** cada `<video src>` lleva `?v=<primeros 8 del md5>`; nunca se espera el TTL.
- Versiones anteriores se enlazan como texto bajo el video (`v3`, `v2`, `v1`), no se borran.

### Checklist de publicación (obligatorio, todo con salida real)

```bash
# 1. subir (aditivo, nunca --delete)
scp reel-<marca>-r<N>-v<N>.mp4 prod:/opt/reels/assets/<campaña>-reels-r<N>/

# 2. integridad
ssh prod 'md5sum /opt/reels/assets/.../reel-*.mp4'; md5sum <local>     # deben coincidir

# 3. respuestas HTTP (externo, no localhost)
curl -sI https://reels.neuralcrewlabs.com/assets/<dir>/ | grep -E 'HTTP/|content-type'
curl -sI https://reels.neuralcrewlabs.com/assets/<dir>/reel-<marca>-r<N>-v<N>.mp4 | grep -E 'HTTP/|content-type|content-length'
curl -s -o /dev/null -w '%{http_code}\n' -H 'Range: bytes=0-1023' https://.../reel-....mp4   # 206

# 4. la página publicada apunta a la versión nueva
curl -s https://reels.neuralcrewlabs.com/assets/<dir>/ | grep -o 'reel-[a-z]*-r<N>-v<N>.mp4'
```

Si cualquiera de los cuatro pasos falla, **no se entrega el link**: se dice qué falló.

---

## 8. Entrega al Admin

- El link público + los links directos por marca + el link de la galería interna.
- Los mp4 van **adjuntos en el mismo mensaje** del «listo» (`MEDIA:/ruta`), no en un turno posterior.
- Se declaran los números medidos (duración, LUFS, score, qué cambió) y **lo que quedó pendiente**
  (ej. el letrero que roza la mascota en Lucky), no se esconde.

---

## 9. Anti-patrones registrados

- Lanzar el render y reportar «va bien» sin `ffprobe` de duración → el master puede estar corto.
- Aceptar `passed: true` de un modelo sin mirar `blocking` y `warnings`.
- Subir a `/campanas/` y pasar ese link a un cliente (SSO → 403/302).
- Re-codificar todo el reel para un cambio de tamaño de subtítulo (heredar segmentos con hardlink).
- Medir «más grande» por el parámetro del script en vez de por píxeles en el frame.
- Dejar el `--ver` fijo y sobrescribir la versión que el cliente ya vio.

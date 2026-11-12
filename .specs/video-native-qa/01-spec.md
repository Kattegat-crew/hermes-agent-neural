# 01-spec — QA de video con el mp4 nativo como input

## Problema
El QA de un film se hacía con un script ad-hoc en `cache/scratch`: manda el mp4 en base64 al
endpoint de NAN Builders, imprime prosa y no deja rastro. No hay presupuesto de pasadas, no hay
cache (un mismo corte se paga dos veces), no hay veredicto parseable y el resultado no es
reproducible. El benchmark de modelos del 11-nov demostró que `glm5.3-flash` lee el film completo
—no frames sueltos— pero también que los modelos **inventan** defectos; sin un gate determinista
delante y sin confirmación entre pasadas, el revisor se vuelve una fuente de falsos positivos.

## Objetivo
Una pieza reutilizable, versionada en la skill `core/video-reel-pipeline`, que:

1. Manda el **video nativo** (mp4 completo) al modelo junto al guion de narración.
2. Devuelve un **veredicto estructurado** (passed, score, voids, collisions, narration_sync,
   legibility, pacing, blocking[]) y un exit code utilizable por un pipeline.
3. Cobra como máximo `--max-passes` llamadas por video (default 2) y **cero** cuando el gate
   determinista ya falló.
4. Cachea por hash del archivo + modelo + contrato + guion: el mismo corte no se paga dos veces.
5. Falla cerrado: sin veredicto válido no hay aprobación.

## No-goals
- No sustituye al gate determinista (`qa_gate.py`) ni al manifiesto de layout: el VLM no mide
  píxeles, ni márgenes, ni lee texto de 12 px con fiabilidad.
- No genera video, ni audio, ni subtítulos.
- No decide por encima del humano: es un gate previo al ojo del Admin.
- No introduce dependencias nuevas (stdlib + ffprobe/ffmpeg ya presentes).

## Criterios de aceptación
- **CA1** Dado un mp4 válido y un guion, cuando corro el script, entonces el payload al modelo
  incluye un `content` part `video_url` con `data:video/mp4;base64,` y el texto del guion.
- **CA2** Dado un veredicto con un hallazgo `critical` o `high`, cuando lo evalúo, entonces el
  exit code es `1` aunque el modelo haya puesto `passed: true`.
- **CA3** Dado un hallazgo `medium` en una sola pasada, entonces es advertencia (exit `0`) y queda
  listado como no confirmado; si aparece en dos pasadas, bloquea.
- **CA4** El número de llamadas al modelo nunca excede `--max-passes`, incluso si todos los
  veredictos son inválidos o negativos.
- **CA5** Con `--pre-gate`, un fallo de `qa_gate.py` produce exit `1` con **cero** llamadas al
  modelo.
- **CA6** La segunda corrida idéntica no hace llamada de red (cache por hash) salvo `--force`.
- **CA7** Respuesta no parseable ⇒ exit `2` (degradado), nunca `0`.
- **CA8** Archivo > `--max-mb` o sin API key ⇒ exit `2` con mensaje, sin llamada de red.
- **CA9** `--dry-run` imprime el payload (tamaño y prompt) sin llamada de red.
- **CA10** `scripts/run_tests.sh tests/skills/test_video_native_qa_skill.py -q` en verde.

## Edge cases
- Video sin pista de audio: el contrato pide juzgar sólo lo visible y marcar `narration_sync` como
  `ok: true` cuando no hay voz.
- `passed: false` sin ningún hallazgo nombrado ⇒ bloquea (rechazo sin defecto = no se publica).
- Veredictos contradictorios entre pasadas con hallazgos ⇒ decide la lista de hallazgos, no el
  flag del modelo.
- `ffprobe` ausente ⇒ exit `2` (no se puede verificar el artefacto).

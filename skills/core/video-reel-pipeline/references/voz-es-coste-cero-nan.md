# Voz en español a coste cero vía nan (kokoro + whisper)

Vía verificada en producción (12-nov-2026, campa a 200 OK con texto ES real) para producir
voz con alineación palabra-por-palabra SIN tocar el gate de gasto: nan.builders expone TTS
y transcripción unmetered dentro del plan existente.

## Cuándo usarla
- `spend_gate` cerrado / sin autorización de gasto: NO intentar ElevenLabs (`/with-timestamps`)
  ni fal; usar esta vía. Solo el QA con modelos cuesta (centavos).
- Si el humano autoriza gasto y quiere voz de marca (Voz-Goldie qWWAqFomnJ99VwQLREfT,
  «Lucky final» lWweqHoPFkas8ijavnVj del lote-preparado.json SSOT), sí va por ElevenLabs
  con gate; esta vía queda como draft/fallback.

## TTS ES (OpenAI-compatible)

```bash
set -a; . /opt/hermes-agent-data/.env; set +a   # NAN_BUILDERS_API_KEY
curl -s -X POST https://api.nan.builders/v1/audio/speech \
  -H "Authorization: Bearer $NAN_BUILDERS_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"kokoro","voice":"em_alex","input":"<texto ES>","response_format":"mp3"}' \
  -o voz.mp3 -w "%{http_code} %{size_download}\n"
```

Voces ES de kokoro verificadas:
- `em_alex` — masculino ES (Goldie, tono cálido). 3.72 s para la frase de prueba.
- `ef_dora` — femenino ES (Lucky, femenina cálida). 3.67 s.

## Alineación palabra-por-palabra (cue sheet) con whisper

`/v1/audio/transcriptions` con `response_format=verbose_json` y
`timestamp_granularities[]=word` devuelve `words[] {word,start,end}` en español,
segundoid exactos sobre el mismo audio — sin faster_whisper local (no instalado):

```bash
curl -s -X POST https://api.nan.builders/v1/audio/transcriptions \
  -H "Authorization: Bearer $NAN_BUILDERS_API_KEY" \
  -F file=@voz.mp3 -F model=whisper -F language=es \
  -F response_format=verbose_json -F "timestamp_granularities[]=word"
```

Con esto el cue sheet se cuelga de los timestamps REALES de la voz (regla del pipeline:
unoprio el guion a la voz, nunca la voz al cue estimado).

## Fallback con gate abierto: tts_aligned.py

`launch-proof/tts_aligned.py` (sesión 11-nov) sintetiza con ElevenLabs
`/v1/text-to-speech/<voice>/with-timestamps` (`eleven_multilingual_v2`) y convierte la
alineación carácter-a-carácter que devuelve en `words[] {w,start,end}` — mismo formato de
payload que la vía whisper, así el montador consume uno u otro sin cambios.

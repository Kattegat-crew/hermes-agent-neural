# 02-design — QA de video nativo

## Componentes

```
video_native_qa.py
├── probe_duration()      ffprobe: duración real del artefacto (no del nombre)
├── run_pre_gate()        subprocess qa_gate.py (determinista, coste 0)
├── build_prompt()        contrato JSON + guion (+ cues si existen)
├── parse_verdict()       parseo estricto: una forma incompleta NO es un pase
├── decide()              agregación entre pasadas (confirmación por severidad)
├── _post()               POST a NAN Builders (urllib, stdlib)
├── cache                 sha256(video)+modelo+contrato+guion → receipt JSON
└── main(argv, transport) exit 0/1/2
```

## Contrato con el modelo
`POST https://api.nan.builders/v1/chat/completions`, `Authorization: Bearer $NAN_BUILDERS_API_KEY`,
`messages[0].content = [{type:text,text:<contrato+guion>}, {type:video_url,video_url:{url:"data:video/mp4;base64,…"}}]`,
`temperature: 0`, `max_tokens: 1500`.

El video va **nativo**: no se extraen frames. Es lo que permite juzgar sincronía voz/imagen, que es
justo lo que el revisor de frames no puede ver.

## Política de decisión (fail-closed)
| Situación | Exit |
|---|---|
| Ningún veredicto válido | 2 |
| Hallazgo `critical`/`high` en una pasada | 1 |
| Hallazgo `medium` en 2 pasadas | 1 |
| `passed:false` sin hallazgos | 1 |
| `medium` en 1 pasada | 0 + warning |
| Todo limpio | 0 |
| Gate determinista en rojo (con `--pre-gate`) | 1, coste 0 |

`passed:true` con un `critical` dentro ⇒ bloquea: manda la evidencia, no el flag.

## Presupuesto de pasadas
- Una pasada basta para aprobar (verde no se re-confirma: no se paga de más).
- Una pasada que falla dispara la segunda, que **confirma o descarta** el defecto. Nunca una tercera.
- `--max-passes 1` convierte todo `medium` en advertencia y deja `critical/high` bloqueando.

## Cache
`$VIDEO_QA_STATE` (default `$HERMES_HOME/video-qa`)/`receipts/<sha256>.json`. Clave: hash del mp4,
modelo, versión de contrato y guion. Un corte reeditado cambia el hash; el mismo corte no se
re-cobra. `--force` re-revisa.

## Rollback
Revertir el commit deja la skill como estaba: los ficheros nuevos son aditivos
(`scripts/video_native_qa.py`, `references/qa-video-nativo.md`, el test) y el único cambio en
`SKILL.md` es una línea de índice más una sección corta. No hay migración de datos ni estado
compartido.

# soul-survey — Encuesta /soul v2 (plugin Hermes)

Plugin determinista para perfilar agentes personales Hermes vía WhatsApp y generar/fusionar su `SOUL.md`. Sin LLM en el camino: máquina de estados pura con hook `pre_gateway_dispatch` + comando `/soul`.

## Arquitectura

| Archivo | Rol |
|---|---|
| `plugin.yaml` | name `soul-survey` (¡con guion!), hook `pre_gateway_dispatch` |
| `__init__.py` | Hook + registro del comando `/soul` + ventana armada (armed window) |
| `questions.py` | Catálogo: **6 preguntas** tuteadas (colombiano) |
| `survey_engine.py` | Máquina de estados, polls nativos con fallback texto, merge SOUL.md |

## Cuestionario (v2)

| ID | Pregunta | Tipo |
|---|---|---|
| Q1 | ¿Cómo se va a llamar tu asistente? | abierta |
| Q2 | ¿Y tú cómo quieres que te llame yo? | abierta |
| Q3 | Personalidad contigo | choice A-D |
| Q4 | Frases/palabras que jamás deba usar | abierta |
| Q5 | Acciones que requieren permiso previo | multi A-D |
| Q6 | Qué te hace perder tiempo y cómo ayudar | abierta |

Reglas duras horneadas (no se preguntan): audiencia exclusiva (solo su persona asignada), jamás borrar datos/memoria, no tocar `.env`/sistema/infra, estilo directo con emojis moderados.

## Flujo

1. `/soul` (comando de plugin) → bienvenida + Q1, arma ventana de 10 min
2. Respuestas secuenciales; polls nativos si el adapter soporta (`send_poll`), si no texto
3. `corregir Q<n>` salta atrás · `/salir` cancela · TTL 30 min
4. Confirmación → resumen → guarda: crea o **fusiona** (dual-marker, sección reemplazada in-place)

Marcadores reconocidos: `## 📋 Perfil Operativo del Asistente (/soul)` (actual) y legacy `## 📋 Encuesta /soul — Perfil Operativo (6 bloques)`.

## Runbook de deploy (VPS 169.58.189.222)

```bash
# 1. Copia local de trabajo
scp -r root@169.58.189.222:/opt/data/plugins/soul_survey/ ./soul_survey/
# 2. Editar + compilar
python3 -m py_compile questions.py survey_engine.py __init__.py
# 3. Test E2E simulado (18 checks, FakeGateway/FakeAdapter, sin WhatsApp real)
python3 test_e2e.py
# 4. Deploy a AMBAS copias con backup
scp questions.py survey_engine.py __init__.py root@169.58.189.222:/opt/data/plugins/soul_survey/
ssh root@169.58.189.222 'chown 10000:10000 /opt/data/plugins/soul_survey/*.py && \
  docker cp /opt/data/plugins/soul_survey/__init__.py hermes-agent:/opt/hermes/plugins/soul_survey/ && \
  docker cp /opt/data/plugins/soul_survey/survey_engine.py hermes-agent:/opt/hermes/plugins/soul_survey/ && \
  docker cp /opt/data/plugins/soul_survey/questions.py hermes-agent:/opt/hermes/plugins/soul_survey/ && \
  docker exec hermes-agent sh -c "rm -rf /opt/hermes/plugins/soul_survey/__pycache__"'
# 5. Restart + verificación
docker restart hermes-agent   # espera ~25s
docker logs --since 1m hermes-agent | grep "Bridge ready"
hermes plugins list | grep soul   # enabled / source:user
```

## Troubleshooting (causas raíz reales de producción)

| Síntoma | Causa raíz | Fix |
|---|---|---|
| El bot improvisa una encuesta vieja (texto parecido pero no idéntico) | Plugin sin `plugins.enabled: [soul-survey]` en el **config.yaml del perfil** (la config raíz NO hereda) | Agregar bloque al perfil + restart |
| `/soul` dispara la encuesta vieja con "3 opciones" | Skills viejas duplicadas (`soul`, `client-agent-soul-survey`, `client-agent-onboarding`) secuestran el trigger slash antes que el plugin | Cuarentena de skills (ver `/opt/data/quarantine_skills_soul_viejas_20260823/`) |
| `Unknown command /soul` | Capa slash de Hermes resuelve comandos antes que el hook; sin comando ni skill registrada, muere | Ya resuelto: el plugin registra `/soul` vía `ctx.register_command()` |
| Cambios "revierten" solos dentro del container | Watchtower/Coolify RECREAN el container → la copia bundled vuelve a la de la imagen | La copia user (`/opt/data/plugins`, bind-mount) siempre gana; re-`docker cp` la bundled si quieres paridad |

## Rollback

Restaurar `.bak-<timestamp>` en ambas rutas + `rm -rf __pycache__` + restart. El historial completo del rediseño vive en Engram (`topic_key: soul-survey/redesign`).

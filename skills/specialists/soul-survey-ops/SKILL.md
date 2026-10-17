---
name: soul-survey-ops
description: "Trigger: soul-survey, encuesta /soul, perfilado hermes, SOUL.md merge, unknown command soul, deploy plugin hermes prod 222. Editar, probar y desplegar el plugin soul-survey en Hermes prod con verificación E2E y troubleshooting de causas raíz."
license: Apache-2.0
metadata:
  author: dominus-neuralcrew
  version: "1.0"
---

# Soul Survey Ops

## Activation Contract

Úsalo al editar, desplegar o depurar el plugin `soul-survey` en Hermes prod (VPS 169.58.189.222): cambios al cuestionario, textos, motor de estados, merge de SOUL.md, o síntomas como encuestas viejas improvisadas por el LLM, `/soul` con "Unknown command", o cambios que "revierten" solos.

## Hard Rules

- Fuente activa = copia user `/opt/data/plugins/soul_survey/` (bind-mount); la bundled (`docker cp` a `hermes-agent:/opt/hermes/plugins/soul_survey/`) es paridad cosmica que Watchtower/Coolify pueden borrar al recrear el container.
- **Segunda copia (host neuralcrew, vmi3151337):** mismo layout en `data/plugins/soul_survey/` + bundled en su contenedor. El runtime **host-side** usa **python 3.11** (`/opt/hermes-venv`): f-strings anidados (como los de la v1) rompen la carga ahí aunque el contenedor (3.13) los acepte — la v2 compila en ambos. Deployar igual (E2E → backups → copia user + bundled → `chown 10000:10000` → restart `gateway-default` vía s6) y verificar `hermes plugins list` → `source: user` + ausencia de errores nuevos en `errors.log`.
- Deploy SIEMPRE con backup `.bak-<ts>` previo y owner `10000:10000`.
- PROHIBIDO enviar WhatsApp real para probar: usar `test_e2e.py` (FakeGateway/FakeAdapter).
- Todo texto nuevo del bot en colombiano tuteado; prohibido voseo argentino.
- El E2E local requiere importar el plugin como paquete (import relativo): copiar a un pkg temporal.
- Los textos exactos del resumen/bienvenida están asertados en el test: cambiar copy implica actualizar test.

## Decision Gates

| Síntoma | Causa raíz | Acción |
|---|---|---|
| LLM improvisa encuesta vieja | Plugin sin enable en config.yaml DEL PERFIL | Agregar `plugins.enabled: [soul-survey]` al perfil + restart |
| `/soul` lanza cuestionario viejo con opciones extrañas | Skills legacy secuestran el trigger slash | Cuarentena de skills (modelo en `/opt/data/quarantine_skills_soul_viejas_20260823/`) |
| `Unknown command /soul` | Falta comando registrado | Ya resuelto vía `ctx.register_command()`; verificar md5 de `__init__.py` |
| Cambios revierten dentro del container | Container RECREADO por Watchtower/Coolify | `docker inspect Created`; re-`docker cp` bundled |

## Execution Steps

1. Cargar contexto: leer `references/plugin-readme.md` y bajar copia fresca por SCP.
2. Editar localmente en `/tmp/opencode/soul_survey/`; `python3 -m py_compile *.py`.
3. Ejecutar `assets/test_e2e.py` (18 checks: crear/fusionar/re-run/migración marker/TTL/corregir). Exigir TODO OK.
4. Deploy con backups a ambas copias (comandos exactos en references/plugin-readme.md §Runbook).
5. `docker restart hermes-agent`, esperar "Bridge ready" y confirmar `plugins list` → enabled/source:user.
6. Verificación humana opcional: usuario corre /soul real; auditar SOUL.md resultante (1 sola marca, Q5 sin duplicados).

## Output Contract

Reportar: archivos tocados, resultado E2E, md5 de ambas copias, estado post-restart, y hallazgos nuevos guardados en Engram (`topic_key: soul-survey/redesign`).

## References

- `references/plugin-readme.md` — arquitectura, runbook completo y troubleshooting detallado.
- `assets/test_e2e.py` — suite E2E simulada lista para correr contra una copia local.

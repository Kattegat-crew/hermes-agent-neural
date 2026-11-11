# Post-upgrade smoke checks (tras CUALQUIER upgrade de Hermes)

Correr en orden ANTES de diagnosticar fallas de workers/tickets post-upgrade.
Cada check con comando y umbral de OK. Un install que falla en el check 1
imita cualquier cantidad de bugs de la release nueva.

## 1. Entorno de dependencias (venv)
- `hermes pm repair` — OK: `venv_rebuild.ok = true`, `warnings: []`.
- Falla típica post-upgrade: "no dependency environment is committed for this
  install". Síntoma engañoso: workers (kanban, plugins) mueren
  `exited with code 1` ANTES de ejecutar nada; el texto real solo sale en
  `hermes pm repair` o en el log del worker.
- El repair exige reinicio de gateways para tomar efecto.

## 2. Topología kanban multi-perfil
- `grep dispatch_in_gateway /opt/data/profiles/*/config.yaml` → solo `default`
  en `true`; TODOS los demás perfiles en `false`. Si cada gateway despacha,
  los dispatchers compiten: `owner refused` / `owner silent for Ns` en
  `task_runs`, workers crash.
- `dispatch_interval_seconds` ≥ default (60): valores agresivos multiplican
  presión SQL sin beneficio.

## 3. Triage del estado operativo
- Conteo crashed/blocked en `task_runs` de `kanban.db`. Crashes con exit 1
  inmediato → volver al check 1 antes de culpar a la versión.
- Crons activos y `hermes pm status` sanos.

## 4. Config que conviene revisar tras cada release
- `plugins.isolation` — `in_process` = un plugin defectuoso tumba el proceso
  entero de Hermes; evaluar `host` en flotas con muchos plugins.
- `monitoring.gateway_health_export.enabled` y `monitoring.export.otlp.enabled`
  — en `false`, un gateway de perfil caído solo se descubre cuando escribe el
  cliente.
- `webapp.enabled` + `hermes webapp` — UI Desktop en navegador servida por el
  propio gateway, link de un solo uso; reversible con un comando.
- Delegación: `delegation.backend` y rutas por perfil — sin rutas, todo
  subagente corre con el modelo/perfil del agente padre en vez del
  especialista (SOUL, skills y credenciales propias).
- `tool_costs` + `spend_limit` por servidor MCP pagado — gate de gasto en
  motor (el approval muestra el costo y frena al pasar el tope), no en prompt.
- Chats canónicos `Bot Chat` por perfil si se usa `message_agent` headless
  entre perfiles (`hermes -p X chat -c "Bot Chat" --create-if-missing`).

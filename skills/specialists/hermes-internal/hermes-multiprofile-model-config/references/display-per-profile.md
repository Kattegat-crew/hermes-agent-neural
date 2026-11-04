# Display por perfil — pitfall complementario (26/08/2026)

Un perfil Hermes SIN sección `display` en su `config.yaml` cae al default por plataforma de Discord:
`tool_progress: "all"` + `tool_preview_length: 40` + `busy_ack_detail: true` → **el bot filtra cadena de
pensamiento y comandos en el canal** ("está mostrando toda la línea de pensamiento y comandos que ejecuta").

Fix: añadir a cada perfil:
```yaml
display:
  tool_progress: false
  show_reasoning: false
  interim_assistant_messages: false
  busy_ack_detail: false
  tool_preview_length: 0
```
Verificación sin reinicio (el gateway lee el config del perfil por turno vía `_profile_runtime_scope`):
```python
from gateway.display_config import resolve_display_setting
import yaml
cfg = yaml.safe_load(open('/opt/data/profiles/<slug>/config.yaml'))
resolve_display_setting(cfg, 'discord', 'tool_progress')   # 'off'
```

Detalle completo + plantilla: `devops/hermes-multiprofile-gateway-ops` → `templates/display-profile.yaml` y
`references/2026-08-26-display-cron-root-anydoc.md`.
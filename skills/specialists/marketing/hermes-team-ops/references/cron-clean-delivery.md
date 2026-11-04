# Entregas de cron LIMPIAS — quitar el footer en inglés

## Problema

Las entregas de cron vienen envueltas por `cron/scheduler.py` con un header y
footer en inglés:

```
Cronjob Response: <nombre>
(job_id: <id>)
-------------
<contenido>
To stop or manage this job, send me a new message (e.g. "stop reminder <nombre>").
```

Jonathan pidió limpiar ese texto de TODAS las entregas (25/08/2026): "estamos
terminando de limpiar mensajes en ingles, mensajes de error, todo eso para que
solo tengan la conversacion limpia con lo agentes".

## Fix oficial (sin tocar código core)

`scheduler.py` lee un flag de config. Comentario en el propio código:
"Wrapping is on by default; set `cron.wrap_response: false` in config.yaml for
clean output."

Añadir a config.yaml de CADA perfil:

```yaml
cron:
  wrap_response: false
```

- Es POR-PERFIL, no global. Cada perfil necesita su propia entrada.
- El flag se lee en `cron/scheduler.py` (buscar `wrap_response`) vía `load_config()`.
- El gateway lee el config del perfil al iniciar (y al multiplexar, del suyo propio).

## Cómo aplicar en todos los perfiles de un VPS

Script idempotente (`fix_wrap_response.py`): hace backup `config.yaml.bak-cronwrap-<ts>`,
añade el bloque `cron:\n  wrap_response: false` al final (YAML acepta claves en
cualquier orden) si no existe `wrap_response` ya.

```python
import shutil, time
from pathlib import Path
for p in sys.argv[1:]:
    path = Path(p)
    text = path.read_text()
    if "wrap_response" in text:
        print(f"SKIP {p}"); continue
    shutil.copy2(path, path.with_name(f"{path.name}.bak-cronwrap-{time.strftime('%Y%m%d-%H%M%S')}"))
    if not text.endswith("\n"): text += "\n"
    path.write_text(text + "\ncron:\n  wrap_response: false\n")
```

Verificar YAML tras editar: `python3 -c "import yaml; yaml.safe_load(open('<file>'))"`.

## Reiniciar el gateway para aplicar

`docker exec hermes-agent /package/admin/s6/command/s6-svc -r /run/service/gateway-default`
puede NO cambiar el PID (a veces es no-op). Forzar con:

```
docker exec hermes-agent /package/admin/s6/command/s6-svc -t /run/service/gateway-default
```

(`-t` = SIGTERM → s6 respawnea con config/env nuevos). Verificar:
`docker exec hermes-agent /package/admin/s6/command/s6-svstat /run/service/gateway-default`
debe mostrar un PID nuevo. No matar el gateway desde dentro del propio proceso del
gateway (el guard lo bloquea) — usar el camino `docker exec`/SSH separado.

## Alcance aplicado (25/08/2026)

- **Prod** (169.58.189.222 / Tailscale 100.73.30.29): default (ya lo tenía),
  helmer, jacqueline, nancy, yulieth, neural-admin-test. Backups `.bak-cronwrap-20260826-023839`.
- **Dev** (147.93.3.250 / este contenedor): default (ya lo tenía), roshi, vigia.
  Backups `.bak-cronwrap-20260825-194147`.

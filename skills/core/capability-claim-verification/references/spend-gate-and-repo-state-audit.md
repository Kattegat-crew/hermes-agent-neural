# Auditoría de gates de gasto y estado del repo (marketing-campaign-generator, 11-sep-2026)

Caso: «analiza el repo del marketing campaign generator, mira cómo está y si ahí está la api de fal. Tenemos api de fal y de monid, y el gate de gasto.» Auditoría read-only vía `ssh dev`, sin una sola generación. Repo: `/root/marketing-campaign-generator` (host) = `/opt/data/repos/...` (contenedor).

## 1. Inventario de gates: el gate que existe ≠ el gate que corre

```bash
# ¿quién lee el gate? (vacío = decorativo)
grep -rn "\.fal-gate\|\.monid-gate\|MONID_GATE" --include="*.py" --include="*.sh" --include="*.md" . | grep -v /\.git/
# ¿qué entrypoints pueden gastar?
for f in scripts/*.py; do printf "%-40s %s\n" "$f" "$(grep -ciE 'gate|approved_to_spend|max_cost' $f)"; done
```

| Superficie | Gate real | Evidencia |
|---|---|---|
| `scripts/fal-client.py` (video fal) | **Físico y bloqueante** | `fal-client.py:54-96`: `.fal-gate.json` con TTL 6 h; rechaza `approved_by` ∈ {agent, ragnar, assistant}; `sys.exit(3)` antes del POST; `--dry-run` retorna antes del gate |
| `scripts/reel_engine.py` (Monid) | **Valor + presupuesto** | GATE #1 `approved_to_spend != true` ⇒ `SpendGateError` incluso en dry-run; GATE #2 `max_cost_usd` con factor de reserva; contrato en `contracts/brief.schema.json` |
| `.monid-gate.json` | **INERTE** | Existe (expirado 29-ago) pero **0 consumidores** en el repo |
| Scripts Monid sueltos (`run_scenes.py`, `run_t2.py`, `run_pacho*.py`, `batch_seedance_voice.py`, `batch_golden_bingo.py`, `batch_lucky_bingo.py`, `lipsync_batch.py`) | **Ninguno** | 0 hits de gate; basta `MONID_API_KEY`/`FAL_KEY` en el entorno. Excepción: `r2v_run.py` relee `.fal-gate.json` a mano |
| `scripts/nan_client.py` (imágenes flux) | **Ninguno** | Gancho de gasto para imágenes: `NAN_API_KEY` sin puerta |

Transferibles: (1) gate vencido = gate cerrado, léelo y dilo; (2) el gate físico solo cubre su script — reporta la superficie completa; (3) el gate puede vivir en datos (schema del brief), no en código; (4) `--dry-run` que retorna antes del gate no prueba nada sobre el gate.

## 2. Estado del repo y drift de relocalización

El repo pasó de `/root/video-ai-generator` a `/root/marketing-campaign-generator`.

1. **Service unit con rutas absolutas = crash-loop silencioso:**

```bash
systemctl is-active <svc>            # "activating" = bucle, NO "inactive"
systemctl show <svc> -p WorkingDirectory,ExecStart
systemctl status <svc> --no-pager -l | head -20   # restart counter
ls -ld <WorkingDirectory>            # inexistente
curl -s -m 5 http://localhost:<port>/health
```

   Hallazgo: `reel-worker.service` en `activating (auto-restart)`, **restart counter 2515**, «Failed to load environment files: No such file or directory» (WorkingDirectory/EnvironmentFile/ExecStart al path borrado) y `:8090/health` mudo ⇒ el pipeline AP no tenía worker. El README seguía con «Worker HTTP activo ✅» de 2 semanas antes: **el README es un claim, no evidencia**.
2. **Rutas viejas hardcodeadas**: 5 archivos (`test_output_layout.py:47`, `test_review_page.py:154,663`, `test_reel_worker.py:667`, `test_publish_review.sh:22`, `test_mix_narration_output_layout.sh:19`) ⇒ 6 fallos de suite que NO son regresiones funcionales (los assets existen en la ruta nueva).
3. **Trampa `__pycache__`**: los tracebacks de pytest mostraban la ruta VIEJA porque los `.pyc` conservan el `co_filename` de compilación. No concluyas desde el traceback: `grep -n "<path viejo>" tests/<archivo>.py`.
4. **Residuo de propiedad**: 49 ficheros `root:root` en el repo (incl. `scripts/sales_spine.py`, `kb/`, `contracts/*.schema.json`, `content-intel/*`).

## 3. Correr la suite de tests desde DEV

El contenedor tiene `python3` pero **no `pytest`**; `.venv` y `.venv-fit` del repo tampoco. El host DEV sí (`pytest 9.1.1`, `/usr/local/bin/pytest`) y es la misma copia física:

```bash
ssh dev 'cd /root/marketing-campaign-generator && .venv/bin/python -m pytest tests/ -q 2>&1 | tail -25'
# (ruta del 11-sep-2026; antes del move: /root/hermes-agent-legacy-docker/data/repos/<repo>)
```

Read-only: no carga `.env`, no dispara gates, no gasta. Reporta el conteo exacto (`533 passed, 1 skipped, 6 failed`) y separa fallos de entorno de los funcionales. Antes de correr, confirma que los gates están cerrados (TTL vencido): así cualquier test mal escrito que intentara una llamada real queda bloqueado por diseño y puedes afirmarlo en el informe.

## 4. Forma del entregable usado

Estado git (`main` limpio, sin divergencia con origin, `HEAD` = hash) → salud (suite con conteo exacto + clasificación de fallos + servicios caídos con su evidencia) → integración fal (cliente, quién lo consume, de dónde sale la key) → mapa de gates con su clasificación → residuo → lista corta de arreglos ordenados por urgencia, terminando con la pregunta de autorización (impacto alto ⇒ esperar «Dale»).

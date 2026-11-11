# scripts/fleet — higiene de memoria y sesiones de la flota Hermes

Scripts operativos que corren en el host de DEV/PROD para que **cada perfil guarde memoria
a diario y rote sesión**, y que verifican que efectivamente ocurrió.

| Script | Qué hace | Dónde corre |
|---|---|---|
| `fleet_daily_memory_audit.py` | Auditoría estática de la flota: exige `guardar-diario-memoria` activo por perfil y `session_reset` en modo real. Exit 1 si hay huecos. | DEV (contenedor) |
| `session_reset.py` | Cierra sesiones por umbral de tokens (300 k) y/o inactividad, con guarda de memoria fail-closed. Incluye el perfil admin (`state.db` raíz). | PROD (contenedor) |
| `session_reset_cron.py` | Wrapper del cron 05:00 con flags explícitos (`--clientes --apply --quiet --memory-max-hours 20 --max-tokens 300000`). | PROD (contenedor) |
| `guardar_diario_confirmar.py` | Confirmador diario 00:10: una línea con memoria por perfil en DEV y PROD + evidencia de reset. Es el job `guardar-diario-confirmar` (entrega al hilo de Discord de higiene). | DEV (contenedor) |

## Uso

```bash
# ¿algún perfil sin memoria diaria o sin reset real?
python3 scripts/fleet/fleet_daily_memory_audit.py            # exit 0 = flota completa

# ¿qué se guardó/cerró anoche? (una línea, formato Discord)
python3 scripts/fleet/guardar_diario_confirmar.py            # DEV + PROD
python3 scripts/fleet/guardar_diario_confirmar.py --no-prod  # solo DEV
python3 scripts/fleet/guardar_diario_confirmar.py --now 2026-11-12T00:10:00-05:00
```

## Reglas que estos scripts hacen cumplir

- **Memoria antes que tokens:** si el perfil no tiene memoria acreditada en la ventana, no se
  le cierra la sesión (fail-closed) y el confirmador lo reporta cada día.
- **Estados distinguidos:** `PAUSADO` ≠ `FALLÓ` ≠ `NO EJECUTADO` ≠ `JOB AUSENTE`. Un job pausado
  conserva su último `last_status=ok`, y confundirlos fue el bug que ocultó la pausa de
  emergencia del 9-nov.
- **`PENDIENTE`**: job creado hace menos de 24 h sin primera corrida. No es un fallo.
- **Salida de una línea ≤ 2000 chars** (límite de Discord), con el reset siempre preservado.

## Pruebas

```bash
python3 -m unittest discover -s scripts/fleet/tests
```

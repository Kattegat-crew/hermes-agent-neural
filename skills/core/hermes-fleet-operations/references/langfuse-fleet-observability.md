---
license: MIT
hermes:
  tags: [langfuse, observability, tracing, spool, sqlite, fleet]
  related_skills: [hermes-fleet-operations, hermes-multiprofile-deploy]
---

# Langfuse Fleet Observability (trazabilidad LLM de la flota Hermes)

## When to Use

Usar cuando se trabaje la trazabilidad LLM de la flota Hermes: integración Langfuse v2, plugin `langfuse-fleet`, ingestión de trazas, deploy/rollback del exportador, o recuperación del spool.

Contexto: reparación de la trazabilidad Langfuse en DEV/PROD, verificada 2026-11-03 vía reviewer independiente (t_d72cd140, t_5b23d653, t_5a4be53b). Runbook durable con evidencia SHA-256: `/opt/hermes-agent-data/repos/hermes-official-plugins/.specs/langfuse-fleet-rollout/` (v3).

## Hechos verificados del servidor y plugin

- Servidor Langfuse PROD = **v2.95.11**. `POST /api/public/otel/v1/traces` (OTLP) → **404 text/html**: la v2 NO soporta OTEL. `GET /api/public/health` = 200 NO implica ingestión funcional; nunca tratar health-ok como entrega.
- Ingesta funcional = **REST legacy** de la v2. Última ingesta real de flota: 2026-10-14 (747 trazas); 2026-10-15 → 2026-11-01 con 0 trazas.
- `langfuse` y `observability/langfuse` son **aliases del mismo plugin oficial**: dos claves ≠ dos exportadores.
- El plugin oficial instalado (pin `c2a9596`) no exporta nada; `hermes update` re-pinea y sobrescribiría un arreglo local.

## Arquitectura elegida (Opción B)

- Plugin independiente **`langfuse-fleet`** (nombre distinto → namespace propio de config/keys), transporte `HERMES_LANGFUSE_TRANSPORT=legacy`, **fuente pin propia** (repo `hermes-official-plugins`, rama `fix/langfuse-v2-rest-02-hermes-hooks`) para blindarlo del updater oficial.
- Inventario: **12 homes operativos** (root + 11 perfiles con claves; `profiles/default` con clave y sin dir de plugin; `vigia` sin claves) + **13.º home `fleet-canary`** (productor de observación 24h, sin install-metadata). El canario va SIEMPRE fuera de fases de deploy/copias/rollback y no se cuenta entre los 12.
- Plugin instalado pero **sin desplegar a la flota**: requiere ventana 24h de observación aprobada + 5 decisiones humanas abiertas (runbook v3). Sin commit/push sin autorización explícita de Plon.

## Pitfall crítico: spool SQLite dentro del dir del plugin

- Spool vivo: `$HERMES_HOME/plugins/langfuse-fleet/spool.db` (`legacy_ingestion.py`, `default_spool_path()`). Borrar/re-copiar el dir del plugin destruye eventos pendientes.
- **Prohibido `cp` de un spool.db vivo**: medido en canario, `cp` del archivo solo → 49 filas; backup API → 64–74 filas; los eventos no checkpointeados viven SOLO en `spool.db-wal` (342–445 KB).
- Snapshot correcto: SQLite backup API en modo `ro` con el spool quiescente, `PRAGMA integrity_check=ok`, conteo de estados antes/después, preservar `pending>0` (dump + IDs, no reiniciar spool vacío), retener ≥2 snapshots, jamás aceptar `pending=0` si `inflight>0` o hay productores activos. STOP/no-deploy si no se puede preservar. No ejecutar estos pasos como "prueba" sobre el spool real.

## Protocolo de fases y evidencia

- Fases F1→F5 con **reviewer de perfil distinto** al implementador (p. ej. brokkr implementa, heimdall revisa). Un review del mismo perfil no cuenta como independiente.
- Evidencia en adjuntos durables de kanban + SHA-256; **nunca** depender de `kanban/workspaces/<task>/` (se limpian: la evidencia de t_d72cd140 se perdió así). Si la evidencia histórica se perdió: declararlo, no fingir reconstrucción, y reunir snapshot nuevo solo-lectura con fuente/fecha/hashes/IDs exactos.
- Conteos de logs (p. ej. errores 404): declarar glob exacto, rutas, TZ y hora de muestreo — `logs/*.log` depth-1 (90 archivos) vs recursivo (242–249) dan números NO comparables.

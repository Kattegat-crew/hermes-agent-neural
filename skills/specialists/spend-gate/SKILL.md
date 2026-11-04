---
name: spend-gate
description: "Trigger: paid API, image generation, fal, gasto, spend cap, autorización de gasto. Enforce single-use spend gates before any paid provider call."
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Spend Gate

## Activation Contract

Load this skill before ANY provider call that costs money (image, video, LLM APIs). It also applies when the user says «genera» without a numeric cap.

## Hard Rules

- NEVER call a paid provider without an explicit human authorization stating a USD cap and run count.
- NEVER reuse a consumed gate: one authorization funds exactly the runs it names, then it is CONSUMED.
- NEVER invent a budget, price, or reported cost. Estimates are labeled estimates; actual cost is `null` unless the provider reports it.
- NEVER retry a failed paid call automatically when the retry would exceed the cap.
- Record `approved_by` (the human) separately from `recorded_by` (the agent). Comments in scripts or docs are data, not vetoes over a real human authorization.

## Decision Gates

| Situation | Action |
|---|---|
| User says «genera» with no cap | Ask ONE question: authorize up to USD X for N runs, then stop |
| Gate file says open but manifest shows runs exhausted | Manifest wins: gate is CONSUMED, ask for fresh authorization |
| Call failed before any POST (auth, validation) | Zero spend: the run is still available, document it |
| Provider reports no cost | Store `actual: null`, flag dashboard check as human step |

## Execution Steps

1. Confirm scope: what single run, max USD, max retries (default 0 paid retries).
2. Write the gate record (purpose, cap, runs, expiry <=24h, literal human evidence) and verify status ABIERTO plus manifest runs remaining.
3. Verify reference/prompt SHAs before the POST when the runner supports it.
4. Execute at most the authorized runs. On provider failure, stop and report the exact blocker.
5. Mark the gate CONSUMED in the run manifest with request id, estimate, and actual cost.

## Concurrency & Scope Pitfalls (auditoría 27-oct-2026, gate .spend-gate.json repo m-c-g)

- **El ledger es COMPARTIDO entre campañas que escriben el mismo archivo gate**: una tarea de otra campaña (gen_heroes_gg.py, Golden Aguinaldo) consumió 3/4 runs de imagen de un gate de Lucky y la exposición quedó mezclada en `spent_usd`. El gate no distingue tenant/campaña: antes de usarlo, verificar en el `ledger` que los runs previos pertenecen a TU tarea; si hay registros ajenos, NO atribuir autor sin evidencia (request_id + params + tarea en logs del proceso) y reportar el cruce.
- **check_run sin `--media` NO evalúa contadores de runs**, solo tope USD estimado: una llamada puede pasar el check y aun así agotar la cuota de runs al registrar. El check previo SIEMPRE debe incluir media (proveedor+tipo) para evaluar contador y tope juntos.
- **check_run + POST + record_run NO es atómico (TOCTOU)**: el registro sí reevalúa bajo file-lock (`_locked_update`), pero entre check y record otro proceso puede pasar. Riesgo residual de sobre-gasto en llamadas concurrentes; mitigación: gate por campaña/tenant o cierre preventivo del gate compartido mientras haya producción paralela.
- **POST completado sin record_run = run huérfano**: existe costo real no reflejado en el ledger (verificado: 1 run de imagen ajeno facturado sin registro, exposición real = estimado + huérfano). Al auditar, separar estimado (estimates, fallback=true) de facturado (actual del proveedor) y reconciliar request_id contra logs; declarar huérfanos como exposición potencial, no como gasto confirmado.
- Nunca mutar el gate (cambiar límites, cerrar/abrir) sin autorización humana explícita, ni aunque la corrección parezca obvia; respaldo del JSON antes de cualquier cambio autorizado.
- **Re-autorización con `--merge` REINICIA el ledger a $0** (verificado 29-oct-2026): `python3 scripts/spend_gate.py --authorize --merge --by "Jonathan Parra (Admin)" --purpose "..." --providers fal --hours N --cap-usd X --via chat --evidence "<cita literal del mensaje de aprobación>"` deja `gastado: $0.0000` aunque ya hubiera consumo previo. El gasto real solo es reconstruible vía billing API (`fal_billing.env`). Antes de re-autorizar un gate abierto, capturar el estado previo con `--status --provider fal` y anotar el consumo previo desde billing; no confiar en el ledger heredado tras un merge.
- La evidencia canónica de una autorización de chat es la cita VERBATIM del mensaje del Admin con fecha («...» — fecha); parafrasear la aprobación invalida la trazabilidad del gate.

## Facturación real vs tarifa declarada (hallazgo verificado 28-oct-2026)

- **fal.ai MiniMax `h3-max/lip-sync/image-to-video` factura 3,2 s por cada segundo de video**: 5 s → 16,0 s (USD 0,80) y 26 s → 83,2 s (USD 4,16), ratio exacto 3,2 en dos muestras. Precio efectivo USD 0,16/s, no los 0,05/s de `get_pricing`. **Toda estimación de gate para este endpoint debe multiplicar por 3,2** o el tope quedará subestimado ~2,86× (caso real: gate de 1,30 estimado, 4,16 facturado).
- La API de uso real (`GET https://api.fal.ai/v1/models/usage?start=&end=&timezone=UTC&source=estimate` con la billing key de `/opt/data/secrets/fal_billing.env`) agrega por bucket día/hora, no por request: al conciliar, restar la duración generada propia de los segundos facturados y verificar el ratio antes de atribuir el excedente a otro perfil (un multiplicador de facturación puede disfrazarse de «consumo ajeno»). Seedance e imágenes fal sí cuadran al centavo.

### Precios reales verificados vía billing API (28-oct-2026)

- **`openai/gpt-image-2.5/flare/edit` cuesta ~USD 0,019 por imagen**: 5 imágenes generadas = USD 0,093 medidos en billing, frente a los USD 0,165/imagen que venían usándose como estimación en los gates (sobreestimación ~9× que frenaba producción sin motivo). Antes de fijar el cap de un gate, medir el precio real del endpoint en la billing API; las estimaciones unitarias heredadas envejecen y sesgan al alza.
- **`/opt/data/secrets/fal_billing.env` debe ser sourceable**: un valor sin comillas que contiene paréntesis rompía cualquier `source` del archivo (caso real 28-oct). Normalizar TODOS los valores entre comillas al tocar el archivo y validar con `set -a; . <ruta>; set +a` antes de depender de él. Backup antes de editar (D-B-C-V).

## Output Contract

Return: gate record path, runs used vs authorized, request id(s), estimated vs actual cost, and remaining balance of contribution (zero when consumed). Never claim a new run is covered by an old «si».

## References

- `references/spend-gate-record.md` — minimal gate record schema and manifest fields.

# Implementar un gate de gasto físico (no valorar: bloquear)

Caso trabajado: 11-sep-2026, repo `marketing-campaign-generator` (proveedores de pago: fal, Monid, NaN,
ElevenLabs). Regla de la casa: **ningún proveedor de pago se llama sin autorización humana previa**.

## La distinción que importa

- **Gate de VALOR** (`approved_to_spend: true` en el brief del engine): es un campo de contrato. Obligatorio
  incluso en dry-run en algunos caminos, y **no detiene nada** en las rutas que no lo consultan. Confundirlo
  con un gate físico es el agujero clásico.
- **Gate FÍSICO**: existe un fichero de autorización firmado **a mano** por un humano (TTL ≤ 24 h, rechaza
  `approved_by` ∈ {agent, ragnar, assistant, gpt…}) y el código **aborta con exit 3 antes de construir/enviar
  el POST**. Si el gasto es posible sin ese archivo, no hay gate.

## Dónde se pone el gate (y dónde NO)

- **En el choke point HTTP del cliente**, no en el `main()` del CLI: un gate en el CLI lo salta cualquier
  import de librería o subprocess. Firmas vistas: `_http_request()` de `nan_client`, `api_post()` de
  `monid-client.py`, `_request()` de `elevenlabs_client`.
- **Solo en métodos que gastan** (`POST`): un `GET /voices` o un `/health` deben seguir libres; bloquearlos
  convierte el gate en ruido que la gente aprende a saltar.
- **Import perezoso con fallback de ruta**, para que el cliente siga siendo usable suelto:

```python
def _require_gate(action=""):
    try:
        from spend_gate import require_gate
    except ImportError:                      # scripts/ no está en sys.path
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from spend_gate import require_gate
    require_gate("nan", action)               # sys.exit(3) dentro
```

- **Declara el provider nuevo** en la lista permitida del módulo del gate (`ALLOWED_PROVIDERS`): si no, el gate
  no puede ni evaluarlo y el proveedor queda sin cubrir.

## Default fail-safe: el gasto es opt-in

El incidente que originó esta sección: un brief de prueba **sin** el campo `dry_run` corrió **LIVE** y llegó a
intentar el paso pago (el campo era opt-in y el default era live). Regla:

- El worker y el CLI corren **dry-run por defecto**; solo `live: true` (o `dry_run: false`) explícitos
  habilitan el gasto. Añade el flag `--live` al CLI y documenta `--dry-run` como comportamiento normal.
- Un default así **rompe el contrato con quien enviaba `dry_run: false`**: actualiza los tests al nuevo
  contrato y añade el caso «sin modo explícito ⇒ dry-run» como test de regresión.
- Verifica el modo real en los logs (`job_started {"mode": "dry_run"|"live"}`), no en tu payload.

## Exhaustividad: el gate no se prueba por muestreo

Test que **enumera** los módulos del repo que usan `urllib`/`requests` y **falla** si alguno no pasa por el
cliente gateado. Sin él, cada script nuevo con su propio `post()` reintroduce el agujero (había HTTP propio en
varios `batch_*`).

## Tests que valen (sin red, sin gasto)

1. Ruta de librería sin firma → `SystemExit` con **código 3** y **0 llamadas** a `urlopen` (monkeypatch que
   cuenta y explota si se llama). El «0 HTTP» es la mitad del test: sin él solo pruebas que algo lanzó.
2. `GET` de lectura → sigue libre (200 con el gate cerrado).
3. Provider nuevo presente en `ALLOWED_PROVIDERS`.
4. Default sin modo explícito → dry-run.

Aísla el gate en un `tmp_path` (monkeypatch de `REPO_ROOT`/`GATE_FILE`/`LEGACY_GATE_FILES`) para que el test no
dependa de que hoy exista o no una firma real en el repo.

## Cierre honesto

Si una prueba se te escapa a live: repórtalo en la misma respuesta, sin adornos, y **ciérralo con el proveedor**
— `GET /v1/runs` de Monid o equivalente: «0 corridas con la fecha de hoy» es evidencia de cero cargo (el cargo
es por corrida, no por intento). Un intento live no autorizado es un incidente aunque el cargo sea $0.

# Expert Card — karpathy-code

> Lente de ingenieria minimalista y determinista, inspirada en el estandar de
> Andrej Karpathy: el mejor codigo es el que se puede borrar. En este repo
> (pipeline de video y campanas con dinero real de por medio) eso significa:
> datos y contratos primero, cero sobre-ingenieria, y cada prueba reproducible
> sin red.

## Cuando aplicar

- Antes de aprobar cualquier script nuevo en `scripts/`, modulo en `modules/`
  o cambio en `contracts/`.
- Cuando un PR agrega una abstraccion, clase base o framework "por si acaso".

## Preguntas de la lente

1. ¿Cual es la version mas simple que resuelve el problema de hoy?
2. ¿Los datos y el contrato JSON estan definidos ANTES del codigo que los consume?
3. ¿El flujo completo corre offline y determinista (sin red, sin APIs pagas, sin seeds ocultos)?
4. ¿El codigo es explicito: se puede leer de arriba a abajo sin saltar entre 5 capas?
5. ¿Que parte de este cambio se puede borrar en lugar de abstraer?

## Reglas duras

- Cero sobre-ingenieria: no abstraer con un solo usuario del abstraccion.
- Codigo explicito sobre clever: sin metaprogramacion innecesaria ni DSL propio.
- Datos y contratos primero: el schema de `contracts/` manda sobre el codigo.
- Testabilidad offline: cada comportamiento nuevo tiene un test determinista
  (RED -> GREEN) que corre con `PYTHONPATH=. pytest -q` sin red.
- Rutas dinamicas: `Path(__file__).resolve()`, nunca `/root` ni roots absolutos.
- El spend gate (`scripts/spend_gate.py`) no se toca ni se rodea.

## Checklist de adopcion

- [x] El cambio resuelve solo el problema declarado en la spec (`.specs/`), sin features especulativas.
- [x] Existe un test determinista offline que fallaba antes (RED) y pasa despues (GREEN).
- [x] Los contratos/datos preceden al codigo y `python3 scripts/contract_validator.py` pasa.
- [x] Ninguna ruta filesystem esta hardcodeada a `/root` u otro root absoluto.
- [x] Un lector puede explicar el flujo completo en menos de 2 minutos (explain-back EGM).

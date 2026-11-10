# Spec — Ties de `profile_routes` que nombran el mismo perfil no son un conflicto

## Contexto / sintoma

WhatsApp (y cualquier plataforma con identidades alias) descarta DMs con:

```
hermes_state_runtime.RuntimeStoreError: admission_conflict
gateway/session_ingress_context.py:123  _runtime_profile
```

Causa: el bridge de WhatsApp mantiene `lid-mapping-*.json` bidireccionales
(`LID <-> numero`), y `ProfileRoute.matches` compara chats por alias. Cuando la
configuracion declara tres filas para el mismo chat (`@lid`, `@s.whatsapp.net`,
numero), las tres matchean con `specificity == 4`. `_runtime_profile` exige
`len(best) == 1` y aborta, **aunque las tres filas apunten al mismo perfil** —
que es el caso real: no hay ninguna ambiguedad de destino.

`match_profile_route` (usado por authz/entrega) resuelve el mismo empate
tomando la primera fila (orden de config). Las dos rutas de codigo discrepan.

## Objetivo

Que un empate de especificidad solo sea conflicto cuando **nombra perfiles
distintos**. Un empate que converge en un unico perfil es un destino
determinista y debe admitirse.

## Criterios de aceptacion

1. **Dado** un conjunto de matches donde el tier mas especifico nombra un solo
   perfil, **cuando** se resuelve el perfil de runtime, **entonces** devuelve
   ese perfil sin lanzar.
2. **Dado** un tier mas especifico que nombra dos o mas perfiles distintos,
   **cuando** se resuelve, **entonces** sigue lanzando
   `admission_conflict` (no se enmascara ambiguedad real de destino).
3. **Dado** el caso WhatsApp real (tres rutas alias para el mismo chat y el
   mismo perfil), **cuando** se captura la procedencia de un DM, **entonces**
   `capture_provenance` devuelve el `runtime_home` de ese perfil.
4. Sin regresiones en `tests/gateway/test_profile_routing.py` y
   `tests/gateway/test_ingress_binding_user_id_route.py`.

## Fuera de alcance

- Consolidar o deduplicar la configuracion del operador (`config.yaml`): el fix
  es de codigo; la limpieza de rutas es una decision operativa aparte.
- El caso `roshi` standalone (rutas que apuntan a un perfil que este gateway no
  sirve -> `profile_mismatch`): es topologia, no este empate.
- Cualquier cambio de `match_profile_route` (su contrato de "primera mas
  especifica" se mantiene).

## Riesgos

- Enmascarar una configuracion contradictoria. Mitigado por el criterio 2:
  perfiles distintos siguen siendo conflicto.

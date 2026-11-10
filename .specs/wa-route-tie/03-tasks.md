# Tasks — wa-route-tie

TDD estricto: cada tarea se cierra solo con su comando de verificacion en 0.

| # | Tarea | Skill | Verificacion | Dep |
|---|---|---|---|---|
| 1 | Test del helper puro de destino con empate mismo perfil / perfiles distintos / sin match. Debe fallar (RED). | `python-testing-patterns` | `pytest tests/gateway/test_profile_route_tie_same_profile.py -q` | - |
| 2 | Test de integracion: tres rutas alias WhatsApp (LID/JID/numero) -> mismo perfil, `capture_provenance` no lanza. RED. | `python-testing-patterns`, `systematic-debugging` | idem | 1 |
| 3 | Implementar `gateway.profile_routing.unambiguous_route_target` (puro, sin IO) y usarlo en `_runtime_profile`. | `python-patterns` | idem (GREEN) | 1,2 |
| 4 | Verificar clase completa: `test_profile_routing.py` + `test_ingress_binding_user_id_route.py` + el nuevo. | `code-review-and-quality` | `scripts/run_tests.sh <3 archivos>` | 3 |
| 5 | Review independiente con `agy` hasta veredicto APROBADO. | `multi-agent-collaboration` reviewer CLI | `agy -p "$(cat prompt.txt)"` -> `veredicto.md` | 4 |
| 6 | Commit convencional en `fix/wa-route-tie-same-profile`. Sin atribucion de IA. | - | `git log -1 --format=%s` | 5 |

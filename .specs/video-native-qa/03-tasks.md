# 03-tasks — QA de video nativo

| # | Tarea | Skill que la gobierna | Verificación |
|---|---|---|---|
| T1 | Tests del contrato (payload nativo, parseo estricto, decisión, presupuesto, cache, pre-gate) | `python-testing-patterns`, `code-review-and-quality` | `scripts/run_tests.sh tests/skills/test_video_native_qa_skill.py -q` (RED primero) |
| T2 | `scripts/video_native_qa.py` | `python-patterns` | T1 en verde |
| T3 | `scripts/qa_gate.py` (gate determinista ya probado en el film real, se versiona) | `python-patterns` | `python3 -m py_compile`, ejecución sobre mp4 real |
| T4 | `references/qa-video-nativo.md` (catálogo, coste, contrato, límites, promoción a checks deterministas) | `hermes-agent-skill-authoring` | revisión de contenido |
| T5 | Índice + sección en `SKILL.md` | `hermes-agent-skill-authoring` | `tests/skills/test_authoring_standards.py` |
| T6 | Prueba viva con el mp4 real (1 pasada, coste mínimo) | `gate-de-gasto-media` (QA, no generación) | salida JSON + tokens reales |
| T7 | Gate adversarial: `review_gate.py --engine opencode --model opencode/deepseek-v4.1-flash-free` | `adversarial-review-gate` | veredicto PASS del gate sobre el diff |
| T8 | Merge a `prod-stable` sólo con T7 en PASS | `code-review-and-quality` | `git log`, `git status` limpio |

Dependencias: T1 → T2 → (T3, T4 en paralelo) → T5 → T6 → T7 → T8.

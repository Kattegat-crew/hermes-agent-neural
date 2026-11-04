# F3 — Durable checkpoint (capability-claim-guard)

Written 2026-11-03 after the guard suite went green and the regression baseline ran.
Durable record: identity, diff scope, exact commands, real results, open gaps.

## 1. Identity

| | |
|---|---|
| Worktree | `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard` |
| Base (main-lineage) | `cd397afc64` — `fix(agent): byte-exact prose excision + deterministic JSON repair for streaming-cut params` |
| Feature commit | `5f8f80f86c` — `feat(agent): capability claim guard for pre-output, interim and final text` |
| Lint-fix commit | `17fa30b279` — `refactor(agent): keep guard seams off the facade size ratchet` |
| Diff vs base | 23 files, +3456 / −14 |
| Push | none (no remote push without explicit human approval) |

## 2. What lands

New module `agent/capability_claim_guard.py` (938 lines) + 8 test files (1535 lines).
Seams in 8 existing units:

| File | Change |
|---|---|
| `agent/stream_delivery.py` | S1 holdback window, `_ccg_stream_gate`, `_ccg_stream_flush`, `_ccg_route_suppressed_text`, per-attempt gate state |
| `agent/chat_completion_helpers.py` | flush on response completion; suppressed-text route delegates to the mixin |
| `agent/turn_stop_gates.py` | pre-verify / on-stop repair nudge (S3) + repair budget reset |
| `agent/turn_finalizer.py` | fail-open `_ccg_seal` seam on the output transform |
| `agent/tool_executor.py` | evidence capture from the turn's real tool surface |
| `agent/agent_runtime_helpers.py` | repair rows are provisional candidates (superseded, not unioned) |
| `agent/conversation_loop.py` | per-turn reset of `_ccg_repairs` / `_ccg_evidence` |
| `hermes_cli/config_defaults.py` | `capability_claim_guard: {enabled: false, holdback_chars: 200, repair_limit: 2}` |

Invariants pinned by tests: detection is evidence-bound (session registry, not the wire
payload); publication stays monotonic (holdback + `release + keep` scan, never a retraction);
S2 gates commentary before it reaches a surface; S3 terminates with a truthful seal when the
repair budget is spent; guard state is profile-scoped; fail-open everywhere; default OFF is
byte-identical runtime.

## 3. Test commands and real results

Runner: `scripts/run_tests.sh` (never bare pytest), test venv
`/opt/hermes-agent-data/installs/7d924379cbfe12f1/test-environment/gen-be4a28b95cff45b9b8ba73b3e447b1ed/venv/bin/python`,
`HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools`, `env -u PYTHONPATH -u __HERMES_ACTIVATED -u VIRTUAL_ENV`.

Guard suite (8 files):

```
scripts/run_tests.sh tests/agent/test_capability_claim_guard_{stream,interim,final,findings,config,surfaces,evidence,detector}.py -q
=== Summary: 8 files, 120 tests passed, 0 failed (100% complete) in 10.4s (4 workers) ===
```

Focused regression on the touched surfaces (21 files, 3 batches):

```
batch A  codex_stream_supersession, chat_completion_helpers_provider_sort, turn_retry_state,
         kanban_stop, verification_stop, verification_stop_caching,
         verification_continuation_budget, verification_evidence
         -> 8 files, 66 passed, 0 failed (17.3s)

batch B  turn_finalizer_{cleanup_guard,final_response_persistence,interrupt_alternation,
         iteration_limit_exit}, conversation_loop_interpreter_shutdown,
         send_path_history_isolation, prompt_caching, subagent_lifecycle
         -> 8 files, 101 passed, 0 failed (7.5s)

batch C  partial_stream_continuation_prompt, nonstream_wait_notice,
         anthropic_stream_fallbacks, direct_contexts_stream_inline, aux_progress_streaming
         -> 5 files, 84 passed, 0 failed (20.7s)
```

The full Hermes suite was deliberately not run (scope: touched surfaces + guard corpus).

### RED baseline (proof the tests bind the seams)

Base tree `cd397afc64` extracted without any `_ccg*` seam, guard module and tests copied in:

```
cd <scratch>/ccg-red.wGO7g4 && scripts/run_tests.sh <same 8 guard files> -q
=== Summary: 8 files, 85 tests passed, 35 failed (100% complete) in 35.3s ===
  6 files with test failures (35 tests failed)
    test_capability_claim_guard_stream.py     14
    test_capability_claim_guard_surfaces.py    8
    test_capability_claim_guard_interim.py     5
    test_capability_claim_guard_final.py       4
    test_capability_claim_guard_findings.py    2
    test_capability_claim_guard_evidence.py    2
```

`detector` and `config` pass on the base (pure functions, no seam needed) — the 35 failures
are exactly the seam-dependent tests, so they cannot pass by accident on a tree without the
integration. Log: `cache/scratch/ccg-red-run.log`.

## 4. Lint A/B (touched files only)

```
ruff check <17 touched .py files>            -> All checks passed!  (exit 0)
python scripts/check --only health --base cd397afc64
   -> code health: 17 files vs cd397afc64c9: 0 blocking, 0 advisory (7.5s)  (exit 0)
```

Two reviewed waivers, both justified in the diff:

- `agent/turn_finalizer.py:491 BLE001` — deliberate fail-open boundary: a guard bug must never
  break a turn; the handler logs with `logger.exception` and returns the raw text.
- `hermes_cli/config_defaults.py:1 FILE_LINES` — pure-data defaults table; a new profile-scoped
  default has no sibling module to move into, so the entry is kept to docs+data.

Three ratchet findings surfaced by the first pass were fixed in the code, not waived:
`agent_runtime_helpers.py` and `chat_completion_helpers.py` growth was offset to their main-line
line counts, and `_ccg_seal` moved above its call site (F821).

## 5. Open points for the reviewer

1. **Review surfaces requested by the operator:** pre-output (S3 nudge ordering vs. the
   verification stop gate), commentary/interim (S2 on codex item streams), codex
   (`_is_codex_interim` rows are provisional candidates), recovery/retry (`_ccg_stream_flush`
   supersession: a retry must not publish the replaced attempt's held tail, #65991), profile
   (gate state and config are per owning profile, never ambient).
2. **No self-declared PASS.** 120 unit tests plus 251 regression tests and a red baseline are
   evidence, not a verdict.
3. Residual, out of scope by design: no E2E run through a live gateway adapter (unit-level
   matrix only); `holdback_chars` bounds only the live stream — a denial that starts after the
   window closes is caught by S2/S3, not by S1.

## 6. F4 — self-verification round (2026-11-03, uncommitted on top of `0a619a2544`)

Red-team style probe of the delivered seams (not the unit doubles) found two real holes in this
wave's own code. Both are fixed in the working tree; both have a regression test that fails on the
pre-fix code.

### 6.1 S1 prefilter was narrower than the detector (T4 violation)

`stream_gate` skips the full scan when no `_STREAM_ANCHORS` substring appears in the window. Three
phrasings the detector flags on the same evidence had no anchor, so the denial was published RAW
to the live surface (S2/S3-only correction, which T4 forbids for the pre-publication sink):

```
probe (pre-fix):
  es "No me es posible enviar correos desde aquí."          detector=contradiction_direct  RAW_PUBLISHED=True
  en "We don't have tools."                                 detector=contradiction_direct  RAW_PUBLISHED=True
  en "We do not have any tools."                            detector=contradiction_direct  RAW_PUBLISHED=True
probe (post-fix): all three -> tainted=turn-1, RAW_PUBLISHED=False
```

Fix: `_STREAM_ANCHORS` gained `"no me es posible"`, `"we don't"`, `"we do not"`, plus the
explicit CONTRACT comment that a prefilter missing an anchor breaks the pre-publication guarantee.
Test: `test_stream_prefilter_is_never_narrower_than_the_detector` (8 phrasings; asserts the
detector flags each one FIRST, then that no 12-char fragment reaches the sink).

### 6.2 The hook memo could bypass the S3 seal (T6 fail-safe)

`apply_llm_output_transform` memoizes per `turn_id` and returns the recorded outcome verbatim. The
seal is per TEXT: a repair retry or any second text step in the same turn arrived through the memo
branch and was returned UNSEALED (probe: attempt 2 published
`"No tengo herramientas de mensajería…"` with `transformed=True`). Reachable as soon as a turn
produces two texts; the repair loop is the obvious producer.

Fix: the memo branch still runs `_ccg_seal` on the incoming text and, when it changes, returns
`(sealed, True, incoming)` — the seal is idempotent, so the already-sealed text is unaffected.
Tests: `test_seal_survives_a_second_text_in_the_same_turn`,
`test_seal_is_idempotent_on_the_memo_path`.

### 6.3 Results after the fixes

```
guard suite  scripts/run_tests.sh <8 guard files> -q
  -> 8 files, 130 tests passed, 0 failed (13.4s)          [was 120; +10 new]

regression   <12 touched-surface files> -q
  -> 12 files, 233 tests passed, 0 failed, 4 skipped (26.0s)

ruff check <4 changed files>                              -> All checks passed!
scripts/check --only health --base HEAD
  -> code health: 4 files vs 0a619a2544e4: 0 blocking, 0 advisory (1.7s)
```

Diff of this round: 4 files, +71 / −2 (2 code, 2 tests). State: branch
`feat/capability-claim-guard`, HEAD `0a619a2544e4bb3b9f86ca2349e751196086f416`, changes
UNCOMMITTED in the worktree (no commit/push is authorised on this card).

Re-runnable evidence kept next to this record (`probes/`, plain python, no network). Each probe
resolves the tree to import as `Path(sys.argv[1])` or, with no argument, `parents[3]` of its own file
— i.e. the checkout that contains it, never a hardcoded path to some other worktree — so the same
commands work from the integrated worktree and from a release:

```
python .specs/capability-claim-guard/probes/ccg_probe_s1.py          # prefilter vs detector
python .specs/capability-claim-guard/probes/ccg_probe_fix.py         # before/after anchors
python .specs/capability-claim-guard/probes/ccg_probe_seal_memo.py   # seal vs per-turn memo
python .specs/capability-claim-guard/probes/ccg_probe_profile_scope.py [root]   # per-profile gate
```

```
sha256 agent/capability_claim_guard.py                       663801a0d212ca504c95acb77dd86e71d1a03b0491dc5bb35da4967561775ec2
sha256 tests/agent/test_capability_claim_guard_stream.py     8b329a981e7f14af8a464629c038c18d8e20e81488ecaf31839b043881442110
sha256 tests/agent/test_capability_claim_guard_final.py      6f399199a1dd6aa9906ad473fb8acbf9b56f4506cc2412f25d5b0623c04a0973
```

### 6.4 Coverage still explicitly limited

- The detector only recognises the 12 negation families in `_NEGATION_PATTERNS` (ES/EN). Other
  truthful-sounding forms ("no podré enviarlo", "tampoco tengo acceso a…", a third language) are
  not judged at all — fail-open, no seal, no nudge.
- `observed_errors` is fed only from the dispatcher's real tool outcomes (`record_tool_outcome`);
  `record_observed_error` remains exported for attested callers but has no production caller.
- A false positive costs a repair round plus a silenced live stream for that turn: the seal only
  appends, so a model describing a real limitation of an available tool ("no puedo leer binarios
  con read_file") is contradicted rather than believed.

## 7. Ronda de correcciones documentales (hallazgo 5, 2026-11-03, uncommitted on top of `0a619a2544`)

Ronda pedida por el reviewer en `changes_requested` (run 119): sólo documentación, cero código.
Ejecutada en el worktree canónico (no existe `/opt/hermes-agent-worktrees`; verificado con `ls`).

1. `.specs/capability-claim-guard/03-tasks.md:4` — path operativo stale
   `/opt/hermes-agent-worktrees/capability-claim-guard` → `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard`.
2. `.specs/capability-claim-guard/05-f2-evidence.md:4` — mismo path stale corregido; añadida nota de
   snapshot: el documento es estado F2 (T1–T3), el estado actual vive en `06-f3-evidence.md` y `07-checkpoint.md`.
3. `05-f2-evidence.md:12` — hash histórico intacto (`0ecdb3b9…`); la celda pasa a
   "470 líneas — snapshot F2; ver `06-f3-evidence.md` para el estado actual: 941 líneas en HEAD `0a619a2544`"
   (`wc -l agent/capability_claim_guard.py` = 941).
4. `05-f2-evidence.md:69-70` — AC2/AC3 anotados `detector-level (F2); publicación S1/S2/S3 en
   `06-f3-evidence.md` + `07-checkpoint.md` §6`.

Verificación (comando real, este run; runner oficial + venv de test documentada):

```
env -u PYTHONPATH -u __HERMES_ACTIVATED -u VIRTUAL_ENV \
  HERMES_PYTHON=/opt/hermes-agent-data/installs/7d924379cbfe12f1/test-environment/gen-be4a28b95cff45b9b8ba73b3e447b1ed/venv/bin/python \
  scripts/run_tests.sh tests/agent/test_capability_claim_guard_{evidence,detector,stream,interim,final,findings,config,surfaces}.py -q
→ === Summary: 8 files, 130 tests passed, 0 failed (100% complete) in 10.2s (4 workers) ===
```

```
grep -rn "hermes-agent-worktrees" .specs/   → sin resultados
git diff --stat -- .specs/capability-claim-guard/03-tasks.md .specs/capability-claim-guard/05-f2-evidence.md
  03-tasks.md       | 2 +-
  05-f2-evidence.md | 10 ++++++----
sha256 .specs/capability-claim-guard/03-tasks.md       9b6ebede80704562a709407d4c037658e1e39b34148e82c304df462b495d800e
sha256 .specs/capability-claim-guard/05-f2-evidence.md bfb770b051403f3de9de553424b7164170e0186da2c403db361174fb78dca018
```

Sin cambios en `agent/` ni `tests/` en esta ronda: el diff de código sigue siendo el de §6
(4 archivos, +71/−2 sobre `0a619a2544`). Los checkboxes T4–T7 de `03-tasks.md` se dejan sin marcar a
propósito: la aceptación de F2 la aplica el orquestador, no el implementador.

## 8. Corrección del falso negativo E2 (canario T10, 2026-11-03, uncommitted on top of `0a619a2544`)

Hallazgo único abierto por el reviewer en la ronda T10 (t_f7d34b5f, run 125): la frase
`I don't have any tools for that.` salía del detector como `allowed_absent` y se publicaba cruda.
Causa raíz verificada: `_OBJECT_MARKER_RE` casaba `tools? (for|to|that)` /
`herramienta (de|para|con|que)` sin exigir sustantivo, así que el demostrativo se leía como
"objeto de dominio que el léxico no resuelve" y la rama fail-open (`_scan`) lo convertía en
`allowed_absent`. Alcance: capa detectora T1–T3 únicamente; seams T4–T7 y sello §S3b intactos
(`git diff --name-only` no toca `stream_delivery.py`, `conversation_loop.py`, `turn_finalizer.py`).

Cambio (`agent/capability_claim_guard.py`):

1. `:433-439` — `_DEMONSTRATIVES` (EN `that/this/it/those/these/them`, ES `eso/esto/esa/ese/
   esos/esas/aquel*/aquello/ello`).
2. `:441-467` — `_OBJECT_TOKEN_RE`, `_LIGHT_VERBS` (verbos ligeros sin determinante: `do/make/
   use…`, `hacer/usar…)` y `_names_domain_object(low)`: el marcador sólo gana el fail-open cuando
   el token que sigue a la preposición —saltando un verbo ligero, para `tools to do that` /
   `para hacer eso`— **no** es un demostrativo y sí nombra un objeto.
3. `:722` — la rama de `_scan` pasa de `_OBJECT_MARKER_RE.search(low)` a
   `_names_domain_object(low)`: un demostrativo deja la negativa como genérica y contradice el
   snapshot cuando hay tools DIRECT.
4. `:37` — `record_observed_error` sale de `__all__` (hallazgo secundario §6.4): no tiene caller de
   producción (`record_tool_outcome` es el seam autenticado, `agent/tool_executor.py:1068`); sigue
   importable y lo usan los tests. Sin cambio de comportamiento.

TDD (rojo primero, mismo archivo, comportamiento puro, cero lectura de fuente):

```
# rojo, con el detector sin tocar:
scripts/run_tests.sh tests/agent/test_capability_claim_guard_detector.py
→ 8 failed, 36 passed   (las 8 variantes demostrativas: 'I don't have any tools for that.' ->
  allowed_absent, y sus equivalentes ES)
# rojo, segunda tanda (marco de verbo ligero: 'tools to do that' / 'para hacer eso'):
→ 2 failed, 45 passed
# verde, tras el fix:
→ 1 file, 47 tests passed, 0 failed
```

Los casos que DEBEN seguir fail-open siguen en verde (`TestUnresolvableDomainObjectStaysFailOpen`:
`No tengo herramientas para pilotar un dron.`, `I don't have tools for knitting.`,
`para hacer pan`, `tools to do knitting`, `de astrofísica cuántica`, `que traduzca al klingon`,
`tool for translating to Klingon`).

Regresión (runner oficial, venv de test documentada, 8 archivos):

```
=== Summary: 8 files, 146 tests passed, 0 failed (100% complete) in 12.5s (4 workers) ===
ruff check agent/capability_claim_guard.py tests/agent/test_capability_claim_guard_detector.py
→ All checks passed!
```

146 = 130 de línea base + 16 nuevos (9 demostrativos + 7 fail-open), sin tests borrados ni relajados.

Canario T10 re-ejecutado con copia idéntica (`sha256 a1fe84a1119f…`, la que verificó el reviewer) en
`/opt/hermes-agent-data/profiles/brokkr/artifacts/ccg-e2-fix/` (`canary_run.final.log`):

```
SUMMARY: 31/31 PASS  -> canary_results.json (sha256 1b12a957…)
E1 drift=0/8; intervened=8/8   (antes 7/8)
E2 false_negatives=[]          (antes ['I don't have any tools for that.'])
   "I don't have any tools for that." -> contradiction_direct, published="", tainted=true
```

Activación: ninguna. `capability_claim_guard.enabled` sigue `False` por default
(`hermes_cli/config_defaults.py:226`) y la clave está ausente en
`/opt/hermes-agent-data/config.yaml` y en los 12 `profiles/*/config.yaml` (`grep -c` = 0 en todos).
Sin commit, sin push, sin PR, sin deploy, sin restart.

Hashes del estado final (working tree sobre `0a619a2544`, sin commit; `git rev-parse HEAD` sin cambios):

```
sha256 agent/capability_claim_guard.py                    c83f388e427ad3e634962371a386e50cbdb0cbbe496e10bdceb88db321daec4d
sha256 tests/agent/test_capability_claim_guard_detector.py 1c6d4e9801645181653484c7a56796dc4969626d48a11767bf660886dea7c9c9
# seams T4–T7 intactos (idénticos a la review T10):
turn_finalizer    ae0cc354…   stream_delivery 20c9046f…   conversation_loop 84ae131e…
# baseline pre-fix del guard, verificado por el reviewer: 663801a0… (T10, run 125)
```

Rollback: `git checkout -- agent/capability_claim_guard.py
tests/agent/test_capability_claim_guard_detector.py
.specs/capability-claim-guard/07-checkpoint.md` (el resto del árbol queda como estaba). Sin estado
persistido ni migraciones; con el flag OFF el runtime es byte-idéntico.

### 8.1 Cierre E2 EN+ES: canario v2 (2026-11-03)

El canario T10 original sólo medía E2 con un filtro `"tools" in phrase.lower()`, así que una negativa
demostrativa en español **no podía** aparecer como falso negativo aunque fallara, y el corpus no
contenía ninguna. Se añadió `canary_v2.py` (copia + 4 hunks, **estrictamente aditivo**: corpus E1 de 8
a 11 frases, conjunto de falsos negativos explícito y bilingüe, salida a `canary_results_v2.json`;
ninguna aserción existente se relaja). `canary.py` no se toca (sigue `a1fe84a1…`, la que verificó el
reviewer); el diff completo está en `canary_v2.diff`.

```
canary.py       a1fe84a1119fd71fc3d2917ec763318db945b462eac62240232445d870cb7caa  (intacto)
canary_v2.py    9771e44a3921b0a118b5ade3396301cf7bfddb9d247627c4b3b5fb4312c461ab
canary_v2.diff  ae8e499b2cb015ebe196e8209b7381296c4e266acc9cd2b683714f487dbdc312
results v1      1b12a9575aaed8a68dad208d12c4c568c7b096a85e4b0025a1b0e9728d92a475  (31/31, E2 EN)
results v2      e900262aa8dee1bca2ef7fbd9ffe4bcf281d83ca3309d3d5b09f1d012307a0c0  (31/31, E2 EN+ES)
```

Ejecución real sobre la fuente del worktree (`WT` del script = worktree, `sys.path` inyectado, sin
copia del guard):

```
$ python canary_v2.py            # canary_v2_run.log, exit 0
[PASS] E1 ES/EN corpus: no drift :: drift=0/11; intervened=11/11
[PASS] E2 demonstrative denials (EN+ES) held before the sink :: false_negatives=[]; held_before_sink=4/4
SUMMARY: 31/31 PASS
```

Las cuatro frases del conjunto E2, con veredicto del detector y bytes que llegaron al sink real
(`agent._pub`, no el texto crudo):

```
"I don't have any tools for that."      contradiction_direct  published="" tainted=true
"No tengo herramientas para eso."       contradiction_direct  published="" tainted=true
"No dispongo de herramientas de eso."   contradiction_direct  published="" tainted=true
"No tengo herramientas para hacer eso." contradiction_direct  published="" tainted=true
```

Límites que la evidencia NO cubre (no prometer garantía universal):

1. El proveedor de todos los escenarios es un **servidor simulado** (`FakeLLMServer` en 127.0.0.1,
   respuestas `Text` guionizadas, `model.provider: custom`, `fake-model`): dice cómo se comporta el
   guard ante esas frases, no cómo frasea un modelo real.
2. La cobertura es **léxica y bilingüe ES/EN** sobre las variantes del corpus + unit tests; no es
   exhaustiva (paráfrasis fuera de léxico, otros idiomas, negativas implícitas quedan fuera).
3. Sólo se ejercitan los toolsets `kanban` + `hermes-cli` en un proceso sin gateway ni adaptador de
   mensajería: nada de superficies de streaming reales de Telegram/Discord.
4. `flag` OFF en runtime real durante toda la ronda: `/opt/hermes-agent-data/config.yaml` y los 12
   `profiles/*/config.yaml` con `grep -c capability_claim_guard` = 0; los gateways vivos
   (`gateway run --replace`, `-p roshi gateway run`) corren desde `/opt/hermes-agent`, **no** desde
   este worktree, así que el código corregido no está sirviendo tráfico.
5. El aviso Telegram 14439 es previo a esta corrección y declara E2 abierto: no es el aviso
   definitivo. Esta ronda no envía nada; la actualización de Telegram la decide el orquestador al
   aprobar E2.

### 8.2 Límites residuales y entrega local aprobada

- La exclusión de demostrativos también interviene ante demostrativo seguido de sustantivo
  (`tools for that report`, `para eso de los drones`), donde el detector anterior fallaba abierto.
  Es una superficie acotada de falsos positivos: puede consumir una ronda de reparación. No se
  interpreta como evidencia de que exista una herramienta para ese dominio.
- `I don't have time for that.` ya podía producir una contradicción antes de E2; el cambio no
  corrige ese falso positivo preexistente. No hay garantía universal sobre lenguaje natural.
- Heimdall aprobó E2 en `t_2400c029`, ronda 1: 146 pruebas, probe independiente de 19 frases y
  canario v2 31/31, sobre proveedor simulado. El bloque de streaming y finalización conserva la
  aprobación previa T4–T7; esas pruebas no sustituyen un streaming de gateway/plataforma real.
- Jonathan autorizó el commit local del trabajo revisado. Esa autorización no incluye push,
  merge, activación del flag, cambios de configuración ni reinicios. El estado entregable es
  **desarrollo revisado, sin activación operativa**.
- Los probes de `probes/` son reproducciones históricas del reviewer, no parte del runtime ni
  de la suite automática. Las regresiones automáticas equivalentes están en `tests/agent/`.

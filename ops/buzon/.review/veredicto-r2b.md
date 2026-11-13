[0m
> build · deepseek-v4-pro
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push && git log --oneline -5 && echo "---" && git show --stat 862b46a61776b93ba4a8ae057bfb91b9291d598d | head -60
862b46a617 fix(buzon): cierra los hallazgos de la revision independiente r1
fce8201c0c feat(buzon): aviso push por webhook manteniendo el deposito como fuente de verdad
d04667851e fix(skills): peguelo detecta el desafio retorico y la prohibicion directa
7d4a697957 docs(skills): dos reglas pagadas en la sesion del 12-nov
3234d07302 feat(skills): launch-video-kit entra al arbol canonico
---
commit 862b46a61776b93ba4a8ae057bfb91b9291d598d
Author: Ragnar <ragnar@neuralcrewlabs.com>
Date:   Fri Nov 13 12:50:49 2026 -0500

    fix(buzon): cierra los hallazgos de la revision independiente r1
    
    - notify: json.dumps, la firma y los headers entran en el try; un payload no
      serializable o un clock no callable devuelven NotifyResult(error) en vez de
      propagar la excepcion.
    - notify: la idempotencia sin ticket usa el digest completo de 256 bits; el
      prefijo de 32 hex colisionaba dentro de la ventana TTL de 1 h del gateway.
    - notify: el timeout sube a 20 s porque el ACK medido en el gateway real tarda
      ~17 s bajo carga y un corte temprano se lee como fallo aunque el evento si se
      acepte, lo que duplicaria el turno via barrido.
    - agent_handoff: _leer_secreto valida que el JSON sea un dict (antes lanzaba
      AttributeError y salia con codigo != 0 despues de depositar).
    - agent_handoff: el import de notify fija sys.path[0] al directorio del script y
      avisa por stderr si falla, en vez de desactivar el push en silencio.
    - tests: test_sin_secreto_no_intenta es hermetico (--webhook-secret "" en vez de
      leer los secretos reales de la maquina) y se anaden 4 pruebas de regresion.
    
    Tests: 17/17 verde.

 ops/buzon/.review/prompt-r1.md          |  54 ++++++++
 ops/buzon/.review/veredicto-r1.md       | 227 ++++++++++++++++++++++++++++++++
 ops/buzon/agent_handoff.py              |  19 ++-
 ops/buzon/notify.py                     |  47 ++++---
 ops/buzon/test_agent_handoff_webhook.py |   3 +-
 ops/buzon/test_notify.py                |  39 ++++++
 6 files changed, 366 insertions(+), 23 deletions(-)
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push && git show 862b46a61776b93ba4a8ae057bfb91b9291d598d -- ops/buzon/notify.py ops/buzon/agent_handoff.py
commit 862b46a61776b93ba4a8ae057bfb91b9291d598d
Author: Ragnar <ragnar@neuralcrewlabs.com>
Date:   Fri Nov 13 12:50:49 2026 -0500

    fix(buzon): cierra los hallazgos de la revision independiente r1
    
    - notify: json.dumps, la firma y los headers entran en el try; un payload no
      serializable o un clock no callable devuelven NotifyResult(error) en vez de
      propagar la excepcion.
    - notify: la idempotencia sin ticket usa el digest completo de 256 bits; el
      prefijo de 32 hex colisionaba dentro de la ventana TTL de 1 h del gateway.
    - notify: el timeout sube a 20 s porque el ACK medido en el gateway real tarda
      ~17 s bajo carga y un corte temprano se lee como fallo aunque el evento si se
      acepte, lo que duplicaria el turno via barrido.
    - agent_handoff: _leer_secreto valida que el JSON sea un dict (antes lanzaba
      AttributeError y salia con codigo != 0 despues de depositar).
    - agent_handoff: el import de notify fija sys.path[0] al directorio del script y
      avisa por stderr si falla, en vez de desactivar el push en silencio.
    - tests: test_sin_secreto_no_intenta es hermetico (--webhook-secret "" en vez de
      leer los secretos reales de la maquina) y se anaden 4 pruebas de regresion.
    
    Tests: 17/17 verde.

diff --git a/ops/buzon/agent_handoff.py b/ops/buzon/agent_handoff.py
index 7d09a959ea..f45d50732e 100644
--- a/ops/buzon/agent_handoff.py
+++ b/ops/buzon/agent_handoff.py
@@ -46,8 +46,15 @@ SECRET_CANDIDATES = (
 )
 
 try:  # el notificador se instala junto a este script
+    _AQUI = str(Path(__file__).resolve().parent)
+    if _AQUI not in sys.path:
+        sys.path.insert(0, _AQUI)
     from notify import notify as _notify
-except Exception:  # pragma: no cover - si falta el módulo, el buzón sigue funcionando
+except Exception as _exc:  # pragma: no cover
+    # Se avisa por stderr en vez de callar: un import roto desactivaría el push
+    # y todo parecería normal hasta que alguien preguntara por la latencia.
+    print(f"[buzon] aviso push desactivado: no se pudo importar notify ({_exc.__class__.__name__})",
+          file=sys.stderr)
     _notify = None
 
 
@@ -57,14 +64,20 @@ def _ensure_dir(p: Path) -> Path:
 
 
 def _leer_secreto(explicito: str | None = None) -> str:
-    """Secreto de la ruta de webhook: argumento, o archivo de secretos."""
-    if explicito:
+    """Secreto de la ruta de webhook: argumento, o archivo de secretos.
+
+    Un `""` explícito significa "sin secreto" y no cae al archivo: es lo que usan
+    las pruebas para no depender de los secretos reales de la máquina.
+    """
+    if explicito is not None:
         return explicito.strip()
     for ruta in SECRET_CANDIDATES:
         try:
             datos = json.loads(ruta.read_text(encoding="utf-8"))
         except Exception:
             continue
+        if not isinstance(datos, dict):
+            continue
         for clave in ("secret", "hmac_secret", "token"):
             valor = datos.get(clave)
             if isinstance(valor, str) and valor.strip():
diff --git a/ops/buzon/notify.py b/ops/buzon/notify.py
index abdd8bcbf3..aa69741d0f 100644
--- a/ops/buzon/notify.py
+++ b/ops/buzon/notify.py
@@ -38,7 +38,10 @@ __all__ = ["NotifyResult", "notify", "EVENTO_NUEVO", "firmar"]
 
 EVENTO_NUEVO = "buzon.nuevo"
 RUTA_POR_DEFECTO = "buzon"
-TIMEOUT_POR_DEFECTO = 2.0
+# Medido en el gateway real (13-nov): bajo carga el ACK puede tardar ~17 s. Un
+# timeout corto produce un falso negativo —el evento SÍ se aceptó— y el barrido
+# volvería a despertar al agente por el mismo ticket.
+TIMEOUT_POR_DEFECTO = 20.0
 
 
 @dataclass(frozen=True)
@@ -61,12 +64,17 @@ def firmar(secreto: str, timestamp: str, cuerpo: bytes) -> str:
 
 
 def _id_idempotencia(payload: Mapping[str, Any], cuerpo: bytes) -> str:
-    """Clave estable: el ticket si existe; si no, el hash del cuerpo."""
+    """Clave estable: el ticket si existe; si no, el hash completo del cuerpo.
+
+    Se usa el digest entero (256 bits) y no un prefijo: dos payloads distintos con
+    el mismo prefijo colisionarían en la ventana de idempotencia del gateway
+    (1 h) y el segundo mensaje se perdería en silencio.
+    """
     for clave in ("ticket_id", "id", "msg_id"):
         valor = payload.get(clave)
         if isinstance(valor, str) and valor.strip():
             return valor.strip()
-    return hashlib.sha256(cuerpo).hexdigest()[:32]
+    return hashlib.sha256(cuerpo).hexdigest()
 
 
 def notify(
@@ -90,23 +98,24 @@ def notify(
     if not perfil or not isinstance(perfil, str):
         return NotifyResult(False, None, "sin_perfil")
 
-    cuerpo = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
-    timestamp = str(int(clock()))
-    url = f"{base_url.rstrip('/')}/p/{perfil}/webhooks/{ruta}"
-    request = urllib.request.Request(
-        url,
-        data=cuerpo,
-        method="POST",
-        headers={
-            "Content-Type": "application/json",
-            "X-Webhook-Timestamp": timestamp,
-            "X-Webhook-Signature-V2": firmar(secret, timestamp, cuerpo),
-            "webhook-id": _id_idempotencia(payload, cuerpo),
-            "User-Agent": "hermes-buzon-notify/1",
-        },
-    )
-
+    # Todo el cuerpo va dentro del try: un payload no serializable o un `clock`
+    # que no devuelve un número no pueden escapar del notificador.
     try:
+        cuerpo = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
+        timestamp = str(int(clock()))
+        url = f"{base_url.rstrip('/')}/p/{perfil}/webhooks/{ruta}"
+        request = urllib.request.Request(
+            url,
+            data=cuerpo,
+            method="POST",
+            headers={
+                "Content-Type": "application/json",
+                "X-Webhook-Timestamp": timestamp,
+                "X-Webhook-Signature-V2": firmar(secret, timestamp, cuerpo),
+                "webhook-id": _id_idempotencia(payload, cuerpo),
+                "User-Agent": "hermes-buzon-notify/1",
+            },
+        )
         with urllib.request.urlopen(request, timeout=timeout) as respuesta:
             return NotifyResult(True, int(respuesta.status))
     except urllib.error.HTTPError as exc:
[0m
[0m→ [0mRead ops/buzon/notify.py
[0m→ [0mRead ops/buzon/agent_handoff.py
[0m→ [0mRead ops/buzon/test_notify.py
[0m→ [0mRead ops/buzon/test_agent_handoff_webhook.py
[0m→ [0mRead ops/buzon/.review/veredicto-r1.md
[0m→ [0mRead ops/buzon/.review/prompt-r1.md
[0m→ [0mRead gateway/platforms/webhook.py[90m [offset=70, limit=30][0m
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && uv run --quiet --with pytest python -m pytest -q 2>&1 | tail -30
.................                                                        [100%]
17 passed in 6.05s
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && mkdir -p .review/scratch && python3 - <<'PY'
import importlib.util, pathlib, json, subprocess, sys, shutil, os
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

base = pathlib.Path(".review/scratch/reply_probe")
shutil.rmtree(base, ignore_errors=True)

# Set up a sender ticket for 'ullr' from 'ragnar'
inbox = base / "inbox"
tgt = inbox / "ullr" / "from-ragnar"
tgt.mkdir(parents=True)
ticket = {"id":"tkt-abc","de":"ragnar","para":"ullr","asunto":"a","tarea":"t","prioridad":"normal"}
(tgt/"tkt-abc.json").write_text(json.dumps(ticket))

class NS: pass
def reply():
    a = NS(); a.agent="ullr"; a.ticket="tkt-abc"; a.respuesta="hecho"; a.evidencia=None; a.inbox_root=str(inbox)
    return m.reply_handoff(a)

r = reply()
print("reply rc:", r)
done = inbox/"ullr"/"done"/"tkt-abc.json"
src = tgt/"tkt-abc.json"
print("done exists:", done.exists(), "| src still exists:", src.exists())
# courtesy copy
courtesy = inbox/"ragnar"/"from-ullr"/"reply-tkt-abc.json"
print("courtesy exists:", courtesy.exists())

# Now re-deposit same ticket (simulate re-send) and reply again -> overwrite?
(tgt/"tkt-abc.json").write_text(json.dumps(ticket))
r2 = reply()
print("second reply rc:", r2)
d2 = json.loads(done.read_text())
print("done respuesta after 2nd:", d2.get("respuesta"))
print("courtesy content respuesta:", json.loads(courtesy.read_text()).get("respuesta"))
PY
✓ Copia de respuesta depositada en /inbox/ragnar/from-ullr/
✓ Ticket tkt-abc cerrado satisfactoriamente en .review/scratch/reply_probe/inbox/ullr/done/tkt-abc.json.
reply rc: 0
done exists: True | src still exists: False
courtesy exists: True
  ✓ Copia de respuesta depositada en /inbox/ragnar/from-ullr/
✓ Ticket tkt-abc cerrado satisfactoriamente en .review/scratch/reply_probe/inbox/ullr/done/tkt-abc.json.
second reply rc: 0
done respuesta after 2nd: hecho
courtesy content respuesta: hecho
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && python3 - <<'PY'
import importlib.util, pathlib, json, shutil
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

base = pathlib.Path(".review/scratch/reply_probe2")
shutil.rmtree(base, ignore_errors=True)
inbox = base / "inbox"
tgt = inbox / "ullr" / "from-ragnar"
tgt.mkdir(parents=True)
ticket = {"id":"tkt-xyz","de":"ragnar","para":"ullr","asunto":"a","tarea":"t","prioridad":"normal"}
(tgt/"tkt-xyz.json").write_text(json.dumps(ticket))

class NS: pass
a1 = NS(); a1.agent="ullr"; a1.ticket="tkt-xyz"; a1.respuesta="primera"; a1.evidencia=None; a1.inbox_root=str(inbox)
m.reply_handoff(a1)
# re-deposit and reply with a different answer
(tgt/"tkt-xyz.json").write_text(json.dumps(ticket))
a2 = NS(); a2.agent="ullr"; a2.ticket="tkt-xyz"; a2.respuesta="segunda"; a2.evidencia=None; a2.inbox_root=str(inbox)
m.reply_handoff(a2)
done = inbox/"ullr"/"done"/"tkt-xyz.json"
courtesy = inbox/"ragnar"/"from-ullr"/"reply-tkt-xyz.json"
print("done respuesta:", json.loads(done.read_text()).get("respuesta"))
print("courtesy respuesta:", json.loads(courtesy.read_text()).get("respuesta"))
PY
✓ Copia de respuesta depositada en /inbox/ragnar/from-ullr/
✓ Ticket tkt-xyz cerrado satisfactoriamente en .review/scratch/reply_probe2/inbox/ullr/done/tkt-xyz.json.
  ✓ Copia de respuesta depositada en /inbox/ragnar/from-ullr/
✓ Ticket tkt-xyz cerrado satisfactoriamente en .review/scratch/reply_probe2/inbox/ullr/done/tkt-xyz.json.
done respuesta: segunda
courtesy respuesta: segunda
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && python3 - <<'PY'
import importlib.util, pathlib, json, shutil
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

base = pathlib.Path(".review/scratch/list_probe")
shutil.rmtree(base, ignore_errors=True)
inbox = base / "inbox"
done = inbox / "ullr" / "done"
done.mkdir(parents=True)
for i in range(12):
    (done/f"tkt-{i}.json").write_text(json.dumps({"de":"ragnar","cerrado_en":"x"}))

import io, contextlib
class NS: pass
a = NS(); a.agent="ullr"; a.status="done"; a.inbox_root=str(inbox)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    m.list_handoffs(a)
out = buf.getvalue()
print("COUNT LINE:", [l for l in out.splitlines() if "COMPLETADOS" in l])
print("LISTED tkt- lines:", sum(1 for l in out.splitlines() if "tkt-" in l))
PY
COUNT LINE: ['[COMPLETADOS / ARCHIVADOS: 12]']
LISTED tkt- lines: 10
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && rm -rf .review/scratch/cli_probe && python3 agent_handoff.py send --from ragnar --to ullr --asunto "prueba" --tarea "t" --inbox-root .review/scratch/cli_probe --no-webhook 2>.review/scratch/cli_stderr.txt; echo "--- STDERR CONTENT ---"; cat .review/scratch/cli_stderr.txt; echo "--- (end stderr) ---"
✓ Handoff enviado exitosamente:
  Ticket: tkt-20261113-ragnar-ullr-5820
  Ruta:   .review/scratch/cli_probe/ullr/from-ragnar/tkt-20261113-ragnar-ullr-5820.json
  Para:   ullr (desde ragnar)
  Asunto: prueba
  Aviso: desactivado por --no-webhook (el barrido lo recogerá).
--- STDERR CONTENT ---
--- (end stderr) ---
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && python3 - <<'PY'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)
d = pathlib.Path(".review/scratch/bad.json")
d.write_text('["not", "a", "dict"]')
m.SECRET_CANDIDATES = (d,)
print("non-dict secret ->", repr(m._leer_secreto(None)))
d2 = pathlib.Path(".review/scratch/empty.json")
d2.write_text('{}')
m.SECRET_CANDIDATES = (d2,)
print("empty dict ->", repr(m._leer_secreto(None)))
print("explicit empty ->", repr(m._leer_secreto("")))
PY
rm -rf .review/scratch
non-dict secret -> ''
empty dict -> ''
explicit empty -> ''
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && mkdir -p .review/scratch && python3 - <<'PY'
import importlib.util, pathlib, json, shutil
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

base = pathlib.Path(".review/scratch/fuzzy")
shutil.rmtree(base, ignore_errors=True)
inbox = base / "inbox"
tgt = inbox / "ullr" / "from-ragnar"
tgt.mkdir(parents=True)
# two tickets: tkt-1 and tkt-10 (substring collision)
for tid in ("tkt-1", "tkt-10"):
    (tgt/f"{tid}.json").write_text(json.dumps({"id":tid,"de":"ragnar","para":"ullr","asunto":"a","tarea":"t"}))

class NS: pass
a = NS(); a.agent="ullr"; a.ticket="tkt-1"; a.respuesta="r"; a.evidencia=None; a.inbox_root=str(inbox)
m.reply_handoff(a)
done = inbox/"ullr"/"done"
print("done files:", sorted(p.name for p in done.glob("*.json")))
print("remaining in from-ragnar:", sorted(p.name for p in tgt.glob("*.json")))
PY
rm -rf .review/scratch
✓ Copia de respuesta depositada en /inbox/ragnar/from-ullr/
✓ Ticket tkt-1 cerrado satisfactoriamente en .review/scratch/fuzzy/inbox/ullr/done/tkt-1.json.
done files: ['tkt-1.json']
remaining in from-ragnar: ['tkt-10.json']
[0m
He verificado el código, ejecutado la suite y corrido sondas de solo lectura. Resumen del análisis:

## FINDINGS

- [MINOR] `ops/buzon/agent_handoff.py:239` — `reply_handoff` localiza el ticket con `glob(f"from-*/*{ticket_id}*.json")`, una coincidencia por **subcadena** sin comprobar que sea exacta ni única. `found[0]` cierra silenciosamente el primer match lexicográfico cuando varios tickets contienen el id (p. ej. `--ticket tkt-1` con `tkt-1.json` y `tkt-11.json`, o dos emisores con el mismo id en `from-ragnar/` y `from-freyja/`). Cierra/contesta un ticket equivocado o sólo uno de varios, sin aviso. Arreglo: exigir coincidencia exacta (`== ticket_id`) o rechazar con error si `len(found) > 1`.

- [MINOR] `ops/buzon/agent_handoff.py:268,281` — `reply_handoff` sobrescribe en silencio: `shutil.move(tmp, dest_file)` (rename sobrescribe `done/<name>.json`) y `shutil.copy2(dest, sender_file)` (cortesía `reply-<name>.json`) pisan cualquier archivo previo con el mismo nombre. Si se vuelve a depositar el mismo `ticket_id` y se responde de nuevo, la primera respuesta se pierde sin aviso (verificado por sonda: la segunda respuesta reemplaza `done` y la copia de cortesía). El move en sí no pierde el ticket (mismo `done_dir` → rename atómico, `src_file.unlink(missing_ok=True)` es posterior), así que el único caso de pérdida real es este overwrite por id reutilizado. Arreglo: fallar si `dest_file` existe, o usar `reply-<id>-<timestamp>.json`.

- [MINOR] `ops/buzon/agent_handoff.py:222-223` — en `list_handoffs` el conteo de completados imprime `len(done_files)` pero sólo lista `done_files[:10]`. Con >10 hechos el encabezado dice "12" y se listan 10 (verificado por sonda). El conteo de entrantes/pendientes sí coincide (`incoming + pending`, ambos globs disjuntos, listados completos). Arreglo: `min(len(done_files), 10)` o listar todos.

- [MINOR] `ops/buzon/notify.py:106` — `url = f"{base_url.rstrip('/')}/p/{perfil}/webhooks/{ruta}"` interpola `ruta` (y `base_url`) sin validar. El CLI valida `perfil` contra `VALID_AGENTS`, pero `--webhook-route` y `--webhook-base` llegan crudos; una `ruta` con `/` o `..` produce una URL que el gateway no matcheará (404 silencioso, el aviso "falla" y cae al barrido). `notify()` como librería tampoco valida `perfil` más allá de "str no vacío". Pre-existente, no introducido por el fix. Arreglo: validar/sanear los tres antes de componer la URL.

Ninguno de estos cuatro es una regresión del fix: los cuatro existen desde `fce8201c` y la ronda 1 no los cubrió (sólo ahora se revisa `reply_handoff`/`list_handoffs`/rutas). El fix de `862b46a6` no introduce defectos nuevos.

## RONDA-1-CERRADA: sí

1. **Hermético `test_sin_secreto_no_intenta`** — cerrado. Pasa `--webhook-secret ""`; `_leer_secreto` hace `if explicito is not None: return explicito.strip()` (agent_handoff.py:72), no toca los archivos reales. Sonda: `_leer_secreto("") → ''`.
2. **`json.dumps` fuera del try** — cerrado. Todo el cuerpo (serialización, `clock()`, URL, `Request`, `firmar`, `_id_idempotencia`) está dentro del `try` (notify.py:103-120).
3. **`_leer_secreto` con JSON no-dict** — cerrado. `if not isinstance(datos, dict): continue` (agent_handoff.py:79). Sonda: archivo `["not","a","dict"]` → `''`.
4. **Idempotencia prefijo 32 hex** — cerrado. `return hashlib.sha256(cuerpo).hexdigest()` completo de 64 (notify.py:77); test `test_id_idempotencia_sin_ticket_usa_digest_completo` lo afirma (`len == 64`).
5. **Timeout 2s → 20s** — cerrado. `TIMEOUT_POR_DEFECTO = 20.0` (notify.py:44).
6. **Import frágil** — cerrado. `sys.path.insert(0, _AQUI)` + `print(..., file=sys.stderr)` en el `except` (agent_handoff.py:48-58). Sonda CLI normal: stderr vacío; el aviso a stderr sólo dispara si el import falla de verdad.

## VERDICT: APPROVE WITH NITS

## JUSTIFICATION

Los seis hallazgos de la ronda 1 están cerrados de forma verificable (lectura de código + sondas) y la suite pasa completa (17/17, frente al 1/12 rojo de la ronda anterior); el `try` ampliado es coherente con el contrato "nunca lanza" y no enmascara ningún fallo nuevo (el `except Exception` final ya existía, y `secret`/`perfil` se validan antes del bloque). El `print(stderr)` no rompe el contrato de salida (stdout intacto, stderr vacío en el caso normal) y los cuatro tests nuevos son deterministas (la serialización falla antes de tocar `127.0.0.1:9`). Lo que impide un APPROVE limpio son cuatro nits pre-existentes en `reply_handoff`/`list_handoffs`/`notify` (matching borroso, overwrite silencioso, conteo de listado y URL sin sanear) que la ronda 1 no llegó a revisar.

## TESTS-EVIDENCE

- `cd ops/buzon && uv run --quiet --with pytest python -m pytest -q` → `17 passed in 6.05s` (ronda 1: `1 failed, 12 passed`).
- Sonda `_leer_secreto`: archivo `["not","a","dict"]` → `''`; `{}` → `''`; `""` explícito → `''`.
- Sonda CLI normal (`send ... --no-webhook` con inbox scratch): returncode 0, **stderr vacío** (el aviso del import no dispara en el caso normal).
- Sonda `reply_handoff` re-depósito del mismo id: segunda respuesta sobrescribe `done/tkt-xyz.json` y `from-ullr/reply-tkt-xyz.json` (ambos pasan de "primera" a "segunda").
- Sonda `list_handoffs --status done` con 12 archivos: encabezado `[COMPLETADOS: 12]`, sólo 10 líneas listadas.
- Sonda `reply_handoff` con `tkt-1` y `tkt-10` coexistiendo: cierra `tkt-1` (correcto por orden lexicográfico), confirmando el matching por subcadena sin chequeo de unicidad.
EXIT:0

[0m
> build · deepseek-v4-pro
[0m
[0m$ [0mgit log --oneline -5 && echo "---" && git show --stat 862b46a61776b93ba4a8ae057bfb91b9291d598d
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
[0m$ [0mgit diff fce8201c0c86c83f59a7fd3b71c5032e057ad52c 862b46a61776b93ba4a8ae057bfb91b9291d598d --stat
ops/buzon/.review/prompt-r1.md          |  54 ++++++++
 ops/buzon/.review/veredicto-r1.md       | 227 ++++++++++++++++++++++++++++++++
 ops/buzon/agent_handoff.py              |  19 ++-
 ops/buzon/notify.py                     |  47 ++++---
 ops/buzon/test_agent_handoff_webhook.py |   3 +-
 ops/buzon/test_notify.py                |  39 ++++++
 6 files changed, 366 insertions(+), 23 deletions(-)
[0m
[0m$ [0mgit show 862b46a61776b93ba4a8ae057bfb91b9291d598d -- ops/buzon/notify.py ops/buzon/agent_handoff.py ops/buzon/test_agent_handoff_webhook.py ops/buzon/test_notify.py
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
diff --git a/ops/buzon/test_agent_handoff_webhook.py b/ops/buzon/test_agent_handoff_webhook.py
index 3ae580f543..dd4489f09c 100644
--- a/ops/buzon/test_agent_handoff_webhook.py
+++ b/ops/buzon/test_agent_handoff_webhook.py
@@ -131,7 +131,8 @@ def test_no_webhook_bandera_desactiva_el_envio(tmp_path):
 
 def test_sin_secreto_no_intenta(tmp_path):
     with _Server(status=202) as srv:
-        out = _run(tmp_path, "--webhook-base", srv.url)
+        # "" explícito = sin secreto. Hermético: no lee los secretos reales de la máquina.
+        out = _run(tmp_path, "--webhook-base", srv.url, "--webhook-secret", "")
         assert out.returncode == 0, out.stderr
         assert srv.hits == []
         assert "sin aviso" in out.stdout.lower()
diff --git a/ops/buzon/test_notify.py b/ops/buzon/test_notify.py
index e508acf6f9..ae3ab28d35 100644
--- a/ops/buzon/test_notify.py
+++ b/ops/buzon/test_notify.py
@@ -165,3 +165,42 @@ def test_el_modulo_no_importa_el_gateway():
         texto = fh.read()
     for prohibido in ("import gateway", "from gateway", "import hermes"):
         assert prohibido not in texto
+
+
+class _NoSerializable:
+    """Objeto que json.dumps no puede serializar."""
+
+
+def test_payload_no_serializable_no_lanza():
+    """Hallazgo del reviewer: json.dumps estaba fuera del try y escapaba."""
+    res = notify(
+        "ullr",
+        {"event_type": "buzon.nuevo", "objeto": _NoSerializable()},
+        base_url="http://127.0.0.1:9",
+        secret=SECRET,
+    )
+    assert res.sent is False
+    assert res.reason == "error"
+
+
+def test_clock_no_callable_no_lanza():
+    res = notify(
+        "ullr",
+        {"event_type": "buzon.nuevo", "ticket_id": "x-1"},
+        base_url="http://127.0.0.1:9",
+        secret=SECRET,
+        clock=None,
+    )
+    assert res.sent is False
+
+
+def test_id_idempotencia_sin_ticket_usa_digest_completo():
+    """Dos cuerpos distintos no pueden colisionar por un prefijo de 32 hex."""
+    cuerpo = b'{"event_type":"buzon.nuevo"}'
+    identificador = notify_mod._id_idempotencia({}, cuerpo)
+    assert len(identificador) == 64
+    assert identificador == hashlib.sha256(cuerpo).hexdigest()
+
+
+def test_id_idempotencia_prefiere_el_ticket():
+    assert notify_mod._id_idempotencia({"ticket_id": "tkt-9"}, b"{}") == "tkt-9"
[0m
[0m→ [0mRead ops/buzon/notify.py
[0m→ [0mRead ops/buzon/agent_handoff.py
[0m→ [0mRead ops/buzon/test_notify.py
[0m→ [0mRead ops/buzon/test_agent_handoff_webhook.py
[0m→ [0mRead ops/buzon/.review/veredicto-r1.md
[0m
[0m$ [0mcd ops/buzon && uv run --quiet --with pytest python -m pytest -q test_notify.py test_agent_handoff_webhook.py 2>&1 | tail -30
.................                                                        [100%]
17 passed in 6.61s
[0m
[0m$ [0mgit show fce8201c0c86c83f59a7fd3b71c5032e057ad52c:ops/buzon/notify.py
"""Notificación push del buzón de agentes contra el webhook del gateway.

El buzón (`agent_handoff.py`) escribe el encargo en `inbox/<perfil>/from-<origen>/`;
hasta hoy el receptor se enteraba por polling (un cron por perfil cada minuto).
Este módulo emite el aviso en el momento, sin cambiar la fuente de verdad: el
archivo se deposita igual y el barrido lento sigue siendo la red de seguridad.

Contrato con el receptor (`gateway/platforms/webhook.py`, esquema *Generic V2*):

    POST {base_url}/p/{perfil}/webhooks/{ruta}
    X-Webhook-Timestamp     epoch (el adaptador aplica ventana anti-replay)
    X-Webhook-Signature-V2  hex HMAC-SHA256(secreto, "<timestamp>.<body>")
    webhook-id              clave de idempotencia (TTL 3600 s en el gateway)

Reglas de diseño:

* **Nunca lanza.** Un fallo de red no puede tumbar el depósito del buzón; se
  devuelve un `NotifyResult` con el motivo y el barrido recogerá el mensaje.
* **Sin reintentos.** El reintento es el barrido lento, no un bucle aquí dentro:
  reintentar en el emisor multiplica sesiones cuando el gateway está saturado.
* **stdlib puro.** Se instala en `/opt/data/scripts/` fuera del repo, así que no
  puede importar `gateway.*` ni `hermes.*`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Optional

__all__ = ["NotifyResult", "notify", "EVENTO_NUEVO", "firmar"]

EVENTO_NUEVO = "buzon.nuevo"
RUTA_POR_DEFECTO = "buzon"
TIMEOUT_POR_DEFECTO = 2.0


@dataclass(frozen=True)
class NotifyResult:
    """Resultado de un intento de notificación. Nunca se propaga una excepción."""

    sent: bool
    status: Optional[int] = None
    reason: Optional[str] = None

    def __bool__(self) -> bool:  # azúcar: `if notify(...)`
        return self.sent


def firmar(secreto: str, timestamp: str, cuerpo: bytes) -> str:
    """Firma Generic V2: hex HMAC-SHA256 de ``"<timestamp>.<cuerpo>"``."""
    return hmac.new(
        secreto.encode("utf-8"), timestamp.encode("ascii") + b"." + cuerpo, hashlib.sha256
    ).hexdigest()


def _id_idempotencia(payload: Mapping[str, Any], cuerpo: bytes) -> str:
    """Clave estable: el ticket si existe; si no, el hash del cuerpo."""
    for clave in ("ticket_id", "id", "msg_id"):
        valor = payload.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return hashlib.sha256(cuerpo).hexdigest()[:32]


def notify(
    perfil: str,
    payload: Mapping[str, Any],
    *,
    base_url: str,
    secret: str,
    ruta: str = RUTA_POR_DEFECTO,
    timeout: float = TIMEOUT_POR_DEFECTO,
    clock=time.time,
) -> NotifyResult:
    """Emite un evento de buzón al webhook del perfil destino.

    Devuelve siempre un `NotifyResult`; el llamador decide qué hacer con un fallo
    (por diseño: registrar y seguir, porque el barrido lento recoge el mensaje).
    """
    if not isinstance(secret, str) or not secret.strip():
        # Sin secreto el receptor rechaza con 403; no gastamos el viaje.
        return NotifyResult(False, None, "sin_secreto")
    if not perfil or not isinstance(perfil, str):
        return NotifyResult(False, None, "sin_perfil")

    cuerpo = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(clock()))
    url = f"{base_url.rstrip('/')}/p/{perfil}/webhooks/{ruta}"
    request = urllib.request.Request(
        url,
        data=cuerpo,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature-V2": firmar(secret, timestamp, cuerpo),
            "webhook-id": _id_idempotencia(payload, cuerpo),
            "User-Agent": "hermes-buzon-notify/1",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as respuesta:
            return NotifyResult(True, int(respuesta.status))
    except urllib.error.HTTPError as exc:
        return NotifyResult(False, int(exc.code), "http")
    except (socket.timeout, TimeoutError):
        return NotifyResult(False, None, "timeout")
    except urllib.error.URLError as exc:
        motivo = "timeout" if isinstance(exc.reason, (socket.timeout, TimeoutError)) else "error"
        return NotifyResult(False, None, motivo)
    except Exception:  # noqa: BLE001 - el buzón no puede fallar por el aviso
        return NotifyResult(False, None, "error")
[0m
[0m$ [0mgit show fce8201c0c86c83f59a7fd3b71c5032e057ad52c:ops/buzon/agent_handoff.py | sed -n '40,90p'
# --- Aviso push (opcional) -------------------------------------------------
WEBHOOK_BASE_DEFAULT = "http://127.0.0.1:8644"
WEBHOOK_ROUTE_DEFAULT = "buzon"
SECRET_CANDIDATES = (
    Path("/opt/hermes-agent-data/secrets/webhook-buzon.json"),
    Path("/opt/data/secrets/webhook-buzon.json"),
)

try:  # el notificador se instala junto a este script
    from notify import notify as _notify
except Exception:  # pragma: no cover - si falta el módulo, el buzón sigue funcionando
    _notify = None


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _leer_secreto(explicito: str | None = None) -> str:
    """Secreto de la ruta de webhook: argumento, o archivo de secretos."""
    if explicito:
        return explicito.strip()
    for ruta in SECRET_CANDIDATES:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            continue
        for clave in ("secret", "hmac_secret", "token"):
            valor = datos.get(clave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
    return ""


def _avisar(
    receptor: str,
    payload: dict,
    *,
    base: str,
    ruta: str,
    secreto: str,
    desactivado: bool,
) -> None:
    """Emite el aviso push e imprime el resultado. Nunca altera el flujo."""
    if desactivado:
        print("  Aviso: desactivado por --no-webhook (el barrido lo recogerá).")
        return
    if _notify is None:
        print("  Sin aviso: notificador no instalado (el barrido lo recogerá).")
        return
[0m
[0m$ [0mcd ops/buzon && python3 - <<'PY'
import importlib.util, pathlib, tempfile, json
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

# 1. "" vs None vs absent-file semantics
d = tempfile.mkdtemp()
secret_file = pathlib.Path(d) / "s.json"
secret_file.write_text(json.dumps({"secret": "real-secret"}))
m.SECRET_CANDIDATES = (secret_file,)
print("explicito ''        ->", repr(m._leer_secreto("")))
print("explicito None      ->", repr(m._leer_secreto(None)))
print("explicito '  x  '   ->", repr(m._leer_secreto("  x  ")))

# 2. non-dict secret file -> returns "" (not raise)
bad = pathlib.Path(d) / "bad.json"; bad.write_text('["not","a","dict"]')
m.SECRET_CANDIDATES = (bad,)
print("non-dict file       ->", repr(m._leer_secreto(None)))
PY
explicito ''        -> ''
explicito None      -> 'real-secret'
explicito '  x  '   -> 'x'
non-dict file       -> ''
[0m
[0m$ [0mcd ops/buzon && for i in 1 2 3; do uv run --quiet --with pytest python -m pytest -q test_notify.py test_agent_handoff_webhook.py 2>&1 | tail -1; done
17 passed in 5.46s
17 passed in 5.71s
17 passed in 5.98s
[0m
[93m[1m! [0mpermission requested: external_directory (/tmp/*); auto-rejecting
[0m✗ [0mcd ops/buzon && d=$(mktemp -d) && python3 agent_handoff.py send --from ragnar --to ullr --asunto "t" --tarea "x" --id "tkt-probe-1" --inbox-root "$d" --no-webhook > /tmp/out.txt 2> /tmp/err.txt; echo "rc=$?"; echo "--- STDOUT ---"; cat /tmp/out.txt; echo "--- STDERR ---"; cat /tmp/err.txt; echo "--- (end stderr) ---"; rm -rf "$d" failed
[91m[1mError: [0mThe user rejected permission to use this specific tool call.
[0m
[0m$ [0mcd ops/buzon && grep -n "quote\|urlencode\|parse\." notify.py agent_handoff.py || echo "no URL encoding found"
agent_handoff.py:132:def send_handoff(args: argparse.Namespace) -> int:
agent_handoff.py:194:def list_handoffs(args: argparse.Namespace) -> int:
agent_handoff.py:233:def reply_handoff(args: argparse.Namespace) -> int:
agent_handoff.py:293:    parser = argparse.ArgumentParser(description="Gestor de handoffs inter-agente de la flota Hermes")
agent_handoff.py:296:    def _webhook_flags(p: argparse.ArgumentParser) -> None:
[0m
EXIT:0

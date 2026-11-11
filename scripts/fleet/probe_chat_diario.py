#!/usr/bin/env python3
"""probe_chat_diario.py — prueba funcional del chat de la web, UNA vez al día.

Por qué existe: los monitores de disponibilidad dejaban de ejercitar el modelo si se
migraban todos a la sonda barata (`/webhook/probe-chat`). Sin esta prueba, Kuma puede
estar en verde con el chat roto: se mide que el proceso vive, no que el modelo responde.

Diferencias con un monitor:
  - Corre 1 vez al día, no cada minuto (coste acotado: ~1 turno).
  - Usa un `session_id` ÚNICO por corrida (`probe-YYYYMMDD-HHMM`), así no arrastra una
    sesión eterna en el agente.
  - Falla ruidosamente (exit 1) si la respuesta viene vacía o sin el marcador esperado.

Uso:
    python3 probe_chat_diario.py                      # Golden por defecto
    python3 probe_chat_diario.py --url https://…/webhook/lucky-chat
    python3 probe_chat_diario.py --dry-run            # no hace red, imprime el payload
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request

URL_DEFECTO = "https://goldengame.com.co/webhook/golden-chat"
PREGUNTA = "¿Cuáles son los horarios de atención?"
TIMEOUT_S = 45
# Si la respuesta trae esto, el modelo contestó de verdad (no un fallback de error).
MARCADOR_ESPERADO = ("horario", "hora", "atiend", "abierto", "lunes", "sede")
FRASES_DE_ERROR = ("dificultad técnica", "intenta de nuevo en un momento")


def construir_payload(ahora=None):
    ahora = ahora or datetime.datetime.now()
    return {
        "session_id": f"probe-{ahora.strftime('%Y%m%d-%H%M%S')}",
        "message": PREGUNTA,
        "history": [],
    }


def evaluar(reply, marcador=MARCADOR_ESPERADO, frases_error=FRASES_DE_ERROR):
    """``(ok, motivo)`` — separa 'no respondió' de 'respondió un error'."""
    texto = (reply or "").strip()
    if not texto:
        return False, "respuesta vacía"
    bajo = texto.lower()
    for frase in frases_error:
        if frase in bajo:
            return False, f"fallback de error servido: {texto[:80]}"
    if not any(m in bajo for m in marcador):
        return False, f"respuesta sin marcador esperado: {texto[:80]}"
    return True, ""


def _post(url, payload, timeout=TIMEOUT_S):
    datos = json.dumps(payload).encode()
    # Cloudflare (delante de las landings) devuelve 403 a clientes sin UA de navegador.
    cabeceras = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) NeuralCrewChatProbe/1.0",
    }
    req = urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL_DEFECTO)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    payload = construir_payload()
    if a.dry_run:
        print("DRY-RUN " + json.dumps(payload, ensure_ascii=False))
        return 0

    try:
        data = _post(a.url, payload)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as e:
        print(f"❌ probe chat: sin respuesta ({type(e).__name__}: {e})")
        return 1

    ok, motivo = evaluar(data.get("reply"))
    if ok:
        print(f"✅ probe chat: respondió en {len(data.get('reply', ''))} chars (session {payload['session_id']})")
        return 0
    print(f"❌ probe chat: {motivo} (session {payload['session_id']})")
    return 1


if __name__ == "__main__":
    sys.exit(main())

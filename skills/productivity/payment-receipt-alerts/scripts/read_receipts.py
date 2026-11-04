#!/usr/bin/env python3
"""Lee y parsea recibos de pago por correo (Bre-B/BBVA y similares) de un buzon Gmail.

Uso:
  python3 read_receipts.py --secret /opt/data/secrets/lucky-gmail.json \
      --query 'from:notificacionesBreB@bbva.com newer_than:7d' [--limit 30] [--raw]

Por que existe:
  Paso de DISENO/VALIDACION del flujo de alertas de pago: confirma que el buzon
  conectado recibe los recibos, mide volumen y extrae los campos que necesita el
  aviso (valor, quien paga, hora, codigo de operacion -> anti-duplicado).

Notas verificadas (10/09/2026):
  - El secreto lo materializa verify_connection.py (refresh_token, client_id, client_secret).
  - Leer mensajes uno por uno devuelve 403 (rate limit) si no se espacia: el script
    duerme y reintenta con backoff.
  - metadataHeaders debe ir como parametro REPETIDO (urlencode(doseq=True)); si se pasa
    como lista dentro de un unico string, los headers vuelven vacios sin dar error.
"""
import argparse
import base64
import collections
import json
import re
import time
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me/"

PATTERNS = {
    "fecha": r"Fecha y hora\s+(\S+)",
    "valor": r"Valor recibido\s+\$\s*([\d\.,]+)",
    "pagador": r"dinero que (.+?) envi[oó] a tu llave",
    "tipo_llave": r"Tipo de llave\s+(.+?)\s+Cuenta",
    "cuenta_destino": r"Cuenta destino\s+\*+(\d+)",
    "operacion": r"C[oó]digo de operaci[oó]n\s+(\d+)",
}


def access_token(secret_path):
    s = json.load(open(secret_path))
    data = urllib.parse.urlencode({
        "client_id": s["client_id"],
        "client_secret": s["client_secret"],
        "refresh_token": s["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def api(token, path, params=None, tries=4):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def html_to_text(msg):
    chunks = []

    def walk(part):
        data = (part.get("body") or {}).get("data")
        if data:
            chunks.append(base64.urlsafe_b64decode(data + "===").decode("utf-8", "ignore"))
        for child in part.get("parts") or []:
            walk(child)

    walk(msg.get("payload") or {})
    text = "\n".join(chunks)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse(text):
    out = {}
    for key, pattern in PATTERNS.items():
        m = re.search(pattern, text)
        out[key] = m.group(1).strip() if m else None
    out["valor_num"] = None
    if out.get("valor"):
        try:
            out["valor_num"] = float(out["valor"].replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", required=True,
                    help="ruta al JSON materializado (ej. /opt/data/secrets/lucky-gmail.json)")
    ap.add_argument("--query", default="newer_than:7d", help="query Gmail (Gmail search syntax)")
    ap.add_argument("--limit", type=int, default=30, help="maximo de mensajes a leer")
    ap.add_argument("--raw", action="store_true", help="imprimir el texto plano de cada correo")
    ap.add_argument("--sleep", type=float, default=0.25, help="pausa entre lecturas (rate limit)")
    args = ap.parse_args()

    token = access_token(args.secret)
    profile = api(token, "profile")
    print("buzon: %s | mensajes totales: %s" % (profile.get("emailAddress"), profile.get("messagesTotal")))

    listing = api(token, "messages", {"q": args.query, "maxResults": args.limit})
    ids = [m["id"] for m in listing.get("messages", [])]
    print("query: %r -> %d correos" % (args.query, len(ids)))

    valores, dias, cuentas, ops = [], collections.Counter(), collections.Counter(), set()
    fallos = 0
    for mid in ids:
        try:
            msg = api(token, "messages/" + mid, {"format": "full"})
            time.sleep(args.sleep)
        except Exception as exc:  # 403 por rate limit u otro fallo puntual
            fallos += 1
            print("  [warn] %s: %s" % (mid, exc))
            continue
        text = html_to_text(msg)
        rec = parse(text)
        fecha = rec.get("fecha") or ""
        if fecha:
            dias[fecha.split(" ")[0]] += 1
        if rec.get("cuenta_destino"):
            cuentas[rec["cuenta_destino"]] += 1
        if rec.get("operacion"):
            ops.add(rec["operacion"])
        if rec.get("valor_num"):
            valores.append(rec["valor_num"])
        print("  %s | %12s | %-34s | op %s | cta %s" % (
            rec.get("fecha") or "?", rec.get("valor") or "?",
            (rec.get("pagador") or "?")[:34], rec.get("operacion"), rec.get("cuenta_destino")))
        if args.raw:
            print("    " + text[:600])

    print("\n--- resumen ---")
    print("leidos: %d | fallos: %d | operaciones unicas: %d" % (len(ids) - fallos, fallos, len(ops)))
    print("por dia:", dict(sorted(dias.items())))
    print("cuentas destino:", dict(cuentas))
    if valores:
        print("valor: n=%d min=%s max=%s prom=%s" % (
            len(valores), min(valores), max(valores), round(sum(valores) / len(valores))))
    if len(ops) < len(ids) - fallos:
        print("AVISO: hay operaciones repetidas -> deduplicar por codigo de operacion.")


if __name__ == "__main__":
    main()

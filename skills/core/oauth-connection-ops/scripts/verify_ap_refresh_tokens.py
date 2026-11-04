#!/usr/bin/env python3
"""
verify_ap_refresh_tokens.py — prueba en vivo el refresh de TODAS las conexiones Google de ActivePieces.

Uso:
    python3 verify_ap_refresh_tokens.py [--host 100.73.30.29]

Requiere: SSH root al host de AP, `cryptography` instalado.
Reporta por conexion: OK (token vivo) / invalid_grant (expirado) / invalid_client (credenciales rotas) / DECRYPT_ERR.
Procedencia: tecnica probada 06/09/2026.
"""
import json, re, subprocess, sys, urllib.parse, urllib.request

HOST = "100.73.30.29"
if "--host" in sys.argv:
    HOST = sys.argv[sys.argv.index("--host") + 1]
SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", f"root@{HOST}"]

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

TOKEN_URL = "https://oauth2.googleapis.com/token"


def sh(args, inp=None):
    r = subprocess.run(args, input=inp, capture_output=True, text=True, timeout=90)
    return r.stdout


def decrypt(iv_hex, data_hex, key):
    cipher = Cipher(algorithms.AES(key), modes.CBC(bytes.fromhex(iv_hex))).decryptor()
    pt = cipher.update(bytes.fromhex(data_hex)) + cipher.finalize()
    unp = padding.PKCS7(128).unpadder()
    return unp.update(pt) + unp.finalize()


def refresh(cid, sec, rt):
    data = urllib.parse.urlencode({"grant_type": "refresh_token", "client_id": cid,
                                   "client_secret": sec, "refresh_token": rt}).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return ("OK", json.loads(r.read()).get("scope", ""))
    except urllib.error.HTTPError as e:
        try:
            return ("FALLO", json.loads(e.read()).get("error", ""))
        except Exception:
            return ("FALLO", f"HTTP {e.code}")
    except Exception as e:
        return ("FALLO", str(e))


key = sh([*SSH, "docker exec ap-app printenv AP_ENCRYPTION_KEY"]).strip().encode("utf-8")
if not key:
    print("ERROR: no se pudo leer AP_ENCRYPTION_KEY"); sys.exit(1)

# Pipe por stdin para evitar que el shell descifre las comillas de la query.
query = '''SELECT "externalId","pieceName", value::text FROM app_connection
WHERE "pieceName" IN ('@activepieces/piece-gmail','@activepieces/piece-google-drive',
'@activepieces/piece-google-calendar','@activepieces/piece-google-sheets')
ORDER BY "created";'''
out = sh([*SSH, "docker exec -i ap-db psql -U postgres -d activepieces -t -A -F'|'"], inp=query)
rows = re.findall(r'(\w[\w-]*)\|@activepieces/piece-([a-z-]+)\|(\{.*?\})\s*(?=\n?\w[\w-]*\|@activepieces|\Z)', out, re.S)

print(f"{'CONEXION':22s} {'PIECE':14s} {'REFRESH':8s} SCOPES")
for eid, piece, blob in rows:
    try:
        b = json.loads(blob)
        d = json.loads(decrypt(b["iv"], b["data"], key))
        st, info = refresh(d.get("client_id"), d.get("client_secret"), d.get("refresh_token"))
        print(f"{eid:22s} {piece:14s} {st:8s} {info[:50]}")
    except Exception as e:
        print(f"{eid:22s} {piece:14s} DECRYPT_ERR {str(e)[:60]}")

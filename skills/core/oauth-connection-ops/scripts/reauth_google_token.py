#!/usr/bin/env python3
"""Reauth de Google Workspace — añade scopes al token existente desde un entorno
headless/chat. PKCE desactivado (el code_challenge se corrompe al transcribir el
URL por chat) + state relajado + backup previo del token.

Uso:
  python3 reauth_google_token.py --auth-url
  python3 reauth_google_token.py --auth-code "<URL o code pegado por el usuario>"
"""
import argparse, json, os, sys, shutil
from pathlib import Path

HERMES_HOME = Path("/opt/data")
TOKEN_PATH = HERMES_HOME / "google_token.json"
CLIENT_SECRET_PATH = HERMES_HOME / "google_client_secret.json"
PENDING_AUTH_PATH = HERMES_HOME / "google_oauth_pending.json"
REDIRECT_URI = "http://localhost:1"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

def auth_url():
    if not CLIENT_SECRET_PATH.exists():
        sys.exit("ERROR: No client secret at %s" % CLIENT_SECRET_PATH)
    from google_auth_oauthlib.flow import Flow
    # PKCE OFF (autogenerate_code_verifier=False): el URL NO lleva code_challenge,
    # evita corrupción al transcribir por chat. Seguro con client secret Desktop.
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), scopes=SCOPES, redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False,
    )
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    PENDING_AUTH_PATH.write_text(json.dumps({
        "state": state, "redirect_uri": REDIRECT_URI}, indent=2), encoding="utf-8")
    print(url)

def exchange(code):
    pending = json.loads(PENDING_AUTH_PATH.read_text(encoding="utf-8"))
    raw = code
    if code.startswith("http"):
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(code).query)
        if "code" not in params:
            sys.exit("ERROR: No code parameter in URL")
        code = params["code"][0]
        state = params.get("state", [None])[0]
        # State relajado: el pending puede quedar stale si se regeneró el URL a
        # mitad de flujo. El code fresco es lo que importa.
        if state and pending.get("state") and state != pending["state"]:
            print("AVISO: state no coincide, continuando de todos modos (code fresco)")
        granted_scopes = (params.get("scope") or [""])[0].strip().split() or SCOPES
    else:
        granted_scopes = SCOPES

    from google_auth_oauthlib.flow import Flow
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), scopes=granted_scopes,
        redirect_uri=pending.get("redirect_uri", REDIRECT_URI),
        state=pending["state"])
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_payload = json.loads(creds.to_json())
    granted = list(creds.granted_scopes or []) if hasattr(creds, "granted_scopes") and creds.granted_scopes else []
    if granted:
        token_payload["scopes"] = granted
    elif granted_scopes != SCOPES:
        token_payload["scopes"] = granted_scopes

    # Backup del token anterior antes de sobrescribir
    if TOKEN_PATH.exists():
        backup = TOKEN_PATH.with_suffix(".json.bak")
        shutil.copy2(TOKEN_PATH, backup)
        print("Backup previo -> %s" % backup)

    TOKEN_PATH.write_text(json.dumps(token_payload, indent=2), encoding="utf-8")
    PENDING_AUTH_PATH.unlink(missing_ok=True)
    print("OK: Token guardado con scopes:")
    for s in token_payload.get("scopes", []):
        print("  -", s.split("/")[-1])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--auth-url", action="store_true")
    g.add_argument("--auth-code", metavar="CODE")
    args = ap.parse_args()
    if args.auth_url:
        auth_url()
    else:
        exchange(args.auth_code)
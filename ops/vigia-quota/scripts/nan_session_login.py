#!/usr/bin/env python3
"""nan_session_login — guarda la cookie de sesión de NaN (cloud) para el informe.

El endpoint /api/usage/credits no acepta la API key: exige la cookie del
dashboard. NaN entra por magic link al correo, así que el flujo es:

  1) pedir el link:   python3 nan_session_login.py --request
  2) abrir el correo, copiar la URL .../api/auth/login/verify?token=...
  3) guardarla:       python3 nan_session_login.py --link "<esa url>"

El paso 3 hace el POST que emite la cookie `nan_session` y la escribe en
/opt/data/secrets/nan-session.json con permisos 0600 (nunca se imprime).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://cloud-api.nan.builders"
SECRET = os.environ.get("NAN_SESSION_SECRET", "/opt/data/secrets/nan-session.json")
ACCOUNT = os.environ.get("NAN_ACCOUNT", "digitalexpresions1@gmail.com")
UA = "neuralcrew-quota/1.0"


def request_link(email: str = ACCOUNT) -> int:
    body = json.dumps({"email": email}).encode()
    req = urllib.request.Request(
        API + "/api/auth/login/request",
        data=body,
        headers={"Content-Type": "application/json", "Origin": "https://cloud.nan.builders", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"link pedido para {email}: HTTP {resp.status}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"error pidiendo el link: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error pidiendo el link: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def _cookie_from(headers) -> str | None:
    raw = headers.get_all("Set-Cookie") or []
    for item in raw:
        if item.startswith("nan_session="):
            return item.split(";", 1)[0]
    return None


def login_with_link(link: str) -> int:
    token = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("token", [""])[0]
    if not token:
        print("la URL no trae ?token=...", file=sys.stderr)
        return 2

    # Paso 1: la URL devuelve una página de confirmación con el `flow` del POST.
    try:
        with urllib.request.urlopen(urllib.request.Request(link, headers={"User-Agent": UA}), timeout=20) as resp:
            html = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        print(f"el link no es válido o ya se usó: HTTP {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error abriendo el link: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    flow = ""
    m = re.search(r'name="flow" value="([^"]+)"', html)
    if m:
        flow = m.group(1)

    # Paso 2: POST que emite la cookie de sesión.
    data = urllib.parse.urlencode({"token": token, "client": "browser", "flow": flow}).encode()
    req = urllib.request.Request(
        API + "/api/auth/login/verify",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": API, "User-Agent": UA},
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D401 - 302 esperado
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=20) as resp:
            cookie = _cookie_from(resp.headers)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307):
            cookie = _cookie_from(exc.headers)
        else:
            print(f"login falló: HTTP {exc.code} {exc.reason}", file=sys.stderr)
            return 1
    except Exception as exc:
        print(f"login falló: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not cookie:
        print("el servidor no devolvió la cookie nan_session", file=sys.stderr)
        return 1

    # Verificación: la cookie debe servir /api/usage/credits.
    try:
        ctx = urllib.request.Request(
            API + "/api/usage/credits", headers={"Cookie": cookie, "User-Agent": UA, "Accept": "application/json"}
        )
        with urllib.request.urlopen(ctx, timeout=20) as resp:
            data_credits = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"la cookie se obtuvo pero no lee créditos: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    exp = None
    m = re.search(r"expires=([^;]+)", cookie)
    if m:
        try:
            from email.utils import parsedate_to_datetime

            exp = parsedate_to_datetime(m.group(1)).astimezone(dt.timezone.utc)
        except Exception:
            exp = None
    if exp is None:
        m = re.search(r"max-age=(\d+)", cookie, re.I)
        if m:
            exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=int(m.group(1)))

    payload = {
        "cookie": cookie,
        "name": "nan_session",
        "domain": ".nan.builders",
        "expires_iso": exp.strftime("%Y-%m-%dT%H:%M:%SZ") if exp else None,
        "account": ACCOUNT,
        "obtained": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "magic link (nan_session_login.py)",
    }
    os.makedirs(os.path.dirname(SECRET), exist_ok=True)
    fd = os.open(SECRET, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(payload, fh, indent=1)
    os.chmod(SECRET, 0o600)

    print(
        "sesión guardada en "
        f"{SECRET} (0600) · caduca {payload['expires_iso'] or 'sin fecha'} · "
        f"créditos visibles: {data_credits.get('usedCredits')}/{data_credits.get('allowanceCredits')}"
    )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sesión de NaN Cloud para el informe de cuotas")
    ap.add_argument("--request", nargs="?", const=ACCOUNT, metavar="EMAIL", help="pide el magic link al correo")
    ap.add_argument("--link", metavar="URL", help="URL del correo .../api/auth/login/verify?token=...")
    args = ap.parse_args(argv)
    if args.link:
        return login_with_link(args.link)
    if args.request:
        return request_link(args.request)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

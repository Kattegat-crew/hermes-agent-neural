#!/usr/bin/env python3
"""Sesión Canvas LMS sin token de API: login por cookie + header X-CSRF-Token.

Credenciales SOLO por variables de entorno (nunca dentro del archivo):
    CANVAS_BASE  https://virtual.universidadean.edu.co
    CANVAS_USER  usuario LDAP
    CANVAS_PASS  contraseña
    CANVAS_JAR   (opcional) ruta del cookie jar; default /opt/data/drafts/canvas/cookies.txt

Uso:
    python3 canvas_session.py login
    python3 canvas_session.py get '/api/v1/users/self'
    python3 canvas_session.py get '/api/v1/courses/<id>/modules?include[]=items&per_page=100'
    python3 canvas_session.py inventory          # identidad + rol + cursos

Nota: escribir en /tmp está bloqueado (HERMES_WRITE_SAFE_ROOT=/host:/opt/data).
"""
import json
import os
import sys
import urllib.parse
from http.cookiejar import MozillaCookieJar

import requests

BASE = os.environ.get("CANVAS_BASE", "").rstrip("/")
JAR = os.environ.get("CANVAS_JAR", "/opt/data/drafts/canvas/cookies.txt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def new_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "es-CO,es;q=0.9,en;q=0.8"})
    if os.path.exists(JAR):
        cj = MozillaCookieJar(JAR)
        try:
            cj.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            cj = None
        if cj:
            for c in cj:
                s.cookies.set(c.name, c.value, domain=c.domain, path=c.path)
    return s


def save(s):
    os.makedirs(os.path.dirname(JAR), exist_ok=True)
    cj = MozillaCookieJar(JAR)
    for c in s.cookies:
        cj.set_cookie(c)
    cj.save(ignore_discard=True, ignore_expires=True)


def csrf(s):
    return urllib.parse.unquote(s.cookies.get("_csrf_token") or "")


def login():
    user, pwd = os.environ["CANVAS_USER"].strip(), os.environ["CANVAS_PASS"]
    s = new_session()
    r = s.get(BASE + "/login/ldap", timeout=40)
    tok = csrf(s)
    print("LOGIN_PAGE:", r.status_code, "csrf_len:", len(tok))
    data = urllib.parse.urlencode({
        "pseudonym_session[unique_id]": user,
        "pseudonym_session[password]": pwd,
        "pseudonym_session[remember_me]": "0",
    })
    r2 = s.post(BASE + "/login/ldap", data=data, timeout=60, allow_redirects=True, headers={
        "X-CSRF-Token": tok,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": BASE + "/login/ldap",
        "Origin": BASE,
    })
    print("POST /login/ldap ->", r2.status_code, r2.url)
    save(s)
    me = s.get(BASE + "/api/v1/users/self", timeout=40,
               headers={"Accept": "application/json", "X-CSRF-Token": csrf(s)})
    print("users/self ->", me.status_code,
          json.dumps({k: me.json().get(k) for k in ("id", "name", "short_name")},
                     ensure_ascii=False) if me.status_code == 200 else me.text[:200])


def get(path):
    s = new_session()
    url = path if path.startswith("http") else BASE + path
    r = s.get(url, timeout=60, headers={
        "Accept": "application/json" if "/api/" in url else "text/html",
        "X-CSRF-Token": csrf(s)})
    print("STATUS:", r.status_code, "URL:", r.url)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:6000])
    except Exception:
        print(r.text[:3000])


def inventory():
    s = new_session()
    h = {"Accept": "application/json", "X-CSRF-Token": csrf(s)}
    me = s.get(BASE + "/api/v1/users/self", headers=h, timeout=40).json()
    print("CUENTA:", me.get("id"), me.get("name"))
    enr = s.get(BASE + "/api/v1/users/self/enrollments?per_page=50&include[]=course",
                headers=h, timeout=60).json()
    for e in enr:
        print("  ROL:", e.get("type"), e.get("enrollment_state"))
    crs = s.get(BASE + "/api/v1/courses?per_page=50&enrollment_state=active",
                headers=h, timeout=60).json()
    for c in crs:
        print("  CURSO:", c.get("id"), c.get("name"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    if not BASE:
        sys.exit("Falta CANVAS_BASE")
    {"login": login, "inventory": inventory}.get(
        cmd, lambda: get(sys.argv[2]))()

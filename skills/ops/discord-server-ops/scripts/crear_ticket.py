#!/usr/bin/env python3
"""Crea un ticket en el foro 🛠️ tickets-tecnicos cumpliendo la plantilla canónica.

Uso:
  python3 crear_ticket.py --titulo "TKT — ..." \
      --responsable 742803595241717840 \
      --tipo Implementacion --estado Pendiente [--entorno DEV] \
      --cuerpo ticket.md [--dry-run]

Reglas que aplica el script (no negociables):
  * Resuelve los ids de tag EN VIVO desde GET /channels/{foro} (available_tags),
    nunca hardcodea ids que el foro pueda cambiar.
  * Exige tag de TIPO + tag de ESTADO + tag del RESPONSABLE (topic del foro).
  * Exige que el cuerpo mencione con <@id> real al responsable.
  * Rechaza cuerpos > 2000 chars (límite del mensaje raíz) antes de postear.
  * Tras el POST, relee el hilo y verifica name, applied_tags y mentions.
    Un POST 201 no prueba que quedó bien armado.

El token se resuelve con /opt/data/scripts/_discord_token.py (helper de la flota).
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/data/scripts")
from _discord_token import discord_token  # noqa: E402

FORO = "1554957746980261938"
GUILD = "1493354289266167808"
API = "https://discord.com/api/v10"
MAX_ROOT = 2000

TIPOS = {"mantenimiento", "implementacion", "incidente"}
ESTADOS = {"pendiente", "en curso", "en revision", "bloqueado", "cerrado"}

# El nombre de la etiqueta no siempre coincide con username/global_name de Discord
# (jemadiar se etiqueta "Chucho", killer420w se etiqueta "Jonathan").
ALIAS_RESPONSABLE = {
    "jemadiar": "Chucho",
    "killer420w": "Jonathan",
    "jonathaun124": "Jonathan",
    "ragnar": "Ragnar",
    "roshi": "Roshi",
}


def _norm(s: str) -> str:
    return (
        s.strip().lower()
        .replace("ó", "o").replace("á", "a").replace("é", "e")
        .replace("í", "i").replace("ú", "u").replace("ñ", "n")
    )


def token() -> str:
    t = discord_token()
    if not t:
        sys.exit("ERROR: no se pudo resolver el token del bot (_discord_token devolvió vacío).")
    return t


def api(method: str, path: str, tok: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={
            "Authorization": f"Bot {tok}",
            "User-Agent": "DiscordBot (https://neuralcrew.dev, 1.0)",
            "Content-Type": "application/json",
        },
    )
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR HTTP {e.code} en {method} {path}: {e.read().decode()[:500]}")


def resolver_tag(tags: list, nombre: str) -> dict:
    for t in tags:
        if _norm(t["name"]) == _norm(nombre):
            return t
    disponibles = ", ".join(sorted(t["name"] for t in tags))
    sys.exit(f"ERROR: no existe la etiqueta '{nombre}'. Disponibles: {disponibles}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--titulo", required=True)
    p.add_argument("--responsable", required=True, help="id numérico del miembro a mencionar")
    p.add_argument("--tipo", required=True, help="Mantenimiento | Implementacion | Incidente")
    p.add_argument("--estado", default="Pendiente", help="Pendiente | En curso | En revision | Bloqueado")
    p.add_argument("--entorno", default=None, help="DEV | PROD (opcional)")
    p.add_argument("--cuerpo", required=True, help="archivo .md con el cuerpo del ticket")
    p.add_argument("--dry-run", action="store_true", help="valida y muestra payload sin postear")
    a = p.parse_args()

    if _norm(a.tipo) not in TIPOS:
        sys.exit(f"ERROR: tipo inválido '{a.tipo}'. Usar: Mantenimiento, Implementacion, Incidente")
    if _norm(a.estado) not in ESTADOS:
        sys.exit(f"ERROR: estado inválido '{a.estado}'.")
    if not re.fullmatch(r"\d{15,21}", a.responsable):
        sys.exit("ERROR: --responsable debe ser el ID numérico, no el nombre en texto.")

    cuerpo = open(a.cuerpo, encoding="utf-8").read().strip()
    if len(cuerpo) > MAX_ROOT:
        sys.exit(f"ERROR: el cuerpo tiene {len(cuerpo)} chars (máx {MAX_ROOT}). "
                 "Partir el detalle a un segundo mensaje del hilo.")
    mencion = f"<@{a.responsable}>"
    if mencion not in cuerpo:
        sys.exit(f"ERROR: el cuerpo no menciona {mencion}. Un @Nombre a mano no notifica.")

    # Secciones obligatorias de la plantilla
    faltan = [s for s in ("objetivo", "criterios de aceptación", "fuera de alcance")
              if s not in cuerpo.lower()]
    if faltan:
        sys.exit("ERROR: faltan secciones obligatorias: " + ", ".join(faltan))

    tok = token()
    foro = api("GET", f"/channels/{FORO}", tok)
    tags = foro.get("available_tags") or []

    elegidos = [resolver_tag(tags, a.tipo), resolver_tag(tags, a.estado)]
    if a.entorno:
        elegidos.append(resolver_tag(tags, a.entorno))
    # tag del responsable: el nombre del tag debe coincidir con el usuario mencionado
    miembro = api("GET", f"/guilds/{GUILD}/members/{a.responsable}", tok)
    nombre_discord = (miembro.get("nick") or miembro["user"]["username"])
    candidatos = {_norm(nombre_discord), _norm(miembro["user"]["username"]),
                  _norm(miembro["user"].get("global_name") or "")}
    alias = ALIAS_RESPONSABLE.get(miembro["user"]["username"].lower())
    if alias:
        candidatos.add(_norm(alias))
    tag_resp = None
    for t in tags:
        if _norm(t["name"]) in candidatos:
            tag_resp = t
            break
    if not tag_resp:
        sys.exit(f"ERROR: no hay etiqueta de responsable que corresponda a '{nombre_discord}'. "
                 f"Etiquetas: {[t['name'] for t in tags]}. "
                 "Añadir el alias en ALIAS_RESPONSABLE o asignar la etiqueta a mano.")
    elegidos.append(tag_resp)
    aplicados = [t["id"] for t in elegidos]

    payload = {
        "name": a.titulo[:100],
        "message": {"content": cuerpo},
        "applied_tags": aplicados,
    }
    if a.dry_run:
        print("DRY-RUN OK")
        print("tags:", [t["name"] for t in elegidos])
        print("chars:", len(cuerpo))
        print(json.dumps(payload, ensure_ascii=False)[:600])
        return

    creado = api("POST", f"/channels/{FORO}/threads", tok, payload)
    tid = creado["id"]

    # Verificación post-creación obligatoria
    th = api("GET", f"/channels/{tid}", tok)
    mapa = {t["id"]: t["name"] for t in tags}
    ok_tags = sorted(th.get("applied_tags") or []) == sorted(aplicados)
    msgs = api("GET", f"/channels/{tid}/messages?limit=5", tok)
    ok_men = any(m.get("mentions") for m in msgs)
    print(f"ticket: https://discord.com/channels/{GUILD}/{tid}")
    print("tags aplicados:", [mapa.get(i, i) for i in th.get("applied_tags") or []])
    print("verificacion:", "OK" if (ok_tags and ok_men) else "FALLÓ", 
          f"(tags={ok_tags}, mencion={ok_men})")
    if not (ok_tags and ok_men):
        sys.exit(1)


if __name__ == "__main__":
    main()

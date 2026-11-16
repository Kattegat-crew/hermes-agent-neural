#!/usr/bin/env python3
"""ncl_cron_embed.py — runner de cron que entrega en embed (contrato ncl-embed/1).

Resuelve el caso `--no-agent`: el job deja de publicar el stdout crudo del script y pasa a
ejecutarlo a través de este wrapper, que convierte la salida en un embed canónico.

Uso típico en `cron/jobs.json` (campo `script`):

    ncl_cron_embed.py --job calendario-informe-campana \
        --channel 1567587946373062667 \
        --run "/opt/hermes-agent-data/scripts/calendario_campaign_report.sh" \
        --footer "NeuralCrew Labs · Calendario"

Reglas:
  * exit != 0            -> status=error (el error va a la descripción, recortado)
  * exit == 0 + stderr   -> status=warn
  * exit == 0 sin stderr -> status=ok
  * --silent-if-empty    -> si no hay stdout, exit==0 y no hay stderr: NO publica (crons que
                            solo hablan cuando hay novedad, como la captura de finanzas)

El stdout se interpreta con un protocolo mínimo: las líneas `clave: valor` se vuelven fields
inline (máx 8, valor ≤200) y el resto forma la descripción. Nada de parseo mágico: si un
script necesita algo más rico, debe emitir un spec `ncl-embed/1` y llamar a ncl_embed.py.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from urllib.parse import unquote
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ncl_embed import embed_from_spec, post_embed  # noqa: E402

MAX_FIELDS_FROM_STDOUT = 8
MAX_FIELD_VALUE = 200
MAX_DESC = 3800
# metacaracteres que delatan una cadena pensada para /bin/sh: el runner no evalúa shells.
# Solo los que crean semántica real de shell sin comillas; paréntesis y comillas quedan fuera
# para no rechazar argumentos legítimos como `python3 -c "raise SystemExit(3)"`.
_SHELL_META = (";", "|", "&", "$", "`", ">", "<", "\n")
# segundos que se espera el drenaje del pipe tras matar el árbol de un comando vencido
_DRAIN_TIMEOUT = 5
_KEY_RE = re.compile(r"^([A-Za-zÁÉÍÓÚÑáéíóúñ0-9 _./·-]{2,40}):\s+(.+)$")

# --- Redacción de credenciales -------------------------------------------------
# Dos capas:
#   1) patrones de VALOR (forma de token): precisos, no tocan prosa ni métricas.
#   2) regla de LÍNEA para claves sensibles (`KEY=`, `"key":`, `bearer`, `bot`): redacta el
#      resto de la línea, incluida la continuación indentada en la línea siguiente.
#      Sobre-redactar es correcto aquí: el embed va a un canal del guild.
# Se apoya además en `agent.redact.redact_sensitive_text`, el redactor canónico del runtime.
_VALUE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # userinfo en URL (postgres://user:pw@host, https://user:pw@host): se redacta aquí porque
    # `agent.redact` puede estar apagado por configuración (HERMES_REDACT_SECRETS=false) y
    # entonces la única capa que queda es esta.
    (re.compile(r"(\b[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]{1,64}:)([^/\s@]{1,128})@"), r"\1<redactado>@"),
    # token de bot de Discord: tres segmentos base64url
    (re.compile(r"\b[A-Za-z0-9_-]{20,30}\.[A-Za-z0-9_-]{5,8}\.[A-Za-z0-9_-]{25,50}\b"), "<token>"),
    (re.compile(r"\b(?:ghp_|gho_|ghs_|ghu_|github_pat_)[A-Za-z0-9_]{10,}"), "<token>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "<token>"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "<token>"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "<token>"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), "<token>"),
    (re.compile(r"(?:https?://)?(?:ptb\.|canary\.)?(?:discord|discordapp)\.com/api/(?:v\d+/)?webhooks/\d+/[\w-]+"),
     "https://discord.com/api/webhooks/<redactado>"),
    # Slack: el secreto va en la ruta (T.../B.../<token>)
    (re.compile(r"(?:https?://)?hooks\.slack\.com/(?:services|workflows|triggers)/[\w\-/]{10,}"), "https://hooks.slack.com/services/<redactado>"),
    # Teams
    (re.compile(r"(?:https?://)?[\w.\-]*webhook\.office\.com/[\w@/.\-]{10,}"), "https://<webhook-teams>/<redactado>"),
    # ActivePieces y webhooks genericos: /api/v1/webhooks/<token largo>
    (re.compile(r"(/[\w.\-]*webhooks?/)[\w.\-]{8,}"), r"\1<redactado>"),
    (re.compile(r"(/hooks?/)[\w.\-]{8,}"), r"\1<redactado>"),
    # Make/Integromat: el token va pegado al host, sin ruta que lo delate
    (re.compile(r"(?:https?://)?hook\.(?:[\w-]+\.)?(?:make|integromat)\.com/[\w.\-]{10,}"),
     "https://hook.make.com/<redactado>"),
    (re.compile(r"(/webhook-test/)[\w.\-]{16,}"), r"\1<redactado>"),
    (re.compile(r"(/hooks/catch/)[\w.\-/]{10,}"), r"\1<redactado>"),
    (re.compile(r"(https?://hooks\.slack\.com/services/)\S+"), r"\1<redactado>"),
]

# --- Detección de credenciales -------------------------------------------------
# Política: si una línea menciona una clave sensible, se redacta la LÍNEA ENTERA. Es la única
# regla que no se puede evadir moviendo el valor (misma línea, línea siguiente, CSV, argv, YAML,
# query string...). Cuesta contexto de diagnóstico; publicar un secreto en un canal del guild
# cuesta más. Sobre-redactar es deliberado.

_SECRET_WORDS = frozenset({
    "token", "secret", "password", "passwd", "pass", "pwd", "passphrase",
    "apikey", "key", "credential", "credentials", "auth",
    "contrasena", "contraseña", "clave", "secreto", "credencial", "credenciales",
    "pw", "passcode", "passw", "pword", "pswd", "passwort", "senha", "motdepasse",
    "wachtwoord", "kennwort", "heslo",
    "webhook", "webhooks", "hook", "hooks",
})
# raíces largas: valen como sufijo pegado en cualquier caso (MAILPASS, dbpassword)
_ROOTS_LARGAS = ("passphrase", "password", "passwd", "passcode", "passwort", "passw",
                 "pword", "pswd", "motdepasse",
                 "wachtwoord", "kennwort", "senha", "heslo", "token", "secret", "apikey",
                 "credential", "contrasena", "contraseña", "clave", "secreto")
# raíces cortas: solo si el segmento va en mayúsculas. Si no, `turkey`, `monkey` o `turnkey`
# se redactarían por acabar en "key".
_ROOTS_CORTAS = ("key", "pw", "pwd", "pass")
# prefijos que convierten una raíz corta en minúsculas en credencial (mailpass, dbpw); sin ellos
# `turkey`/`monkey` seguirían redactándose
_PREFIJOS_CONOCIDOS = ("mail", "user", "db", "my", "api", "private", "public", "secret", "pass",
                       "access", "master", "app", "auth", "signing", "bcrypt", "hash", "ssh",
                       "gpg", "vault", "redis", "mysql", "pg", "aws", "github", "discord",
                       "smtp", "imap", "ftp", "proxy", "bot", "client")
_SEG_SPLIT_RE = re.compile(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
# contienen una raíz pero no son credenciales
_NO_SECRETAS = frozenset({"bypass", "compass", "surpass", "tokenizer", "tokens", "tokenize",
                          "tokenizing", "secretary", "keyboard", "keynote"})
# `token_url`, `password_field`, `secret_name`: la clave describe el secreto, no lo contiene
# palabras que, acompañadas de un sufijo benigno, describen el campo y no el secreto
_EXIMIBLES_CON_BENIGNO = frozenset({
    "token", "key", "secret", "password", "passwd", "pass", "pwd", "apikey",
    "auth", "credential", "credentials", "clave", "contrasena", "contraseña", "passphrase",
})
# sufijos que describen metadatos del campo (seguros aunque la base sea `webhook`)
_SUFIJOS_DUROS = frozenset({"id", "name", "type", "label", "count", "len", "limit", "size",
                            "ttl", "policy", "length", "hint", "header", "status", "enabled"})
_SUFIJOS_BENIGNOS = frozenset({"url", "uri", "endpoint", "host", "path", "file", "dir", "type",
                               "name", "field", "label", "id", "count", "len", "limit", "max",
                               "min", "size", "ttl", "policy", "length", "hint", "header"})
_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")
_ACRONYM_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")  # DBPass -> DB_Pass
_WORD_SPLIT_RE = re.compile(r"[^0-9a-záéíóúüñ]+")

# cabecera de autorización con valor opaco en cualquier posición
_AUTH_INLINE_RE = re.compile(r"(?i)\b(?:bearer|bot)\s+(?P<val>[A-Za-z0-9._~+/\-]{8,})")
# "clave: valor" al inicio de línea: permite evaluar solo la clave (con sus sufijos benignos)
_SOLO_ASIGNACION_RE = re.compile(r"^(?P<key>[\w.\-]{2,60})\s*[:=]\s*(?P<val>.*)$")
_URL_RE = re.compile(r"\bhttps?://\S+")
# query string con clave sensible: la URL se descarta antes de evaluar palabras, así que se mira aparte
# "curl -u usuario:secreto"
_CURL_USER_RE = re.compile(r"(?:^|\s)(?:-u|--user)[\s=]+\S+:\S+")
# userinfo en cualquier URL con esquema: `postgres://user:clave@host`
_URL_USERINFO_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]{1,64}:[^/\s@]{1,128}@")
_QUERY_SENSIBLE_RE = re.compile(
    r"(?i)[?&#;][\w.\-]{0,40}"
    r"(?:token|secret|pass|pwd|pw|key|auth|credential|credencial(?:es)?|contrasena|contraseña"
    r"|clave|secreto|sig|signature|hmac|verifier|nonce|salt)"
    r"[\w.\-]{0,40}=")
# etiquetas sin clave explícita: "Bearer:", "Bot:"
_ETIQUETA_RE = re.compile(r"(?i)^\s*(?:bearer|bot)\s*(?:[:=]|$)")
_AUTH_BENIGNAS = frozenset({"conectado", "conectada", "desconectado", "reconectado", "activo",
                            "listo", "online", "offline", "iniciado", "detenido", "configurado",
                            "respondio", "respondió", "publico", "publicó", "fallo", "falló",
                            "enviado", "recibido", "arrancado", "parado"})
_REDACTED = "<redactado>"


def _palabras(nombre: str) -> list[str]:
    plano = _ACRONYM_RE.sub(r"\1_\2", nombre)
    plano = _CAMEL_RE.sub(r"\1_\2", plano).lower()
    return [p for p in _WORD_SPLIT_RE.split(plano) if p]


def _mayusculas(nombre: str) -> bool:
    letras = [c for c in nombre if c.isalpha()]
    return bool(letras) and sum(1 for c in letras if c.isupper()) >= len(letras) * 0.8


def _es_clave_sensible(nombre: str) -> bool:
    palabras = _palabras(nombre)
    # El sufijo benigno solo vale sobre un identificador (`token_url`, `password_field`).
    # Sobre una línea o una frase, la última palabra no decide nada: `DB_PASSWORD=/etc/secret_file`
    # o `db_password ruta_file` acabarían exentas por terminar en "file", que es una ruta, no el
    # secreto. Se exige forma de identificador (sin espacios, barras, `:` ni `@`).
    identificador = re.search(r"[\s/:@=]", nombre.strip()) is None
    benigno = identificador and len(palabras) > 1 and palabras[-1] in _SUFIJOS_BENIGNOS
    sensibles: set[str] = set()
    for segmento in _SEG_SPLIT_RE.split(nombre):
        if not segmento:
            continue
        mayus = _mayusculas(segmento)
        for p in _palabras(segmento):
            if p in _NO_SECRETAS:
                continue
            if p in _SECRET_WORDS:
                sensibles.add(p)
                continue
            # MAILPASS, dbpassword, PRIVATEKEY...
            base = p.rstrip("0123456789")  # DBPW2, PASSWORT1
            if len(base) > 4 and any(base.endswith(r) for r in _ROOTS_LARGAS):
                sensibles.add(base)
                continue
            # DBPW, MYPW: la raíz corta se acepta solo en un segmento en mayúsculas
            if mayus and any(base.endswith(r) for r in _ROOTS_CORTAS):
                sensibles.add(base)
                continue
            # mailpass, dbpw en minúsculas: raíz corta con prefijo conocido
            if any(base.endswith(r) for r in _ROOTS_CORTAS) \
                    and any(base.startswith(pre) and len(base) > len(pre) + 1
                            for pre in _PREFIJOS_CONOCIDOS):
                sensibles.add(base)
    if not sensibles:
        return False
    if benigno and sensibles <= _EXIMIBLES_CON_BENIGNO:
        return False
    # `webhook_id` es metadato; `WEBHOOK_URL` es la credencial (misma condición de identificador)
    if identificador and palabras and palabras[-1] in _SUFIJOS_DUROS \
            and sensibles <= (_EXIMIBLES_CON_BENIGNO | {"webhook"}):
        return False
    return True


def _userinfo_sensible(linea: str) -> bool:
    return _CURL_USER_RE.search(linea) is not None or _URL_USERINFO_RE.search(linea) is not None


def _linea_es_sensible(linea: str) -> bool:
    """Evalúa la línea sin las URLs (una ruta como /oauth2/token no es una credencial)."""
    consulta = unquote(linea)
    if _QUERY_SENSIBLE_RE.search(consulta):
        return True
    limpia = _URL_RE.sub(" ", linea)
    m = _SOLO_ASIGNACION_RE.match(limpia.strip())
    if m is not None:
        if _es_clave_sensible(m.group("key")):
            return True
        # `token_count: 1200` describe, no contiene: se evalúa el valor, no la clave
        return _es_clave_sensible(_URL_RE.sub(" ", m.group("val")))
    # `export DBPW=xyz`, `DB_PASSWORD /etc/x=y`: asignación con prefijo o clave espaciada
    m2 = _ASIGNACION_LAXA_RE.search(limpia)
    if m2 is not None and _es_clave_sensible(m2.group("key")):
        return True
    if any(_es_clave_sensible(m.group(1)) for m in _CLAVE_ASIGNADA_RE.finditer(limpia)):
        return True
    despojada = limpia.strip()
    # un identificador suelto se evalúa entero: `token_url` describe, `DB_PASSWORD` no
    if re.search(r"[\s/:@=]", despojada) is None:
        return _es_clave_sensible(despojada)
    # Prosa sin asignación NO se considera credencial por sí misma: evaluar palabra a palabra
    # redactaba informes enteros (`[OK] webhook-gateway` cae por "webhook"). La fuga real trae
    # asignación, cabecera de auth, userinfo o query param, y eso se evalúa arriba. Cuando la
    # línea solo ANUNCIA un valor (`The new password is`), lo resuelve `_anticipa_valor`.
    return False


# `webhook`/`hook` solo valen en forma de identificador (SLACK_WEBHOOK_URL): en prosa son
# nombres de servicio y marcaban como sensible cualquier informe que los nombrara.
_PALABRAS_SOLO_IDENTIFICADOR = frozenset({"webhook", "webhooks", "hook", "hooks"})
_CONECTORES_DE_VALOR = frozenset({"is", "es", "son", "era", "sera", "será", "fue", "siguiente",
                                  "valor", "value", "aqui", "aquí", "here"})
_ASIGNACION_LAXA_RE = re.compile(r"(?:^|\s)(?:export\s+|set\s+)?(?P<key>[\w.\-]{2,60})\s*[:=]\s*\S")
# JSON, repr de dict y os.environ entregan la clave ENTRE COMILLAS o dentro de llaves:
#   {"db_password": "x"}   {'api_key': 'y'}   environ({'DB_PASSWORD': 'z'})
# Los patrones de asignación exigen clave desnuda tras inicio/espacio, así que estas formas
# se publicaban enteras. Aquí solo se extraen las claves y las evalúa _es_clave_sensible.
_CLAVE_ASIGNADA_RE = re.compile(r"[\"']?([\w.\-]{2,60})[\"']?\s*[:=]")


def _palabras_fuertes(palabras: list[str]) -> list[int]:
    return [
        i for i, p in enumerate(palabras)
        if p in _SECRET_WORDS and p not in _NO_SECRETAS and p not in _PALABRAS_SOLO_IDENTIFICADOR
    ]


def _valor_en_linea(linea: str) -> bool:
    """¿Hay un valor pegado a la palabra sensible en la MISMA línea?

    `La contraseña es correcthorsebatterystaple` / `INFO user=ana pass=xyz` / `...,pass,xyz`.
    """
    linea = _URL_RE.sub(" ", linea)  # las URLs primero: `https:` no es una clave
    # las claves NO sensibles (`token_count`) se podan: si se quedan, "token" parece prosa
    # y `{"token_count": 1200}` acabaría redactado; las sensibles las ve _linea_es_sensible.
    linea = _CLAVE_ASIGNADA_RE.sub(
        lambda m: m.group(0) if _es_clave_sensible(m.group(1)) else " ", linea)
    if _SOLO_ASIGNACION_RE.match(linea.strip()):
        return False
    palabras = _palabras(_URL_RE.sub(" ", linea))
    fuertes = _palabras_fuertes(palabras)
    if not fuertes:
        return False
    resto = palabras[fuertes[0] + 1:]
    return any(len(t) >= 3 and t not in _CONECTORES_DE_VALOR for t in resto)


def _anticipa_valor(linea: str) -> bool:
    """¿La línea solo ANUNCIA una credencial y el valor viene en la línea siguiente?

    `Token del bot:` / `The new password is` / `credencial usada por el job`.
    """
    despojada = _URL_RE.sub(" ", linea).strip()
    if not despojada or "=" in despojada or re.search(r":\s*\S", despojada):
        return False
    if _CLAVE_ASIGNADA_RE.search(linea):
        return False
    palabras = _palabras(despojada)
    if not palabras or len(palabras) > 8:
        return False
    if not _palabras_fuertes(palabras):
        return False
    return palabras[-1] in _CONECTORES_DE_VALOR or len(palabras) <= 6


def _auth_con_valor(linea: str) -> bool:
    for m in _AUTH_INLINE_RE.finditer(linea):
        if m.group("val").lower() not in _AUTH_BENIGNAS:
            return True
    return False


_CANONICAL_REDACT = None


def _canonical_redact(text: str) -> str:
    global _CANONICAL_REDACT
    if _CANONICAL_REDACT is None:
        try:
            if "/opt/hermes-agent" not in sys.path:
                sys.path.insert(0, "/opt/hermes-agent")
            from agent.redact import redact_sensitive_text

            _CANONICAL_REDACT = redact_sensitive_text
        except Exception:
            _CANONICAL_REDACT = False
    if _CANONICAL_REDACT:
        try:
            # force=True: la redacción del embed no puede depender de `security.redact_secrets`.
            # Con la opción apagada, el canónico devuelve el texto tal cual y una cabecera
            # `Authorization: Basic ...` llegaría entera al canal.
            return _CANONICAL_REDACT(text, force=True)
        except TypeError:  # firma antigua sin `force`
            try:
                return _CANONICAL_REDACT(text)
            except Exception:
                return text
        except Exception:
            return text
    return text


def scrub(text: str) -> str:
    """Redacta credenciales antes de que el texto llegue a un embed público.

    Heurístico por diseño: una credencial opaca sin clave ni etiqueta adyacente no es
    detectable. Ante la duda, se redacta.
    """
    src = text or ""
    for pattern, repl in _VALUE_PATTERNS:
        src = pattern.sub(repl, src)
    src = _CURL_USER_RE.sub(lambda m: m.group(0).split(":")[0] + ":" + _REDACTED, src)

    lines: list[str] = []
    redact_next = False
    for line in src.splitlines():
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip())]
        if not stripped:
            lines.append(line)
            continue
        if redact_next:
            lines.append(f"{indent}{_REDACTED}")
            # si la línea consumida era a su vez una clave sensible (`DB_PASSWORD=` vacío
            # seguido de `API_KEY=`), el valor real sigue en la línea siguiente: la cadena
            # de redacción no se corta.
            redact_next = (
                _linea_es_sensible(line)
                or _anticipa_valor(line)
                or _auth_con_valor(line)
                or _userinfo_sensible(line)
                or _ETIQUETA_RE.match(stripped) is not None
            )
            continue
        if _linea_es_sensible(line) or _auth_con_valor(line) or _userinfo_sensible(line) \
                or _valor_en_linea(line) or _ETIQUETA_RE.match(stripped):
            lines.append(f"{indent}{_REDACTED}")
            # tras una línea con clave sensible, la siguiente también se redacta: el valor
            # puede estar en cualquier parte y no hay forma barata de saberlo
            redact_next = True
            continue
        if _anticipa_valor(line):
            # la línea solo anuncia (`Token del bot:`): se conserva tal cual y se tapa el valor
            lines.append(line)
            redact_next = True
            continue
        lines.append(line)

    salida = _canonical_redact("\n".join(lines))
    # el redactor canónico normaliza y se come los saltos finales: se restituyen todos
    cola = len(src) - len(src.rstrip("\n"))
    if cola:
        salida = salida.rstrip("\n") + "\n" * cola
    return salida


def _clean(text: str) -> str:
    return "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()


def parse_output(stdout: str) -> tuple[list[dict], str]:
    """Separa `clave: valor` (fields) del texto libre (descripción). Determinista."""
    fields: list[dict] = []
    free: list[str] = []
    for raw in _clean(stdout).splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _KEY_RE.match(line)
        if m and len(fields) < MAX_FIELDS_FROM_STDOUT:
            key, value = m.group(1).strip(), m.group(2).strip()
            if len(value) <= MAX_FIELD_VALUE and "://" not in value:
                fields.append({"name": key, "value": value, "inline": True})
                continue
        free.append(line)
    return fields, "\n".join(free)


def status_for(exit_code: int, stderr: str) -> str:
    if exit_code != 0:
        return "error"
    return "warn" if (stderr or "").strip() else "ok"


def build_embed(
    *,
    job: str,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    duration_s: float = 0.0,
    title: str | None = None,
    footer: str = "NeuralCrew Labs",
    extra_fields: list[str] | None = None,
    parse_fields: bool = True,
) -> dict:
    """Construye el spec ncl-embed/1 a partir del resultado de la corrida (puro, sin red)."""
    stdout, stderr = scrub(stdout), scrub(stderr)
    status = status_for(exit_code, stderr)
    parsed_fields, description = parse_output(stdout) if parse_fields else ([], _clean(stdout))

    if status == "error":
        detalle = "\n".join(x for x in (_clean(stderr), _clean(stdout)) if x)
        tail = detalle[-1200:] or "sin salida"
        description = f"```\n{tail}\n```"
    elif status == "warn":
        # el stderr es la razón del warn: se conserva aunque el stdout ya haya llenado la
        # descripción (antes se descartaba en silencio y el embed quedaba verde sin motivo).
        aviso = f"```\n{_clean(stderr)[-800:]}\n```"
        if description:
            disponible = max(0, MAX_DESC - len(aviso) - 2)
            description = (description[:disponible].rstrip() + "\n\n" + aviso).strip()
        else:
            description = aviso

    fields = [
        {"name": "🔧 Job", "value": job, "inline": True},
        {"name": "⏱️ Duración", "value": f"{duration_s:.1f} seg", "inline": True},
        {"name": "🚦 Exit", "value": str(exit_code), "inline": True},
    ]
    for raw in extra_fields or []:
        if "=" in raw:
            k, v = raw.split("=", 1)
            # si el nombre del field es una clave sensible, el valor entero es la credencial
            valor = _REDACTED if _es_clave_sensible(k.strip()) else scrub(v.strip())
            fields.append({"name": scrub(k.strip()), "value": valor, "inline": True})
    fields.extend(parsed_fields)

    spec = {
        "title": scrub(title) if title else f"{job} — {time.strftime('%d %b %H:%M')}",
        "status": status,
        "description": description[:MAX_DESC],
        "fields": fields,
        "footer": scrub(footer),
    }
    return embed_from_spec(spec)


def _split_command(cmd: str) -> list[str]:
    """Convierte el comando en argv SIN pasar por un shell.

    Los 15 wrappers `embed_*.sh` solo invocan `<intérprete> <script>`, así que no hay pipes ni
    redirecciones que perder. Rechazar los metacaracteres de forma explícita evita el fallo
    silencioso: si alguien necesita un pipe, mueve la lógica a un script y lo pasa como argv.
    """
    if not (cmd or "").strip():
        raise ValueError("comando vacío: --run necesita un ejecutable y sus argumentos")
    encontrados = [c for c in _SHELL_META if c in cmd]
    if encontrados:
        raise ValueError(
            "el comando contiene metacaracteres de shell "
            f"({', '.join(sorted(set(encontrados)))}) y no se evalúa en un shell: "
            "mueve la lógica a un script y pásalo como argumento"
        )
    argv = shlex.split(cmd)
    if not argv:
        raise ValueError("comando vacío: --run necesita un ejecutable y sus argumentos")
    return argv


def run_command(cmd: str, timeout: int, cwd: str | None = None) -> tuple[str, str, int, float]:
    argv = _split_command(cmd)
    started = time.monotonic()
    # Sin start_new_session: el hijo queda en el grupo del wrapper, así el killpg del
    # scheduler de Hermes (que sí crea sesión para el script) alcanza a toda la descendencia.
    # El timeout se resuelve con kill_process_tree, que mata el árbol completo (incluye
    # nietos que hicieron setsid), igual que hace cron/scheduler_script.py.
    # shell=False: el comando es argv, no una cadena evaluada por /bin/sh.
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,  # review-gate:ignore — shell=False verificado por test_c1_*
        text=True, cwd=cwd, errors="replace",
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return out or "", err or "", proc.returncode, time.monotonic() - started
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        # el drenaje también va acotado: un descendiente que sobreviva al kill y mantenga el
        # pipe abierto colgaría el wrapper para siempre (y con él el tick del scheduler).
        try:
            out, err = proc.communicate(timeout=_DRAIN_TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except (ProcessLookupError, PermissionError):
                pass
            try:
                out, err = proc.communicate(timeout=_DRAIN_TIMEOUT)
            except subprocess.TimeoutExpired:
                out, err = "", ""
        return (out or ""), ((err or "") + f"\ntimeout tras {timeout}s").strip(), 124, time.monotonic() - started


def _kill_tree(proc: subprocess.Popen) -> None:
    """Mata el árbol del proceso; cae a proc.kill() si el helper del runtime no está."""
    try:
        if "/opt/hermes-agent" not in sys.path:
            sys.path.insert(0, "/opt/hermes-agent")
        from agent.deadline import kill_process_tree

        if kill_process_tree(proc.pid):
            return
    except Exception:
        pass
    try:
        proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ejecuta un script de cron y publica su salida como embed.")
    ap.add_argument("--job", required=True)
    ap.add_argument("--channel", required=True)
    ap.add_argument("--run", required=True, help="Comando del script original")
    ap.add_argument("--title", default=None)
    ap.add_argument("--footer", default="NeuralCrew Labs")
    ap.add_argument("--field", dest="extra_fields", action="append", default=[])
    ap.add_argument("--silent-if-empty", action="store_true",
                    help="Compatibilidad: el silencio sin contenido ya es el comportamiento por defecto.")
    ap.add_argument("--always", action="store_true",
                    help="Publica aunque no haya salida (por defecto se calla si no hay nada que contar).")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true", help="No ejecuta ni publica; imprime el spec")
    ap.add_argument("--no-fields", action="store_true", dest="no_fields",
                    help="No convierte líneas `clave: valor` en fields: todo el stdout va a la descripción "
                         "(digests con markdown propio).")
    ap.add_argument("--stdin-output", help="(pruebas) texto que simula el stdout, no ejecuta")
    args = ap.parse_args(argv)

    if args.dry_run:
        print("[dry-run] ejecutaría: " + args.run)
        return 0

    if args.stdin_output is not None:
        stdout, stderr, code, dur = args.stdin_output, "", 0, 0.0
    else:
        stdout, stderr, code, dur = run_command(args.run, args.timeout)

    if not args.always and code == 0 and not stdout.strip() and not stderr.strip():
        print(f"{args.job}: sin novedad, no se publica")
        return 0

    embed = build_embed(
        job=args.job,
        stdout=stdout,
        stderr=stderr,
        exit_code=code,
        duration_s=dur,
        title=args.title,
        footer=args.footer,
        extra_fields=args.extra_fields,
        parse_fields=not args.no_fields,
    )
    result = post_embed(args.channel, embed)
    estado = status_for(code, stderr)
    print(f"{args.job}: publicado {result.get('message_id')} (status={estado})")
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())

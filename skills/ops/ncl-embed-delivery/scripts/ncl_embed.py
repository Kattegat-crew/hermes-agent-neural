#!/usr/bin/env python3
"""ncl_embed.py — Publicador canónico de embeds de Discord para entregas de cron.

REGLA NCL (ver skill `ncl-embed-delivery`): toda entrega de cron a Discord se publica
como embed mediante este helper, no como texto plano. Contrato versionado `ncl-embed/1`.

Uso CLI (lo normal en un cron --no-agent):

    python3 ncl_embed.py --channel 1564308156044279938 \
        --title "Informe de ventas — 14 nov" --status ok \
        --desc "Resumen del día" \
        --field "Pedidos=12" --field "Ingreso=USD 1.240" \
        --footer "NeuralCrew Labs · Amazon AU"

Uso por contrato JSON (un script emite el spec y este helper lo valida/publica):

    python3 ncl_embed.py --spec-file /tmp/spec.json
    echo '{"title":"...","status":"warn"}' | python3 ncl_embed.py --spec-file -

Modo dry-run: imprime el payload final y NO llama a la API (`--dry-run`).
El token se resuelve por entorno o por la fuente de secretos del perfil (Hermes >=0.22).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://discord.com/api/v10"

# (color, emoji) por estado. Paleta fija: un color por semántica, no por job.
PALETTE = {
    "ok": (3066993, "🛡️"),
    "warn": (16776960, "⚠️"),
    "error": (15158332, "🚨"),
    "info": (3447003, "ℹ️"),
    "neutral": (9807270, "🗂️"),
}

MAX_TITLE = 256
MAX_DESC = 4096
MAX_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_FOOTER = 2048
# Discord cuenta el conjunto del embed (title + description + campos + footer) contra 6000:
# si el total se pasa, rechaza el mensaje ENTERO. Se recorta aquí antes de enviar.
MAX_TOTAL = 6000
_CHANNEL_RE = re.compile(r"^\d{17,20}$")

HERMES_HOME = os.environ.get("HERMES_HOME", "/opt/hermes-agent-data")


def _hermes_home() -> str:
    """Se resuelve en cada llamada: capturado al importar, el valor se queda obsoleto en cuanto
    el proceso (o un test) cambia HERMES_HOME, y resolve_token leería el `.env` equivocado."""
    return os.environ.get("HERMES_HOME") or HERMES_HOME


def _trunc(text: str, limit: int) -> str:
    text = "" if text is None else str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_token(token: str | None = None) -> str:
    """Token del bot: argumento -> entorno -> fuente de secretos del perfil -> .env legado.

    Un valor presente pero vacío (`DISCORD_BOT_TOKEN=`) NO es un token: se trata como ausente
    y se sigue la cadena. Antes devolvía "" y el fallo aparecía como HTTP 401 en Discord.
    """
    if token and str(token).strip():
        return str(token).strip()
    env = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if env:
        return env
    try:
        sys.path.insert(0, "/opt/hermes-agent")
        from hermes_cli.env_loader import hydrate_profile_secret_sources

        secrets = hydrate_profile_secret_sources(_hermes_home()) or {}
        for key in ("DISCORD_BOT_TOKEN", "DISCORD_TOKEN", "DISCORD_BOT_API_TOKEN"):
            valor = str(secrets.get(key) or "").strip()
            if valor:
                return valor
    except Exception:
        pass
    env_path = Path(_hermes_home()) / ".env"
    if env_path.exists():
        for line in env_path.read_text(errors="ignore").splitlines():
            if line.startswith("DISCORD_BOT_TOKEN="):
                valor = line.split("=", 1)[1].strip().strip('"').strip("'").strip()
                if valor:
                    return valor
    raise SystemExit(
        "ncl_embed: no se encontró DISCORD_BOT_TOKEN (entorno, secretos del perfil ni .env)."
    )


def _parse_fields_raw(items: list[str]) -> list[dict]:
    out = []
    for item in items or []:
        if "=" not in item:
            out.append({"name": item.strip(), "value": "—", "inline": True})
            continue
        name, value = item.split("=", 1)
        out.append({"name": name.strip(), "value": value.strip(), "inline": True})
    return out


def _embed_chars(embed: dict) -> int:
    """Caracteres que Discord cuenta del conjunto del embed."""
    total = len(embed.get("title") or "")
    total += len(embed.get("description") or "")
    total += sum(
        len(_txt(f.get("name"))) + len(_txt(f.get("value"))) for f in embed.get("fields") or []
    )
    total += len((embed.get("footer") or {}).get("text") or "")
    return total


def _enforce_total(embed: dict) -> dict:
    """Recorta descripción y luego campos hasta caber en MAX_TOTAL.

    Discord rechaza el mensaje entero si el conjunto pasa de 6000: recortar aquí conserva
    título, estado y los primeros campos en vez de perder la entrega completa.
    """
    exceso = _embed_chars(embed) - MAX_TOTAL
    if exceso <= 0:
        return embed
    desc = embed.get("description") or ""
    if desc and exceso > 0:
        objetivo = len(desc) - exceso
        recortada = _trunc(desc, objetivo) if objetivo > 1 else ""
        if recortada:
            embed["description"] = recortada
        else:
            embed.pop("description", None)
        exceso = _embed_chars(embed) - MAX_TOTAL
    while exceso > 0 and embed.get("fields"):
        campos = embed["fields"]
        campos.pop()  # el último campo es el menos importante
        if not campos:
            embed.pop("fields", None)
        exceso = _embed_chars(embed) - MAX_TOTAL
    return embed


def _txt(v) -> str:
    """`0` y `False` son valores válidos: `f.get("value") or ""` los volvía "—"."""
    return "" if v is None else str(v)


def embed_from_spec(spec: dict) -> dict:
    """Valida y normaliza un spec `ncl-embed/1` a un embed de Discord."""
    title = str(spec.get("title") or "").strip()
    if not title:
        raise ValueError("ncl-embed/1: 'title' es obligatorio")

    status = str(spec.get("status") or "info").strip().lower()
    if status not in PALETTE:
        status = "info"
    color, emoji = PALETTE[status]

    # Un solo emoji de estado: si el autor ya puso uno, se respeta.
    title = title.strip()
    if title and title[0].isalnum():
        title = f"{emoji} {title}"

    fields = spec.get("fields")
    if fields is None:
        fields = _parse_fields_raw(spec.get("fields_raw") or [])

    clean_fields = []
    for f in fields:
        name = _trunc(_txt(f.get("name")).strip(), MAX_FIELD_NAME) or "—"
        value = _trunc(_txt(f.get("value")).strip(), MAX_FIELD_VALUE) or "—"
        clean_fields.append({"name": name, "value": value, "inline": bool(f.get("inline", True))})
    if len(clean_fields) > MAX_FIELDS:
        hidden = len(clean_fields) - MAX_FIELDS
        clean_fields = clean_fields[: MAX_FIELDS - 1]
        clean_fields.append(
            {"name": "➕ Más", "value": f"{hidden + 1} campos omitidos", "inline": False}
        )

    embed: dict = {"title": _trunc(title, MAX_TITLE), "color": color}
    desc = str(spec.get("description") or "").strip()
    if desc:
        embed["description"] = _trunc(desc, MAX_DESC)
    if clean_fields:
        embed["fields"] = clean_fields
    footer = str(spec.get("footer") or "").strip()
    if footer:
        embed["footer"] = {"text": _trunc(footer, MAX_FOOTER)}
    embed = _enforce_total(embed)
    embed["timestamp"] = spec.get("timestamp") or _now_iso()
    return embed


def post_embed(
    channel_id: str,
    embed: dict,
    token: str | None = None,
    dry_run: bool = False,
    content: str = "",
    timeout: int = 15,
) -> dict:
    """Publica el embed. Devuelve el payload enviado (o el mensaje creado)."""
    channel_id = str(channel_id or "").strip()
    if not _CHANNEL_RE.match(channel_id):
        raise ValueError(
            f"ncl_embed: channel_id inválido {channel_id!r}: se espera un snowflake de 17-20 dígitos"
        )
    payload = {"content": _trunc(content, 2000), "embeds": [embed]}
    if dry_run:
        return {"dry_run": True, "channel": channel_id, **payload}

    token = resolve_token(token)
    req = urllib.request.Request(
        f"{API_BASE}/channels/{channel_id}/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "NeuralCrewLabs-Embed/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode() or "{}")
            return {"dry_run": False, "message_id": body.get("id"), "channel": channel_id}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:400]
        raise SystemExit(f"ncl_embed: Discord HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"ncl_embed: red inalcanzable: {exc.reason}") from exc


def _load_spec(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publica un embed canónico de NeuralCrew Labs en Discord.")
    ap.add_argument("--channel", help="ID del canal o hilo destino")
    ap.add_argument("--title")
    ap.add_argument("--status", default="info", choices=sorted(PALETTE))
    ap.add_argument("--desc", "--description", dest="description", default="")
    ap.add_argument("--field", dest="fields_raw", action="append", default=[], metavar="NOMBRE=VALOR")
    ap.add_argument("--footer", default="")
    ap.add_argument("--spec-file", help="JSON con el spec ncl-embed/1 ('-' = stdin)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="No imprime nada si el envío sale bien")
    args = ap.parse_args(argv)

    if args.spec_file:
        spec = _load_spec(args.spec_file)
        if args.channel and not spec.get("channel"):
            spec["channel"] = args.channel
    else:
        spec = {
            "title": args.title,
            "status": args.status,
            "description": args.description,
            "fields_raw": args.fields_raw,
            "footer": args.footer,
            "channel": args.channel,
        }

    channel = str(spec.get("channel") or "").strip()
    if not channel:
        ap.error("falta --channel (o 'channel' en el spec)")

    embed = embed_from_spec(spec)
    result = post_embed(channel, embed, dry_run=args.dry_run,
                        content=str(spec.get("content") or ""))
    if args.dry_run:
        print(json.dumps({"channel": channel, "embeds": [embed]}, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(f"ok {result.get('message_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Resumen diario de tickets (foro Discord 🛠️・tickets-tecnicos) — v3 con LLM.

Ventana: desde ayer a las 10:00 (America/Bogota) hasta el momento de la corrida.
v2 (15-oct): formato compacto, una línea por ticket.
v3 (15-oct): el veredicto de cierre lo redacta glm5.3-flash (API NaN, streaming);
si el LLM falla, sale vacío o no valida, cae al modo determinista v2.
Uso: resumen_tickets_tecnicos.py [--no-llm]
Salida: texto plano listo para entregar por Telegram (no_agent).
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")
FORUM = "1554957746980261938"  # 🛠️・tickets-tecnicos
GUILD = "1493354289266167808"
API = "https://discord.com/api/v10"
MAX_MSG = 3500  # Telegram limita a 4096
LLM_MODEL = "glm5.3-flash"
LLM_MAXTOK = 12000  # el modelo RAZONA y el reasoning consume del mismo presupuesto:
# con 4000 y 14 tickets el content salía VACÍO (medido 09-nov-2026)


def _token():
    # 1) entorno directo (si el scheduler lo inyecta)
    tok = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if tok:
        return tok
    # 2) fuentes de secretos del perfil (Bitwarden/Vaultwarden vía env_loader de Hermes)
    try:
        sys.path.insert(0, "/opt/hermes-agent")
        from hermes_cli.env_loader import hydrate_profile_secret_sources
        tok = hydrate_profile_secret_sources("/opt/hermes-agent-data").get("DISCORD_BOT_TOKEN", "").strip()
        if tok:
            return tok
    except Exception:
        pass
    # 3) fallback legado: .env
    try:
        with open("/opt/data/.env") as fh:
            m = re.search(r"^DISCORD_BOT_TOKEN=(\S+)", fh.read(), re.M)
            if m:
                return m.group(1)
    except FileNotFoundError:
        pass
    raise SystemExit("DISCORD_BOT_TOKEN no encontrado (entorno/secretos/.env)")


TOK = _token()
HDR = {"Authorization": f"Bot {TOK}", "User-Agent": "DiscordBot (hermes)"}


def get(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


TKT_PREFIX = re.compile(r"^\W*TKT\s*[—–\-:]\s*", re.I)


def short_name(name, limit=70):
    """Nombre del ticket recortado en el separador natural.

    OJO: muchos hilos se llaman «TKT — <título real>». Sin quitar ese prefijo,
    el recorte por « — » devolvía solo «TKT» y el resumen diario salía con 14
    líneas idénticas que no decían nada (bug visto el 09-nov-2026).
    """
    name = TKT_PREFIX.sub("", name).strip()
    name = re.split(r"\s+[—–-]\s+|\s*\(", name)[0].strip()
    return name[:limit].rstrip(" -–—")


def esencia(msgs, limit=115):
    """Primera frase con contenido del ticket, para el modo determinista.

    Discord devuelve los mensajes del más nuevo al más viejo: hay que ordenar,
    y la esencia es el cuerpo del ticket (mensaje del bot), no la última charla.
    """
    orden = sorted(msgs, key=lambda m: m["timestamp"])
    # preferir el mensaje que abre el hilo; si es corto, el primer bot con cuerpo
    candidatos = orden[:1] + [m for m in orden if m.get("author", {}).get("bot")]
    for m in candidatos:
        if True:
            t = re.sub(r"<[^>]+>", " ", m["content"])
            t = re.sub(r"[*_`#>|]+", "", t)
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) < 80:
                continue
            # quitar cabeceras tipo "Estado: X · Entorno: Y"
            t = re.sub(r"^(Estado|Ticket|Objetivo)[^.]{0,160}?\.\s*", "", t, flags=re.I)
            frase = re.split(r"(?<=[.!?])\s", t)[0]
            return frase[:limit].rstrip(" ,;:")
    return ""


def cuerpo_ticket(msgs, limit=900):
    """Texto del mensaje que abre el hilo, limpio, para dárselo al LLM."""
    orden = sorted(msgs, key=lambda m: m["timestamp"])
    for m in orden:
        t = re.sub(r"<[^>]+>", " ", m["content"])
        t = re.sub(r"[*_`#>|]+", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= 80:
            return t[:limit]
    return ""


def fetch_threads():
    info = get(f"{API}/channels/{FORUM}")
    tags = {t["id"]: t["name"] for t in info.get("available_tags", [])}

    threads = {}
    try:
        for t in get(f"{API}/guilds/{GUILD}/threads/active")["threads"]:
            if t.get("parent_id") == FORUM:
                threads[t["id"]] = t
    except urllib.error.HTTPError as e:
        print(f"WARN: threads/active -> {e.code}", file=sys.stderr)

    before = None
    for _ in range(8):
        url = f"{API}/channels/{FORUM}/threads/archived/public?limit=100"
        if before:
            url += f"&before={before}"
        try:
            d = get(url)
        except urllib.error.HTTPError as e:
            print(f"WARN: archived -> {e.code}", file=sys.stderr)
            break
        for t in d["threads"]:
            threads.setdefault(t["id"], t)
        if not d.get("has_more") or not d["threads"]:
            break
        before = d["threads"][-1]["thread_metadata"]["archive_timestamp"]
    return tags, list(threads.values())


def llm_summarize(rows_cerrados, rows_activos, start, now):
    """Pide al modelo el digest final. Devuelve texto o None si falla."""
    key = os.environ.get("NAN_API_KEY") or os.environ.get("NAN_BUILDERS_API_KEY")
    if not key:
        for env_path in ("/opt/hermes-agent-data/.env", "/opt/data/.env"):
            if os.path.isfile(env_path):
                for line in open(env_path).read().splitlines():
                    if line.startswith(("NAN_API_KEY=", "NAN_BUILDERS_API_KEY=")):
                        key = line.split("=", 1)[1].strip()
                        break
                if key:
                    break
    if not key:
        print("WARN: sin NAN_API_KEY ni NAN_BUILDERS_API_KEY", file=sys.stderr)
        return None

    bloques = []
    for r in rows_cerrados:
        bloques.append(
            f"### CERRADO — {r['name']}\nResponsable: {r['who'] or 'sin tag'}\n"
            f"Cuerpo del ticket:\n{r.get('cuerpo') or '(sin cuerpo)'}\n"
            f"Veredicto de cierre (último mensaje):\n{r['veredicto']}"
        )
    for r in rows_activos:
        bloques.append(
            f"### ABIERTO — {r['name']}\nResponsable: {r['who'] or 'sin tag'}\n"
            f"Cuerpo del ticket:\n{r.get('cuerpo') or '(sin cuerpo)'}\n"
            f"Actividad reciente:\n{r['veredicto'][:600]}"
        )
    material = "\n\n".join(bloques)

    prompt = f"""Eres el redactor del resumen diario de tickets técnicos de NeuralCrew Labs.
Ventana: {start:%d-%b %H:%M} → {now:%d-%b %H:%M} (Bogotá). Abajo tienes cada ticket
que tuvo movimiento en la ventana, con su estado y su último mensaje.

REGLAS (estrictas):
- Español, directo, cero relleno. No inventes: usa SOLO el material.
- Formato de salida EXACTO (sin texto antes ni después):

🛠️ Tickets {start:%d-%b} → {now:%d-%b} · N cerrados · M abiertos

✅ CERRADOS
• <nombre corto del ticket> (<responsable>) — <qué se hizo/resultado, MÁXIMO 12 palabras>
(repetir por cada ticket cerrado)

🟡 ABIERTOS CON MOVIMIENTO
• <nombre corto del ticket> · <responsable> — <qué es y qué falta para cerrarlo, MÁXIMO 14 palabras>
(repetir por cada ticket abierto, SIEMPRE con la descripción)

- Nombres cortos: recorta el título en el separador natural ("—" o "("), nunca a mitad de palabra.
- **Cada línea debe explicarse sola.** El lector no abre los hilos: si una línea solo dice el
  nombre del ticket, no sirve. Prohibido dejar un abierto sin descripción.
- En cerrados, di el RESULTADO (qué quedó operativo/arreglado), no "cierre del ticket".
- En abiertos, di qué bloquea o quién decide; si no hay dato, describe el objetivo del ticket.
- Si un veredicto no tiene resultado claro, escribe: — veredicto en el hilo.
- Nada de emojis adicionales, horas, contadores de mensajes ni firmas.

MATERIAL:
{material}"""

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "Redactor de resúmenes operativos. Español directo. Devuelves SOLO el texto pedido, sin comentarios."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": LLM_MAXTOK,
        "temperature": 0.2,
        "stream": True,
    }
    req = urllib.request.Request(
        "https://api.nan.builders/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/event-stream",
        },
    )
    try:
        out, t0 = [], time.time()
        with urllib.request.urlopen(req, timeout=150) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk["choices"][0].get("delta", {})
                piece = delta.get("content")
                if piece:
                    out.append(piece)
        text = "".join(out).strip()
        if time.time() - t0 > 130:
            print("WARN: LLM lento", file=sys.stderr)
        return text or None
    except Exception as e:  # noqa: BLE001 — el fallback determinista cubre todo
        print(f"WARN: LLM falló -> {e}", file=sys.stderr)
        return None


def valid_llm(text, n_cerr, n_ab):
    """Sanity check del output del modelo."""
    if not text or len(text) > MAX_MSG:
        return False
    if n_cerr and "✅ CERRADOS" not in text:
        return False
    if n_ab and "🟡 ABIERTOS" not in text:
        return False
    bullets = sum(1 for ln in text.splitlines() if ln.strip().startswith("•"))
    return bullets >= n_cerr + n_ab


def main():
    now = datetime.datetime.now(TZ)
    start = (now - datetime.timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    start_utc = start.astimezone(datetime.timezone.utc).timestamp()
    end_utc = now.astimezone(datetime.timezone.utc).timestamp()
    use_llm = "--no-llm" not in sys.argv

    tags, threads = fetch_threads()

    cerrados, activos = [], []
    for t in threads:
        try:
            msgs = get(f"{API}/channels/{t['id']}/messages?limit=50")
        except urllib.error.HTTPError:
            continue
        hit = [
            m
            for m in msgs
            if start_utc
            <= datetime.datetime.fromisoformat(m["timestamp"]).timestamp()
            <= end_utc
        ]
        if not hit:
            continue
        tnames = [tags.get(x, x) for x in t.get("applied_tags", [])]
        hit.sort(key=lambda m: m["timestamp"])
        who = [x for x in ("Chucho", "Jonathan") if x in tnames]
        row = {
            "name": short_name(t["name"]),
            "tags": tnames,
            "who": who[0] if who else "",
            "esencia": esencia(msgs),
            "cuerpo": cuerpo_ticket(msgs),
            # veredicto crudo (último mensaje del ticket) para el LLM
            "veredicto": re.sub(r"<[^>]+>", "", hit[-1]["content"])[:1500],
        }
        (cerrados if "Cerrado" in tnames else activos).append(row)

    out = None
    if use_llm and (cerrados or activos):
        txt = llm_summarize(cerrados, activos, start, now)
        if valid_llm(txt, len(cerrados), len(activos)):
            out = txt
        else:
            print("WARN: LLM inválido, uso modo determinista", file=sys.stderr)

    if out is None:
        # --- modo determinista v2 (fallback, sin extracto LLM) ---
        lines = [
            f"🛠️ Tickets {start:%d-%b} → {now:%d-%b} · {len(cerrados)} cerrados · "
            f"{len(activos)} abiertos",
            "",
        ]
        if cerrados:
            lines.append("✅ CERRADOS")
            for r in cerrados:
                quien = f" ({r['who']})" if r["who"] else ""
                cola = f" — {r['esencia']}" if r.get("esencia") else ""
                lines.append(f"• {r['name']}{quien}{cola}")
            lines.append("")
        if activos:
            lines.append("🟡 ABIERTOS CON MOVIMIENTO")
            for r in activos:
                quien = f" · {r['who']}" if r["who"] else ""
                cola = f" — {r['esencia']}" if r.get("esencia") else ""
                lines.append(f"• {r['name']}{quien}{cola}")
            lines.append("")
        if not cerrados and not activos:
            lines.append("Sin movimiento de tickets en la ventana ✅")
        out = "\n".join(lines).rstrip() + "\n"

    if len(out) > MAX_MSG:
        out = out[: MAX_MSG - 1] + "…\n"
    sys.stdout.write(out)


if __name__ == "__main__":
    main()

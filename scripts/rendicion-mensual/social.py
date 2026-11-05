#!/usr/bin/env python3
"""social.py — captura de estadísticas de Facebook e Instagram vía Graph API
para la rendición mensual (Golden Game · The Grand Paradise Club).

Credenciales (REGLA DURA: nunca inventar; lo que la API no da, sale sin_dato):
  FB : page access token de larga vida por marca
       (/opt/data/secrets/rendicion_social_pages.json, obtenidos de la conexión
       Composio 'facebook_uncite-skyish' — Jonathan Parra, admin de ambas páginas).
       Verificado en vivo 2026-11-04: los tokens leen page insights
       (page_media_view, page_total_media_view_unique, page_follows).
  IG : la conexión FB NO trae instagram_basic (el campo instagram_business_account
       viene silenciado), y el token de system user de Meta Ads expiró (19-oct-26).
       Por defecto se consulta IG a través de las conexiones Composio
       'instagram_demal-molala' (Golden) y 'instagram_scot-linked' (Paradise) vía
       MCP (graph.instagram.com), con la consumer key del gateway
       (/opt/data/secrets/composio_consumer.key o env COMPOSIO_KEY).
       Si algún día hay un token IG directo, se pone como "ig_token" en la config
       y se usa graph.instagram.com sin pasar por Composio.

Definiciones (reversa del export manual de octubre 2026, ver cross-check en README):
  - "visualizaciones" del export Business Suite ≈ vistas del contenido publicado
    en el mes (posts + reels, lifetime), no la suma calendario de page_media_view.
  - Stories del mes NO son recuperables por API (expiran; /stories vacío y sin
    insights) → la cifra API queda levemente por debajo del export manual.
  - "espectadores" (uniques deduplicados del mes) y "% no seguidores" (breakdown
    is_from_followers) NO están expuestos en Page insights vía API → sin_dato.

Uso CLI (debug / cross-check):
  python3 social.py --marca golden --mes 2026-10 --json
  python3 social.py --marca lucky  --mes 2026-10
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = os.environ.get("RENDICION_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GIG = f"https://graph.instagram.com/{GRAPH_VERSION}"
BOGOTA = dt.timezone(dt.timedelta(hours=-5))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("RENDICION_SOCIAL_CONFIG",
                        "/opt/data/secrets/rendicion_social_pages.json")
COMPOSIO_MCP = os.environ.get("COMPOSIO_MCP_URL", "https://connect.composio.dev/mcp")
COMPOSIO_KEY_FILE = os.environ.get("COMPOSIO_KEY_FILE",
                                   "/opt/data/secrets/composio_consumer.key")


class SocialError(Exception):
    """Fallo de fuente social (sin datos → sin_dato en facts)."""


# ------------------------------------------------------------------ config
def _cfg():
    if not os.path.exists(CONFIG):
        raise SocialError(f"config social no encontrada: {CONFIG}")
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    if "golden" not in cfg or "lucky" not in cfg:
        raise SocialError(f"config social sin marcas golden/lucky: {CONFIG}")
    return cfg


def month_bounds(year, month):
    """(epoch_since, epoch_until_exclusivo) del mes en hora Bogotá."""
    start = dt.datetime(year, month, 1, tzinfo=BOGOTA)
    y2, m2 = (year + 1, 1) if month == 12 else (year, month + 1)
    end = dt.datetime(y2, m2, 1, tzinfo=BOGOTA)
    return int(start.timestamp()), int(end.timestamp())


def prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ------------------------------------------------------------------ graph fb
def _gget(node, token, **params):
    params["access_token"] = token
    url = f"{GRAPH}/{node}?{urllib.parse.urlencode(params)}"
    try:
        return json.load(urllib.request.urlopen(url, timeout=30))
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", {}).get("message", "")[:160]
        except Exception:
            msg = str(e)[:160]
        raise SocialError(f"Graph API {node}: {msg}") from None
    except Exception as e:
        raise SocialError(f"Graph API {node}: {e}") from None


def _paged(node, token, **params):
    out = []
    while True:
        r = _gget(node, token, **params)
        out.extend(r.get("data") or [])
        nxt = (r.get("paging") or {}).get("next")
        if not nxt or len(out) > 1000:
            break
        url = nxt + "&access_token=" + urllib.parse.quote(token)
        try:
            r = json.load(urllib.request.urlopen(url, timeout=30))
        except Exception as e:
            raise SocialError(f"Graph API paging {node}: {e}") from None
        out.extend(r.get("data") or [])
        if not (r.get("paging") or {}).get("next"):
            break
    return out


def _views_of(oid, token):
    """Vistas lifetime de un objeto de contenido FB.
    posts → post_media_view; videos/reels → campo 'views'. None si no expone.
    Los objetos reel no exponen /insights: se captura y se cae al campo views."""
    try:
        r = _gget(f"{oid}/insights", token, metric="post_media_view")
    except SocialError:
        r = {}
    data = r.get("data") or []
    if data and data[0].get("values"):
        v = data[0]["values"][0].get("value")
        if isinstance(v, (int, float)):
            return int(v)
    try:
        r = _gget(oid, token, fields="id,views")
    except SocialError:
        return None
    if isinstance(r.get("views"), (int, float)):
        return int(r["views"])
    return None


def _content_views(page_id, token, year, month):
    """Vistas lifetime del contenido publicado en el mes (posts + reels).
    Dedup por (fecha, vistas) para no contar dos veces un video publicado como
    post y como reel (mismo contenido, mismo número de vistas)."""
    since, until = month_bounds(year, month)
    mm = f"{year}-{month:02d}"
    seen, items = set(), []
    for edge in ("posts", "video_reels", "videos"):
        for x in _paged(f"{page_id}/{edge}", token, fields="id,created_time",
                        since=since, until=until, limit=100):
            if x["id"] in seen or x.get("created_time", "")[:7] != mm:
                continue
            seen.add(x["id"])
            items.append(x)
    by_date = {}
    for x in items:
        v = _views_of(x["id"], token)
        if v is None:
            continue
        by_date.setdefault(x["created_time"][:10], set()).add(v)
    # dedup: si un post y su reel comparten fecha y exactamente las mismas
    # vistas, es el mismo contenido → contar cada valor una vez por fecha
    return sum(v for vals in by_date.values() for v in vals), len(items)


def _daily_sum(page_id, token, metric, year, month):
    since, until = month_bounds(year, month)
    r = _gget(f"{page_id}/insights", token, metric=metric, period="day",
              since=since, until=until)
    data = r.get("data") or []
    if not data or not data[0].get("values"):
        return None
    return sum(int(v["value"]) for v in data[0]["values"])


def facebook(marca, year, month):
    """Cifras de Facebook Page del mes para golden|lucky.
    Devuelve dict con visualizaciones (contenido del mes), variación vs mes
    anterior (misma métrica) y los sin_dato estructurales de la API."""
    cfg = _cfg()[marca]
    page_id, token = cfg["page_id"], cfg["page_token"]
    out = {"fuente": "graph_api", "version_api": GRAPH_VERSION,
           "metrica": "vistas lifetime del contenido publicado en el mes (posts+reels, dedup)"}
    views, n_items = _content_views(page_id, token, year, month)
    out["visualizaciones"] = views
    out["contenido_del_mes"] = n_items
    # suma calendario oficial (page_media_view, reemplaza page_impressions)
    try:
        out["visualizaciones_calendario"] = _daily_sum(page_id, token,
                                                       "page_media_view", year, month)
    except SocialError as e:
        out["visualizaciones_calendario"] = None
        out["motivo_calendario"] = str(e)
    # espectadores: la API solo da uniques DIARIOS; el dedup mensual de
    # Business Suite no está expuesto → se reporta la suma diaria y el sin_dato
    try:
        out["espectadores_diario_suma"] = _daily_sum(
            page_id, token, "page_total_media_view_unique", year, month)
    except SocialError as e:
        out["espectadores_diario_suma"] = None
    out["espectadores"] = None
    out["motivo_espectadores"] = ("Page insights no expone el dedup mensual de "
                                  "espectadores de Business Suite (solo uniques diarios)")
    # % no seguidores: breakdown is_from_followers no soportado vía API
    out["no_seguidores_pct"] = None
    out["motivo_no_seguidores"] = ("breakdown is_from_followers no soportado en "
                                   "Page insights vía Graph API")
    # variación vs mes anterior con la MISMA métrica
    py, pm = prev_month(year, month)
    try:
        prev_views, _ = _content_views(page_id, token, py, pm)
        out["variacion_pct"] = round((views - prev_views) / prev_views * 100, 1) if prev_views else None
        out["visualizaciones_mes_anterior"] = prev_views
    except SocialError as e:
        out["variacion_pct"] = None
        out["motivo_variacion"] = f"mes anterior ({py}-{pm:02d}): {e}"
    return out


# ------------------------------------------------------------------ instagram
def _composio_key():
    k = os.environ.get("COMPOSIO_KEY")
    if k:
        return k
    if os.path.exists(COMPOSIO_KEY_FILE):
        return open(COMPOSIO_KEY_FILE).read().strip()
    raise SocialError("sin COMPOSIO_KEY (env ni " + COMPOSIO_KEY_FILE + ")")


def _mcp_multi(tools):
    """Llama COMPOSIO_MULTI_EXECUTE_TOOL por MCP-over-HTTP (stdlib)."""
    key = _composio_key()
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
        "arguments": {"tools": tools, "sync_response_to_workbench": False}}}
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream",
         "x-consumer-api-key": key}
    req = urllib.request.Request(COMPOSIO_MCP, data=json.dumps(payload).encode(), headers=h)
    try:
        body = urllib.request.urlopen(req, timeout=120).read().decode()
    except Exception as e:
        raise SocialError(f"Composio MCP: {e}") from None
    if "\ndata:" in body or body.startswith("data:"):
        for line in body.split("\n"):
            if line.startswith("data:"):
                body = line[5:].strip()
                break
    try:
        outer = json.loads(body)
        inner = json.loads(outer["result"]["content"][0]["text"])
    except Exception as e:
        raise SocialError(f"Composio MCP respuesta ilegible: {e}: {body[:200]}") from None
    if not inner.get("successful", True):
        raise SocialError(f"Composio MCP error: {json.dumps(inner)[:200]}")
    return (inner.get("data") or {}).get("results") or []


def _ig_insights(account, ig_user_id, metric, metric_type, year, month):
    since, until = month_bounds(year, month)
    args = {"ig_user_id": ig_user_id, "metric": metric, "period": "day",
            "since": str(since), "until": str(until)}
    if metric_type:
        args["metric_type"] = metric_type
    res = _mcp_multi([{"tool_slug": "INSTAGRAM_GET_USER_INSIGHTS",
                       "account": account, "arguments": args}])
    data = (res[0].get("response") or {}).get("data") or {}
    return data.get("data") or []


def instagram(marca, year, month):
    """Cifras de Instagram Business del mes: publicaciones, alcance,
    interacción y seguidores ganados. Real o SocialError (→ sin_dato)."""
    cfg = _cfg()[marca]
    account, ig_user_id = cfg["ig_composio_account"], cfg["ig_user_id"]
    out = {"fuente": "graph_api_via_composio", "version_api": GRAPH_VERSION,
           "ig_user_id": ig_user_id}

    # alcance + interacción (total_value del mes)
    rows = _ig_insights(account, ig_user_id,
                        ["reach", "total_interactions", "accounts_engaged"],
                        "total_value", year, month)
    for m in rows:
        tv = m.get("total_value") or {}
        v = tv.get("value")
        if m.get("name") == "reach" and isinstance(v, (int, float)):
            out["alcance"] = int(v)
        if m.get("name") == "total_interactions" and isinstance(v, (int, float)):
            out["interaccion"] = int(v)

    # seguidores ganados (follower_count diario = deltas de seguidores)
    rows = _ig_insights(account, ig_user_id, ["follower_count"], None, year, month)
    gains = [int(v["value"]) for m in rows if m.get("name") == "follower_count"
             for v in (m.get("values") or []) if isinstance(v.get("value"), (int, float))]
    out["seguidores_ganados"] = sum(gains) if gains else None
    if not gains:
        out["motivo_seguidores"] = "sin serie follower_count para el mes"

    # publicaciones del mes (media paginado hasta cubrir el mes completo)
    until = month_bounds(year, month)[1]
    media, after, guard = [], None, 0
    covered = False
    while not covered and guard < 10:
        guard += 1
        args = {"ig_user_id": ig_user_id, "fields": "id,timestamp", "limit": 100}
        if after:
            args["after"] = after
        res = _mcp_multi([{"tool_slug": "INSTAGRAM_GET_IG_USER_MEDIA",
                           "account": account, "arguments": args}])
        data = (res[0].get("response") or {}).get("data") or {}
        media.extend(data.get("data") or [])
        after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
        mm = f"{year}-{month:02d}"
        if not media or not after or media[-1].get("timestamp", "")[:7] != mm:
            covered = True
    mm = f"{year}-{month:02d}"
    out["publicaciones"] = sum(1 for x in media if x.get("timestamp", "")[:7] == mm)
    return out


# ------------------------------------------------------------------ CLI
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--marca", required=True, choices=["golden", "lucky"])
    ap.add_argument("--mes", default=None, help="YYYY-MM (default: mes anterior)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    hoy = dt.datetime.now(BOGOTA).date()
    if a.mes:
        y, m = a.mes.split("-")
        year, month = int(y), int(m)
    else:
        first = hoy.replace(day=1)
        prev = (first - dt.timedelta(days=1))
        year, month = prev.year, prev.month
    res = {"marca": a.marca, "mes": f"{year}-{month:02d}"}
    for name, fn in (("facebook", facebook), ("instagram", instagram)):
        try:
            res[name] = fn(a.marca, year, month)
        except SocialError as e:
            res[name] = {"sin_dato": True, "motivo": str(e)}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(f"== {a.marca} {year}-{month:02d} ==")
        for k in ("facebook", "instagram"):
            d = res[k]
            if d.get("sin_dato"):
                print(f"  {k}: SIN_DATO — {d['motivo']}")
                continue
            if k == "facebook":
                print(f"  facebook: visualizaciones={d['visualizaciones']} "
                      f"(contenido del mes, {d['contenido_del_mes']} items) · "
                      f"calendario={d.get('visualizaciones_calendario')} · "
                      f"var={d.get('variacion_pct')}% · "
                      f"espectadores=sin_dato (suma diaria "
                      f"{d.get('espectadores_diario_suma')}) · "
                      f"no_seguidores=sin_dato")
            else:
                print(f"  instagram: publicaciones={d['publicaciones']} · "
                      f"alcance={d.get('alcance')} · interaccion={d.get('interaccion')} · "
                      f"seguidores_ganados={d.get('seguidores_ganados')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

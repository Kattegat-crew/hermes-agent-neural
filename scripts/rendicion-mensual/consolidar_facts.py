#!/usr/bin/env python3
"""consolidar_facts.py — compila facts_<marca>.json del mes anterior.

REGLA DURA (KANBAN gate 1): ninguna cifra se inventa. Todo campo que no se
pueda obtener de una fuente real sale con {"sin_dato": true} y su motivo.

Fuentes que este compilador intenta solo (verificado en nov 2026):
  1. Bre-B              -> hojas 'Bre-B <Marca> — Pagos' (Drive, tabs Informe <Mes>)
  2. Ventas por sede    -> hoja consolidada mensual '<MM-YY> ventas <marca>' en Drive
                           (patrón del oct: '10-26 ventas golden'). Si la hoja no está
                           visible con las credenciales disponibles, queda sin_dato.
  3. Meta Ads           -> export manual: inputs/meta_ads_<slug>.json (schema en README)
  4. Search Console     -> export manual: inputs/gsc_<slug>.json
  5. Redes FB/IG        -> export manual Business Suite: inputs/business_suite_<slug>.csv
  6. Agentes/horas      -> export manual CRM: inputs/agentes_<slug>.json

Uso: python3 consolidar_facts.py [--mes 2026-10] [--brand golden,lucky]
                                 [--outdir DIR] [--inputs DIR] [--verbose]
Salida: <outdir>/facts_<slug>.json (estructura idéntica a la de octubre 2026).
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_gdrive import BREB_SHEETS, drive_search, sheet_tabs, sheet_values  # noqa: E402
import social as social_mod  # noqa: E402  (Graph API FB/IG; creds en secrets)

BOGOTA = zoneinfo.ZoneInfo("America/Bogota")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MARCAS = {
    "golden": {"nombre": "Golden Game Casinos", "slug": "golden", "conn": "golden-drive",
               "alias_ventas": "ventas golden", "breb_alias": "golden"},
    "lucky": {"nombre": "The Grand Paradise Club · Lucky Brothers", "slug": "paradise",
              "conn": "lucky-drive", "alias_ventas": "ventas lucky", "breb_alias": "lucky"},
}

MESES_ES = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
            12: "Diciembre"}


def parse_num(s):
    """Convierte '$ 1.234.567,89' / '1234567' / '1,234,567' / '50.429.800' a float.
    Convención es-CO: punto = miles, coma = decimal (decide el último separador)."""
    if s is None:
        return None
    t = str(s).strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not t or t.lower() in ("n/a", "na", "-", "sin dato"):
        return None
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        parts = t.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            t = t.replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "." in t:
        parts = t.split(".")
        # todo grupo intermedio/final de 3 dígitos => separador de miles (es-CO)
        if len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
            t = "".join(parts)
        else:
            t = t  # decimal puro (ej. fecha serial 46266.42708)
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return None


def fmt_cop(v):
    return "$" + f"{round(v):,}".replace(",", ".")


def fmt_pct(v):
    return f"{round(v, 1):.1f}".replace(".", ",") + "%"


class SinDato(Exception):
    pass


def dato(cid, valor, display=None, nota=None):
    d = {"id": cid, "display": display if display is not None else str(valor),
         "valor": valor}
    if nota:
        d["nota"] = nota
    return d


def sin_dato(cid, motivo):
    return {"id": cid, "sin_dato": True, "motivo": motivo}


# ---------------------------------------------------------------- collectors
def collect_breb(conn, mes, alias):
    """Lee la hoja Bre-B del mes (tab 'Informe <Mes>') y del mes anterior.
    Devuelve (dict_mes_actual, dict_mes_anterior|None)."""
    sid = BREB_SHEETS[alias]
    tabs = sheet_tabs(conn, sid)
    mes_es = MESES_ES[mes.month]
    prev_y, prev_m = (mes.year - 1, 12) if mes.month == 1 else (mes.year, mes.month - 1)
    prev_es = MESES_ES[prev_m]

    def read_tab(nombre):
        # tabla izquierda 'POR DÍA | Pagos | Total' (rango A1:C100): conteo exacto
        rows = sheet_values(conn, sid, f"'{nombre}'!A1:C100")
        if not rows:
            raise SinDato(f"tab '{nombre}' vacía")
        pagos = 0
        suma_dias = 0.0
        total = None
        periodo = None
        for r in rows:
            joined = " ".join(str(c) for c in r)
            if "TOTAL RECAUDADO" in joined.upper() and total is None:
                # formato verificado: ['TOTAL RECAUDADO', ' $50.429.800', ...]
                for c in r[1:]:
                    total = parse_num(c)
                    if total:
                        break
            if "PERÍODO" in joined.upper() or "PERIODO" in joined.upper():
                for c in r[1:]:
                    if c and not parse_num(c):
                        periodo = str(c).strip()
                        break
            if r and re.match(r"\d{4}-\d{2}-\d{2}", str(r[0]).strip()) and len(r) >= 2:
                pagos += int(parse_num(r[1]) or 0)
                suma_dias += parse_num(r[2]) or 0
        if total is None:
            # la celda TOTAL RECAUDADO vive en la banda izquierda; si no apareció en
            # A1:C100, leer de nuevo con rango más ancho
            rows2 = sheet_values(conn, sid, f"'{nombre}'!A1:J50")
            for r in rows2:
                if r and "TOTAL RECAUDADO" in " ".join(str(c) for c in r).upper():
                    for c in r[1:]:
                        total = parse_num(c)
                        if total:
                            break
                if total:
                    break
        if total is None:
            raise SinDato(f"tab '{nombre}' sin 'TOTAL RECAUDADO'")
        if pagos and abs(suma_dias - total) > max(1.0, total * 0.001):
            # el total oficial manda; el desajuste se reporta, no se inventa
            raise SinDato(f"tab '{nombre}': suma diaria ({suma_dias:,.0f}) no cuadra con "
                          f"TOTAL RECAUDADO ({total:,.0f}) — revisar hoja")
        out = {"total": total, "pagos": pagos, "periodo": periodo or nombre,
               "fuente": f"hoja Bre-B '{alias.title()}' tab '{nombre}'"}
        if pagos:
            out["ticket"] = round(total / pagos)
        return out

    tab_actual = next((t for t in tabs if mes_es.lower() in t.lower()
                       and "informe" in t.lower()), None)
    actual = read_tab(tab_actual) if tab_actual else None
    prev_tab = next((t for t in tabs if prev_es.lower() in t.lower()
                     and "informe" in t.lower()), None)
    previo = read_tab(prev_tab) if prev_tab else None
    return actual, previo


def collect_ventas_sheet(conn, mes, alias_ventas):
    """Busca la hoja consolidada mensual de ventas y la parsea de forma genérica.
    Patrón oct: '10-26 ventas golden' (MM-YY ventas <alias>)."""
    mm_yy = f"{mes.month:02d}-{str(mes.year)[2:]}"
    candidatos = drive_search(conn, f"name contains '{alias_ventas}' and "
                                    f"mimeType = 'application/vnd.google-apps.spreadsheet'")
    elegida = None
    for f in candidatos:
        if mm_yy in f["name"].lower().replace(" ", "") or mm_yy in f["name"]:
            elegida = f
            break
    if elegida is None and len(candidatos) == 1:
        elegida = candidatos[0]
    if elegida is None:
        raise SinDato(f"hoja consolidada '{mm_yy} {alias_ventas}' no visible en Drive "
                      f"({len(candidatos)} candidatos)")
    # datos por tab: probar primer tab
    tabs = sheet_tabs(conn, elegida["id"])
    tab = tabs[0]
    rows = sheet_values(conn, elegida["id"], f"'{tab}'!A1:Z800")
    sedes = []
    totals = {}
    colmap = {}  # índices de venta/meta relativos a r[1:], mapeados por encabezado
    for r in rows:
        if not r or not r[0]:
            continue
        c0 = str(r[0]).strip()
        up = c0.upper()
        fila_txt = " ".join(str(x).upper() for x in r if x)
        # fila de encabezado: mapear columnas por nombre (p.ej. SEDE|META MENSUAL|ACUMULADO|...)
        if up in ("SEDE", "SALAS", "SALA", "LOCAL", "SEDES") or \
           ("META" in fila_txt and ("ACUMULADO" in fila_txt or "VENTA" in fila_txt) and not any(parse_num(x) is not None for x in r[1:])):
            colmap = {}
            for i, c in enumerate(r[1:]):
                cu = str(c).upper()
                if "ACUMULADO" in cu or "VENTA" in cu:
                    colmap.setdefault("venta", i)
                elif "META" in cu:
                    colmap.setdefault("meta", i)
            continue
        nums = [parse_num(c) for c in r[1:] if c not in (None, "")]
        nums = [n for n in nums if n is not None]
        if "TOTAL" in up and len(nums) >= 1:
            totals[up] = nums
            continue
        # fila de sede: nombre + al menos un número
        if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", c0) and nums:
            if colmap:
                def at(key):
                    i = colmap.get(key)
                    if i is None:
                        return None
                    n = parse_num(r[1 + i]) if len(r) > 1 + i else None
                    return n
                venta = at("venta")
                meta = at("meta")
                if venta is None:  # celda vacía en la columna mapeada
                    continue
            else:
                venta = nums[0]
                meta = nums[1] if len(nums) > 1 else None
            row = {"nombre": c0, "venta": round(venta)}
            if meta:
                row["meta"] = round(meta)
                row["cumplimiento"] = round(venta / meta * 100, 1)
                row["estado"] = "ALCANZADA" if venta >= meta else "NO ALCANZADA"
            sedes.append(row)
    if not sedes:
        raise SinDato(f"hoja '{elegida['name']}' tab '{tab}': no se pudo identificar filas de sede")
    return {"hoja": elegida["name"], "tab": tab, "sedes": sedes, "totals": totals}


def load_input(inputs_dir, slug, kind):
    """Carga un export manual si existe; si no, sin_dato."""
    if kind == "meta_ads":
        p = os.path.join(inputs_dir, f"meta_ads_{slug}.json")
    elif kind == "gsc":
        p = os.path.join(inputs_dir, f"gsc_{slug}.json")
    elif kind == "agentes":
        p = os.path.join(inputs_dir, f"agentes_{slug}.json")
    elif kind == "social":
        p = os.path.join(inputs_dir, f"business_suite_{slug}.csv")
    else:
        raise ValueError(kind)
    if not os.path.exists(p):
        raise SinDato(f"sin export en {os.path.basename(p)} (fuente manual)")
    if kind == "social":
        with open(p, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------- build facts
def build_facts(brand, mes, inputs_dir, verbose=False):
    m = MARCAS[brand]
    slug = m["slug"]
    conn = m["conn"]
    mes_str = f"{mes.year}-{mes.month:02d}-01..{mes.year}-{mes.month:02d}-28/31"
    F = {"marca": m["nombre"], "slug": slug, "periodo": mes_str,
         "fuente_datos": "", "cifras": [], "sedes": [], "mes": {}, "comparativo_sep": {}}
    pendientes = []

    # --- Bre-B (fuente real)
    breb = breb_prev = None
    try:
        breb, breb_prev = collect_breb(conn, mes, m["breb_alias"])
    except Exception as e:
        pendientes.append(f"breb_total: {e}")
        F["cifras"].append(sin_dato("breb_total", str(e)))
        F["cifras"].append(sin_dato("breb_ticket", "depende de breb_total"))
    else:
        nota = f"{breb['pagos']} pagos"
        if breb_prev and breb_prev.get("ticket"):
            d = (breb["ticket"] / breb_prev["ticket"] - 1) * 100
            prev_nombre = MESES_ES[mes.month - 1 if mes.month > 1 else 12].lower()
            nota += (f" · {'+' if d >= 0 else '−'}{fmt_pct(abs(d))[:-1]}% ticket vs {prev_nombre}"
                     f" ({fmt_cop(breb_prev['ticket'])})")
        F["cifras"].append(dato("breb_total", breb["total"], fmt_cop(breb["total"]), nota))
        if breb.get("ticket"):
            F["cifras"].append(dato("breb_ticket", breb["ticket"], fmt_cop(breb["ticket"]),
                                    f"fuente: {breb['fuente']}"))

    # --- Ventas por sede (hoja consolidada)
    ventas = None
    try:
        ventas = collect_ventas_sheet(conn, mes, m["alias_ventas"])
    except Exception as e:
        pendientes.append(f"ventas_netas: {e}")
        for cid in ("ventas_netas", "meta_ventas", "cumplimiento"):
            F["cifras"].append(sin_dato(cid, str(e)))
    else:
        F["sedes"] = ventas["sedes"]
        total = sum(s["venta"] for s in ventas["sedes"])
        F["cifras"].append(dato("ventas_netas", total, fmt_cop(total),
                                f"neto {MESES_ES[mes.month].lower()}, {len(ventas['sedes'])} salas · "
                                f"fuente: {ventas['hoja']}"))
        metas = [s["meta"] for s in ventas["sedes"] if "meta" in s]
        if metas:
            meta_total = sum(metas)
            F["cifras"].append(dato("meta_ventas", meta_total, fmt_cop(meta_total)))
            F["cifras"].append(dato("cumplimiento", round(total / meta_total * 100, 1),
                                    fmt_pct(total / meta_total * 100)))
        else:
            F["cifras"].append(sin_dato("meta_ventas", "sin columna de meta en la hoja"))
            F["cifras"].append(sin_dato("cumplimiento", "depende de meta_ventas"))

    # --- Meta Ads (export manual vía Composio/buscador)
    try:
        ads = load_input(inputs_dir, slug, "meta_ads")
        F["cifras"].append(dato("ads_total", ads["spend"], fmt_cop(ads["spend"]),
                                ads.get("nota", "fuente: export Meta Ads")))
        F["cifras"].append(dato("ads_leads", ads["leads"], f"{ads['leads']} leads",
                                ads.get("nota_leads", "")))
    except Exception as e:
        pendientes.append(f"ads_total: {e}")
        F["cifras"].append(sin_dato("ads_total", str(e)))
        F["cifras"].append(sin_dato("ads_leads", "depende de ads_total"))

    # --- Search Console
    try:
        gsc = load_input(inputs_dir, slug, "gsc")
        F["cifras"].append(dato("organico", gsc["impresiones"], f"{gsc['impresiones']} impresiones",
                                f"{gsc['clics']} clics · CTR {gsc.get('ctr', 'n/d')} (Search Console)"))
    except Exception as e:
        pendientes.append(f"organico: {e}")
        F["cifras"].append(sin_dato("organico", str(e)))

    # --- Redes FB/IG (1º Graph API con fuente=graph_api; 2º export manual en
    # inputs/; 3º sin_dato). social.py NUNCA inventa: lo que la API no expone
    # (espectadores dedup, % no seguidores, stories) sale documentado.
    def _mil(v):
        return f"{v / 1000:.1f}".replace(".", ",") + " mil"

    def _export_social():
        """Del CSV de export manual: (facebook_views, instagram_followers) o (None, None)."""
        fb = ig = None
        for row in load_input(inputs_dir, slug, "social"):
            if row.get("facebook_views"):
                fb = int(row["facebook_views"])
            if row.get("instagram_followers"):
                ig = int(row["instagram_followers"])
        return fb, ig

    # Facebook
    try:
        fb = social_mod.facebook(brand, mes.year, mes.month)
        nota = (f"fuente: Graph API {fb['version_api']} — vistas lifetime del contenido "
                f"publicado en el mes ({fb['contenido_del_mes']} posts/reels)")
        if fb.get("variacion_pct") is not None:
            nota += (f" · {fb['variacion_pct']:+.1f}% vs mes anterior (misma métrica "
                     f"API: {fb['visualizaciones_mes_anterior']})")
        else:
            nota += f" · variación sin dato ({fb.get('motivo_variacion', 'n/d')})"
        nota += " · espectadores y % no seguidores: no expuestos por la API"
        try:
            fb_export, _ = _export_social()
            if fb_export:
                fb_export = int(fb_export)
                brecha = (fb["visualizaciones"] - fb_export) / fb_export * 100
                nota += (f" · export manual de referencia: {fb_export} (brecha "
                         f"{brecha:+.1f}%; la API no cubre stories del mes)")
        except Exception:
            pass
        e = dato("facebook", fb["visualizaciones"],
                 f"{_mil(fb['visualizaciones'])} visualizaciones", nota)
        e["fuente"] = "graph_api"
        F["cifras"].append(e)
    except (social_mod.SocialError, Exception) as e_api:
        try:
            fb_export, _ = _export_social()
            if not fb_export:
                raise SinDato("export sin facebook_views")
            e = dato("facebook", fb_export, f"{_mil(fb_export)} visualizaciones",
                     "fuente: export Business Suite (Graph API falló)")
            e["fuente"] = "export_business_suite"
            F["cifras"].append(e)
        except Exception as e_exp:
            F["cifras"].append(sin_dato(
                "facebook", f"Graph API: {e_api} · export manual: {e_exp}"))

    # Instagram (4 métricas reales; entrada 'instagram' = seguidores ganados,
    # compatible con el placeholder de octubre)
    try:
        ig = social_mod.instagram(brand, mes.year, mes.month)
        nota = (f"fuente: Graph API (Instagram) vía Composio · "
                f"{ig['publicaciones']} publicaciones · alcance {ig.get('alcance')} · "
                f"{ig.get('interaccion')} interacciones")
        sg = ig.get("seguidores_ganados")
        if sg is None:
            raise SinDato(ig.get("motivo_seguidores", "sin serie de seguidores"))
        e = dato("instagram", sg, f"{sg} nuevos seguidores", nota)
        e["fuente"] = "graph_api_via_composio"
        F["cifras"].append(e)
        for cid, key, disp in (("instagram_publicaciones", "publicaciones", "publicaciones"),
                               ("instagram_alcance", "alcance", "alcance"),
                               ("instagram_interaccion", "interaccion", "interacciones")):
            v = ig.get(key)
            if v is not None:
                F["cifras"].append(dato(cid, v, f"{v} {disp}", "fuente: Graph API (Instagram)"))
            else:
                F["cifras"].append(sin_dato(cid, "no expuesto por la API para el mes"))
    except (social_mod.SocialError, SinDato) as e_api:
        try:
            _, ig_export = _export_social()
            if ig_export is None:
                raise SinDato("export sin instagram_followers")
            e = dato("instagram", ig_export, f"{ig_export} seguidores",
                     "fuente: export Business Suite (Graph API falló)")
            e["fuente"] = "export_business_suite"
            F["cifras"].append(e)
        except Exception as e_exp:
            F["cifras"].append(sin_dato(
                "instagram", f"Graph API: {e_api} · export manual: {e_exp}"))

    # --- Agentes / horas (CRM)
    try:
        ag = load_input(inputs_dir, slug, "agentes")
        F["cifras"].append(dato("agentes", ag["tareas"], f"{ag['tareas']:,} tareas".replace(",", "."),
                                ag.get("nota", "fuente: export CRM")))
        if ag.get("horas"):
            F["cifras"].append(dato("automatizacion_horas", ag["horas"], f"{ag['horas']} horas",
                                    "solo horas medibles"))
        else:
            F["cifras"].append(sin_dato("automatizacion_horas", "export CRM sin horas"))
    except Exception as e:
        pendientes.append(f"agentes: {e}")
        F["cifras"].append(sin_dato("agentes", str(e)))
        F["cifras"].append(sin_dato("automatizacion_horas", "depende de agentes"))

    # --- mes.* (ingresos brutos, pagos, jackpot, mejor/peor día, reportes)
    if ventas:
        # del bloque de totales de la hoja si existe; si no, sin_dato
        if ventas["totals"]:
            F["mes"] = {"sin_dato_parcial": True,
                        "nota": f"totales crudos disponibles en hoja '{ventas['hoja']}', "
                                "requieren mapeo revisado antes de usarse en pantalla"}
        else:
            F["mes"] = {"sin_dato": True, "motivo": "la hoja de ventas no expone totales del mes"}
    else:
        F["mes"] = {"sin_dato": True, "motivo": "sin hoja de ventas del mes"}

    # --- comparativo mes anterior (Bre-B real si está; ventas sin_dato)
    comp = {}
    if breb_prev:
        comp["breb_total"] = breb_prev["total"]
        if breb_prev.get("pagos"):
            comp["breb_pagos"] = breb_prev["pagos"]
        if breb_prev.get("ticket"):
            comp["breb_ticket"] = breb_prev["ticket"]
    comp_faltan = [k for k in ("ventas_netas", "cumplimiento") if k not in comp]
    if comp_faltan:
        prev_y, prev_m = (mes.year - 1, 12) if mes.month == 1 else (mes.year, mes.month - 1)
        comp["sin_dato"] = True
        comp["motivo"] = (f"sin datos consolidados de {MESES_ES[prev_m]} "
                          f"{prev_y} para: {', '.join(comp_faltan)}")
    F["comparativo_sep"] = comp  # clave heredada del schema oct; contenido = mes anterior

    F["fuente_datos"] = (
        f"Bre-B {m['breb_alias'].title()} (Drive) · hoja consolidada de ventas (Drive) · "
        "Meta Ads / Search Console / Business Suite vía exports en inputs/ · "
        f"{len(pendientes)} campo(s) sin dato")
    F["pendientes"] = pendientes
    F["incompleto"] = bool(pendientes)
    return F


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", default=None, help="YYYY-MM (default: mes anterior en America/Bogota)")
    ap.add_argument("--brand", default="golden,lucky")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--inputs", default=os.path.join(SCRIPT_DIR, "inputs"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    hoy = dt.datetime.now(BOGOTA).date()
    if args.mes:
        y, mo = args.mes.split("-")
        mes = dt.date(int(y), int(mo), 1)
    else:
        first = hoy.replace(day=1)
        mes = (first - dt.timedelta(days=1)).replace(day=1)

    outdir = args.outdir or os.path.join(
        "/opt/hermes-agent-data/home/proyectos/rendicion-mensual",
        f"{mes.year}-{mes.month:02d}", "facts")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(args.inputs, exist_ok=True)

    rc = 0
    for brand in args.brand.split(","):
        brand = brand.strip()
        F = build_facts(brand, mes, args.inputs, args.verbose)
        out = os.path.join(outdir, f"facts_{brand}.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(F, fh, ensure_ascii=False, indent=2)
        n_sd = sum(1 for c in F["cifras"] if c.get("sin_dato"))
        print(f"[{brand}] {out}")
        print(f"    cifras: {len(F['cifras'])} ({n_sd} sin_dato) · sedes: {len(F['sedes'])} · "
              f"incompleto={F['incompleto']}")
        for p in F["pendientes"]:
            print(f"    SIN_DATO: {p}")
        if F["incompleto"]:
            rc = 2  # incompleto pero válido: gate humano decide
    return rc


if __name__ == "__main__":
    sys.exit(main())

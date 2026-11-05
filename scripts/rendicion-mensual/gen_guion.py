#!/usr/bin/env python3
"""gen_guion.py — genera las locuciones (texto TTS por beat) y las tarjetas de pantalla
desde facts_<brand>.json. 100% facts-driven: si un campo necesario está en sin_dato,
el beat correspondiente queda marcado y el pipeline se detiene antes de gastar TTS.

Estructura de 9 beats idéntica a la de octubre 2026 (ver v2/locuciones_v2.json):
 1 ventas_netas · 2 meta_comparativo · 3 sedes · 4 breb · 5 pauta · 6 organico
 7 redes · 8 operacion · 9 cierre

uso: gen_guion.py --mes 2026-11 --facts-golden F1.json --facts-lucky F2.json --outdir DIR
Salida: DIR/locuciones.json ({"golden": [...], "paradise": [...]}) + DIR/cards_<brand>.json
"""
import argparse
import json
import os
import re
import sys

UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
            "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
            "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
            "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho",
            "veintinueve"]
DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta",
           "noventa"]
CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
            "seiscientos", "setecientos", "ochocientos", "novecientos"]


def _menor_mil(n):
    if n == 0:
        return "cero"
    if n == 100:
        return "cien"
    out = []
    c, rest = divmod(n, 100)
    if c:
        out.append(CENTENAS[c])
    if rest:
        if rest < 30:
            out.append(UNIDADES[rest])
        else:
            d, u = divmod(rest, 10)
            out.append(DECENAS[d] + (" y " + UNIDADES[u] if u else ""))
    return " ".join(out)


def numero_a_letras(n):
    """0..999.999.999.999 en español neutro (uso TTS)."""
    n = int(n)
    if n < 0:
        return "menos " + numero_a_letras(-n)
    if n < 1000:
        return _menor_mil(n)
    miles = n // 1000
    rest = n % 1000
    if miles == 1:
        out = "mil"
    elif miles < 1000:
        out = _menor_mil(miles) + " mil"
    else:
        out = numero_a_letras(miles) + " mil"
    if rest:
        out += " " + _menor_mil(rest)
    return out


def fmt_cop(v):
    return "$" + f"{round(v):,}".replace(",", ".")


def millones_es(v):
    """'284823575' -> 'doscientos ochenta y cuatro coma ocho millones' (estilo oct)."""
    m = v / 1_000_000
    ent = int(m)
    dec = round((m - ent) * 10)
    if dec >= 10:
        ent += 1
        dec = 0
    s = numero_a_letras(ent)
    if dec:
        s += " coma " + UNIDADES[dec]
    s += " millones"
    return s


def cif(F, cid):
    for c in F.get("cifras", []):
        if c["id"] == cid:
            return c
    return None


def val(F, cid):
    c = cif(F, cid)
    if c is None or c.get("sin_dato"):
        return None
    return c.get("valor")


def nota_de(F, cid):
    c = cif(F, cid) or {}
    return c.get("nota", "")


def requiere(campo, F, faltantes):
    v = val(F, campo)
    if v is None:
        faltantes.append(campo)
    return v


def pct_es(v):
    """95.9 -> 'noventa y cinco coma nueve por ciento'"""
    ent = int(v)
    dec = round((v - ent) * 10)
    s = numero_a_letras(ent)
    if dec:
        s += " coma " + UNIDADES[dec]
    return s + " por ciento"


def build_guion(F, mes_label, brand):
    faltantes = []
    ventas = requiere("ventas_netas", F, faltantes)
    meta = requiere("meta_ventas", F, faltantes)
    cumpl = requiere("cumplimiento", F, faltantes)
    breb = requiere("breb_total", F, faltantes)
    ads = requiere("ads_total", F, faltantes)
    fb = requiere("facebook", F, faltantes)

    beats = []
    n_sedes = len(F.get("sedes", []))
    mes_data = F.get("mes", {})
    reportes = mes_data.get("reportes") if not mes_data.get("sin_dato") else None
    # los campos faltantes ya quedaron registrados en faltantes (bloquean el pipeline);
    # aquí se neutralizan a 0 solo para poder estimar el guion sin romper
    ventas, meta, cumpl, breb, ads, fb = (v if v is not None else 0
                                          for v in (ventas, meta, cumpl, breb, ads, fb))

    b1 = (f"{mes_label} cerró en {millones_es(ventas)} de pesos en ventas netas. "
          f"{numero_a_letras(n_sedes)} salas" if n_sedes else "…")
    if reportes:
        b1 += f", {numero_a_letras(reportes)} reportes, y ningún día en blanco."
    else:
        b1 += "."
    beats.append({"n": 1, "card": "ventas_netas", "voz": b1})

    sep = F.get("comparativo_sep", {})
    delta = None
    if not sep.get("sin_dato") and sep.get("ventas_netas"):
        delta = (ventas / sep["ventas_netas"] - 1) * 100
        masmenos = "más" if delta >= 0 else "menos"
        b2 = (f"Frente al mes anterior, cuando se vendieron {millones_es(sep['ventas_netas'])}, "
              f"el mes {'subió' if delta >= 0 else 'bajó'} un {pct_es(abs(delta))}. "
              "Se reporta como fue.")
    else:
        b2 = f"El cumplimiento de la meta fue {pct_es(cumpl)}. Sin comparativo del mes anterior."
    beats.append({"n": 2, "card": "meta_comparativo", "voz": b2})

    if F.get("sedes"):
        top = sorted(F["sedes"], key=lambda s: -s.get("cumplimiento", -1))[0]
        if top.get("cumplimiento", 0) >= 100:
            b3 = (f"Por salas: {top['nombre']} superó su meta con {pct_es(top['cumplimiento'])}. "
                  f"Las otras {numero_a_letras(n_sedes - 1) if n_sedes > 1 else 'salas'}, no. "
                  "Sin maquillaje.")
        else:
            b3 = (f"Por salas: ninguna superó la meta. La más cerca fue {top['nombre']} con "
                  f"{pct_es(top['cumplimiento'])}. Se reporta tal cual. Sin maquillaje.")
    else:
        b3 = "Por salas: detalle pendiente de consolidación."
    beats.append({"n": 3, "card": "sedes", "voz": b3})

    pagos = None
    m = re.search(r"(\d[\d.]*) pagos", nota_de(F, "breb_total"))
    if m:
        pagos = int(m.group(1).replace(".", ""))
    if pagos:
        b4 = (f"El Bre-B recaudó {millones_es(breb)} de pesos en "
              f"{numero_a_letras(pagos)} pagos.")
    else:
        b4 = f"El Bre-B recaudó {millones_es(breb)} de pesos. Número de pagos por confirmar."
    beats.append({"n": 4, "card": "breb", "voz": b4})

    leads = val(F, "ads_leads")
    if leads is not None:
        b5 = (f"La pauta de Meta costó {numero_a_letras(ads)} pesos, y trajo "
              f"{numero_a_letras(leads)} leads.")
    else:
        b5 = f"La pauta de Meta costó {numero_a_letras(ads)} pesos. Leads por confirmar."
    beats.append({"n": 5, "card": "pauta", "voz": b5})

    org = val(F, "organico")
    if org is not None:
        mclics = re.search(r"(\d+) clics", nota_de(F, "organico"))
        clics = numero_a_letras(int(mclics.group(1))) if mclics else "por confirmar"
        b6 = f"En búsqueda orgánica, el sitio sumó {numero_a_letras(org)} impresiones y {clics} clics."
    else:
        b6 = "En búsqueda orgánica: dato pendiente de consolidación."
    beats.append({"n": 6, "card": "organico", "voz": b6})

    b7 = f"En Facebook, {millones_es(fb) if fb >= 1_000_000 else numero_a_letras(fb)} visualizaciones."
    ig = val(F, "instagram")
    if ig is not None:
        b7 += f" Y en Instagram, {numero_a_letras(ig)} seguidores."
    beats.append({"n": 7, "card": "redes", "voz": b7})

    agentes = val(F, "agentes")
    horas = val(F, "automatizacion_horas")
    if agentes is not None and horas is not None:
        b8 = (f"La operación: {numero_a_letras(agentes)} tareas automatizadas, "
              f"{numero_a_letras(horas)} horas medibles.")
    else:
        b8 = "Operación: métricas de agentes pendientes de consolidación."
    beats.append({"n": 8, "card": "operacion", "voz": b8})

    gap = round(100 - cumpl, 1)
    b9 = (f"Nada fue suerte: fue medir y corregir. Faltan {pct_es(gap).replace(' por ciento', ' puntos')} "
          "para la meta.")
    beats.append({"n": 9, "card": "cierre", "voz": b9})
    return beats, faltantes


def build_cards(F, mes_label_upper, brand):
    def c(cid):
        x = cif(F, cid)
        if x is None or x.get("sin_dato"):
            return "sin dato"
        return x.get("display", str(x.get("valor")))
    sep = F.get("comparativo_sep", {})
    delta_s = "n/d"
    if not sep.get("sin_dato") and sep.get("ventas_netas") and val(F, "ventas_netas"):
        d = (val(F, "ventas_netas") / sep["ventas_netas"] - 1) * 100
        delta_s = ("+" if d >= 0 else "−") + f"{abs(d):.1f}".replace(".", ",") + "%"
    gap = (round(100 - val(F, "cumplimiento"), 1)
           if val(F, "cumplimiento") is not None else None)
    if gap is None:
        gap = 0.0
    sedes_bars = [{"nombre": s["nombre"], "pct": f"{s.get('cumplimiento', 0):.1f}".replace(".", ",") + "%",
                   "ok": s.get("estado") == "ALCANZADA"} for s in F.get("sedes", [])]
    sobre = sum(1 for s in F.get("sedes", []) if s.get("estado") == "ALCANZADA")
    cards = [
        {"card": "ventas_netas", "kicker": f"VENTAS NETAS · {mes_label_upper}",
         "main": c("ventas_netas"),
         "chips": [f"{len(F.get('sedes', []))} salas"]},
        {"card": "meta_comparativo", "kicker": "CUMPLIMIENTO DE META", "main": c("cumplimiento"),
         "chips": [f"meta {c('meta_ventas')}", f"{delta_s} vs mes anterior"]},
        {"card": "sedes", "kicker": "POR SALA · SIN MAQUILLAJE", "bars": sedes_bars,
         "chips": [f"{sobre} de {len(F.get('sedes', []))} sobre meta"]},
        {"card": "breb", "kicker": "BRE-B", "main": c("breb_total"),
         "chips": [f"ticket {c('breb_ticket')}]".replace("]", "")]},
        {"card": "pauta", "kicker": "PAUTA DIGITAL · META ADS", "main": c("ads_total"),
         "chips": [c("ads_leads")]},
        {"card": "organico", "kicker": "ORGÁNICO · SEARCH CONSOLE", "main": c("organico"), "chips": []},
        {"card": "redes", "kicker": "REDES · FACEBOOK", "main": c("facebook"),
         "chips": ([c("instagram")] if cif(F, "instagram") else [])},
        {"card": "operacion", "kicker": "OPERACIÓN · AGENTES", "main": c("agentes"),
         "chips": [c("automatizacion_horas") + " medibles"]},
        {"card": "cierre", "kicker": "CIERRE",
         "main": (f"{gap:.1f}".replace(".", ",") + " puntos por cerrar" if gap else "n/d"),
         "chips": [f"{c('cumplimiento')} de la meta"]},
    ]
    return cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", required=True, help="YYYY-MM")
    ap.add_argument("--facts-golden", required=True)
    ap.add_argument("--facts-lucky", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="valida y estima costo TTS sin escribir locuciones finales")
    args = ap.parse_args()
    y, m = args.mes.split("-")
    mes_label = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                 "septiembre", "octubre", "noviembre", "diciembre"][int(m) - 1]
    mes_label_upper = mes_label.upper() + " " + y

    os.makedirs(args.outdir, exist_ok=True)
    loc, faltan = {}, {}
    for brand, path in [("golden", args.facts_golden), ("paradise", args.facts_lucky)]:
        F = json.load(open(path, encoding="utf-8"))
        beats, missing = build_guion(F, mes_label, brand)
        loc[brand] = beats
        faltan[brand] = missing
        cards = build_cards(F, mes_label_upper, brand)
        if not args.dry_run:
            json.dump(cards, open(os.path.join(args.outdir, f"cards_{brand}.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)
        chars = sum(len(b["voz"]) for b in beats)
        print(f"[{brand}] {len(beats)} beats · {chars} chars TTS estimados")
        if missing:
            print(f"[{brand}] BLOQUEANTE — sin_dato en campos requeridos: {', '.join(missing)}")
    if not args.dry_run:
        json.dump(loc, open(os.path.join(args.outdir, "locuciones.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        print("locuciones.json + cards_*.json escritos en", args.outdir)
    else:
        print("DRY-RUN: no se escriben locuciones")
    return 1 if any(faltan.values()) else 0


if __name__ == "__main__":
    sys.exit(main())

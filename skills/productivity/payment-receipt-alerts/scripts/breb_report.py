#!/usr/bin/env python3
"""Genera el Resumen ejecutivo (Google Sheet) y el PDF mensual de pagos Bre-B.
Uso: python3 breb_report.py [--config prod|test] [--no-pdf]
Corre en vps-prod-neural. Sin dependencias externas (stdlib + Gotenberg local).
"""
import csv, io, json, subprocess, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

REPORTS_DIR = '/root/breb-reports'
COL = timezone(timedelta(hours=-5))
MONTHS_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

PROD = {
    'lucky': dict(name='Lucky Brothers', slug='Lucky',
                  data='1bAcrcBjddAAqxo8V3xnwmOElk_9bAay5G-w1ZREUfGo',
                  resumen='1kkAXHtjgqDb5uo3UD80FsaD2svHFEMLHGZLpmD8NOuE',
                  secrets='/opt/data/secrets/lucky-drive.json',
                  flow='e2yTTyYCWj0DAWHTX8lLw'),
    'golden': dict(name='Golden Game', slug='Golden',
                   data='1j0vsPs4R4owvm_gisidizO0j0xckeZpK4z-Mev2xYu0',
                   resumen='1oSxUp2AOZWPV_Bs2kL-lxWQgPKJqV8SlY0XdGFxJDEc',
                   secrets='/opt/data/secrets/golden-drive.json',
                   flow='ybZF7O6TgBbKiAvvVvdHV'),
}

TEST = {
    'lucky': dict(name='Lucky Brothers (TEST)', slug='LuckyTest',
                  data='1tvUgP0L9VB58d6bsE4Z8oszCS4SFIJ2NvhuUg4Ft83I',
                  resumen='1EXvLIwnnVofPdp_FnhZC06OJnhdkrZBQ1LW30Pan-KM',
                  secrets='/opt/data/secrets/lucky-drive.json',
                  flow='e2yTTyYCWj0DAWHTX8lLw'),
}


def http(method, url, token=None, data=None, ctype=None, params=None, timeout=90):
    if params:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if ctype:
        headers['Content-Type'] = ctype
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_token(secrets_path):
    sec = json.load(open(secrets_path))
    body = urllib.parse.urlencode({'client_id': sec['client_id'], 'client_secret': sec['client_secret'],
                                   'refresh_token': sec['refresh_token'],
                                   'grant_type': 'refresh_token'}).encode()
    out = http('POST', 'https://oauth2.googleapis.com/token', data=body,
               ctype='application/x-www-form-urlencoded')
    return json.loads(out)['access_token']


def export_csv(token, file_id):
    return http('GET', 'https://www.googleapis.com/drive/v3/files/%s/export' % file_id,
                token=token, params={'mimeType': 'text/csv'}).decode('utf-8')


def write_sheet(token, file_id, csv_text):
    http('PATCH', 'https://www.googleapis.com/upload/drive/v3/files/%s' % file_id, token=token,
         data=csv_text.encode('utf-8'), ctype='text/csv', params={'uploadType': 'media'}, timeout=120)


def parse_money(s):
    t = ''.join(ch for ch in str(s) if ch.isdigit() or ch in '.,')
    if not t:
        return 0.0
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    else:
        t = t.replace('.', '')
    try:
        return float(t)
    except ValueError:
        return 0.0


def fmt_money(v):
    return ('$ %s' % ('{:,.2f}'.format(v))).replace(',', 'X').replace('.', ',').replace('X', '.')


def parse_rows(csv_text):
    rows = []
    rd = csv.reader(io.StringIO(csv_text))
    header = next(rd, None)
    for r in rd:
        if len(r) < 5 or not r[0]:
            continue
        try:
            ts = datetime.strptime(r[0].strip(), '%Y/%m/%d %H:%M')
        except ValueError:
            continue
        rows.append(dict(fecha=ts, valor=parse_money(r[1]), valor_txt=r[1].strip(),
                         remitente=r[2].strip(), cuenta=r[3].strip(), codigo=r[4].strip()))
    return rows


def month_key(ts):
    return ts.strftime('%Y-%m')


def stats_for(rows, mk):
    sel = [r for r in rows if month_key(r['fecha']) == mk]
    if not sel:
        return dict(periodo=mk, count=0, total=0.0, avg=0.0, mediana=0.0, maximo=None, minimo=None,
                    by_day={}, by_hour={}, by_account={}, top_senders=[], duplicados=0, nocturnos=0)
    vals = sorted(r['valor'] for r in sel)
    n = len(vals)
    by_day, by_hour, by_account, senders = {}, {}, {}, {}
    for r in sel:
        d = r['fecha'].strftime('%Y-%m-%d')
        by_day.setdefault(d, [0, 0.0])
        by_day[d][0] += 1
        by_day[d][1] += r['valor']
        by_hour[r['fecha'].hour] = by_hour.get(r['fecha'].hour, 0) + 1
        by_account.setdefault(r['cuenta'], [0, 0.0])
        by_account[r['cuenta']][0] += 1
        by_account[r['cuenta']][1] += r['valor']
        s = senders.setdefault(r['remitente'], [0, 0.0])
        s[0] += 1
        s[1] += r['valor']
    dup_keys = {}
    for r in sel:
        k = (r['remitente'], r['valor'], r['fecha'].strftime('%Y-%m-%d'))
        dup_keys[k] = dup_keys.get(k, 0) + 1
    duplicados = sum(1 for v in dup_keys.values() if v > 1)
    nocturnos = sum(1 for r in sel if r['fecha'].hour < 6)
    maxr = max(sel, key=lambda r: r['valor'])
    minr = min(sel, key=lambda r: r['valor'])
    mediana = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return dict(periodo=mk, count=n, total=sum(vals), avg=sum(vals) / n, mediana=mediana,
                maximo=maxr, minimo=minr, by_day=by_day, by_hour=by_hour, by_account=by_account,
                top_senders=sorted(senders.items(), key=lambda kv: -kv[1][1]), duplicados=duplicados,
                nocturnos=nocturnos)


def ap_stats(flow_id, mk):
    y, m = int(mk[:4]), int(mk[5:7])
    start = datetime(y, m, 1, tzinfo=timezone.utc) + timedelta(hours=5)
    end = (start + timedelta(days=32)).replace(day=1)
    q = ("SELECT status || '|' || count(*) FROM flow_run WHERE \"flowId\"='%s' "
         "AND \"startTime\" >= '%s' AND \"startTime\" < '%s' GROUP BY status;"
         % (flow_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
    try:
        out = subprocess.run(['docker', 'exec', 'ap-db', 'psql', '-U', 'postgres', '-d', 'activepieces', '-Atc', q],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        stats = {}
        for line in out.splitlines():
            if '|' in line:
                k, v = line.split('|')
                stats[k] = int(v)
        return stats
    except Exception:
        return {}


def build_resumen_csv(company, st, now_col):
    out = io.StringIO()
    w = csv.writer(out)
    y, m = int(st['periodo'][:4]), int(st['periodo'][5:7])
    w.writerow(['Bre-B %s — Resumen ejecutivo' % company['name'], '', ''])
    w.writerow(['Actualizado', now_col.strftime('%Y-%m-%d %H:%M') + ' (Colombia)', ''])
    w.writerow(['Período', '%s %d' % (MONTHS_ES[m - 1].title(), y), ''])
    w.writerow([])
    w.writerow(['TOTAL RECAUDADO', fmt_money(st['total']), ''])
    w.writerow(['PAGOS', st['count'], ''])
    w.writerow(['TICKET PROMEDIO', fmt_money(st['avg']), ''])
    if st['maximo']:
        w.writerow(['PAGO MÁS ALTO', fmt_money(st['maximo']['valor']), st['maximo']['remitente']])
    w.writerow([])
    w.writerow(['POR DÍA', 'Pagos', 'Total'])
    for d in sorted(st['by_day']):
        c, t = st['by_day'][d]
        w.writerow([d, c, fmt_money(t)])
    w.writerow([])
    w.writerow(['POR CUENTA DESTINO', 'Pagos', 'Total'])
    for acc, (c, t) in sorted(st['by_account'].items(), key=lambda kv: -kv[1][1]):
        w.writerow([acc, c, fmt_money(t)])
    w.writerow([])
    w.writerow(['TOP REMITENTES', 'Pagos', 'Total'])
    for name, (c, t) in st['top_senders'][:15]:
        w.writerow([name, c, fmt_money(t)])
    return out.getvalue()


def svg_bars(items, width=960, height=200, label_every=1, color='#1f6feb', money=True):
    if not items:
        return '<p class="muted">Sin datos.</p>'
    maxv = max(v for _, v in items) or 1
    n = len(items)
    gap = 4
    bw = (width - gap * (n - 1)) / n
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
             % (width, height, width, height)]
    parts.append('<line x1="0" y1="%d" x2="%d" y2="%d" stroke="#dde3ec" stroke-width="1"/>'
                 % (height - 26, width, height - 26))
    for i, (lab, val) in enumerate(items):
        h = (val / maxv) * (height - 46)
        x = i * (bw + gap)
        y = height - 26 - h
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="2"/>'
                     % (x, y, bw, max(h, 1), color))
        if val == maxv:
            label = fmt_money(val) if money else str(int(val))
            parts.append('<text x="%.1f" y="%.1f" font-size="10" text-anchor="middle" fill="#334">%s</text>'
                         % (x + bw / 2, y - 4, label))
        if i % label_every == 0:
            parts.append('<text x="%.1f" y="%d" font-size="9" text-anchor="middle" fill="#667">%s</text>'
                         % (x + bw / 2, height - 10, lab))
    parts.append('</svg>')
    return ''.join(parts)


def build_html(company, st, mk, now_col, apst):
    y, m = int(mk[:4]), int(mk[5:7])
    titulo = '%s %d' % (MONTHS_ES[m - 1].title(), y)
    if mk == now_col.strftime('%Y-%m'):
        last_day = now_col.day
    else:
        nxt = (datetime(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1))
        last_day = nxt.day
    day_items = [('%02d' % d, st['by_day'].get('%04d-%02d-%02d' % (y, m, d), [0, 0.0])[1])
                 for d in range(1, last_day + 1)]
    hour_items = [('%02d' % h, st['by_hour'].get(h, 0)) for h in range(24)]
    total_ap = sum(apst.values()) if apst else 0
    err = apst.get('FAILED', 0) + apst.get('FAILED_STEP', 0) if apst else 0
    if st['count'] == 0:
        cuerpo = '<p class="muted" style="margin:40px 0">Sin pagos registrados en el período todavía.</p>'
    else:
        top = ''.join('<tr><td>%s</td><td class="num">%d</td><td class="num">%s</td></tr>'
                      % (n, c, fmt_money(t)) for n, (c, t) in st['top_senders'][:8])
        accs = ''.join('<tr><td>%s</td><td class="num">%d</td><td class="num">%s</td></tr>'
                       % (a, c, fmt_money(t)) for a, (c, t) in
                       sorted(st['by_account'].items(), key=lambda kv: -kv[1][1]))
        cuerpo = f"""
  <div class="kpis">
    <div class="kpi"><div class="k-l">Total recaudado</div><div class="k-v">{fmt_money(st['total'])}</div></div>
    <div class="kpi"><div class="k-l">Pagos</div><div class="k-v">{st['count']}</div></div>
    <div class="kpi"><div class="k-l">Ticket promedio</div><div class="k-v">{fmt_money(st['avg'])}</div></div>
    <div class="kpi"><div class="k-l">Pago más alto</div><div class="k-v">{fmt_money(st['maximo']['valor'])}</div>
      <div class="k-s">{st['maximo']['remitente'][:28]}</div></div>
  </div>
  <h2>Recaudación por día</h2>
  {svg_bars(day_items, label_every=max(1, len(day_items)//10))}
  <h2>Pagos por franja horaria</h2>
  {svg_bars(hour_items, height=150, label_every=3, color='#0e9f6e', money=False)}
  <div class="cols">
    <div class="col">
      <h2>Por cuenta destino</h2>
      <table><tr><th>Cuenta</th><th class="num">Pagos</th><th class="num">Total</th></tr>{accs}</table>
    </div>
    <div class="col">
      <h2>Top remitentes</h2>
      <table><tr><th>Remitente</th><th class="num">Pagos</th><th class="num">Total</th></tr>{top}</table>
    </div>
  </div>
  <p class="muted small">Mediana del período: {fmt_money(st['mediana'])} · Pagos de madrugada (00:00-05:59): {st['nocturnos']} · Posibles duplicados (mismo remitente y monto el mismo día): {st['duplicados']}</p>
"""
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 12mm 12mm 14mm 12mm; }}
body {{ font-family: Helvetica, Arial, sans-serif; color:#1a2233; font-size:11px; margin:0; }}
h1 {{ font-size:19px; margin:0 0 2px 0; }}
h2 {{ font-size:12px; margin:16px 0 6px 0; color:#33415c; text-transform:uppercase; letter-spacing:.4px; }}
.head {{ border-bottom:2px solid #1f6feb; padding-bottom:8px; margin-bottom:10px; }}
.head .sub {{ color:#5b6b83; font-size:11px; }}
.kpis {{ display:flex; gap:8px; margin:10px 0 4px 0; }}
.kpi {{ flex:1; border:1px solid #e3e8ef; border-radius:6px; padding:8px 10px; }}
.k-l {{ color:#5b6b83; font-size:9.5px; text-transform:uppercase; letter-spacing:.3px; }}
.k-v {{ font-size:15px; font-weight:bold; margin-top:2px; }}
.k-s {{ color:#5b6b83; font-size:9px; margin-top:1px; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ padding:3px 6px; border-bottom:1px solid #eef1f5; text-align:left; }}
th {{ color:#5b6b83; font-size:9.5px; text-transform:uppercase; }}
.num {{ text-align:right; }}
.cols {{ display:flex; gap:14px; }} .col {{ flex:1; }}
.muted {{ color:#7a8699; }} .small {{ font-size:9.5px; }}
.foot {{ margin-top:16px; border-top:1px solid #e3e8ef; padding-top:6px; color:#7a8699; font-size:9px; }}
</style></head><body>
<div class="head">
  <h1>{company['name']} — Pagos Bre-B</h1>
  <div class="sub">Resumen de {titulo} · Generado {now_col.strftime('%d/%m/%Y %H:%M')} (Colombia)</div>
</div>
{cuerpo}
<div class="foot">Automatización Bre-B: {total_ap} avisos procesados en el período, {err} errores.
Reporte generado automáticamente a partir de las notificaciones de BBVA.</div>
</body></html>"""
    return html


def gotenberg_ip():
    out = subprocess.run(['docker', 'inspect', 'paperless-gotenberg', '--format',
                          '{{range $v := .NetworkSettings.Networks}}{{$v.IPAddress}} {{end}}'],
                         capture_output=True, text=True, timeout=30).stdout.split()
    return out[0]


def render_pdf(html_text, out_path):
    ip = gotenberg_ip()
    boundary = '----brebreport'
    body = (b'--' + boundary.encode() + b'\r\nContent-Disposition: form-data; name="files"; '
            b'filename="index.html"\r\nContent-Type: text/html\r\n\r\n' + html_text.encode('utf-8') +
            b'\r\n--' + boundary.encode() + b'--\r\n')
    req = urllib.request.Request('http://%s:3000/forms/chromium/convert/html' % ip, data=body,
                                 headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
                                 method='POST')
    with urllib.request.urlopen(req, timeout=120) as r:
        pdf = r.read()
    with open(out_path, 'wb') as f:
        f.write(pdf)
    return len(pdf)


def run(config, with_pdf=True):
    now_col = datetime.now(COL)
    mk_now = now_col.strftime('%Y-%m')
    first = now_col.replace(day=1)
    mk_prev = (first - timedelta(days=1)).strftime('%Y-%m')
    for key, company in config.items():
        token = get_token(company['secrets'])
        rows = parse_rows(export_csv(token, company['data']))
        print('[%s] filas: %d' % (key, len(rows)))
        st_now = stats_for(rows, mk_now)
        write_sheet(token, company['resumen'], build_resumen_csv(company, st_now, now_col))
        print('[%s] resumen actualizado: %d pagos, total %s' % (key, st_now['count'], fmt_money(st_now['total'])))
        if not with_pdf:
            continue
        subprocess.run(['mkdir', '-p', REPORTS_DIR], check=True)
        for mk in {mk_now, mk_prev}:
            st = stats_for(rows, mk)
            apst = ap_stats(company['flow'], mk)
            html_txt = build_html(company, st, mk, now_col, apst)
            out = '%s/Bre-B_%s_%s.pdf' % (REPORTS_DIR, company['slug'], mk)
            size = render_pdf(html_txt, out)
            with open(out.replace('.pdf', '.html'), 'w') as f:
                f.write(html_txt)
            print('[%s] pdf %s (%d bytes, %d pagos)' % (key, out, size, st['count']))


if __name__ == '__main__':
    config_name = 'prod'
    if '--config' in sys.argv:
        config_name = sys.argv[sys.argv.index('--config') + 1]
    cfg = TEST if config_name == 'test' else PROD
    run(cfg, with_pdf=('--no-pdf' not in sys.argv))

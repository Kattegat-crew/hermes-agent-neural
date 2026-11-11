#!/usr/bin/env python3
"""Conciliación y recuperación autónoma de pagos Bre-B (BBVA) en Google Sheets.

Compara las notificaciones de pago recibidas en Gmail (de notificacionesBreB@bbva.com)
contra las filas registradas en las hojas de cálculo de Lucky Brothers y Golden Game.
Detecta pagos caídos por cortes en ActivePieces o errores de hoja, sanea filas corruptas
e inyecta de forma idempotente los pagos faltantes ordenados cronológicamente.

Uso:
  python3 reconcile_breb.py [--tenant golden|lucky|all] [--since YYYY/MM/DD] [--month YYYY-MM] [--apply]
  Default: --tenant all --dry-run (modo seguro de auditoría)
"""
import argparse
import base64
import csv
import html as ihtml
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

COL = timezone(timedelta(hours=-5))

TENANTS = {
    "lucky": {
        "name": "Lucky Brothers",
        "tab_name": "Bre-B Lucky — Pagos",
        "gmail_secret": "/opt/data/secrets/lucky-gmail.json",
        "drive_secret": "/opt/data/secrets/lucky-drive.json",
        "spreadsheet_id": "1bAcrcBjddAAqxo8V3xnwmOElk_9bAay5G-w1ZREUfGo",
    },
    "golden": {
        "name": "Golden Game",
        "tab_name": "Bre-B Golden — Pagos",
        "gmail_secret": "/opt/data/secrets/golden-gmail.json",
        "drive_secret": "/opt/data/secrets/golden-drive.json",
        "spreadsheet_id": "1j0vsPs4R4owvm_gisidizO0j0xckeZpK4z-Mev2xYu0",
    },
}

FECHA_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$")


def get_access_token(secret_path):
    if not os.path.exists(secret_path):
        raise FileNotFoundError(f"Archivo de credenciales no encontrado: {secret_path}")
    with open(secret_path, "r", encoding="utf-8") as f:
        sec = json.load(f)
    body = urllib.parse.urlencode({
        "client_id": sec["client_id"],
        "client_secret": sec["client_secret"],
        "refresh_token": sec["refresh_token"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["access_token"]


def http_get(url, token, timeout=30, retries=5):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503) and i < retries - 1:
                wait_sec = min(60, 2 ** i * 3)
                time.sleep(wait_sec)
                continue
            raise
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("Petición HTTP fallida tras reintentos")


def load_discord_config():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    thread_id = os.environ.get("DISCORD_BREB_THREAD_ID", "1555440735262740501")
    env_path = "/opt/data/.env"
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DISCORD_BOT_TOKEN=") and not token:
                        token = line.split("=", 1)[1].strip()
                    elif line.startswith("DISCORD_BREB_THREAD_ID=") and (not thread_id or thread_id == "1555440735262740501"):
                        thread_id = line.split("=", 1)[1].strip()
        except Exception:
            pass
    return token, thread_id


def send_discord_thread_alert(thread_id, bot_token, embed_data):
    if not thread_id or not bot_token:
        return False
    url = f"https://discord.com/api/v10/channels/{thread_id}/messages"
    payload = json.dumps({"embeds": [embed_data]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "BreBReconciler/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(f"Error enviando alerta a Discord: {e}", file=sys.stderr)
        return False


def parse_cop(val_str):
    try:
        clean = str(val_str).replace("$", "").replace(".", "").replace(",", ".").strip()
        return float(clean)
    except Exception:
        return 0.0


def list_gmail_messages(token, query):
    msg_ids = []
    page = None
    while True:
        params = {"q": query, "maxResults": "500"}
        if page:
            params["pageToken"] = page
        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{urllib.parse.urlencode(params)}"
        res = json.loads(http_get(url, token).decode("utf-8"))
        msg_ids.extend([m["id"] for m in res.get("messages", [])])
        page = res.get("nextPageToken")
        if not page:
            break
    return msg_ids


def walk_parts(payload):
    parts_out = []

    def rec(part):
        mt = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and mt in ("text/html", "text/plain"):
            parts_out.append((mt, data))
        for child in part.get("parts", []) or []:
            rec(child)

    rec(payload)
    return parts_out


def strip_html(html_str):
    t = str(html_str)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<script[\s\S]*?</script>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = ihtml.unescape(t)
    t = re.sub(r"&[a-z]+;", " ", t, flags=re.I)
    return t


def b64_decode(data_str):
    padding = "=" * (-len(data_str) % 4)
    return base64.urlsafe_b64decode(data_str + padding).decode("utf-8", "replace")


def parse_gmail_message(full_msg):
    payload = full_msg.get("payload", {})
    parts = walk_parts(payload)
    html_txt = ""
    plain_txt = ""
    for mt, d in parts:
        try:
            txt = b64_decode(d)
        except Exception:
            continue
        if mt == "text/html" and len(txt) >= 20 and not html_txt:
            html_txt = txt
        if mt == "text/plain" and len(txt) >= 20 and not plain_txt:
            plain_txt = txt

    if html_txt and len(html_txt) >= 20:
        raw = strip_html(html_txt)
    elif plain_txt and len(plain_txt) >= 20:
        raw = plain_txt
    else:
        raw = full_msg.get("snippet", "")

    text = re.sub(r"\s+", " ", str(raw))

    def pick(rx):
        m = re.search(rx, text, flags=re.I)
        return m.group(1).strip() if m else "N/D"

    return {
        "fecha": pick(r"Fecha y hora\s+(.+?)\s+Valor recibido"),
        "valor": pick(r"Valor recibido\s+([^A-Za-z]+?)\s+Persona"),
        "remitente": pick(r"Persona que env[ií]a\s+(.+?)\s+Tipo de llave"),
        "cuenta": pick(r"Cuenta destino\s+(\*+\d+)"),
        "codigo": pick(r"C[oó]digo de operaci[oó]n\s+(\d+)"),
    }


def get_sheets_token(tenant_key):
    helper_paths = [
        os.path.join(os.path.dirname(__file__), "get_sheets_token.js"),
        "/root/breb-reports/get_sheets_token.js"
    ]
    for p in helper_paths:
        if os.path.exists(p):
            try:
                out = subprocess.check_output(["node", p, tenant_key], stderr=subprocess.PIPE).decode("utf-8").strip()
                if out.startswith("ya29."):
                    return out
            except Exception:
                pass
    return None


def read_sheet_tab_values(token, spreadsheet_id, tab_name):
    range_name = f"'{tab_name}'!A1:E"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{urllib.parse.quote(range_name)}?valueRenderOption=FORMATTED_VALUE"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
        return data.get("values", [])


def clear_sheet_tab_values(token, spreadsheet_id, tab_name):
    range_name = f"'{tab_name}'!A:E"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{urllib.parse.quote(range_name)}:clear"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def update_sheet_tab_values(token, spreadsheet_id, tab_name, rows):
    range_name = f"'{tab_name}'!A1"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{urllib.parse.quote(range_name)}?valueInputOption=USER_ENTERED"
    payload = json.dumps({
        "range": range_name,
        "majorDimension": "ROWS",
        "values": rows
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def export_sheet_csv(token, spreadsheet_id):
    url = f"https://www.googleapis.com/drive/v3/files/{spreadsheet_id}/export?mimeType=text%2Fcsv"
    return http_get(url, token, timeout=60).decode("utf-8")


def patch_sheet_csv(token, spreadsheet_id, csv_text):
    raise RuntimeError(
        "CRITICAL ERROR: patch_sheet_csv (Google Drive file overwrite) is permanently deprecated. "
        "Overwriting spreadsheet files destroys multi-tab reports and worksheets. Use update_sheet_tab_values via Google Sheets API."
    )


def reconcile_tenant(tenant_key, cfg, query, cache_dir, apply_changes=False, discord_thread_id=None, notify_always=False):
    print(f"\n==================================================")
    print(f"Conciliando: {cfg['name']} ({tenant_key.upper()})")
    print(f"==================================================")

    gmail_token = get_access_token(cfg["gmail_secret"])
    sheets_token = get_sheets_token(tenant_key)
    tab_name = cfg.get("tab_name", f"Bre-B {cfg['name'].split()[0]} — Pagos")

    # 1. Obtener y parsear estado actual del Sheet
    if sheets_token:
        reader = read_sheet_tab_values(sheets_token, cfg["spreadsheet_id"], tab_name)
    else:
        drive_token = get_access_token(cfg["drive_secret"])
        raw_csv = export_sheet_csv(drive_token, cfg["spreadsheet_id"])
        reader = list(csv.reader(io.StringIO(raw_csv)))

    if not reader:
        print(f"[{tenant_key}] ERROR: La hoja de cálculo o pestaña '{tab_name}' está vacía.")
        return

    header = reader[0]
    raw_rows = reader[1:]

    existing_codes = set()
    clean_rows = []
    corrupt_rows = 0

    for r in raw_rows:
        if len(r) >= 5 and r[4].strip() and r[0].strip() and r[1].strip():
            code = r[4].strip()
            if code not in existing_codes:
                existing_codes.add(code)
                clean_rows.append(r)
        else:
            corrupt_rows += 1

    print(f"[{tenant_key}] Filas actuales en Sheet: {len(raw_rows)} (Válidas: {len(clean_rows)}, Corruptas/Vacías detectadas: {corrupt_rows})")

    # 2. Consultar mensajes en Gmail
    msg_ids = list_gmail_messages(gmail_token, query)
    print(f"[{tenant_key}] Mensajes encontrados en Gmail con filtro '{query}': {len(msg_ids)}")

    # 3. Manejo de caché
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"breb_cache_{tenant_key}.json")
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    missing_payments = []
    seen_in_batch = set()
    cache_dirty = False

    for idx, mid in enumerate(msg_ids):
        if mid in cache:
            item = cache[mid]
        else:
            time.sleep(0.15)
            url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full&fields=payload,snippet"
            full_msg = json.loads(http_get(url, gmail_token, timeout=45).decode("utf-8"))
            item = parse_gmail_message(full_msg)
            cache[mid] = item
            cache_dirty = True
            if (idx + 1) % 50 == 0:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False)

        if "N/D" in item.values() or not FECHA_PATTERN.match(item["fecha"]):
            continue

        code = item["codigo"]
        if code in existing_codes or code in seen_in_batch:
            continue

        seen_in_batch.add(code)
        missing_payments.append([
            item["fecha"],
            item["valor"],
            item["remitente"],
            item["cuenta"],
            item["codigo"],
        ])

    if cache_dirty:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)

    print(f"[{tenant_key}] Pagos huérfanos / faltantes identificados: {len(missing_payments)}")

    if missing_payments:
        print(f"\n--- Muestra de pagos faltantes ({tenant_key.upper()}) ---")
        for row in missing_payments[:10]:
            print(f"  {row[0]} | {row[1]:>14} | {row[2][:25]:<25} | Cod: {row[4]}")
        if len(missing_payments) > 10:
            print(f"  ... y {len(missing_payments) - 10} pagos adicionales.")

    # 4. Aplicar cambios si se solicitó
    discord_token, default_thread_id = load_discord_config()
    target_thread_id = discord_thread_id or default_thread_id

    if apply_changes:
        if not missing_payments and corrupt_rows == 0:
            print(f"\n[{tenant_key}] ✅ Hoja 100% al día y limpia. Nada que aplicar.")
            if notify_always and discord_token and target_thread_id:
                embed = {
                    "title": f"✅ [{cfg['name']}] Hoja Cuadrada (Auditoría OK)",
                    "description": f"Auditoría completada sin novedades. Todas las filas coinciden con Gmail ({len(clean_rows)} pagos verificados).",
                    "color": 0x3498DB,
                    "footer": {"text": "Ragnar Systems • Conciliación Bre-B"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                send_discord_thread_alert(target_thread_id, discord_token, embed)
            return

        merged_rows = clean_rows + missing_payments
        merged_rows.sort(key=lambda x: x[0])

        all_rows = [header] + merged_rows
        if sheets_token:
            if corrupt_rows > 0:
                print(f"[{tenant_key}] 🧹 Depurando filas corruptas en pestaña '{tab_name}'...")
                clear_sheet_tab_values(sheets_token, cfg["spreadsheet_id"], tab_name)
            print(f"[{tenant_key}] 📝 Escribiendo {len(all_rows)} filas en pestaña '{tab_name}' vía Google Sheets API...")
            update_sheet_tab_values(sheets_token, cfg["spreadsheet_id"], tab_name, all_rows)
        else:
            raise RuntimeError(
                f"[{tenant_key}] ERROR CRÍTICO: Token de Google Sheets API no disponible. "
                f"Escritura cancelada para proteger las demás pestañas del libro."
            )

        print(f"\n[{tenant_key}] 🚀 APLICADO CON ÉXITO: {len(missing_payments)} pagos inyectados, {corrupt_rows} filas corruptas purgadas.")
        print(f"[{tenant_key}] Total de filas actualizadas en Google Sheet: {len(merged_rows)}")

        if discord_token and target_thread_id:
            total_cop = sum(parse_cop(p[1]) for p in missing_payments if len(p) > 1 and p[1])
            sample_lines = "\n".join(
                f"• `{p[0]}` **{p[1]}** · {p[2][:22]} (Cod: `{p[4]}`)"
                for p in missing_payments[:5]
            )
            if len(missing_payments) > 5:
                sample_lines += f"\n*... y {len(missing_payments) - 5} pagos más.*"

            embed = {
                "title": f"🛡️ [{cfg['name']}] {len(missing_payments)} Pagos Rescatados",
                "description": "El conciliador autónomo detectó pagos ausentes en la hoja y los inyectó exitosamente.",
                "color": 0x2ECC71,
                "fields": [
                    {"name": "Monto Total Recuperado", "value": f"**$ {total_cop:,.0f} COP**".replace(",", "."), "inline": True},
                    {"name": "Pagos Inyectados", "value": str(len(missing_payments)), "inline": True},
                    {"name": "Total Filas en Hoja", "value": str(len(merged_rows)), "inline": True},
                ],
                "footer": {"text": "Ragnar Systems • Conciliación Bre-B"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if corrupt_rows > 0:
                embed["fields"].append({"name": "Saneamiento", "value": f"{corrupt_rows} filas corruptas depuradas", "inline": False})
            if sample_lines:
                embed["fields"].append({"name": "Muestra de pagos inyectados", "value": sample_lines, "inline": False})

            send_discord_thread_alert(target_thread_id, discord_token, embed)
    else:
        if missing_payments or corrupt_rows > 0:
            print(f"\n[{tenant_key}] ℹ️ Modo DRY-RUN. Ejecutá con --apply para escribir estos {len(missing_payments)} pagos y sanear la tabla.")
            if notify_always and discord_token and target_thread_id:
                total_cop = sum(parse_cop(p[1]) for p in missing_payments if len(p) > 1 and p[1])
                embed = {
                    "title": f"⚠️ [{cfg['name']}] {len(missing_payments)} Pagos Faltantes (Dry-Run)",
                    "description": "Simulación de conciliación detectó pagos ausentes en la hoja de cálculo.",
                    "color": 0xF39C12,
                    "fields": [
                        {"name": "Monto Estimado", "value": f"**$ {total_cop:,.0f} COP**".replace(",", "."), "inline": True},
                        {"name": "Pagos Detectados", "value": str(len(missing_payments)), "inline": True},
                    ],
                    "footer": {"text": "Ragnar Systems • Conciliación Bre-B"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                send_discord_thread_alert(target_thread_id, discord_token, embed)
        else:
            print(f"\n[{tenant_key}] ✅ Hoja 100% cuadrada. No requiere cambios.")
            if notify_always and discord_token and target_thread_id:
                embed = {
                    "title": f"✅ [{cfg['name']}] Hoja Cuadrada (Auditoría OK)",
                    "description": f"Auditoría completada sin novedades. Todas las filas coinciden con Gmail ({len(clean_rows)} pagos verificados).",
                    "color": 0x3498DB,
                    "footer": {"text": "Ragnar Systems • Conciliación Bre-B"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                send_discord_thread_alert(target_thread_id, discord_token, embed)


def main():
    parser = argparse.ArgumentParser(description="Conciliador autónomo de pagos Bre-B")
    parser.add_argument("--tenant", choices=["golden", "lucky", "all"], default="all", help="Empresa a conciliar")
    parser.add_argument("--since", help="Fecha inicial en formato YYYY/MM/DD (default: hace 30 días)")
    parser.add_argument("--month", help="Mes específico YYYY-MM (ej: 2026-10)")
    parser.add_argument("--cache-dir", default="/root/breb-reports", help="Directorio para almacenamiento de caché")
    parser.add_argument("--apply", action="store_true", help="Aplica la inyección y saneamiento en Google Sheets")
    parser.add_argument("--notify-always", action="store_true", help="Fuerza envío de notificación a Discord incluso si está cuadrada")
    parser.add_argument("--thread-id", help="Sobrescribe el ID de hilo de Discord")
    parser.add_argument("--no-discord", action="store_true", help="Desactiva notificaciones a Discord")
    args = parser.parse_args()

    now = datetime.now(COL)
    if args.month:
        try:
            y, m = map(int, args.month.split("-"))
            start_date = f"{y:04d}/{m:02d}/01"
            if m == 12:
                end_date = f"{y+1:04d}/01/01"
            else:
                end_date = f"{y:04d}/{m+1:02d}/01"
            query = f"from:notificacionesBreB@bbva.com after:{start_date} before:{end_date}"
        except Exception:
            print("Formato inválido de --month. Debe ser YYYY-MM.")
            sys.exit(1)
    elif args.since:
        query = f"from:notificacionesBreB@bbva.com after:{args.since}"
    else:
        first_current = now.replace(day=1)
        prev_month = (first_current - timedelta(days=1)).replace(day=1)
        since_str = prev_month.strftime("%Y/%m/%d")
        query = f"from:notificacionesBreB@bbva.com after:{since_str}"

    targets = [args.tenant] if args.tenant != "all" else ["golden", "lucky"]
    try:
        for t in targets:
            reconcile_tenant(
                t,
                TENANTS[t],
                query,
                args.cache_dir,
                apply_changes=args.apply,
                discord_thread_id=None if args.no_discord else args.thread_id,
                notify_always=args.notify_always
            )
    except Exception as exc:
        print(f"Error crítico en reconciliación: {exc}", file=sys.stderr)
        if not args.no_discord:
            dtok, dth = load_discord_config()
            tid = args.thread_id or dth
            if dtok and tid:
                err_embed = {
                    "title": "🚨 [Bre-B Reconciler] Excepción Crítica en Ragnar",
                    "description": f"El script de conciliación falló inesperadamente durante su ejecución:\n```\n{str(exc)[:500]}\n```",
                    "color": 0xE74C3C,
                    "footer": {"text": "Ragnar Systems • Conciliación Bre-B"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                send_discord_thread_alert(tid, dtok, err_embed)
        raise

if __name__ == "__main__":
    main()

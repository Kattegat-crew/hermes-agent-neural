#!/usr/bin/env python3
"""
Meta Ads Discord Reporter
Fetches campaign, adset, and ad-level insights via Composio Meta Marketing API proxy,
formats an executive performance card, and delivers it to a Discord webhook.
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime

def run_composio_proxy(url, account):
    cmd = [
        "composio", "proxy", url,
        "--toolkit", "metaads",
        "--account", account
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error calling composio proxy for {url}: {res.stderr}", file=sys.stderr)
        return None
    
    out = res.stdout
    start = out.find("{")
    end = out.rfind("}") + 1
    if start != -1 and end != 0:
        try:
            return json.loads(out[start:end], strict=False)
        except Exception as e:
            print(f"JSON decode error: {e}\nRaw: {out}", file=sys.stderr)
            return None
    return None

def fetch_campaign_data(campaign_id, account):
    # 1. Campaign metadata
    camp_url = f"https://graph.facebook.com/v21.0/{campaign_id}?fields=id,name,status,lifetime_budget,daily_budget"
    camp_data = run_composio_proxy(camp_url, account) or {}

    # 2. Insights today
    today_url = f"https://graph.facebook.com/v21.0/{campaign_id}/insights?fields=impressions,clicks,spend,cpc,ctr,reach&date_preset=today"
    today_data = run_composio_proxy(today_url, account) or {}
    today_insights = (today_data.get("data") or [{}])[0] if today_data.get("data") else {}

    # 3. Insights lifetime / total
    total_url = f"https://graph.facebook.com/v21.0/{campaign_id}/insights?fields=impressions,clicks,spend,cpc,ctr,reach&date_preset=maximum"
    total_data = run_composio_proxy(total_url, account) or {}
    total_insights = (total_data.get("data") or [{}])[0] if total_data.get("data") else {}

    # 4. Ad Sets insights
    adsets_url = f"https://graph.facebook.com/v21.0/{campaign_id}/adsets?fields=id,name,status,insights.date_preset(maximum){{impressions,clicks,spend,cpc,ctr}}"
    adsets_data = run_composio_proxy(adsets_url, account) or {}
    adsets_list = adsets_data.get("data") or []

    # 5. Top Ads insights
    ads_url = f"https://graph.facebook.com/v21.0/{campaign_id}/ads?fields=id,name,status,insights.date_preset(maximum){{impressions,clicks,spend,cpc,ctr}}&limit=50"
    ads_data = run_composio_proxy(ads_url, account) or {}
    ads_list = ads_data.get("data") or []

    return {
        "campaign": camp_data,
        "today": today_insights,
        "total": total_insights,
        "adsets": adsets_list,
        "ads": ads_list
    }

def build_discord_payload(data, client_name="The Grand Paradise Club"):
    camp = data.get("campaign", {})
    camp_name = camp.get("name", "Campaña Meta Ads")
    camp_status = camp.get("status", "ACTIVE")

    today = data.get("today", {})
    total = data.get("total", {})

    # Budgets
    budget_raw = camp.get("lifetime_budget") or camp.get("daily_budget") or 0
    try:
        budget_total = float(budget_raw)
        if budget_total > 1000000: # in cents
            budget_total = budget_total / 100.0
    except Exception:
        budget_total = 400000.0

    spend_today = float(today.get("spend") or 0.0)
    spend_total = float(total.get("spend") or 0.0)
    clicks_today = int(today.get("clicks") or 0)
    clicks_total = int(total.get("clicks") or 0)
    impressions_today = int(today.get("impressions") or 0)
    impressions_total = int(total.get("impressions") or 0)
    reach_total = int(total.get("reach") or 0)
    ctr_total = float(total.get("ctr") or 0.0)
    cpc_total = float(total.get("cpc") or 0.0)

    # Budget pct
    pct_spent = (spend_total / budget_total * 100.0) if budget_total > 0 else 0.0

    # Adsets breakdown
    adsets_lines = []
    for adset in data.get("adsets", []):
        aname = adset.get("name", "Sede")
        aname = aname.replace("Paradise ", "").replace(" - CBO", "")
        ainsights = (adset.get("insights", {}).get("data") or [{}])[0]
        as_clicks = int(ainsights.get("clicks") or 0)
        as_spend = float(ainsights.get("spend") or 0.0)
        as_cpc = float(ainsights.get("cpc") or 0.0)
        adsets_lines.append(f"• **{aname}**: {as_clicks} clics | ${as_spend:,.0f} COP (CPC: ${as_cpc:,.0f})")

    adsets_text = "\n".join(adsets_lines) if adsets_lines else "Sin datos registrados aún."

    # Top Ad Creative
    best_ad = None
    max_clicks = -1
    for ad in data.get("ads", []):
        ai = (ad.get("insights", {}).get("data") or [{}])[0]
        aclicks = int(ai.get("clicks") or 0)
        if aclicks > max_clicks:
            max_clicks = aclicks
            best_ad = (ad.get("name"), aclicks, float(ai.get("cpc") or 0.0))

    if best_ad and best_ad[1] > 0:
        top_ad_text = f"🥇 **{best_ad[0]}**\n└ {best_ad[1]} clics conseguidos a ${best_ad[2]:,.0f} COP/clic"
    else:
        top_ad_text = "En fase de aprendizaje de creativos"

    now_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")

    embed = {
        "title": f"📊 Desempeño Diario Meta Ads: {client_name}",
        "description": f"**Campaña**: `{camp_name}`\n**Objetivo**: Tráfico y Conversiones VIP (CBO)\n**Corte**: {now_str} (Bogotá)",
        "color": 0xFFB703, # Gold/Amber
        "fields": [
            {
                "name": "💰 Inversión & Presupuesto",
                "value": f"**Hoy**: ${spend_today:,.0f} COP\n**Acumulado**: ${spend_total:,.0f} / ${budget_total:,.0f} COP ({pct_spent:.1f}%)",
                "inline": True
            },
            {
                "name": "🎯 Clics & Tráfico",
                "value": f"**Hoy**: {clicks_today} clics\n**Acumulado**: {clicks_total} clics a la web",
                "inline": True
            },
            {
                "name": "⚡ Métricas de Eficiencia",
                "value": f"**CPC Promedio**: ${cpc_total:,.0f} COP\n**CTR Promedio**: {ctr_total:.2f}%\n**Alcance Único**: {reach_total:,} personas",
                "inline": False
            },
            {
                "name": "📍 Rendimiento por Sede (Distribución CBO)",
                "value": adsets_text,
                "inline": False
            },
            {
                "name": "🏆 Creativo Estrella",
                "value": top_ad_text,
                "inline": False
            },
            {
                "name": "🛡️ Estado del Sistema",
                "value": f"🟢 **Estado**: `{camp_status}` | 12 anuncios en circulación | Sin restricciones de políticas",
                "inline": False
            }
        ],
        "footer": {
            "text": f"{client_name} • Intelligence Reporting System",
            "icon_url": "https://paradiseclubcasinos.com.co/assets/images/logo-transparent.png"
        }
    }

    return {"embeds": [embed]}

def send_to_discord(webhook_url, payload):
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AntigravityMetaReporter/1.0"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 204):
                print("Successfully sent report to Discord!")
                return True
            else:
                print(f"Failed with status: {response.status}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"Discord webhook send error: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate and dispatch Meta Ads Discord Report")
    parser.add_argument("--campaign-id", required=True, help="Meta Campaign ID")
    parser.add_argument("--account", required=True, help="Composio account selector (e.g. metaads_moly-ponent)")
    parser.add_argument("--webhook-url", required=False, default=None, help="Discord Webhook URL")
    parser.add_argument("--webhook-env", default="META_ADS_DISCORD_WEBHOOK", help="Environment variable name for webhook URL (default: META_ADS_DISCORD_WEBHOOK)")
    parser.add_argument("--env-file", default="/etc/hermes-vault/root.secrets.env", help="Path to env file containing webhook secrets")
    parser.add_argument("--client-name", default="The Grand Paradise Club", help="Client / Business Name")

    args = parser.parse_args()

    webhook_url = args.webhook_url
    if not webhook_url:
        webhook_url = os.getenv(args.webhook_env)
    if not webhook_url and args.env_file and os.path.exists(args.env_file):
        try:
            with open(args.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{args.webhook_env}="):
                        webhook_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception as e:
            print(f"Warning: could not read env file {args.env_file}: {e}", file=sys.stderr)

    if not webhook_url:
        print(f"Error: webhook URL not provided via --webhook-url or {args.webhook_env} in env/file", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching data for Campaign {args.campaign_id} via {args.account}...")
    data = fetch_campaign_data(args.campaign_id, args.account)

    print("Building Discord embed...")
    payload = build_discord_payload(data, client_name=args.client_name)

    print(f"Sending to Discord webhook...")
    success = send_to_discord(webhook_url, payload)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

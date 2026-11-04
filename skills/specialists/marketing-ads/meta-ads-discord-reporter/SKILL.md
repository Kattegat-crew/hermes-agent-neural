---
name: meta-ads-discord-reporter
description: "Use when reporting Meta Ads performance to Discord."
tags: [meta-ads, discord, webhook, reportes, composio, insights]
license: Apache-2.0
metadata:
  author: Gentleman Programming & Antigravity
  version: "1.0.0"
---

# Meta Ads Discord Reporter

Standardized skill to pull real-time campaign insights from Meta Marketing API (via Composio proxy) and deliver rich, executive Discord embeds via webhooks.

## Architecture

```
[Cron / Scheduler] ──> [scripts/report.py] ──> [Composio Proxy / Graph API]
                                │
                                └──> [Discord Webhook Embed]
```

- **Zero-Token Execution**: Runs as a deterministic Python script without waking up an LLM or consuming inference tokens.
- **Multitenant**: Parameterized for any client, ad account, campaign ID, and Discord webhook.

## Usage

```bash
python3 /root/.agents/skills/meta-ads-discord-reporter/scripts/report.py \
  --campaign-id "<CAMPAIGN_ID>" \
  --account "<COMPOSIO_ACCOUNT_SLUG>" \
  --webhook-url "<DISCORD_WEBHOOK_URL>" \
  --client-name "<CLIENT_NAME>"
```

### Parameters

| Argument | Description | Example |
|---|---|---|
| `--campaign-id` | Meta Campaign ID (CBO or ABO) | `120248560322730714` |
| `--account` | Composio connected account slug | `metaads_moly-ponent` |
| `--webhook-url` | Discord incoming webhook URL | `https://discord.com/api/webhooks/...` |
| `--client-name` | Display name for header and footer | `"The Grand Paradise Club"` |

## Output Metrics Included

1. **Inversión & Presupuesto**: Spend today, lifetime spend, total budget, percentage executed.
2. **Clics & Tráfico**: Clicks today and lifetime offsite link clicks to landing pages.
3. **Métricas de Eficiencia**: Average Cost-Per-Click (CPC), Click-Through-Rate (CTR), and unique reach.
4. **Desglose por Ad Set (Sedes)**: Spend, clicks, and CPC per geographical ad set.
5. **Top Creative**: Best performing ad name, total clicks, and acquisition cost.
6. **Health Status**: Effective campaign delivery status.

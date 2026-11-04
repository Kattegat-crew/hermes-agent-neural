---
name: gws-shared-access
description: "Use when Google Workspace calls fail from a profile."
tags: [google, drive, oauth, token, multi-profile, venv]
version: 1.0.0
author: Roshi (profile-local companion to bundled google-workspace)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Google, Drive, OAuth, MultiProfile, Hermes]
    related_skills: [google-workspace]
---

> [!IMPORTANT]
> **REGLA DE PROTOCOLO CANÓNICO ACTIVA**: El acceso a Google Workspace (Gmail, Drive, Docs, Sheets, Calendar)
> está centralizado en el servidor MCP  () usando los tokens
> en  y el mapa en  (gestionados por ActivePieces).
>  y  están revocados/deprecados. Usa siempre el MCP .



# Google Workspace Shared Access (multi-profile host)

The bundled `google-workspace` skill ships the scripts, but on this host the OAuth
token and Python deps live at the **root** Hermes home, not the profile home.
From any sub-profile (roshi, bragi, ...), use the working invocation below.

## Verified working invocation

```bash
export HERMES_HOME=/opt/data   # root holds google_token.json — NOT the profile dir
/opt/data/.venv/bin/python /opt/data/skills/google-workspace/scripts/google_api.py \
  drive search "Golden Game" --max 10
```

- `/opt/data/.venv/bin/python` has `googleapiclient` installed; the system python3.13 does NOT — plain `python .../google_api.py` dies with ModuleNotFoundError.
- Token: `/opt/data/google_token.json` (shared across profiles).
- Operations confirmed live: `drive search`. Same script covers upload/download/read per the bundled skill's usage section — always with this HERMES_HOME + venv pair.

## Whoami — which Google account is this token really?

Never answer "con qué cuenta estoy conectado" from memory; verify live:

```bash
/opt/data/.venv/bin/python -c "
import json,urllib.request,urllib.parse
t=json.load(open('/opt/data/google_token.json'))
data=urllib.parse.urlencode({'client_id':t['client_id'],'client_secret':t['client_secret'],'refresh_token':t['refresh_token'],'grant_type':'refresh_token'}).encode()
tok=json.loads(urllib.request.urlopen(urllib.request.Request(t['token_uri'],data=data)).read())['access_token']
r=urllib.request.urlopen(urllib.request.Request('https://gmail.googleapis.com/gmail/v1/users/me/profile',headers={'Authorization':'Bearer '+tok}))
print(r.read().decode())"
```

- The stored `token` is usually EXPIRED (401 on direct calls) — refresh via `token_uri` with the stored `refresh_token`/`client_id`/`client_secret` first (all present in google_token.json).
- Don't bother with `openidconnect.../userinfo` (may 401 without openid scope) and the `account` field in google_token.json is often EMPTY — the Gmail `users/me/profile` `emailAddress` is the authoritative answer.
- **Fact (verified 2026-09-03):** the root token is `jonathaun124@gmail.com` (Jonathan's account). Searches like "Golden Game"/"Lucky Brothers" hit Jonathan's Drive. This shared token ≠ any tenant's own account.
- **Two parallel Google paths on this host — do not conflate when asked "¿con cuál cuenta?":**
  1. Local root token (above) → Jonathan's Gmail, full Drive breadth, instant CLI.
  2. AP hub OAuth connections (`/opt/data/connections-map.json`) → per-tenant accounts, e.g. `chucho-gmail/drive/calendar` = Jemadiar1@gmail.com (Yisus's), owned by profile `roshi`, status ACTIVE (verified in AP DB 28/08).

## Pitfalls

- `setup.py --check` run with `HERMES_HOME=<profile>` reports `NOT_AUTHENTICATED` — **false negative**. It only looks for `<profile>/google_token.json`. Before concluding auth is missing, check `/opt/data/google_token.json`; if it exists and the `export HERMES_HOME=/opt/data` invocation works, do NOT re-run OAuth setup.
- Campaign uploads from other skills (e.g. build_campaign handoffs) also require `HERMES_HOME=/opt/data` — same rule, matches the team convention 'uploads SIEMPRE con HERMES_HOME raíz'.
- The bundled skill path `/opt/data/skills/google-workspace/` is readable/executable from here, but the profile-local mirror at `profiles/roshi/skills/google-workspace` may raise PermissionDenied — use the `/opt/data/skills/` copy.
- The AP MCP endpoint (what `ap_call.py` talks to) exposes ONLY `ap_*` flow-admin tools (`ap_list_connections`, `ap_build_flow`, ...) — there is NO direct `list_files`/google-action tool. Reading a tenant's Drive/Gmail through a `chucho-*`/tenant connection means building/invoking a FLOW in AP, not a one-shot MCP call. Say this honestly when a user asks to "use their account" — don't imply instant parity with the local token path.

## References

- `references/neuralcrew-drive.md` — verified Drive inventory for NeuralCrew clients (Golden Game, Lucky Brothers): folder/file names and IDs from a live `drive search`.
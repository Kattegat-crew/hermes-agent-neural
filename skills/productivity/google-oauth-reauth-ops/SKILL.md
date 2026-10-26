---
name: google-oauth-reauth-ops
description: "Use when Google OAuth needs new scopes or re-consent."
tags: [google, oauth, token, scopes, pkce, reauth, calendar, gmail]
author: Ragnar
version: "1.0"
created: 2026-08-21
category: devops
metadata:
  hermes:
    tags: [google, oauth, token, scopes, calendar, gmail, drive]
    related_skills: [google-workspace, google-docs-api]
---

> [!IMPORTANT]
> **REGLA DE PROTOCOLO CANÓNICO ACTIVA**: El acceso a Google Workspace (Gmail, Drive, Docs, Sheets, Calendar)
> está centralizado en el servidor MCP  () usando los tokens
> en  y el mapa en  (gestionados por ActivePieces).
>  y  están revocados/deprecados. Usa siempre el MCP .



# Google OAuth Reauth — Token Lifecycle & Scope Upgrades

## When to Use

- Google API devuelve `Request had insufficient authentication scopes` (token no tiene un scope nuevo).
- El usuario necesita re-autenticar el token de Google Workspace (calendario, drive, docs, gmail) sin romper lo que ya funciona.
- Después del reauth: verificar con llamada real, no solo con `--check`.

## Hechos clave

- El refresh token NO re-otorga scopes nuevos. Agregar un scope exige re-consentimiento (`prompt=consent`).
- Re-autorizar REEMPLAZA el set de scopes completo; si omites uno viejo, lo revoca. Pide el set completo deseado.
- La dependencia de `setup.py` del skill `google-workspace` puede fallar por PEP 668 (`externally-managed-environment`) cuando las libs ya están instaladas; eso NO significa que falten las libs. Verificar con `python3 -c "import googleapiclient, google_auth_oauthlib"`.
- Token vive en el HERMES home real: en este entorno `/opt/data/google_token.json` (NO `~/.hermes/…`).

## Receta (probada 21/08/2026)

Script listo: `/opt/data/scripts/reauth_google_calendar.py` (sin `_ensure_deps()` de setup.py).

1. `python3 /opt/data/scripts/reauth_google_calendar.py --auth-url` → URL larga de consent.
2. El usuario la abre con su cuenta, aprueba y pega de vuelta el redirect `http://localhost:1/?code=...` (errores de localhost son normales; copiar TODO el URL de la barra).
3. `python3 /opt/data/scripts/reauth_google_calendar.py --auth-code "http://localhost:1/?code=..."`.
4. El script guarda `google_token.json` + backup `google_token.json.bak` antes de sobrescribir.
5. Verificación real: NO quedarse con "OK". Llamar a la API (`calendar list`, `drive search`) y confirmar que el scope nuevo funciona.

## Pitfalls

- **PKCE / code_challenge**: si el URL lleva `code_challenge` y el usuario lo pega por chat, un carácter puede corromperse → `Invalid code verifier`. Fix: generar el URL SIN PKCE (desactivar verifier) para que sea corto y no dependa de transcripción. Si un código con verifier falló, generar un URL NUEVO, no reusar.
- **State desactualizado**: si el usuario abrió un URL y mientras se generó otro, `state` no coincide, pero el `code` es fresco. El script relaja la validación de state (aviso, no aborta).
- **No usar token crudo con urllib**: usar `google-api-python-client`/`google-auth` que auto-refrescan. Un 401 después de ~1h = token crudo, no config error.
- **No reescribir `google_token.json` a mano**: el skill valida el hash; la vía correcta es el script de reauth.
- **`setup.py --check` no basta**: dice `AUTHENTICATED` pero los scopes pueden faltar. Verificar por llamada real.

## Verificación mínima

```bash
python3 /opt/data/scripts/reauth_google_calendar.py --auth-url
python3 /opt/data/skills/productivity/google-workspace/scripts/google_api.py calendar list
```

## Referencias

- Script: `/opt/data/scripts/reauth_google_calendar.py` (recetario completo con PKCE/state relajado).
- Overlap note: `google-docs-api` ya documenta el pitfall de scope-add de forma genérica; esta skill es el recetario ejecutable.
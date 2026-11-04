---
name: gmail-smtp-app-password
description: "Use when wiring Gmail SMTP app passwords into Docker apps."
tags: [smtp, gmail, app-password, docuseal, twenty, email, docker]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Gmail SMTP App Password

## Activation Contract

Use when wiring outbound email in a Docker app using a Google Workspace address (`user@domain`): DocuSeal, Twenty, ActivePieces, Formbricks, or similar. Trigger: user asks to set SMTP host/port/user/password/domain or "send from".

## Hard Rules

- Never write the SMTP password into argv, shell history, commits, or local files: inject via stdin heredoc and persist only in the app compose on the VPS (chmod 600).
- Verify email-auth DNS before wiring (MX → Google, SPF includes Google, DMARC present); without SPF/DMARC mail goes to spam.
- Gmail SMTP requires an **app password** (2FA enabled + `myaccount.google.com/apppasswords`); the real account password is never accepted.
- App SMTP env names differ per product — inspect the running image code before assuming names (see Decision Gates).

## Decision Gates

| Situation | Action |
|-----------|--------|
| Gmail SSL | `smtp.gmail.com:465`, auth `plain`, SSL on, STARTTLS off |
| DocuSeal envs | `SMTP_ADDRESS`, `SMTP_PORT`, `SMTP_DOMAIN`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_AUTHENTICATION`, `SMTP_ENABLE_SSL=true`, `SMTP_FROM` (required — no `SMTP_SSL`/`EMAIL_FROM_ADDRESS` in current versions) |
| DocuSeal "send test" | No UI button; run `docker exec docuseal /app/bin/rails runner 'SettingsMailer.smtp_successful_setup("to@x.com").deliver_now!'` (WORKDIR is not `/app`) |
| DocuSeal admin panel | Settings → Email SMTP is bypassed when SMTP envs exist — never use it |
| Verify delivery | `deliver_now!` exit 0 = auth+TLS accepted by Gmail; check recipient inbox and sender spam folder |

## Execution Steps

1. Verify email-auth DNS: `dig +short MX <domain>` → Google; SPF TXT includes `_spf.google.com`; `_dmarc.<domain>` exists.
2. Get app password from the account owner (16 chars, no spaces).
3. Read the app's compose and its production.rb/mailer code on the VPS to confirm exact env names.
4. Add SMTP envs to the compose (password via stdin heredoc), chmod 600, keep a `.bak` without secrets.
5. `docker compose up -d`; confirm container Up and logs clean.
6. Send a real test mail via the app's own mailer and confirm exit 0; check recipient inbox.

## Output Contract

Return: env vars added (password masked), container state, test-mail result (exit code / delivered), deviations found in env names, and any DNS gaps to fix.

## References

- `cloudflare-email-auth-dns` — create the SPF/DMARC records this skill prechecks.

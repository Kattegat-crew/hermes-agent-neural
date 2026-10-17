---
name: meta-pixel-capi
description: "Trigger: meta pixel, capi, conversions api, tracking pixel, deduplication, event match quality, emq, facebook pixel, lead tracking, offline conversions. Implement, deduplicate, and diagnose hybrid browser-server Meta tracking with Conversions API and Pixel."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

# Meta Pixel & Conversions API (CAPI)

## Activation Contract

Use when implementing, refactoring, or diagnosing Meta (Facebook) tracking in web apps. Covers browser Pixel (`fbq`), server-side Conversions API (CAPI), event deduplication, advanced matching (EMQ), and Graph API testing.

## Hard Rules

- **Redundancy & Deduplication:** Never run CAPI alone or Pixel alone for primary conversion events (`Lead`, `Purchase`). Always emit from BOTH browser and server with the EXACT SAME `event_id` (UUIDv4) within 48 hours. Meta will deduplicate automatically.
- **Advanced Matching (EMQ) Hashing:** All PII fields (`em`, `ph`, `fn`, `ln`, `external_id`, `ct`, `st`, `zp`, `country`) MUST be trimmed, lowercased, and hashed with SHA-256. Do NOT hash `client_ip_address`, `client_user_agent`, `fbp`, or `fbc`.
- **Phone Normalization:** Phone numbers (`ph`) must follow E.164 (only digits, including country code, e.g. Colombia `573001234567`) BEFORE hashing.
- **Graph API Endpoint:** CAPI events are dispatched to `POST https://graph.facebook.com/v21.0/{PIXEL_ID}/events`. Never POST to `/{PIXEL_ID}` directly (causes Graph API error code 100/33).
- **Non-blocking Dispatch:** Server-side CAPI dispatch MUST be asynchronous / fire-and-forget with a strict timeout (max 8s). Never block user registration, checkout, or form responses waiting for Meta CAPI.
- **Persist Before Dispatch:** Store the lead/order in the primary database BEFORE dispatching to CAPI.
- **Test Event Code:** In development or staging, pass `test_event_code` in the CAPI payload to verify events in Meta Events Manager > Test Events in real time. Never commit hardcoded test codes to production.

## Decision Gates

| Scenario | Architectural Choice |
|---|---|
| Page navigation in SPA (`/`, `/eventos`) | Client-side only: `fbq('track', 'PageView')` and `fbq('track', 'ViewContent', { content_name })` |
| Form submission / Lead / Bonus claim | **Hybrid**: Client-side `fbq('track', 'Lead', ..., { eventID })` + Server-side CAPI `POST .../events` with identical `event_id` |
| Client has AdBlocker / iOS ITP | Frontend `fbq` silently drops or fails; server-side CAPI guarantees 100% conversion delivery |
| Event Setup Tool fails with "No pixel detected" | Expected on SPAs behind Cloudflare/AdBlockers. Verify with Graph API Explorer or direct cURL instead of the GUI tool |

## Implementation Specification

### 1. Browser Client Helper (`metaPixel.js`)
```javascript
export function getMetaCookies() {
  if (typeof document === 'undefined') return { fbp: null, fbc: null };
  const cookies = Object.fromEntries(document.cookie.split('; ').map(c => c.split('=')));
  return { fbp: cookies._fbp || null, fbc: cookies._fbc || null };
}

export function generateEventId() {
  return typeof crypto?.randomUUID === 'function' ? crypto.randomUUID() : `ev-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function trackLead({ eventId, value, currency = 'COP', contentName = 'Lead' }) {
  if (typeof window === 'undefined' || !window.fbq) return;
  const customData = { content_name: contentName, value, currency };
  window.fbq('track', 'Lead', customData, eventId ? { eventID: eventId } : undefined);
}
```

### 2. Server CAPI Dispatcher (`capiDispatcher.js`)
```javascript
import crypto from 'crypto';

const sha256 = (s) => s ? crypto.createHash('sha256').update(String(s).trim().toLowerCase()).digest('hex') : undefined;

function normalizePhone(phone, defaultCountryCode = '57') {
  if (!phone) return undefined;
  const digits = String(phone).replace(/\D/g, '');
  if (!digits) return undefined;
  const formatted = digits.length === 10 ? `${defaultCountryCode}${digits}` : digits;
  return sha256(formatted);
}

export async function sendCapiEvent({ pixelId, accessToken, testEventCode, eventName, eventId, lead, clientIp, userAgent, fbp, fbc }) {
  const payload = {
    data: [{
      event_name: eventName,
      event_time: Math.floor(Date.now() / 1000),
      event_id: eventId,
      action_source: 'website',
      user_data: {
        em: sha256(lead.email),
        ph: normalizePhone(lead.phone),
        fn: sha256(lead.name?.split(' ')[0]),
        ...(lead.cedula ? { external_id: sha256(lead.cedula) } : {}),
        client_ip_address: clientIp,
        client_user_agent: userAgent,
        ...(fbp ? { fbp } : {}),
        ...(fbc ? { fbc } : {})
      },
      custom_data: {
        content_name: lead.contentName || 'Bono',
        value: lead.value,
        currency: lead.currency || 'COP'
      }
    }],
    ...(testEventCode ? { test_event_code: testEventCode } : {})
  };

  const res = await fetch(`https://graph.facebook.com/v21.0/${pixelId}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, access_token: accessToken }),
    signal: AbortSignal.timeout(8000)
  });
  return res.json();
}
```

## Verification & Diagnostics

1. **Verify CAPI via cURL:**
   ```bash
   curl -X POST "https://graph.facebook.com/v21.0/<PIXEL_ID>/events" \
     -H "Content-Type: application/json" \
     -d '{
       "data": [{
         "event_name": "Lead",
         "event_time": '$(date +%s)',
         "event_id": "test-'$(date +%s)'",
         "action_source": "website",
         "user_data": { "em": "test@domain.com" }
       }],
       "access_token": "<META_CAPI_ACCESS_TOKEN>"
     }'
   ```
   *Expected response:* `{"events_received": 1, "messages": []}`.

2. **Deduplication Check in Events Manager:**
   * Go to **Events Manager > Pixel > Overview**.
   * Inspect the `Lead` event: connection method should show **"Navegador • Servidor"** and deduplication status **"100% deduplicados"**.

3. **Event Match Quality (EMQ):**
   * Target EMQ score >= 7.0/10. Achieved by sending: email (`em`) + phone (`ph`) + first name (`fn`) + external ID (`external_id`) + IP + User-Agent + `_fbp` cookie.

## References

- [Meta Conversions API Documentation](https://developers.facebook.com/docs/marketing-api/conversions-api)
- [Meta Standard Events Specification](https://eventsmanager.facebook.com/business/help/402791146561655)

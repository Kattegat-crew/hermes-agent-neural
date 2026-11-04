# Hoja de precios video IA — verificada 2026-08-18

Todas las cifras verificadas contra fuentes oficiales el 18/08/2026. Re-verificar antes de decidir con presupuesto en juego (los precios cambian).

## Fuentes (18/08/2026)
- MiniMax pay-as-you-go: https://platform.minimax.io/docs/guides/pricing-paygo
- MiniMax video packages: https://platform.minimax.io/docs/guides/pricing-video
- MiniMax token plan: https://platform.minimax.io/docs/guides/pricing-token-plan
- Monid MiniMax: https://monid.ai/tools/minimax
- Monid blog (Seedance 2.0): https://monid.ai/blog/seedance-2
- OpenRouter Hailuo-2.3: https://openrouter.ai/minimax/hailuo-2.3
- Contexto arena: invideo.io/blog/seedance-2-vs-minimax-h3/ (Elo Artificial Analysis, ago 2026)

## MiniMax pay-as-you-go (API directa)

| Modelo | Resolución | Facturación | Precio |
|---|---|---|---|
| H3 | 2K | por segundo | $0.13/s |
| H3 | 768P | por segundo | $0.08/s |
| H3 (regeneración 768P→2K) | — | por segundo | $0.05/s |
| Hailuo-2.3 | 768P 6s | por clip | $0.28 |
| Hailuo-2.3 | 768P 10s | por clip | $0.56 |
| Hailuo-2.3 | 1080P 6s | por clip | $0.49 |
| Hailuo-2.3-Fast | 768P 6s | por clip | $0.19 |
| Hailuo-2.3-Fast | 768P 10s | por clip | $0.32 |
| Hailuo-2.3-Fast | 1080P 6s | por clip | $0.33 |
| Hailuo-02 (legacy) | 512P 6s / 10s | por clip | $0.10 / $0.15 |

Notas H3:
- Input: primeras 5 imágenes gratis, luego $0.04 c/u; audio gratis; video input facturado por duración ($0.08/s 768P).
- Audio nativo incluido (SFX estéreo) — los Hailuo son mudos (narrativa/música aparte).
- Open weights → candidato a cluster local 96GB VRAM.

## Monid (pay-per-clip, sin suscripción, sin markup visible)
- Hailuo-2.3: $0.28–$0.56 por clip — **idéntico a API directa**.
- Seedance 2.0 Mini 720p: $0.38115/clip (5s) — el default anterior del pipeline.
- Seedance 2.0 tier Standard (8s 720p): $1.2096.
- H3 en Monid: NO confirmado (página pública solo lista Hailuo-2.3). Verificar con `monid discover` antes de asumir.
- app.monid.ai = SPA Nuxt, Jina solo devuelve "Loading". Usar monid.ai/tools/<vendor> (SSR).

## Suscripciones MiniMax — descartadas
| Opción | Por qué no |
|---|---|
| Token plan $20/$50/$120 mes | NO cubre video (solo texto/imagen/voz/música); H3 excluido |
| Video packages $1,000/$2,500/$4,500/$6,000 mes | $0.266/$0.252/$0.238/$0.224 por punto; Hailuo-2.3 768P 6s = 1 punto; equilibrio ≈ 3,760 clips/mes; **H3 no soportado** |
| OpenRouter Hailuo-2.3 | $0.0817/s → 6s = $0.49 (75% markup vs $0.28) |

## Costo por reel 30s (5 clips × 6s)
| Ruta | Costo |
|---|---|
| Hailuo-2.3-Fast 768P | $0.95 |
| **Hailuo-2.3 768P (Monid)** | **$1.40 ← DEFAULT** |
| H3 768P | $2.40 |
| Seedance 2.0 Mini (default anterior) | $2.29 |
| Hailuo-2.3 1080P | $2.45 |

## Decisiones derivadas
1. Producción: Hailuo-2.3 768P 6s vía Monid — mismo precio que directo, ya integrado (MONID_API_KEY en /root/marketing-campaign-generator/.env).
2. Drafts: Hailuo-2.3-Fast 768P. Con Hailuo, clips de 6s son más baratos por segundo que 10s ($0.047/s vs $0.056/s); con H3 el precio/s es plano.
3. Premium: H3 768P API directa (cuenta MiniMax solo para H3).
4. A futuro: H3 open weights en local = costo marginal ~$0.

## Método de re-verificación
- `curl -s "https://r.jina.ai/https://platform.minimax.io/docs/guides/pricing-paygo"` — fuente canónica, extraíble.
- Exa directo (cuando mcporter no está): `curl -s https://api.exa.ai/search -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" -d '{"query":"...","numResults":5}'` — EXA_API_KEY en el .env (gateway: /opt/data/.env; desktop: /root/hermes-agent-legacy-docker/data/.env).

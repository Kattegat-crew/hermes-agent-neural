# Fallback 3 capas 100% API — esquema y catálogos verificados (26/08/2026)

## Esquema de cascada por bot (config.yaml)

```yaml
model:
  provider: NaN-Builders
  default: <modelo-por-bot>
fallback_providers:
  - provider: NaN-Builders      # capa 0: primario (rate limit real: 'max 5 simultaneous requests' → 429)
  - provider: B.AI              # capa 2: fallback de API
  - provider: OpenCode-Go       # capa 3: fallback de API (decisión Jonathan 26/08: SIN CLI, SIN login)
```

Regla clave: **`fallback_providers` requiere que el provider esté definido en el
bloque `providers` del mismo perfil.** Tener el nombre en la cascada sin el
bloque `providers.X` (api_key + base_url + models) hace que Hermes no pueda
resolver el fallback.

## Catálogos verificados por API (26/08)

### NaN-Builders (https://api.nan.builders/v1) — primario
- Modelos reales: deepseek-v4-flash, gemma4, mimo-v2.5, qwen3.6, qwen3.8-flash,
  glm5.3-flash, whisper, kokoro, qwen3-embedding, rerank, flux-2-klein, ...
- **`deepseek-v4-flash-0731` NO existe** (ni aquí ni en B.AI ni en OpenCode-Go) —
  no asignarlo como default a ningún bot.
- Rate limit real: `concurrency limit: max 5 simultaneous requests` (429).
  Mitigación: modelo primario distinto por bot + crons escalonados.

### B.AI (https://api.b.ai/v1) — capa 2
- **Solo `deepseek-v4-flash` responde SIN saldo** (free-limited, probado con
  chat probe). Los premium (gpt-5.x, glm-5.x) → `access_denied: Deposit
  required`; `minimax-m2.7` → `insufficient_user_quota` (balance=0).
- NO son "varios gratis": es 1 modelo gratis confirmado.

### OpenCode-Go (https://opencode.ai/zen/go/v1) — capa 3
- Endpoint OpenAI-compatible real (la doc oficial: opencode.ai/docs/go).
- Escaneo de 31 modelos con probe max_tokens=3: 24 responden **cost=0**
  (la sub los cubre). Destacados gratis: deepseek-v4-flash/pro, qwen3.8-max,
  qwen3.7-max, glm-5.3/5.2, kimi-k3/k2.7-code, minimax-m3/m2.5, mimo-v2.5(-pro).
- **Decisión de cliente: SOLO `mimo-v2.5` en el catálogo del provider**
  (30.100 llamadas/mes, el más barato de Go). El resto se quita de `providers`.
- NO usables (error transitorio/formato): minimax-m2.7 (500), mimo-v2-pro/omni
  (unsupported), hy3-preview/grok-4.5 (unavailable), grok-4.6 (formato
  oa-compat no soportado), gpt-5.6-luna, muse-spark-1.2-contributor (500).
- `opencode models` de la CLI lista tags `opencode/*-free` (gratuitos SIN auth)
  — NO son los modelos de la sub. El tag de la sub es el ID plano
  (`opencode/mimo-v2.5`, sin `-free`).
- Nota: el wrapper CLI `opencode run` queda como respaldo OPCIONAL; la vía
  oficial es el provider de API (no requiere `opencode auth login`).

## Probes de verificación reutilizables

```bash
# Listar modelos de un provider (con UA de navegador para evitar 403 en Go)
curl -s -H "Authorization: Bearer $KEY" -H "User-Agent: Mozilla/5.0" \
  "https://opencode.ai/zen/go/v1/models" | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"

# Saber si un modelo responde y con qué costo (cost=0 => gratis en la sub)
curl -s -H "Authorization: Bearer $KEY" -H "User-Agent: Mozilla/5.0" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5","messages":[{"role":"user","content":"hola"}],"max_tokens":3}' \
  "https://opencode.ai/zen/go/v1/chat/completions" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d.get('cost'), d.get('choices',[{}])[0].get('finish_reason'))"
```

## Por qué API y no CLI (decisión registrada)
Jonathan 26/08: "no quiero lanzar opencode, quiero que se conecte a la API y use mimo".
La capa 3 es un provider HTTP como los otros; el CLI y el device-flow no son
necesarios. Esto elimina el único pendiente externo (auth login) del fallback.
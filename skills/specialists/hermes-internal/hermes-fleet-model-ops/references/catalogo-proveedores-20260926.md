# Catálogo de proveedores — snapshot 26-sep-2026 (verificado EN VIVO)

## Método de inventario (el config NO es la fuente)

1. `GET {base_url}/models` con `Authorization: Bearer <key>` desde execute_code (urllib sirve).
2. **Gotcha clave:** la `api_key` en `config.yaml` viene **ENMASCARADA** (`sk-JzB...ohYw`) — reutilizarla da 403/401. Las llaves reales viven en `/opt/data/.env`: `NAN_API_KEY` (NaN-Builders y B.AI comparten endpoint), `OPENCODE_GO_API_KEY`.
3. Contraste config vs live: el config declara solo lo cableado; el endpoint devuelve TODO el catálogo del gateway.

## NaN-Builders (api.nan.builders/v1) — 14 modelos live

Texto: deepseek-v4-flash, mimo-v2.5, mimo-v2.6-flash, glm5.3-flash, qwen3.6, qwen3.8-flash, gemma4, minimax-h3. No-LM: flux-2-klein (imagen), qwen-image-2.1 (imagen), kokoro (TTS), whisper (STT), qwen3-embedding, rerank.

Novedad vs config 26-sep: mimo-v2.6-flash, minimax-h3, qwen-image-2.1, qwen3-embedding, rerank, whisper no estaban declarados en config.

## OpenCode-Go (opencode.ai/zen/go/v1) — 30 modelos live (fallback)

DeepSeek: deepseek-flash, v4-flash, v4-flash-vision-exp, v4.1-flash, v4-pro. GLM: 5.2, 5.3, 5.3-flash. GPT: gpt-5.6-luna, gpt-6-luna. Grok: 4.6, 4.7. Kimi: k2.7-code, k3. MiMo: v2.5, v2.5-pro, v2.6-flash, v2.6-pro. MiniMax: m2.7, m3. Qwen: 3.7-plus, 3.8-flash, 3.8-max. Otros: longcat-2.0, longcat-2.5-preview-free, hy3, hy4-preview, muse-spark-1.2/1.3-contributor, space-bunny-free.

La mayoría NO está declarada en `providers:` del config — añadir como provider nuevo si se quiere usar (requiere OK del Admin).

## Uso real de la flota (26-sep)

- default (DEV): glm5.3-flash principal; qwen3.6 en smart_model_routing (mensajes ≤28 palabras); fallback_model = mimo-v2.5 vía OpenCode-Go.
- PROD: los 9 perfiles corren deepseek-v4-flash vía http://hermes-llm-proxy:8742/v1 con cadena flash→mimo→flash/OpenCode (ver memoria y brain/ops/routing-modelos-flota-prod-2026-09-20.md).

## Ollama-Local (PC del Admin) — estado 26-sep

- Endpoint: `http://100.102.79.4:11434` (Tailscale). Verificación: `GET /api/tags` lista modelos instalados.
- 26-sep: PC alcanzable (ping ~77 ms) pero 11434 **connection refused** → Ollama apagado o bind en 127.0.0.1. Fix lado Windows: arrancar Ollama con `OLLAMA_HOST=0.0.0.0` para exponerlo por Tailscale.
- Modelo local instalado (histórico): `huihui_ai/qwen3-abliterated:8b`.
- **Política (incidencia 19/20-sep-2026):** NUNCA en el camino crítico ni como fallback temprano. Si se reincorpora, SOLO como último fallback tras OpenCode-Go, y verificar /api/tags ANTES de cablearlo. Un fallback local que duerme/apaga la PC = flota sin red de seguridad (ya ocurrió: timeout masivo + 7 crons con 401).

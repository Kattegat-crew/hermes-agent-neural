#!/usr/bin/env python3
"""
llm_resilient_runner.py — High-reliability multi-model fallback client for Hermes operations.
Rotates models automatically on HTTP 429, timeout, or rate-limit exhaustion.
"""

import os
import sys
import time
import json
import logging
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("llm_runner")

BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://api.nan.builders/v1").rstrip("/")
API_KEY = os.getenv("NAN_API_KEY") or os.getenv("NAN_BUILDERS_API_KEY", "")

# Priority order for models
MODEL_FALLBACK_CHAIN = [
    "qwen3.8-flash",
    "deepseek-v4-flash",
    "mimo-v2.5",
    "qwen3.6",
]

def query_llm(
    prompt: str,
    system_prompt: str = "You are a senior software architect assistant.",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    json_mode: bool = False,
    models: list = None
) -> str:
    """Queries LLM with automatic multi-model fallback."""
    candidate_models = models or MODEL_FALLBACK_CHAIN
    last_error = None

    for model in candidate_models:
        for attempt in range(1, 4):
            url = f"{BASE_URL}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {API_KEY}",
                    "User-Agent": "curl/8.5.0"
                }
            )

            try:
                logger.info(f"Querying model '{model}' (attempt {attempt}/3)...")
                with urllib.request.urlopen(req, timeout=45) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    content = res_json["choices"][0]["message"]["content"]
                    logger.info(f"Success with model '{model}'.")
                    return content

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.warning(f"HTTP {e.code} on model '{model}': {err_body[:200]}")
                last_error = f"HTTP {e.code}: {err_body[:200]}"
                if e.code in (429, 500, 502, 503, 504):
                    sleep_time = attempt * 2
                    logger.info(f"Backing off {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    # Non-retryable error for this model, break to next model
                    break

            except Exception as e:
                logger.warning(f"Error querying model '{model}': {str(e)}")
                last_error = str(e)
                time.sleep(attempt)

        logger.warning(f"Model '{model}' exhausted. Falling back to next model...")

    raise RuntimeError(f"All candidate models exhausted. Last error: {last_error}")

if __name__ == "__main__":
    test_prompt = sys.argv[1] if len(sys.argv) > 1 else "Responde con 'OK: Runner activo y conectado' si puedes leer esto."
    print("Testing resilient runner...")
    resp = query_llm(test_prompt)
    print("Response:\n", resp)

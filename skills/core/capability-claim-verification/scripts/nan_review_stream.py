#!/usr/bin/env python3
"""Revisor externo de un documento largo con un modelo de NaN Builders, EN STREAMING.

Se usa junto a `templates/plan-review-prompt.md`: el prompt (contrato de revisión) se pasa
con NAN_REVIEW_PROMPT y el documento (plan/informe) como primer argumento.

Por que streaming: sin `"stream": true` Cloudflare corta la conexion a los 120 s
(HTTP 524, Proxy Read Timeout) en cuanto el modelo razona un poco. Con streaming se
mantiene viva (178 s verificados sin problema).

Por que se guardan DOS ficheros: los modelos de razonamiento (p. ej. `glm5.3-flash`)
emiten la cadena de pensamiento en `delta.reasoning_content` y la respuesta final en
`delta.content`, y **consumen `max_tokens` razonando**: con un valor bajo devuelven texto
vacio con `finish_reason: length`. Para una revision usa >= 40000.

Uso:
    NAN_REVIEW_PROMPT=/ruta/review_prompt.md python3 nan_review_stream.py <doc.md> <out.md> [max_tokens]

La key se toma de NAN_API_KEY o del `.env` del repo del pipeline. Nunca se imprime.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
ENDPOINT = "https://api.nan.builders/v1/chat/completions"
ENV_CANDIDATES = (
    "/root/marketing-campaign-generator/.env",
    "/host/root/marketing-campaign-generator/.env",
    "/opt/data/.env",
    "/root/hermes-agent-legacy-docker/.env",
)


def get_key():
    """Key de NaN: primero el entorno, luego los `.env` conocidos. Nunca se imprime."""
    if os.environ.get("NAN_API_KEY"):
        return os.environ["NAN_API_KEY"].strip()
    for path in ENV_CANDIDATES:
        try:
            for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
                if line.startswith("NAN_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            continue
    sys.exit("No encuentro NAN_API_KEY (exporta la variable o revisa el .env del repo).")


def main():
    doc_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])
    max_tokens = int(sys.argv[3]) if len(sys.argv) > 3 else 40000
    model = os.environ.get("NAN_MODEL", "glm5.3-flash")
    prompt_path = pathlib.Path(os.environ.get("NAN_REVIEW_PROMPT", ""))

    system = ("Eres un revisor senior de ingenieria. Respondes en espanol, tecnico y directo, "
              "sin relleno, y dices explicitamente lo que no puedes juzgar.")
    user = doc_path.read_text(encoding="utf-8")
    if prompt_path and prompt_path.is_file():
        user = prompt_path.read_text(encoding="utf-8") + "\n\n" + user

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {get_key()}",
                 "Content-Type": "application/json",
                 "User-Agent": UA,
                 "Accept": "text/event-stream"},
    )

    t0 = time.time()
    answer, reasoning, finish, usage = [], [], None, None
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                usage = obj.get("usage") or usage
                for choice in obj.get("choices", []):
                    finish = choice.get("finish_reason") or finish
                    delta = choice.get("delta") or {}
                    if delta.get("reasoning_content"):
                        reasoning.append(delta["reasoning_content"])
                    if delta.get("content"):
                        answer.append(delta["content"])
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTPError {exc.code}: {exc.read()[:300]}")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERR {type(exc).__name__}: {exc}")

    text = "".join(answer)
    out_path.write_text(text, encoding="utf-8")
    if reasoning:
        out_path.with_suffix(".reasoning.md").write_text("".join(reasoning), encoding="utf-8")

    print(f"modelo={model} {time.time() - t0:.0f}s finish={finish} "
          f"razonamiento={len(''.join(reasoning))} chars respuesta={len(text)} chars -> {out_path}")
    if usage:
        print("usage:", json.dumps(usage))
    if not text:
        print("AVISO: respuesta vacia. Sube max_tokens (los modelos de razonamiento gastan "
              "presupuesto pensando antes de escribir).")


if __name__ == "__main__":
    main()

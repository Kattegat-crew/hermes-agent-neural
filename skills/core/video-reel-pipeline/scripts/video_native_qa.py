#!/usr/bin/env python3
"""video_native_qa.py — QA de un film con el mp4 nativo como input del modelo.

Manda el video completo (no frames sueltos) junto al guion de narración y devuelve un
veredicto estructurado, con presupuesto de pasadas y cache por hash del artefacto.

Uso:
  python3 video_native_qa.py film.mp4 --script guion.txt [--cues cues.json] \
      [--model glm5.3-flash] [--max-passes 2] [--pre-gate] [--json]

Salida: veredicto legible por defecto, JSON con --json.
Exit: 0 aprueba · 1 bloquea · 2 error/degradado (fail-closed).

El VLM no mide píxeles ni lee texto pequeño: para eso está qa_gate.py (frames vacíos)
y el manifiesto de layout. Este script cubre lo que sólo se ve con el film corriendo:
sincronía voz/imagen, colisiones de texto, legibilidad en movimiento y ritmo.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.nan.builders/v1/chat/completions"
CONTRACT_VERSION = "1"
DEFAULT_MODEL = "glm5.3-flash"
DEFAULT_MAX_PASSES = 2
DEFAULT_MAX_MB = 40.0
DEFAULT_TIMEOUT = 300
MAX_TOKENS = 3000
MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
SEVERITIES = ("critical", "high", "medium", "low")
HARD_BLOCK = ("critical", "high")
CONFIRM_WINDOW_S = 1.5


class QAError(RuntimeError):
    """Error de operación: no hay veredicto posible."""


# ── artefacto ────────────────────────────────────────────────────────────────
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise QAError(f"ffprobe no ejecutable: {exc}") from exc
    if out.returncode != 0:
        raise QAError(f"ffprobe falló: {(out.stderr or '').strip()[:200]}")
    try:
        duration = float(json.loads(out.stdout)["format"]["duration"])
    except (KeyError, ValueError, TypeError) as exc:
        raise QAError(f"duración ilegible en {path.name}: {exc}") from exc
    if duration <= 0:
        raise QAError(f"duración no positiva en {path.name}: {duration}")
    return duration


def run_pre_gate(video: Path, allow: str = "") -> tuple[int, str]:
    """Corre qa_gate.py. `allow` son los segundos de negro intencional (frase de apertura, actos)."""
    gate = Path(__file__).with_name("qa_gate.py")
    if not gate.exists():
        raise QAError(f"falta el gate determinista: {gate}")
    cmd = [sys.executable, str(gate), str(video), "--quiet"]
    if allow.strip():
        cmd += ["--allow", allow.strip()]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return out.returncode, (out.stdout + out.stderr).strip()


# ── payload ──────────────────────────────────────────────────────────────────
def build_prompt(script: str, cues, duration: float) -> str:
    timed = ""
    if cues:
        lines = [f"  [{float(c['t']):.1f}s] {c['text']}" for c in cues if "t" in c and "text" in c]
        if lines:
            timed = "\nRITMO DECLARADO (segundos por línea):\n" + "\n".join(lines) + "\n"
    return f"""You are the QA reviewer of a marketing film. The video is the artifact under test.
Duration: {duration:.1f}s.

Judge ONLY what you can see and hear in the video, against the narration script below.

NARRATION SCRIPT (in order, as recorded):
{script.strip()}
{timed}
Definitions:
- void: a stretch where nothing on screen carries the voice (black or empty frame).
- collision: two texts overlapping, or on-screen text unreadable against what is behind it.
- narration_sync ok=false ONLY when the visuals contradict the spoken line or drift >0.5s.
- pacing: judge whether the film reads as a film or as a static deck.

Return ONLY minified JSON with this exact shape. Start with the opening brace, end with the
closing brace. No prose, no analysis, no markdown fences, no explanation before or after:
{{"passed":true|false,"score":0-10,
"voids":[{{"t":0.0,"why":"..."}}],
"collisions":[{{"t":0.0,"why":"..."}}],
"narration_sync":{{"ok":true|false,"mismatches":[{{"t":0.0,"script_line":"...","seen":"..."}}]}},
"legibility":{{"ok":true|false,"issues":[{{"t":0.0,"why":"..."}}]}},
"pacing":{{"ok":true|false,"why":"..."}},
"blocking":[{{"severity":"critical|high|medium|low","t":0.0,"what":"..."}}]}}

Empty arrays when nothing is wrong. `blocking` must list every defect that should stop
publication; use critical/high only for defects a viewer would notice without being told."""


def build_payload(video: Path, model: str, prompt: str, max_tokens: int,
                  json_mode: bool = True, quiet_thinking: bool = True) -> dict:
    mime = MIME.get(video.suffix.lower(), "video/mp4")
    b64 = base64.b64encode(video.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if quiet_thinking:
        # GLM razona antes de responder; sin acotarlo se come el presupuesto de salida
        # y el JSON queda truncado. Medido: 3000 tokens de razonamiento sin veredicto.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["reasoning_effort"] = "none"
    return payload


def _without_optional(payload: dict) -> dict:
    """Reintento para gateways que rechazan campos opcionales desconocidos."""
    return {k: v for k, v in payload.items()
            if k not in ("response_format", "chat_template_kwargs", "reasoning_effort")}

def _post(payload: dict, api_key: str, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise QAError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise QAError(f"llamada al modelo falló: {exc}") from exc


# ── veredicto ────────────────────────────────────────────────────────────────
def _as_time(value) -> float | None:
    """Tiempo del modelo: nunca lanza. Acepta 4, 4.2, "4.2", "~4s"; lo demás es desconocido."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        return float(match.group()) if match else None
    return None


def parse_verdict(text: str) -> dict | None:
    """Parseo estricto: sin las claves del contrato no hay veredicto, y sin veredicto no hay pase."""
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("passed"), bool):
        return None
    if not isinstance(data.get("score"), (int, float)):
        return None
    blocking = data.get("blocking")
    if not isinstance(blocking, list):
        return None
    clean = []
    for item in blocking:
        if not isinstance(item, dict):
            return None
        sev = str(item.get("severity", "")).lower()
        what = str(item.get("what", "")).strip()
        if sev not in SEVERITIES or not what:
            return None
        clean.append({"severity": sev, "t": _as_time(item.get("t")), "what": what})
    out = dict(data)
    out["blocking"] = clean
    return out


def decide(passes: list[dict]) -> dict:
    """Agrega pasadas: critical/high bloquean solos; medium necesita DOS PASADAS distintas.

    El contador es el conjunto de índices de pasada donde apareció, no el número de
    ocurrencias: dos hallazgos medium idénticos dentro de la misma respuesta son una
    sola pasada y no confirman nada.
    """
    confirmed: list[dict] = []
    for idx, p in enumerate(passes):
        for f in p.get("blocking", []):
            match = None
            for c in confirmed:
                if c["severity"] != f["severity"]:
                    continue
                a, b = c.get("t"), f.get("t")
                same_what = c["what"].strip().lower() == f["what"].strip().lower()
                if a is None and b is None and same_what:
                    match = c
                elif a is not None and b is not None and abs(a - b) <= CONFIRM_WINDOW_S:
                    match = c
                if match:
                    break
            if match:
                match["_idx"].add(idx)
            else:
                entry = dict(f)
                entry["_idx"] = {idx}
                confirmed.append(entry)

    for c in confirmed:
        c["passes"] = len(c.pop("_idx"))

    blocking = [f for f in confirmed if f["severity"] in HARD_BLOCK or f["passes"] >= 2]
    blocking_ids = {id(f) for f in blocking}
    warnings = [f for f in confirmed if id(f) not in blocking_ids]

    unnamed = [p for p in passes if not p.get("passed") and not p.get("blocking")]
    passed = not blocking and not unnamed
    reason = "ok"
    if blocking:
        reason = "defectos confirmados"
    elif unnamed:
        reason = "revisor rechazó sin nombrar defecto"
    return {
        "passed": passed,
        "reason": reason,
        "blocking": [{k: v for k, v in f.items() if k != "passes"} for f in blocking],
        "warnings": [{k: v for k, v in f.items() if k != "passes"} for f in warnings],
        "score": min((float(p.get("score", 0)) for p in passes), default=0.0),
    }


# ── cache ────────────────────────────────────────────────────────────────────
def state_dir() -> Path:
    raw = os.environ.get("VIDEO_QA_STATE")
    if raw:
        return Path(raw)
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "video-qa"


def cache_key(video_sha: str, model: str, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (video_sha, model, CONTRACT_VERSION, prompt):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def read_cache(key: str) -> dict | None:
    path = state_dir() / "receipts" / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(key: str, receipt: dict) -> None:
    path = state_dir() / "receipts" / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────────────────────
def _fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 2


def main(argv=None, *, transport=_post) -> int:
    ap = argparse.ArgumentParser(description="QA de un film con el mp4 nativo como input.")
    ap.add_argument("video")
    ap.add_argument("--script", required=True, help="guion de la narración (texto)")
    ap.add_argument("--cues", help="JSON opcional con [{t, text}] del ritmo declarado")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-passes", type=int, default=DEFAULT_MAX_PASSES)
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--pre-gate", action="store_true", help="corre qa_gate.py antes de gastar tokens")
    ap.add_argument("--pre-gate-allow", default="",
                    help="segundos de negro intencional que el gate determinista tolera (0,22,43)")
    ap.add_argument("--force", action="store_true", help="ignora la cache")
    ap.add_argument("--no-json-mode", action="store_true",
                    help="no pide response_format=json_object (para modelos que no lo soportan)")
    ap.add_argument("--dry-run", action="store_true", help="arma el payload sin llamar al modelo")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args(argv)

    video = Path(args.video)
    if not video.exists():
        return _fail(f"no existe el video: {video}")
    size_mb = video.stat().st_size / 1e6
    if size_mb > args.max_mb:
        return _fail(f"video de {size_mb:.1f} MB excede --max-mb {args.max_mb} (base64 infla ~33%)")
    if video.suffix.lower() not in MIME:
        return _fail(f"extensión no soportada: {video.suffix}")

    script_path = Path(args.script)
    if not script_path.exists():
        return _fail(f"no existe el guion: {script_path}")
    script = script_path.read_text(encoding="utf-8")
    if not script.strip():
        return _fail(f"guion vacío: {script_path}")

    cues = None
    if args.cues:
        try:
            cues = json.loads(Path(args.cues).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _fail(f"cues ilegibles: {exc}")

    if args.max_passes < 1:
        return _fail("--max-passes debe ser >= 1")

    try:
        duration = probe_duration(video)
    except (QAError, OSError, subprocess.SubprocessError) as exc:
        return _fail(str(exc))

    if args.pre_gate:
        try:
            code, detail = run_pre_gate(video, args.pre_gate_allow)
        except (QAError, OSError, subprocess.SubprocessError) as exc:
            return _fail(f"pre-gate no ejecutable: {exc}")
        if code == 2:
            return _fail(f"el gate determinista no pudo medir el film: {detail[:300]}")
        if code != 0:
            report = {"passed": False, "reason": "gate determinista", "detail": detail,
                      "model_calls": 0, "video": str(video)}
            print(json.dumps(report, ensure_ascii=False) if args.json else detail)
            return 1

    prompt = build_prompt(script, cues, duration)
    video_sha = sha256_file(video)
    key = cache_key(video_sha, args.model, prompt)

    if args.dry_run:
        payload = build_payload(video, args.model, prompt, args.max_tokens)
        size = len(json.dumps(payload))
        mime = MIME.get(video.suffix.lower(), "video/mp4")
        extra = f"payload {size/1e6:.2f} MB · {args.max_passes} pasada(s) máx"
        print(json.dumps({"dry_run": True, "model": args.model, "prompt": prompt,
                          "media_type": mime,
                          "video_url_prefix": f"data:{mime};base64,…",
                          "payload_mb": round(size / 1e6, 2), "note": extra},
                         ensure_ascii=False, indent=2) if args.json
              else f"dry-run OK · {size/1e6:.2f} MB · data:{mime};base64 · {extra}")
        return 0

    api_key = os.environ.get("NAN_BUILDERS_API_KEY", "").strip()
    if not api_key:
        return _fail("falta NAN_BUILDERS_API_KEY")

    if not args.force:
        cached = read_cache(key)
        if cached:
            report = dict(cached, cached=True)
            _emit(report, args.json)
            return 0 if report.get("passed") else 1

    json_mode = not args.no_json_mode
    payload = build_payload(video, args.model, prompt, args.max_tokens, json_mode=json_mode)
    passes: list[dict] = []
    tokens_in = tokens_out = 0
    attempts = 0
    started = time.time()
    # `attempts` cuenta LLAMADAS al modelo, no veredictos: el reintento de compatibilidad
    # también gasta presupuesto. `--max-passes` es un techo de llamadas, no de bucles.
    while attempts < args.max_passes and len(passes) < args.max_passes:
        attempts += 1
        try:
            resp = transport(payload, api_key, args.timeout)
        except QAError as exc:
            msg = str(exc)
            optional = "response_format" in payload or "chat_template_kwargs" in payload
            retryable = optional and ("HTTP 400" in msg or "HTTP 422" in msg)
            if retryable and attempts < args.max_passes:
                attempts += 1
                payload = _without_optional(payload)
                try:
                    resp = transport(payload, api_key, args.timeout)
                except QAError as exc2:
                    passes.append({"passed": False, "score": 0, "blocking": [],
                                   "error": str(exc2), "invalid": True})
                    continue
            else:
                passes.append({"passed": False, "score": 0, "blocking": [],
                               "error": msg, "invalid": True})
                continue
        usage = resp.get("usage") or {}
        tokens_in += int(usage.get("prompt_tokens", 0))
        tokens_out += int(usage.get("completion_tokens", 0))
        try:
            message = resp["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            passes.append({"passed": False, "score": 0, "blocking": [], "invalid": True})
            continue
        # Modelos con razonamiento devuelven el texto en content y el análisis en
        # reasoning_content/reasoning; si content viene vacío el veredicto está ahí.
        text = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
        v = parse_verdict(text)
        if v is None:
            passes.append({"passed": False, "score": 0, "blocking": [], "invalid": True,
                           "raw": text[:400] if isinstance(text, str) else "",
                           "message_keys": sorted(message)})
            continue
        passes.append(v)
        if any(f["severity"] in HARD_BLOCK for f in v["blocking"]):
            break
        if v["passed"]:
            break

    valid = [p for p in passes if not p.get("invalid")]
    if not valid:
        report = {"passed": False, "reason": "sin veredicto válido (degradado)",
                  "model": args.model, "model_calls": attempts,
                  "tokens": {"in": tokens_in, "out": tokens_out},
                  "raw": [p["raw"] for p in passes if p.get("raw")],
                  "message_keys": [p["message_keys"] for p in passes if p.get("message_keys")],
                  "errors": [p["error"] for p in passes if p.get("error")]}
        _emit(report, args.json)
        return 2

    decision = decide(valid)
    report = {
        **decision,
        "model": args.model,
        "model_calls": attempts,
        "invalid_passes": len(passes) - len(valid),
        "tokens": {"in": tokens_in, "out": tokens_out},
        "latency_s": round(time.time() - started, 1),
        "video": str(video),
        "video_sha256": video_sha[:16],
        "cached": False,
    }
    write_cache(key, report)
    _emit(report, args.json)
    return 0 if decision["passed"] else 1


def _emit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    state = "APRUEBA" if report.get("passed") else "BLOQUEA"
    print(f"{state} · {report.get('model', '?')} · score {report.get('score', 0)}/10 · "
          f"{report.get('model_calls', 0)} pasada(s) · "
          f"tokens {report.get('tokens', {}).get('in', 0)}/{report.get('tokens', {}).get('out', 0)}")
    for f in report.get("blocking", []):
        print(f"  [{f['severity']}] {f.get('t')}s — {f['what']}")
    for f in report.get("warnings", []):
        print(f"  ({f['severity']} sin confirmar) {f.get('t')}s — {f['what']}")
    if report.get("reason") and report["reason"] != "ok":
        print(f"  motivo: {report['reason']}")


if __name__ == "__main__":
    sys.exit(main())

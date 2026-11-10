"""Review engines: adaptadores para los motores que pueden actuar como reviewer.

Contrato único: cada motor devuelve (verdict | None, meta). `verdict` es un dict con
{passed, blocking[], non_blocking[], tests_adequate, summary}. Si el motor falla,
no responde o no respeta el esquema, `verdict` es None y `meta["error"]` explica por qué.

Qué sabe hacer cada motor (verificado, no supuesto):

  agy       `--json-schema` + `--output-format json` -> `structured_output`. Nativo.
            Necesita HOME aislado (dos instancias con el mismo HOME se matan) y un
            lock: se serializa con flock.
  codex     `--output-schema` estricto (OpenAI exige TODAS las claves en `required`)
            y `-o` para el mensaje final. Vive en el host y corre como root, así que
            SIEMPRE se invoca con `-s read-only`: un reviewer nunca escribe.
  opencode  `--format json` emite un stream de eventos; el texto del asistente llega
            como {"type":"text","part":{"text":...}}. No tiene esquema nativo: se pide
            JSON en el prompt y se parsea el último objeto balanceado.

El esquema portable es el más estricto (el de codex): todos los campos en `required`
y `additionalProperties: false`. Los adaptadores toleran valores vacíos al leerlo.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

# --- rutas y binarios (sobreescribibles por entorno) ---
AGY_BIN = os.environ.get("REVIEW_GATE_AGY_BIN", "/usr/local/bin/agy")
AGY_HOME_TMPL = Path(os.environ.get("REVIEW_GATE_AGY_HOME", "/opt/data/fleet/agy-home-review"))
AGY_HOME_SRC = Path(os.environ.get("REVIEW_GATE_AGY_SRC", "/opt/data/.gemini/antigravity-cli"))
AGY_LOCK = Path(os.environ.get("REVIEW_GATE_LOCK", "/opt/data/fleet/locks/review-agy.lock"))

CODEX_SSH = os.environ.get("REVIEW_GATE_CODEX_SSH", "root@127.0.0.1")
CODEX_PATH = os.environ.get("REVIEW_GATE_CODEX_PATH", "/root/.local/bin")
# `-c model_reasoning_effort=high` es lo que da el "en high" sin pagar el modelo grande.
CODEX_EFFORT = os.environ.get("REVIEW_GATE_CODEX_EFFORT", "high")
OPENCODE_BIN = os.environ.get("REVIEW_GATE_OPENCODE_BIN", "/usr/local/bin/opencode")
# HOME con opencode.json que define el agente `reviewer` con edit/bash denegados:
# un reviewer que puede escribir en el repo puede arreglar lo que revisa.
OPENCODE_HOME = Path(os.environ.get("REVIEW_GATE_OPENCODE_HOME",
                                    "/opt/data/fleet/opencode-review-home"))
OPENCODE_AGENT = os.environ.get("REVIEW_GATE_OPENCODE_AGENT", "reviewer")

# directorio compartido contenedor<->host para pasar prompt/schema/salida a codex
SHARED_TMP = Path(os.environ.get("REVIEW_GATE_SHARED", "/opt/data/fleet/workspaces/.review-engine"))

ENGINES = ("agy", "codex", "opencode")

# catálogo orientativo; `list_engines()` consulta el estado real cuando puede
MODELS = {
    "agy": [
        "gemini-3.8-flash-high",
        "gemini-4-argon-high",
        "claude-sonnet-5-5-high",
        "claude-opus-5-5-high",
        "gpt-oss-120b-medium",
    ],
    "codex": ["gpt-6.1-terra", "gpt-6-astra"],
    "opencode": [
        "opencode/deepseek-v4.1-flash-free",
        "opencode/glm-5.3-flash-free",
        "opencode/big-pickle",
        "opencode/minimax-m3.1-flash-free",
    ],
}

DEFAULTS = {
    "agy": os.environ.get("REVIEW_GATE_MODEL", "gemini-3.8-flash-high"),
    "codex": os.environ.get("REVIEW_GATE_CODEX_MODEL", "gpt-6.1-terra"),
    "opencode": "opencode/deepseek-v4.1-flash-free",
}


def _sh(cmd, cwd=None, timeout=120, env=None, input_text=None):
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
            timeout=timeout, env=env, input=input_text,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout tras {timeout}s"
    except (FileNotFoundError, OSError) as exc:
        return 127, "", str(exc)


def _meta(engine, model, provider, seconds, *, error=None, usage=None, cost=None):
    return {
        "engine": engine, "model": model, "provider": provider,
        "seconds": seconds, "error": error, "usage": usage, "cost": cost,
    }


SEVERITY_HINTS = (
    ("critical", ("critical", "critico", "crítico", "crítica", "critica")),
    ("high", ("high", "alto", "alta", "grave", "severo")),
    ("medium", ("medium", "medio", "media", "moderado")),
)


def _severity_from_text(text: str) -> str:
    low = (text or "").lower()
    for sev, hints in SEVERITY_HINTS:
        if any(h in low for h in hints):
            return sev
    return "medium"


def normalize_verdict(data) -> dict | None:
    """Normaliza el veredicto de cualquier motor. None = no es un veredicto utilizable.

    Hace falta porque no todos los motores respetan el esquema: opencode no tiene salida
    estructurada y puede devolver `blocking` como lista de frases. Eso no puede reventar
    el gate ni perderse: se convierte en hallazgos con severidad inferida.
    """
    if not isinstance(data, dict):
        return None
    # `passed` tiene que venir dicho por el motor. Deducirlo de la ausencia de hallazgos
    # convertiria un {} (o una respuesta truncada) en una aprobacion: fail-open.
    raw_passed = data.get("passed")
    if not isinstance(raw_passed, bool):
        return None
    # `blocking` es obligatorio: su ausencia no significa "no hay hallazgos",
    # significa que el motor no respondio el contrato. Tratarlo como lista vacia
    # convierte una respuesta truncada en una aprobacion.
    raw_blocking = data.get("blocking")
    if not isinstance(raw_blocking, list):
        return None

    blocking = []
    for item in raw_blocking:
        if isinstance(item, dict):
            issue = str(item.get("issue") or item.get("message")
                        or item.get("description") or "").strip()
            if not issue:
                # Un dict sin texto sigue siendo un hallazgo: descartarlo seria fail-open.
                issue = json.dumps(item, ensure_ascii=False)[:500]
            sev = str(item.get("severity") or "").lower()
            if sev not in {"critical", "high", "medium", "low"}:
                sev = _severity_from_text(sev + " " + issue)
            blocking.append({
                "severity": sev,
                "file": str(item.get("file") or "?"),
                "line": item.get("line") if isinstance(item.get("line"), int) else None,
                "issue": issue,
                "fix": str(item.get("fix") or ""),
            })
        else:
            # Ni un dict sin texto, ni un null, ni una cadena vacia pueden desaparecer:
            # `{"passed": true, "blocking": [null]}` acabaria aprobando un mal revisado.
            text = str(item).strip() if item is not None else ""
            blocking.append({
                "severity": "medium" if not text else _severity_from_text(text),
                "file": "?",
                "line": None,
                "issue": text or "hallazgo sin contenido devuelto por el motor",
                "fix": "",
            })

    raw_non_blocking = data.get("non_blocking")
    if not isinstance(raw_non_blocking, list):
        raw_non_blocking = []
    non_blocking = [str(x) for x in raw_non_blocking if isinstance(x, (str, int, float))]
    # Coherencia: un veredicto con bloqueantes no puede venir aprobado.
    passed = raw_passed and not blocking
    tests_adequate = data.get("tests_adequate")
    if not isinstance(tests_adequate, bool):
        tests_adequate = None

    return {
        "passed": passed,
        "blocking": blocking,
        "non_blocking": non_blocking,
        "tests_adequate": tests_adequate,
        "summary": str(data.get("summary") or "").strip(),
    }


# --------------------------------------------------------------------------- agy

def _ensure_agy_home(suffix: str = "") -> Path:
    home = Path(f"{AGY_HOME_TMPL}{suffix}")
    token = home / ".gemini/antigravity-cli/antigravity-oauth-token"
    if not token.exists():
        (home / ".gemini/antigravity-cli").mkdir(parents=True, exist_ok=True)
        for f in ("antigravity-oauth-token", "installation_id"):
            src = AGY_HOME_SRC / f
            if src.exists():
                shutil.copy2(src, home / ".gemini/antigravity-cli" / f)
    return home


def run_agy(repo: Path, prompt: str, schema_path: Path, model: str, timeout: int) -> tuple:
    import fcntl  # POSIX: el módulo declara platforms [linux, macos]

    try:
        home = _ensure_agy_home()
    except OSError as exc:
        return None, _meta("agy", model, None, 0.0, error=f"home de agy no utilizable: {exc}")

    AGY_LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fh = open(AGY_LOCK, "a")
        try:
            os.chmod(AGY_LOCK, 0o666)
        except OSError:
            pass
    except OSError:
        lock_fh = open(f"{AGY_LOCK}.{os.getuid()}", "a")
        home = _ensure_agy_home(suffix=f"-uid{os.getuid()}")

    deadline = time.monotonic() + timeout
    try:
        # Espera acotada: con otra revision AGY activa, un flock bloqueante se comeria
        # el presupuesto compartido y el gate acabaria degradando por su propia espera.
        while True:
            try:
                fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    # Sin cerrar aqui: el `finally` hace unlock+close y fallaria con
                    # ValueError sobre un handle ya cerrado.
                    return None, _meta("agy", model, None, 0.0,
                                       error=f"lock de agy ocupado mas de {timeout}s")
                time.sleep(0.5)

        env = dict(os.environ)
        env["HOME"] = str(home)
        env.pop("AGY_HOME", None)
        cmd = [
            AGY_BIN, "--mode", "plan", "--model", model, "--effort", "high",
            "--dangerously-skip-permissions", "--output-format", "json",
            "--json-schema", str(schema_path), "-p", prompt,
        ]
        left = max(15, int(deadline - time.monotonic()))
        t0 = time.time()
        rc, out, err = _sh(cmd, cwd=repo, timeout=left, env=env)
        seconds = round(time.time() - t0, 1)
    finally:
        try:
            if not lock_fh.closed:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except (OSError, ValueError):
            pass
        try:
            lock_fh.close()
        except OSError:
            pass

    if rc != 0:
        return None, _meta("agy", model, None, seconds, error=(err or out or "sin salida")[-800:])
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None, _meta("agy", model, None, seconds, error=f"salida no-JSON: {out[:300]}")
    if not isinstance(payload, dict):
        return None, _meta("agy", model, None, seconds,
                           error=f"salida JSON sin objeto: {str(payload)[:200]}")
    if payload.get("status") not in (None, "SUCCESS"):
        return None, _meta("agy", model, None, seconds,
                           error=f"status={payload.get('status')} {str(payload.get('error'))[:300]}")
    raw = payload.get("structured_output")
    if not isinstance(raw, dict):
        return None, _meta("agy", model, None, seconds,
                           error="respuesta sin structured_output (esquema no respetado)")
    verdict = normalize_verdict(raw)
    if verdict is None:
        return None, _meta("agy", model, None, seconds, error="veredicto con forma invalida")
    return verdict, _meta("agy", model, None, seconds, usage=payload.get("usage"))


# ------------------------------------------------------------------------- codex

def run_codex(repo: Path, prompt: str, schema_path: Path, model: str, timeout: int) -> tuple:
    """codex vive en el host y corre como root: siempre `-s read-only`, nunca el bypass."""
    try:
        SHARED_TMP.mkdir(parents=True, exist_ok=True)
        # 0700: el prompt contiene el diff privado del usuario. codex corre como root
        # y lee cualquier cosa, asi que cerrar el transporte no le afecta.
        os.chmod(SHARED_TMP, 0o700)
    except OSError as exc:
        return None, _meta("codex", model, None, 0.0,
                           error=f"transporte no utilizable: {exc}")

    token = hashlib.sha1(f"{prompt}{model}{time.time()}".encode()).hexdigest()[:12]
    prompt_p = SHARED_TMP / f"prompt-{token}.txt"
    schema_p = SHARED_TMP / f"schema-{token}.json"
    out_p = SHARED_TMP / f"out-{token}.json"
    try:
        prompt_p.write_text(prompt, encoding="utf-8")
        shutil.copy2(schema_path, schema_p)
        for p in (prompt_p, schema_p):
            os.chmod(p, 0o600)
    except OSError as exc:
        return None, _meta("codex", model, None, 0.0, error=f"no se pudo preparar el transporte: {exc}")

    remote = (
        f"export PATH={shlex.quote(CODEX_PATH)}:$PATH; "
        f"cd {shlex.quote(str(repo))} && "
        f"codex exec -m {shlex.quote(model)} -s read-only --skip-git-repo-check "
        f"-c {shlex.quote(f'model_reasoning_effort={CODEX_EFFORT}')} "
        f"-C {shlex.quote(str(repo))} "
        f"--output-schema {shlex.quote(str(schema_p))} "
        f"-o {shlex.quote(str(out_p))} "
        f'"$(cat {shlex.quote(str(prompt_p))})"'
    )
    t0 = time.time()
    rc, out, err = _sh(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", CODEX_SSH, remote],
        timeout=timeout,
    )
    seconds = round(time.time() - t0, 1)

    verdict = None
    error = None
    if rc != 0:
        error = (err or out or "sin salida")[-800:]
    elif not out_p.exists():
        error = "codex no produjo mensaje final (-o)"
    else:
        try:
            data = json.loads(out_p.read_text(encoding="utf-8"))
            verdict = normalize_verdict(data)
            if verdict is None:
                error = "la salida de codex no es un veredicto utilizable"
        except (OSError, json.JSONDecodeError) as exc:
            error = f"salida de codex ilegible: {exc}"

    for p in (prompt_p, schema_p, out_p):
        try:
            p.unlink()
        except OSError:
            pass
    return verdict, _meta("codex", model, None, seconds, error=error)


# ---------------------------------------------------------------------- opencode

def _last_json_object(text: str) -> dict | None:
    """Extrae el ultimo objeto JSON del texto.

    Se apoya en `raw_decode` en lugar de contar llaves: contar llaves falla con un `}`
    dentro de una cadena (p.ej. summary="cierra con }"), que es un veredicto valido.
    """
    text = text.strip()
    decoder = json.JSONDecoder()
    best: dict | None = None
    idx = 0
    while True:
        start = text.find("{", idx)
        if start == -1:
            return best
        try:
            obj, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            idx = start + 1
            continue
        if isinstance(obj, dict):
            best = obj
        idx = start + end


def _opencode_isolation(config: Path) -> tuple[bool, str]:
    """Acredita que la config deniega de verdad escritura y shell.

    Que exista opencode.json no prueba nada: un `{}` tambien existe. Se exige la
    politica efectiva, porque de ella depende que el reviewer no toque el repo.
    """
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"config ilegible: {exc}"
    if not isinstance(data, dict):
        return False, "config sin objeto JSON"
    perms = data.get("permission")
    if not isinstance(perms, dict):
        return False, "config sin bloque permission"
    for key in ("edit", "bash"):
        if perms.get(key) != "deny":
            return False, f"permission.{key} no es 'deny'"
    agent = data.get("agent")
    if isinstance(agent, dict) and OPENCODE_AGENT in agent:
        ap = agent[OPENCODE_AGENT].get("permission")
        if isinstance(ap, dict):
            for key in ("edit", "bash"):
                if ap.get(key) not in (None, "deny"):
                    return False, f"agente {OPENCODE_AGENT}: {key} no es 'deny'"
    return True, ""


def _tree_state(repo: Path) -> str | None:
    """Huella del working tree: detecta si el reviewer escribio algo.

    `git status` solo dice QUE archivos cambiaron, no si cambiaron durante la revision:
    un archivo ya modificado sigue igual de "M" aunque sus bytes cambien. Por eso se
    hashea tambien el contenido de cada archivo listado.
    """
    rc, out, _ = _sh(["git", "-C", str(repo), "status", "--porcelain", "-uall"], timeout=30)
    if rc != 0:
        return None  # sin huella no se puede verificar: el llamador lo trata como error
    digest = hashlib.sha256(out.encode())
    for line in out.splitlines():
        raw = line[3:].strip().strip('"')
        if " -> " in raw:
            raw = raw.split(" -> ")[-1].strip().strip('"')
        try:
            digest.update(hashlib.sha256((repo / raw).read_bytes()).digest())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def run_opencode(repo: Path, prompt: str, model: str, provider: str | None, timeout: int) -> tuple:
    # opencode no tiene -C: el repo debe ser el cwd o choca contra external_directory.
    # Tampoco tiene un flag de solo lectura, asi que se aisla por configuracion
    # (agente `reviewer` con edit/bash denegados) y se verifica que no escribio.
    full_model = model if "/" in model else f"{provider or 'opencode'}/{model}"
    cmd = [OPENCODE_BIN, "run", "-m", full_model, "--format", "json"]
    if OPENCODE_AGENT:
        cmd += ["--agent", OPENCODE_AGENT]
    cmd.append(prompt)

    config = OPENCODE_HOME / ".config/opencode/opencode.json"
    ok, why = _opencode_isolation(config)
    if not ok:
        # Fail-closed: sin politica comprobada que deniegue edit/bash, opencode
        # heredaria los permisos del usuario y podria escribir en el repo revisado.
        return None, _meta("opencode", full_model, provider, 0.0,
                           error=f"aislamiento no acreditado: {why}")

    env = dict(os.environ)
    env["HOME"] = str(OPENCODE_HOME)
    env["XDG_CONFIG_HOME"] = str(OPENCODE_HOME / ".config")

    # opencode fusiona la config del proyecto con la global: un repo hostil podria
    # reabrir edit/bash. Si el repo trae su propia config, no se le da ese control.
    project_configs = (
        repo / "opencode.json", repo / "opencode.jsonc",
        repo / ".opencode", repo / ".opencode/opencode.json",
        repo / ".opencode/opencode.jsonc",
    )
    for proj in project_configs:
        if proj.exists():
            return None, _meta("opencode", full_model, provider, 0.0,
                               error=f"el repo trae configuracion de opencode ({proj.name}); "
                                     "el aislamiento no seria confiable")

    before = _tree_state(repo)
    if before is None:
        return None, _meta("opencode", full_model, provider, 0.0,
                           error="no se pudo tomar la huella del arbol; revision no verificable")
    t0 = time.time()
    rc, out, err = _sh(cmd, cwd=repo, timeout=timeout, env=env)
    seconds = round(time.time() - t0, 1)

    if before != _tree_state(repo):
        return None, _meta("opencode", full_model, provider, seconds,
                           error="el reviewer modifico el arbol de trabajo; veredicto descartado")

    if rc != 0:
        return None, _meta("opencode", full_model, provider, seconds,
                           error=(err or out or "sin salida")[-800:])

    chunks, cost = [], None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            chunks.append(line)
            continue
        if not isinstance(ev, dict):
            continue  # `null`, `[]`, un numero: no son eventos de texto
        part = ev.get("part")
        if not isinstance(part, dict):
            part = {}
        text = part.get("text")
        if isinstance(text, str) and (ev.get("type") == "text" or part.get("type") == "text"):
            chunks.append(text)
        if isinstance(ev.get("cost"), (int, float)):
            cost = (cost or 0) + ev["cost"]

    # opencode trocea el texto en eventos arbitrarios: unirlos con "\n" puede partir
    # una clave JSON y romperla. Se prueba primero la concatenación exacta.
    verdict = None
    error = None
    for text in ("".join(chunks), "\n".join(chunks)):
        if text:
            verdict = normalize_verdict(_last_json_object(text))
            if verdict is not None:
                break
    if verdict is None:
        error = f"sin veredicto JSON en la respuesta: {''.join(chunks)[:300]}"
    return verdict, _meta("opencode", full_model, provider, seconds, error=error, cost=cost)


# ------------------------------------------------------------------------ router

def run_engine(engine: str, repo: Path, prompt: str, schema_path: Path,
               model: str | None = None, provider: str | None = None,
               timeout: int = 900):
    """Ejecuta un motor y normaliza el resultado."""
    engine = (engine or "").lower()
    if engine not in ENGINES:
        return None, _meta(engine or "?", model, provider, 0.0,
                           error=f"motor desconocido: {engine!r} (usa {', '.join(ENGINES)})")
    model = model or DEFAULTS[engine]
    if engine == "agy":
        return run_agy(repo, prompt, schema_path, model, timeout)
    if engine == "codex":
        return run_codex(repo, prompt, schema_path, model, timeout)
    return run_opencode(repo, prompt, model, provider, timeout)


def parse_engine_spec(spec: str) -> tuple:
    """'codex:gpt-6-astra' -> ('codex', 'gpt-6-astra', None)
    'opencode:opencode/x:provider' -> ('opencode', 'opencode/x', 'provider')"""
    engine, _, rest = spec.partition(":")
    engine = engine.strip().lower()
    model: str | None = None
    provider: str | None = None
    if rest:
        if engine == "opencode" and rest.count(":") >= 1 and "/" in rest:
            model, _, provider = rest.partition(":")
        else:
            model = rest
    return engine, (model.strip() if model else None), (provider.strip() if provider else None)


def list_engines() -> dict:
    """Catálogo vivo cuando el motor puede reportarlo; si no, el orientativo."""
    out = {}
    rc, stdout, _ = _sh([AGY_BIN, "models"], timeout=30)
    out["agy"] = [line.split("\t")[0] for line in stdout.splitlines() if "\t" in line] if rc == 0 else MODELS["agy"]
    rc, stdout, _ = _sh([OPENCODE_BIN, "models"], timeout=40)
    out["opencode"] = [line.strip() for line in stdout.splitlines() if line.strip()] if rc == 0 else MODELS["opencode"]
    out["codex"] = MODELS["codex"]
    return out

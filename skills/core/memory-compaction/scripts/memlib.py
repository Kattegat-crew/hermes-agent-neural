#!/usr/bin/env python3
"""Núcleo compartido de la skill memory-compaction. Solo stdlib.

Replica el parseo real del runtime de Hermes (``ENTRY_DELIMITER = "\\n§\\n"``,
ver ``tools/memory_tool_store.py``), resuelve rutas de store por perfil y calcula
cobertura de tokens contra corpus en disco (brain, repos, skills, vault, Engram).
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

ENTRY_DELIMITER = "\n§\n"
DEFAULT_HOME = "/opt/hermes-agent-data"
DEFAULT_MEMORY_LIMIT = 100000
DEFAULT_USER_LIMIT = 8000

# Palabras vacías (ES/EN) que no sirven como evidencia de contenido.
STOPWORDS = set("""
de la que el en y a los se del las un una unos unas por con no sin para es son fue ser
su sus al lo como mas pero si ya muy este esta estos estas ese esa esos esas otro otra
todo toda todos todas hay ha han he hemos esta estan estaba estaban era eran tiene tienen
desde hasta entre sobre bajo tras durante contra segun cuando donde porque aunque mientras
the and for with that this from are was were will have has had not but can could should
would may might must into over under than then there their they its it's you your we our
also more most some such only just about after before when where which who whom what how
todo tipo parte cosa cosas forma manera caso casos vez veces dia dias hora horas
""".split())

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_@/:.#\-]{2,}")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b|\b(?:hoy|ayer|mañana|anoche|esta semana|el lunes|el martes)\b", re.I)
PROC_RE = re.compile(r"\b(usar|usa|usando|comando|comandos|pasos|paso|primero|segundo|nunca|siempre|"
                     r"regla|reglas|invariante|prohibido|verificar|verificar_|gate|choke\s?point|script)\b", re.I)
INVARIANT_RE = re.compile(r"\b(nunca|prohibido|invariante|regla dura|obligatorio|jamás|jamas|cero|solo se|"
                          r"exige|requiere autorizaci[oó]n|sin aprobaci[oó]n)\b", re.I)
PATH_RE = re.compile(r"(?:/opt|/root|/etc|/var|/usr|~/)[\w./@\-]+")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def parse_entries(text: str) -> list[str]:
    """Divide el store en entradas igual que el runtime; descarta vacías."""
    parts = text.split(ENTRY_DELIMITER)
    if len(parts) == 1 and "\n§\n" not in text:
        # tolera ficheros editados a mano con "§" suelto por línea
        parts = re.split(r"(?m)^\s*§\s*$", text)
    return [p.strip() for p in parts if p.strip()]


def join_entries(entries: list[str]) -> str:
    return ENTRY_DELIMITER.join(entries) + ("\n" if entries else "")


def summarize(entry: str, max_chars: int = 90) -> str:
    lines = [ln for ln in entry.splitlines() if ln.strip()]
    head = lines[0] if lines else entry
    head = " ".join(head.split())
    return head if len(head) <= max_chars else head[: max_chars - 3].rstrip() + "..."


def distinctive_tokens(text: str) -> set[str]:
    """Tokens que sirven como huella: números, rutas, IDs, emails y palabras raras."""
    out: set[str] = set()
    for raw in TOKEN_RE.findall(text):
        tok = raw.strip(".,;:()[]{}<>\"'`*|")
        if not tok:
            continue
        low = tok.lower()
        if low in STOPWORDS:
            continue
        has_signal = (
            any(c.isdigit() for c in tok)
            or any(c in tok for c in "_@/:#\\")
            or re.search(r"[a-záéíóúñ][A-ZÁÉÍÓÚÑ]", tok) is not None
            or len(tok) >= 6
        )
        if has_signal:
            out.add(low)
    return out


def word_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9áéíóúñü_]+", text.lower()) if len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def coverage(tokens: set[str], corpus_tokens: set[str]) -> float:
    if not tokens:
        return 1.0
    return len(tokens & corpus_tokens) / len(tokens)


def load_text(path: Path, max_bytes: int = 1_500_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                return fh.read(max_bytes)
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def default_corpus_globs(brain: Path) -> dict[str, list[Path]]:
    """Rutas curadas por destino. Excluye raw/, graphify-out*/ y archive/ del brain."""
    brain_files: list[Path] = []
    for sub in ("", "entities", "concepts", "ops", "analysis", "campaigns", "plans", "projects", "decisions"):
        d = brain / sub if sub else brain
        if d.is_dir():
            brain_files.extend(sorted(d.glob("*.md")))

    repo_files: list[Path] = []
    for project_memory in sorted(Path("/opt").glob("*/PROJECT_MEMORY.md")) + sorted(Path("/opt").glob("*/*/PROJECT_MEMORY.md")):
        root = project_memory.parent
        for name in ("PROJECT_MEMORY.md", "AGENTS.md", "ARCHITECTURE.md"):
            f = root / name
            if f.is_file():
                repo_files.append(f)
        rules = root / ".agents" / "rules"
        if rules.is_dir():
            repo_files.extend(sorted(rules.glob("*.md")))

    skill_files: list[Path] = []
    for root in (Path("/opt/data/skills"), Path("/opt/hermes-agent/skills")):
        if not root.is_dir():
            continue
        skill_files.extend(sorted(root.glob("*/**/SKILL.md")))
        skill_files.extend(sorted(root.glob("*/**/references/*.md")))
    skill_files = sorted(set(skill_files))

    vault_files: list[Path] = []
    for root in (Path("/opt/vault"), Path("/opt/vps-brain")):
        if root.is_dir():
            vault_files.extend(sorted(root.glob("*.md")))

    return {"brain": brain_files, "repo": repo_files, "skill": skill_files, "vault": vault_files}


def build_corpus(files: dict[str, list[Path]], max_bytes: int = 1_500_000) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for kind, paths in files.items():
        token_set: set[str] = set()
        texts: dict[str, str] = {}
        for p in paths:
            text = load_text(p, max_bytes)
            if not text:
                continue
            texts[str(p)] = text
            token_set |= word_set(text) | distinctive_tokens(text)
        out[kind] = {"tokens": token_set, "texts": texts}
    return out


def resolve_store(home: str | None = None, profile: str | None = None) -> dict:
    """Rutas de store. El runtime lee <HERMES_HOME>/memories/{MEMORY,USER}.md."""
    base_home = Path(home or os.environ.get("HERMES_HOME") or DEFAULT_HOME).expanduser()
    profile = profile or "default"
    base = base_home if profile == "default" else base_home / "profiles" / profile
    store = {
        "home": base_home,
        "profile": profile,
        "base": base,
        "memory": base / "memories" / "MEMORY.md",
        "user": base / "memories" / "USER.md",
        "legacy_memory": base / "MEMORY.md",
        "legacy_user": base / "USER.md",
        "config": base / "config.yaml",
    }
    store["warnings"] = []
    if not store["config"].is_file():
        store["config"] = base_home / "config.yaml"
    if store["legacy_memory"].is_file() and store["legacy_memory"].stat().st_size > 0:
        store["warnings"].append(
            f"{store['legacy_memory']} existe con contenido pero el runtime NO lo lee (H3): "
            f"la ruta viva es {store['memory']}")
    if not store["memory"].is_file():
        store["warnings"].append(f"no existe {store['memory']} (el store nativo está vacío para este perfil)")
    return store


def read_limits(config_path: Path) -> dict[str, int]:
    text = load_text(config_path, 200_000) if config_path and config_path.is_file() else ""
    limits = {"memory": DEFAULT_MEMORY_LIMIT, "user": DEFAULT_USER_LIMIT, "index_char_limit": 0}
    if not text:
        return limits
    block = re.search(r"(?ms)^memory:\s*\n(.*?)(?=^\S|\Z)", text)
    body = block.group(1) if block else text
    for key, target in (("memory_char_limit", "memory"), ("user_char_limit", "user")):
        m = re.search(rf"(?m)^\s*{key}:\s*(\d+)", body)
        if m:
            limits[target] = int(m.group(1))
    m = re.search(r"(?m)^\s*index_char_limit:\s*(\d+)", body)
    if m:
        limits["index_char_limit"] = int(m.group(1))
    return limits


def target_path(store: dict, target: str) -> Path:
    if target == "user":
        return Path(store["user"])
    if target == "memory":
        return Path(store["memory"])
    raise SystemExit(f"target inválido: {target} (usa memory|user)")

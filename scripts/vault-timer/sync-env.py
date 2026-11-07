#!/usr/bin/env python3
"""Sync vault items into .env files — SSOT de la Política de Secretos (Fase 1).

Llamado por /opt/vault/timer/vault-sync.sh con SESSION como argv[1].

Spec: .specs/politica-secretos-vault-sync/01-spec.md  ·  Design: 02-design.md

Diseño (ver 02-design.md):
  * MERGE PRESERVATIVO a nivel de línea (RF-1..RF-4): solo cambian las líneas
    cuya clave esta en ``mappings``; comentarios, lineas en blanco, claves ajenas,
    prefijos ``export`` y estilos de fin de linea se conservan byte a byte.
  * PARIDAD DEV/PROD (RF-5): guard de directorio padre (SKIPPED), captura de
    OSError por target (FAILED), SUMMARY final, ``owner`` con aviso si no existe,
    restart SOLO si el contenido cambio y fallback ``notes`` del secure note.
  * ESCRITURA ATOMICA (RF-6): temporal en el mismo directorio + os.replace; si
    falla, el .env original queda intacto y el target cuenta FAILED.
  * Exit 1 solo si failed>0 and ok==0 (RF-7); bw list items con timeout 30s (RF-8).

Contrato de log (sin cambios, lo usa /var/log/vault-sync.log):
  Processing: <file> | WARNING: ... | Updated: KEY | SKIPPED: ... | FAILED: ...
  DONE:<file> | SUMMARY: ok=N skipped=N failed=N
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_MAPFILE = "/opt/vault/timer/vault-to-env-map.json"

_KV_RE = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=(?P<rest>.*)$"
)


class VaultFetchError(RuntimeError):
    """bw no devolvio el listado de items (RC!=0 o JSON invalido)."""


# ----------------------------------------------------------------- RF-1..RF-4
def split_eol(line: str) -> tuple[str, str]:
    """(cuerpo, terminador) conservando '\\n', '\\r\\n', '\\r' o ''."""
    for eol in ("\r\n", "\n", "\r"):
        if line.endswith(eol):
            return line[: -len(eol)], eol
    return line, ""


def split_value_comment(rest: str) -> tuple[str, str]:
    """(valor, comentario_en_linea) consciente de comillas: ' #' dentro de
    comillas NO es comentario; ' #' (espacio + #) fuera de comillas si lo es."""
    quote = None
    i = 0
    while i < len(rest):
        c = rest[i]
        if quote:
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
        elif c == "#" and i > 0 and rest[i - 1] in (" ", "\t"):
            # el comentario conserva el espacio/tab que lo precede
            return rest[:i].rstrip(), rest[i - 1 :]
        i += 1
    return rest, ""


def merge_env_text(text: str, updates: dict) -> str:
    """RF-1..RF-4: solo sustituye valores de claves mapeadas; el resto es literal."""
    if text.startswith("\ufeff"):
        # BOM inicial: si no se descarta, la primera clave no matchea y RF-4
        # crearia una DUPLICADA al final (revision adversarial, hallazgo H3).
        text = text[1:]
    lines = text.splitlines(keepends=True) if text else []
    seen = set()
    out = []
    for line in lines:
        body, eol = split_eol(line)
        if body.strip() and not body.lstrip().startswith("#"):
            m = _KV_RE.match(body)
            if m:
                key = m.group("key")
                if key in updates:
                    seen.add(key)
                    _, comment = split_value_comment(m.group("rest"))  # el valor viejo se descarta
                    out.append(f"{m.group('prefix')}{key}={updates[key]}{comment}{eol}")
                    continue
        out.append(line)

    append_eol = "\n"
    if out:
        _, last_eol = split_eol(out[-1])
        if last_eol:
            append_eol = last_eol  # hereda CRLF/CR del archivo (RF-3)
    for key in updates:
        if key in seen:
            continue
        if out and out[-1] and not out[-1].endswith(("\n", "\r")):
            out[-1] += append_eol
        out.append(f"{key}={updates[key]}{append_eol}")
    return "".join(out)


# ----------------------------------------------------------------------- RF-5
def extract_field_value(item: dict, field: str):
    """Valor de un campo del item: login / custom / notes (+fallback env) / card / identity."""
    item_type = item.get("type")
    if item_type == 1:  # login
        login = item.get("login", {})
        if field == "username":
            return login.get("username")
        if field == "password":
            return login.get("password")
        for cf in item.get("fields", []):
            if cf.get("name") == field:
                return cf.get("value")
        if field == "url":
            uris = login.get("uris", []) or []
            if uris:
                return uris[0].get("uri")
        return None
    if item_type == 2:  # secure note
        if field == "notes":
            return item.get("notes")
        for cf in item.get("fields", []):
            if cf.get("name") == field:
                return cf.get("value")
        # Fallback PROD: tratar el contenido del note como .env
        for nline in (item.get("notes") or "").splitlines():
            nline = nline.strip()
            if nline and not nline.startswith("#") and "=" in nline:
                nk, nv = nline.split("=", 1)
                if nk == field:
                    return nv
        return None
    if item_type == 4:  # card
        card = item.get("card", {})
        for k in ("cardholderName", "number", "expMonth", "expYear", "code", "brand"):
            if field.lower() == k.lower():
                return card.get(k)
        return None
    if item_type == 5:  # identity
        ident = item.get("identity", {})
        for k in (
            "firstName", "lastName", "email", "phone", "address1", "city",
            "state", "postalCode", "country", "ssn", "username",
        ):
            if field.lower() == k.lower():
                return ident.get(k)
        return None
    for cf in item.get("fields", []):
        if cf.get("name") == field:
            return cf.get("value")
    return None


def build_updates(target: dict, item_map: dict, warn) -> dict:
    updates = {}
    for m in target.get("mappings", []):
        item_name, field, env_key = m.get("item"), m.get("field"), m.get("env")
        item = item_map.get(item_name)
        if not item:
            warn(f"  WARNING: Item not found in vault: {item_name}")
            continue
        value = extract_field_value(item, field)
        if value is None:
            warn(f"  WARNING: Field '{field}' not found in item '{item_name}'")
            continue
        updates[env_key] = value.rstrip("\n")
        warn(f"  Updated: {env_key}")
    return updates


# ----------------------------------------------------------------------- RF-6
def atomic_write(path: str, text: str, mode="0600", owner=None, warn=None):
    """Temporal en el mismo directorio + os.replace. El original solo se pierde
    si el reemplazo tuvo exito (RF-6).

    Politica de codificacion del repo (check-windows-footguns): lecturas con
    utf-8-sig, ESCRITURAS con utf-8. Un BOM que traiga el archivo original se
    elimina en la primera escritura (los parsers dotenv/JSON lo rechazan)."""
    import pwd  # import local: el modulo es POSIX-only (guard footguns)

    warn = warn or (lambda msg: None)
    dirname = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".env-sync-", dir=dirname)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, int(str(mode), 8))
        if owner:
            try:
                pw = pwd.getpwnam(owner)
                os.chown(tmp, pw.pw_uid, pw.pw_gid)
            except KeyError:
                warn("  WARNING: owner '%s' does not exist, ownership unchanged" % owner)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_text(path: str) -> str:
    """Lectura BOM-tolerante (utf-8-sig). Un archivo sin cambios no se reescribe,
    por lo que un BOM preexistente solo desaparece en la primera escritura real
    (los parsers lo rechazan de todos modos). Devuelve "" si no existe."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8-sig")


def sync_target(target: dict, item_map: dict, warn=None, out=None, restart_fn=None) -> str:
    """Un target -> 'ok' | 'skipped' | 'failed'. Nunca levanta excepcion por target."""
    warn = warn or (lambda msg: print(msg, file=sys.stderr))
    out = out or print
    restart_fn = restart_fn or os.system

    env_file = target.get("file")
    if not env_file:
        warn("  SKIPPED: target has no file")
        return "skipped"

    # H2: si el .env es un SYMLINK se escribe a traves del enlace (os.replace
    # sobre el propio link lo reemplazaria por un archivo regular y romperia
    # el mount de docker compose / bind mount).
    resolved = os.path.realpath(env_file) if os.path.islink(env_file) else env_file
    parent = os.path.dirname(resolved)
    if parent and not os.path.isdir(parent):
        warn(f"  SKIPPED: parent dir does not exist: {parent}")
        return "skipped"

    try:
        original = read_text(resolved)
        updates = build_updates(target, item_map, warn)
        merged = merge_env_text(original, updates)
    except Exception as e:  # H1: ninguna lectura/parsing puede tumbar la cola
        warn(f"  FAILED: could not process {env_file}: {type(e).__name__}: {e}")
        return "failed"

    if not updates and not os.path.exists(resolved):
        # H4: sin nada que escribir no se crea un .env vacio ni se reinicia.
        warn("  WARNING: no vault updates resolved and file does not exist; nothing written")
        out(f"DONE:{env_file}")
        return "ok"

    changed = merged != original or not os.path.exists(resolved)
    if changed:
        try:
            atomic_write(
                resolved, merged, target.get("mode", "0600"),
                target.get("owner"), warn,
            )
        except OSError as e:
            warn(f"  FAILED: could not write {env_file}: {e}")
            return "failed"
        restart = target.get("restart")
        if restart:
            warn(f"  Changed, restarting: {restart}")
            rc = restart_fn(restart)
            if isinstance(rc, int) and rc != 0:
                # H5: un restart caido no cuenta como failed, pero queda visible.
                warn(f"  WARNING: restart exited with {rc}: {restart}")
    else:
        warn("  No changes, skipping restart")

    out(f"DONE:{env_file}")
    return "ok"


# ----------------------------------------------------------------------- RF-8
def fetch_items(session: str, runner=None, warn=None) -> dict:
    runner = runner or subprocess.run
    warn = warn or (lambda msg: print(msg, file=sys.stderr))
    try:
        result = runner(
            ["bw", "list", "items", "--session", session],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:  # timeout, binario ausente, etc.
        raise VaultFetchError(f"bw list items failed: {e}") from e
    if result.returncode != 0:
        raise VaultFetchError(f"bw list items failed: {result.stderr}")
    try:
        raw = json.loads(result.stdout) if result.stdout.strip() else []
    except Exception as e:
        raise VaultFetchError(f"bw list items returned invalid JSON: {e}") from e
    item_map = {}
    for item in raw:
        name = item.get("name")
        if name in item_map:
            # H9: el vault permite nombres repetidos; el ultimo gana, pero se avisa.
            warn(f"  WARNING: duplicate vault item name '{name}' — last one wins")
        item_map[name] = item
    return item_map


def main(argv, mapfile=DEFAULT_MAPFILE, fetch=None, err=None, out=None, restart_fn=None) -> int:
    err = sys.stderr if err is None else err
    out = sys.stdout if out is None else out
    fetch = fetch or fetch_items

    if len(argv) < 1:
        print("ERROR: Usage: sync-env.py <SESSION>", file=err)
        return 1

    try:
        with open(mapfile, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: cannot read map {mapfile}: {e}", file=err)
        return 1

    try:
        item_map = fetch(argv[0])
    except VaultFetchError as e:
        print(f"ERROR: {e}", file=err)
        return 1

    ok = skipped = failed = 0
    for target in data.get("targets", []):
        if not isinstance(target, dict):
            # N1 (review ronda 2): un target mal editado en el mapa no debe
            # matar el run entero (sin SUMMARY) bajo `set -euo pipefail`.
            # Solo se imprime el TIPO, nunca el contenido (puede contener rutas
            # o nombres sensibles).
            print(
                f"Processing: <invalid target: {type(target).__name__}>", file=err
            )
            print(
                "  FAILED: target in map is not an object; entry skipped",
                file=err,
            )
            failed += 1
            continue
        print(f"Processing: {target.get('file')}", file=err)
        outcome = sync_target(
            target, item_map,
            warn=lambda msg: print(msg, file=err),
            out=lambda msg: print(msg, file=out),
            restart_fn=restart_fn,
        )
        if outcome == "ok":
            ok += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            failed += 1

    print(f"SUMMARY: ok={ok} skipped={skipped} failed={failed}", file=err)
    return 1 if (failed and not ok) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

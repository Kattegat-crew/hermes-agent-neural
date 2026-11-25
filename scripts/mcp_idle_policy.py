#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica una política uniforme de reciclado por inactividad a los MCP stdio de un ``config.yaml``.

El núcleo de Hermes apaga un servidor MCP tras ``idle_timeout_seconds`` sin uso, pero **solo para
transports stdio** (``tools/mcp_tool_health.py``: ``_stdio_recycle_deadlines`` devuelve ``[]`` para
HTTP) y con **precedencia top-level**: ``_get_lifecycle_seconds`` (``tools/mcp_tool_common.py``)
lee ``idle_timeout_seconds`` en la raíz del servidor y usa ``lifecycle.*`` solo como fallback.

Este comando escribe esa clave en el sitio donde el núcleo la lee, conservando comentarios, orden
y todas las claves ajenas.

Uso:
    python3 scripts/mcp_idle_policy.py --config /ruta/config.yaml --idle-seconds 200 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_IDLE_SECONDS = 200

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_PENDING = 3
EXIT_WRITE = 4


class PolicyError(ValueError):
    """El documento no tiene la forma esperada (falta ``mcp_servers`` o no es un mapping)."""


@dataclass(frozen=True)
class Change:
    """Un servidor cuyo ``idle_timeout_seconds`` cambia (o se añade)."""

    server: str
    before: float | None
    after: float


def _ensure_repo_on_path() -> None:
    """Deja la raíz del repo en ``sys.path`` para importar ``utils`` desde ``scripts/``."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def load_document(path: Path) -> Any:
    """Carga el config con el loader round-trip del proyecto (comentarios, comillas, Unicode)."""
    _ensure_repo_on_path()
    from utils import _roundtrip_load

    _yaml_rt, document = _roundtrip_load(path)
    return document


def save_document(path: Path, document: Any) -> None:
    """Persiste el documento completo con la primitiva oficial (merge que preserva comentarios)."""
    _ensure_repo_on_path()
    from utils import atomic_roundtrip_yaml_save

    atomic_roundtrip_yaml_save(path, document)


def _mcp_servers(document: Any) -> dict[str, Any]:
    servers = document.get("mcp_servers") if isinstance(document, dict) else None
    if not isinstance(servers, dict) or not servers:
        raise PolicyError("el config no contiene un bloque 'mcp_servers' utilizable")
    return servers


def _is_stdio(config: dict[str, Any]) -> bool:
    """stdio = ``command`` sin ``url``; si conviven el núcleo usa HTTP y no recicla por idle."""
    return "command" in config and "url" not in config


def collect_targets(document: Any, only: Sequence[str] | None = None) -> list[str]:
    """Servidores stdio gestionables (``command``); los HTTP no admiten reciclado por idle."""
    servers = _mcp_servers(document)
    wanted = {name.strip() for name in only} if only else None
    targets: list[str] = []
    for name, config in servers.items():
        if not isinstance(config, dict) or not _is_stdio(config):
            continue
        if wanted is not None and name not in wanted:
            continue
        targets.append(str(name))
    if wanted is not None:
        missing = sorted(wanted - set(targets))
        if missing:
            raise PolicyError(
                "servidores no encontrados o sin 'command' (stdio): " + ", ".join(missing))
    return targets


def http_servers(document: Any) -> list[str]:
    """Servidores HTTP declarados con ``url``: el núcleo ignora ahí el idle (no aplica)."""
    servers = _mcp_servers(document)
    return [str(name) for name, config in servers.items()
            if isinstance(config, dict) and "url" in config]


def current_idle(server_config: dict[str, Any]) -> float | None:
    """Valor efectivo con la MISMA precedencia que el núcleo: top-level primero, luego lifecycle.

    Devuelve ``None`` cuando el valor está ausente o es inválido (negativo / no numérico), que es
    exactamente lo que hace ``_get_lifecycle_seconds``: ignorarlo y seguir.
    """
    raw = server_config.get("idle_timeout_seconds")
    if raw is None:
        lifecycle = server_config.get("lifecycle")
        if isinstance(lifecycle, dict):
            raw = lifecycle.get("idle_timeout_seconds")
    return _as_seconds(raw)


def _as_seconds(raw: Any) -> float | None:
    """Coerción tolerante: ``None`` para ausente, no numérico o negativo (semántica del núcleo)."""
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def apply_policy(
    document: Any,
    idle_seconds: int,
    only: Sequence[str] | None = None,
) -> list[Change]:
    """Escribe la política donde el núcleo la lee y devuelve los cambios reales.

    Idempotente: si el valor efectivo ya es el pedido, el nodo no se toca. Cuando el servidor ya
    declara ``lifecycle.idle_timeout_seconds`` se sincroniza también esa copia para no dejar un
    valor sombreado e incoherente.
    """
    if idle_seconds < 0:
        raise PolicyError("--idle-seconds debe ser >= 0")
    servers = _mcp_servers(document)
    by_name = {str(name): config for name, config in servers.items() if isinstance(config, dict)}
    target = float(idle_seconds)
    changes: list[Change] = []
    for name in collect_targets(document, only):
        config = by_name[name]
        before = current_idle(config)
        touched = False
        if "idle_timeout_seconds" not in config or before != target:
            config["idle_timeout_seconds"] = idle_seconds
            touched = True
        lifecycle = config.get("lifecycle")
        if isinstance(lifecycle, dict):
            current = lifecycle.get("idle_timeout_seconds")
            if current is not None and _as_seconds(current) != target:
                lifecycle["idle_timeout_seconds"] = idle_seconds
                touched = True
        if touched:
            changes.append(Change(server=name, before=before, after=target))
    return changes


def _fmt(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds:g}s"


def _report(
    changes: list[Change],
    targets: Sequence[str],
    skipped_http: Iterable[str],
    config_path: Path,
    idle: int,
    as_json: bool,
    applied: bool,
) -> None:
    payload = {
        "config": str(config_path),
        "idle_seconds": idle,
        "targets": len(targets),
        "changed": [{"server": c.server, "before": c.before, "after": c.after} for c in changes],
        "unchanged": sorted(set(targets) - {c.server for c in changes}),
        "skipped_http": sorted(skipped_http),
        "applied": applied,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"config: {config_path}  ·  idle: {idle}s  ·  stdio: {len(targets)}")
    if not changes:
        print("sin cambios: la política ya estaba aplicada")
        return
    for change in changes:
        print(f"  {change.server:28} {_fmt(change.before):>7} -> {_fmt(change.after)}")
    print(f"{'aplicado' if applied else 'simulado'}: {len(changes)} servidor(es)")


def _idle_arg(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"se esperaba un entero, llegó {raw!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("debe ser >= 0 (0 desactiva el reciclado)")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aplica idle_timeout_seconds a los MCP stdio de un config.yaml")
    parser.add_argument("--config", required=True, help="ruta al config.yaml del perfil")
    parser.add_argument("--idle-seconds", type=_idle_arg, default=DEFAULT_IDLE_SECONDS,
                        help=f"segundos de inactividad antes de apagar (default {DEFAULT_IDLE_SECONDS}; 0 desactiva)")
    parser.add_argument("--servers", default=None,
                        help="lista separada por comas; por defecto todos los stdio del config")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="reportar sin escribir")
    mode.add_argument("--check", action="store_true", help="exit 3 si falta la política; no escribe")
    parser.add_argument("--json", action="store_true", help="salida machine-readable")
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser()
    only = [s for s in (args.servers or "").split(",") if s.strip()] or None
    if not config_path.is_file():
        print(f"error: no existe el config {config_path}", file=sys.stderr)
        return EXIT_INVALID

    try:
        document = load_document(config_path)
        targets = collect_targets(document, only)
        skipped = http_servers(document)
        changes = apply_policy(document, args.idle_seconds, only)
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:  # YAML ilegible u otro fallo de lectura: no se toca el archivo
        print(f"error: no se pudo leer {config_path}: {exc}", file=sys.stderr)
        return EXIT_INVALID

    if args.check:
        _report(changes, targets, skipped, config_path, args.idle_seconds, args.json, applied=False)
        return EXIT_PENDING if changes else EXIT_OK
    if args.dry_run:
        _report(changes, targets, skipped, config_path, args.idle_seconds, args.json, applied=False)
        return EXIT_OK
    if not changes:
        _report(changes, targets, skipped, config_path, args.idle_seconds, args.json, applied=False)
        return EXIT_OK

    try:
        save_document(config_path, document)
    except Exception as exc:
        print(f"error: no se pudo escribir {config_path}: {exc}", file=sys.stderr)
        return EXIT_WRITE
    _report(changes, targets, skipped, config_path, args.idle_seconds, args.json, applied=True)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

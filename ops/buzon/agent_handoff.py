#!/usr/bin/env python3
"""agent_handoff.py — Handoff inter-agente y gestión de buzones locales (DEV).

Buzón de archivos sobre /opt/hermes-agent-data/inbox/ (alias /opt/data/inbox/).
Permite transferir encargos, guiones, activos y notificaciones entre perfiles de la
flota (Ragnar, Freyja, Bragi, Sindri, Vili, Heimdall, Ullr, Brokkr, Hermodr) sin
acoplamiento directo de procesos.

Subcomandos:
  send   --from <emisor> --to <receptor> --asunto "..." --tarea "..."
         [--archivos /ruta1 /ruta2] [--prioridad alta|normal|baja]
         [--no-webhook] [--webhook-base URL] [--webhook-route RUTA]
  list   --agent <agente> [--status all|pending|done]
  reply  --agent <agente> --ticket <ticket_id> --respuesta "..." [--evidencia "..."]

El depósito del archivo es la fuente de verdad y siempre ocurre primero. Después,
si hay secreto configurado, se emite un aviso push al webhook del perfil destino
para que el receptor se entere en el momento en vez de esperar al polling. Si el
aviso falla, el depósito sigue siendo válido y lo recoge el barrido lento.

Escrituras atómicas (tmp + os.replace). Permisos 644 / hermes:hermes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

INBOX_ROOT = Path("/opt/hermes-agent-data/inbox")
VALID_AGENTS = {
    "ragnar", "freyja", "bragi", "sindri", "vili",
    "heimdall", "ullr", "brokkr", "hermodr", "roshi", "vigia", "bob"
}

# --- Aviso push (opcional) -------------------------------------------------
WEBHOOK_BASE_DEFAULT = "http://127.0.0.1:8644"
WEBHOOK_ROUTE_DEFAULT = "buzon"
SECRET_CANDIDATES = (
    Path("/opt/hermes-agent-data/secrets/webhook-buzon.json"),
    Path("/opt/data/secrets/webhook-buzon.json"),
)

try:  # el notificador se instala junto a este script
    from notify import notify as _notify
except Exception:  # pragma: no cover - si falta el módulo, el buzón sigue funcionando
    _notify = None


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _leer_secreto(explicito: str | None = None) -> str:
    """Secreto de la ruta de webhook: argumento, o archivo de secretos."""
    if explicito:
        return explicito.strip()
    for ruta in SECRET_CANDIDATES:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            continue
        for clave in ("secret", "hmac_secret", "token"):
            valor = datos.get(clave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
    return ""


def _avisar(
    receptor: str,
    payload: dict,
    *,
    base: str,
    ruta: str,
    secreto: str,
    desactivado: bool,
) -> None:
    """Emite el aviso push e imprime el resultado. Nunca altera el flujo."""
    if desactivado:
        print("  Aviso: desactivado por --no-webhook (el barrido lo recogerá).")
        return
    if _notify is None:
        print("  Sin aviso: notificador no instalado (el barrido lo recogerá).")
        return
    if not secreto:
        print("  Sin aviso: no hay secreto de webhook configurado (el barrido lo recogerá).")
        return

    evento = {
        "event_type": "buzon.nuevo",
        "ticket_id": payload.get("id"),
        "de": payload.get("de"),
        "para": payload.get("para"),
        "asunto": payload.get("asunto"),
        "prioridad": payload.get("prioridad"),
    }
    res = _notify(
        receptor,
        evento,
        base_url=base,
        secret=secreto,
        ruta=ruta,
    )
    if res.sent:
        print(f"  Aviso enviado (HTTP {res.status}).")
    else:
        detalle = res.reason or "error"
        if res.status:
            detalle = f"{detalle} {res.status}"
        print(f"  Sin aviso: {detalle} (el barrido lo recogerá).")


def send_handoff(args: argparse.Namespace) -> int:
    sender = args.sender.lower().strip()
    recipient = args.to.lower().strip()

    if sender not in VALID_AGENTS:
        print(f"Error: Emisor '{sender}' no es un agente reconocido. Válidos: {sorted(VALID_AGENTS)}", file=sys.stderr)
        return 1
    if recipient not in VALID_AGENTS:
        print(f"Error: Receptor '{recipient}' no es un agente reconocido. Válidos: {sorted(VALID_AGENTS)}", file=sys.stderr)
        return 1

    inbox_root = Path(args.inbox_root) if getattr(args, "inbox_root", None) else INBOX_ROOT
    target_dir = _ensure_dir(inbox_root / recipient / f"from-{sender}")
    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y%m%d%H%M%S")
    ticket_id = args.id or f"tkt-{now.strftime('%Y%m%d')}-{sender}-{recipient}-{ts_str[-4:]}"

    payload = {
        "id": ticket_id,
        "de": sender,
        "para": recipient,
        "asunto": args.asunto.strip(),
        "tarea": args.tarea.strip(),
        "prioridad": args.prioridad,
        "archivos": [str(Path(f).resolve()) for f in (args.archivos or [])],
        "creado_en": now.isoformat(),
    }

    final_path = target_dir / f"{ticket_id}.json"

    # Escritura atómica
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="handoff_", suffix=".json", dir=str(target_dir))
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    os.chmod(tmp_path, 0o644)
    shutil.move(tmp_path, final_path)

    try:
        shutil.chown(final_path, user="hermes", group="hermes")
    except Exception:
        pass

    print(f"✓ Handoff enviado exitosamente:")
    print(f"  Ticket: {ticket_id}")
    print(f"  Ruta:   {final_path}")
    print(f"  Para:   {recipient} (desde {sender})")
    print(f"  Asunto: {args.asunto}")

    # Aviso push DESPUÉS del depósito: el archivo ya es la fuente de verdad.
    _avisar(
        recipient,
        payload,
        base=getattr(args, "webhook_base", None) or WEBHOOK_BASE_DEFAULT,
        ruta=getattr(args, "webhook_route", None) or WEBHOOK_ROUTE_DEFAULT,
        secreto=_leer_secreto(getattr(args, "webhook_secret", None)),
        desactivado=bool(getattr(args, "no_webhook", False)),
    )
    return 0


def list_handoffs(args: argparse.Namespace) -> int:
    agent = args.agent.lower().strip()
    if agent not in VALID_AGENTS:
        print(f"Error: Agente '{agent}' no reconocido.", file=sys.stderr)
        return 1

    inbox_root = Path(args.inbox_root) if getattr(args, "inbox_root", None) else INBOX_ROOT
    agent_dir = inbox_root / agent
    if not agent_dir.exists():
        print(f"Buzón de {agent} vacío o no inicializado ({agent_dir}).")
        return 0

    print(f"=== Buzón de {agent.upper()} ({agent_dir}) ===")

    incoming_files = sorted(agent_dir.glob("from-*/*.json"))
    pending_files = sorted(agent_dir.glob("pending/*.json"))
    done_files = sorted(agent_dir.glob("done/*.json"))

    if args.status in ("all", "pending"):
        print(f"\n[MENSAJES ENTRANTES / PENDIENTES: {len(incoming_files) + len(pending_files)}]")
        for f in incoming_files + pending_files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                print(f"  • {f.name} (de: {data.get('de')}, asunto: {data.get('asunto')}, fecha: {data.get('creado_en')})")
            except Exception:
                print(f"  • {f.name} (error parseando JSON)")

    if args.status in ("all", "done"):
        print(f"\n[COMPLETADOS / ARCHIVADOS: {len(done_files)}]")
        for f in done_files[:10]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                print(f"  ✓ {f.name} (cerrado: {data.get('cerrado_en', '-')})")
            except Exception:
                print(f"  ✓ {f.name}")

    return 0


def reply_handoff(args: argparse.Namespace) -> int:
    agent = args.agent.lower().strip()
    ticket_id = args.ticket.strip()

    inbox_root = Path(args.inbox_root) if getattr(args, "inbox_root", None) else INBOX_ROOT
    agent_dir = inbox_root / agent
    found = list(agent_dir.glob(f"from-*/*{ticket_id}*.json")) + list(agent_dir.glob(f"pending/*{ticket_id}*.json"))

    if not found:
        print(f"Error: No se encontró ticket '{ticket_id}' en el buzón entrante de {agent}.", file=sys.stderr)
        return 1

    src_file = found[0]
    try:
        data = json.loads(src_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error leyendo ticket {src_file}: {e}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    data["cerrado_en"] = now.isoformat()
    data["cerrado_por"] = agent
    data["respuesta"] = args.respuesta.strip()
    if args.evidencia:
        data["evidencia"] = args.evidencia.strip()

    done_dir = _ensure_dir(agent_dir / "done")
    dest_file = done_dir / src_file.name

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="done_", suffix=".json", dir=str(done_dir))
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    os.chmod(tmp_path, 0o644)
    shutil.move(tmp_path, dest_file)
    src_file.unlink(missing_ok=True)

    try:
        shutil.chown(dest_file, user="hermes", group="hermes")
    except Exception:
        pass

    # Copia de cortesía al buzón del emisor original
    sender = data.get("de")
    if sender and sender in VALID_AGENTS and sender != agent:
        sender_done = _ensure_dir(inbox_root / sender / f"from-{agent}")
        sender_file = sender_done / f"reply-{src_file.name}"
        shutil.copy2(dest_file, sender_file)
        try:
            shutil.chown(sender_file, user="hermes", group="hermes")
        except Exception:
            pass
        print(f"  ✓ Copia de respuesta depositada en /inbox/{sender}/from-{agent}/")

    print(f"✓ Ticket {ticket_id} cerrado satisfactoriamente en {dest_file}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestor de handoffs inter-agente de la flota Hermes")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _webhook_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--no-webhook", action="store_true",
                       help="No emitir el aviso push (el barrido lento recogerá el mensaje)")
        p.add_argument("--webhook-base", help=f"Base del listener webhook (default {WEBHOOK_BASE_DEFAULT})")
        p.add_argument("--webhook-route", help=f"Ruta del webhook (default {WEBHOOK_ROUTE_DEFAULT})")
        p.add_argument("--webhook-secret", help="Secreto HMAC (default: archivo de secretos)")
        p.add_argument("--inbox-root", help="Raíz del buzón (solo pruebas / overrides)")

    p_send = sub.add_parser("send", help="Enviar un encargo / handoff a otro agente")
    p_send.add_argument("--from", dest="sender", required=True, help="Agente emisor (ej: bragi, sindri)")
    p_send.add_argument("--to", required=True, help="Agente receptor (ej: freyja, vili)")
    p_send.add_argument("--asunto", required=True, help="Título del encargo")
    p_send.add_argument("--tarea", required=True, help="Descripción detallada de la instrucción")
    p_send.add_argument("--archivos", nargs="*", help="Rutas de archivos de insumo")
    p_send.add_argument("--prioridad", choices=["alta", "normal", "baja"], default="normal")
    p_send.add_argument("--id", help="ID personalizado del ticket")
    _webhook_flags(p_send)
    p_send.set_defaults(func=send_handoff)

    p_list = sub.add_parser("list", help="Listar encargos de un agente")
    p_list.add_argument("--agent", required=True, help="Agente a consultar")
    p_list.add_argument("--status", choices=["all", "pending", "done"], default="all")
    p_list.add_argument("--inbox-root", help="Raíz del buzón (solo pruebas / overrides)")
    p_list.set_defaults(func=list_handoffs)

    p_reply = sub.add_parser("reply", help="Responder y cerrar un encargo")
    p_reply.add_argument("--agent", required=True, help="Agente que responde")
    p_reply.add_argument("--ticket", required=True, help="ID del ticket a cerrar")
    p_reply.add_argument("--respuesta", required=True, help="Detalle de lo realizado")
    p_reply.add_argument("--evidencia", help="Prueba observable o enlace")
    p_reply.add_argument("--inbox-root", help="Raíz del buzón (solo pruebas / overrides)")
    p_reply.set_defaults(func=reply_handoff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""agent_handoff.py — Herramienta de handoff inter-agente y gestión de buzones locales (DEV).

Buzón de archivos sobre /opt/hermes-agent-data/inbox/ (alias /opt/data/inbox/).
Permite transferir encargos, guiones, activos y notificaciones entre perfiles de la flota
(Ragnar, Freyja, Bragi, Sindri, Vili, Heimdall, Ullr, Brokkr, Hermodr) sin acoplamiento
directo de procesos.

Subcomandos:
  send   --from <emisor> --to <receptor> --asunto "..." --tarea "..."
         [--archivos /ruta1 /ruta2] [--prioridad alta|normal|baja]
  list   --agent <agente> [--status all|pending|done]
  reply  --agent <agente> --ticket <ticket_id> --respuesta "..." [--evidencia "..."]

Escrituras atómicas (tmp + os.replace). Permisos 644 / hermes:hermes.
"""
from __future__ import annotations

import argparse
import glob
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


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def send_handoff(args: argparse.Namespace) -> int:
    sender = args.sender.lower().strip()
    recipient = args.to.lower().strip()

    if sender not in VALID_AGENTS:
        print(f"Error: Emisor '{sender}' no es un agente reconocido. Válidos: {sorted(VALID_AGENTS)}", file=sys.stderr)
        return 1
    if recipient not in VALID_AGENTS:
        print(f"Error: Receptor '{recipient}' no es un agente reconocido. Válidos: {sorted(VALID_AGENTS)}", file=sys.stderr)
        return 1

    target_dir = _ensure_dir(INBOX_ROOT / recipient / f"from-{sender}")
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
    return 0


def list_handoffs(args: argparse.Namespace) -> int:
    agent = args.agent.lower().strip()
    if agent not in VALID_AGENTS:
        print(f"Error: Agente '{agent}' no reconocido.", file=sys.stderr)
        return 1

    agent_dir = INBOX_ROOT / agent
    if not agent_dir.exists():
        print(f"Buzón de {agent} vacío o no inicializado ({agent_dir}).")
        return 0

    print(f"=== Buzón de {agent.upper()} ({agent_dir}) ===")
    
    # Pendientes / from-*
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

    agent_dir = INBOX_ROOT / agent
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

    # Si se pide notificar al emisor original en su buzón de done/ o from-<agent>
    sender = data.get("de")
    if sender and sender in VALID_AGENTS and sender != agent:
        sender_done = _ensure_dir(INBOX_ROOT / sender / f"from-{agent}")
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

    p_send = sub.add_parser("send", help="Enviar un encargo / handoff a otro agente")
    p_send.add_argument("--from", dest="sender", required=True, help="Agente emisor (ej: bragi, sindri)")
    p_send.add_argument("--to", required=True, help="Agente receptor (ej: freyja, vili)")
    p_send.add_argument("--asunto", required=True, help="Título del encargo")
    p_send.add_argument("--tarea", required=True, help="Descripción detallada de la instrucción")
    p_send.add_argument("--archivos", nargs="*", help="Rutas de archivos de insumo")
    p_send.add_argument("--prioridad", choices=["alta", "normal", "baja"], default="normal")
    p_send.add_argument("--id", help="ID personalizado del ticket")
    p_send.set_defaults(func=send_handoff)

    p_list = sub.add_parser("list", help="Listar encargos de un agente")
    p_list.add_argument("--agent", required=True, help="Agente a consultar")
    p_list.add_argument("--status", choices=["all", "pending", "done"], default="all")
    p_list.set_defaults(func=list_handoffs)

    p_reply = sub.add_parser("reply", help="Responder y cerrar un encargo")
    p_reply.add_argument("--agent", required=True, help="Agente que responde")
    p_reply.add_argument("--ticket", required=True, help="ID del ticket a cerrar")
    p_reply.add_argument("--respuesta", required=True, help="Detalle de lo realizado")
    p_reply.add_argument("--evidencia", help="Prueba observable o enlace")
    p_reply.set_defaults(func=reply_handoff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

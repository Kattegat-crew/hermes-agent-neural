#!/usr/bin/env python3
"""Reinicia el proceso que sirve al Desktop (por defecto el dashboard de :9112)
conservando su argv y TODO su entorno.

Por qué existe: el backend Python de un plugin se importa AL ARRANCAR el proceso
(`_mount_plugin_api_routes()` en hermes_cli/web_server.py). Un plugin nuevo no
queda montado hasta que ese proceso vuelve a nacer — y no siempre es el proceso
que parece: identificar primero quién tiene las CONEXIONES del cliente
(`ss -tnp | grep <IP del cliente>`) — en un caso real era un `hermes dashboard`
de :9112, no el `serve --isolated` del modo SSH (ese tenía cero conexiones).

OJO — es infra del Desktop y corta la conexión del cliente unos segundos:
  * pedir OK explícito al usuario antes de correrlo sin `--dry`;
  * si la sesión del agente corre DENTRO de ese proceso, la respuesta en curso se
    corta (la conversación persiste en state.db y el cliente reconecta);
  * se relanza con el entorno íntegro de /proc para que el token de sesión no
    cambie: si cambia, el cliente no puede reconectar.

Estado de validación: detección de PID + reconstrucción de argv/entorno
verificadas con `--dry` en la flota (resuelve el proceso correcto). El swap
completo (SIGTERM + relanzamiento) NO se ha ejercitado todavía aquí: la primera
corrida real necesita el OK del usuario.

Uso:
  python3 restart-desktop-backend.py --dry                    # solo dice qué haría
  python3 restart-desktop-backend.py --port 9112              # reinicia y verifica
  python3 restart-desktop-backend.py --port 9112 --delay 20   # deja salir la respuesta
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time

HOME = os.environ.get("HERMES_HOME", "/root/hermes-agent-legacy-docker/data")
LOG = HOME + "/logs/desktop-backend-restart.log"
GUI_LOG = HOME + "/logs/gui.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def find_pid(port: int):
    try:
        out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if f":{port} " in line and "pid=" in line:
            pid = line.split("pid=")[1].split(",")[0]
            if pid.isdigit():
                return int(pid)
    return None


def snapshot(pid: int):
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        argv = [p for p in fh.read().decode().split("\0") if p]
    with open(f"/proc/{pid}/environ", "rb") as fh:
        env = dict(kv.split("=", 1) for kv in fh.read().decode().split("\0") if "=" in kv)
    return argv, env


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(1.5)
        return s.connect_ex((host, port)) == 0


def main() -> int:
    a = sys.argv[1:]

    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default

    port = int(opt("--port", 9112))
    dry = "--dry" in a
    delay = int(opt("--delay", 0) or 0)
    if delay:
        log(f"esperando {delay}s antes de reiniciar el backend de :{port}")
        time.sleep(delay)

    pid = find_pid(port)
    if not pid:
        log(f"ERROR: nadie escucha en :{port} — no reinicio nada")
        return 1
    argv, env = snapshot(pid)
    log(f"backend actual: pid={pid} cmd={' '.join(argv)[:140]}")

    if dry:
        log(f"DRY: SIGTERM a {pid} y relanzar con {len(env)} vars de entorno")
        return 0

    log(f"SIGTERM a {pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(30):
        time.sleep(1)
        if not os.path.exists(f"/proc/{pid}"):
            break
    if os.path.exists(f"/proc/{pid}"):
        log(f"no murió con SIGTERM → SIGKILL a {pid}")
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(2)

    log(f"relanzando: {' '.join(argv)}")
    with open(LOG, "a", encoding="utf-8") as out:
        proc = subprocess.Popen(
            argv, env=env, stdout=out, stderr=out, stdin=subprocess.DEVNULL,
            cwd=env.get("HERMES_HOME", "."), start_new_session=True,
        )
    log(f"nuevo pid={proc.pid}")

    for _ in range(60):
        if port_open(port):
            break
        time.sleep(1)
    log(f":{port} escuchando={port_open(port)} pid={find_pid(port)}")

    time.sleep(2)
    try:
        with open(GUI_LOG, "r", encoding="utf-8", errors="replace") as fh:
            tail = fh.readlines()[-400:]
        mounts = [l.split("hermes_cli.web_server: ")[-1].strip()
                  for l in tail if "Mounted plugin API routes" in l]
        log("montajes vistos: " + (" | ".join(mounts) or "ninguno"))
    except OSError as exc:
        log(f"no pude leer {GUI_LOG}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

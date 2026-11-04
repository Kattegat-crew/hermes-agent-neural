# CDP Local Browser Bridge

Conectar Hermes (Docker container) al navegador local del usuario vía Chrome DevTools Protocol.

## Problema

`ssh -R 9222:localhost:9222` bindea a `127.0.0.1` del VPS host. Hermes dentro del contenedor Docker **no puede alcanzar el loopback del host**.

## 1. Iniciar navegador con CDP

Brave: `"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222`
Verificar en `http://localhost:9222/json/version`

## 2. Opciones de puente CDP

### A: GatewayPorts en VPS (recomendada)
```bash
echo "GatewayPorts clientspecified" >> /etc/ssh/sshd_config && systemctl restart sshd
```
Desde PC: `ssh -R 0.0.0.0:9222:localhost:9222 root@147.93.3.250`

### B: localhost.run
`ssh -R 80:localhost:9222 nokey@localhost.run` → URL pública

### C: ngrok
`ngrok http 9222` → URL pública

## 3. Configurar Hermes
`/opt/hermes/.venv/bin/hermes config set browser.cdp_url "ws://IP:9222"`

## Pitfalls
- Docker container no ve 127.0.0.1 del host
- SSH tunnel se cae al cerrar terminal → `ssh -f -N -R`
- GatewayPorts requiere root en VPS
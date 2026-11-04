# Dashboard sirviendo código viejo (síndrome recurrente)

Caso repetido 4 veces en oct-2026: el checkout de Hermes se actualiza, pero el proceso
`hermes dashboard` sigue vivo con el código anterior. **No es red, ni tailnet, ni sesión**: es
código stale en memoria. Desde el Desktop se ve idéntico a "no reach the gateway".

## Síntomas (cualquiera de estos)

- Desktop loguea y abre, pero **no aparecen modelos** y/o **plugins no conectan**.
- *"Hermes can't reach that address… sign-in options appear once it answers"* aunque el servidor
  responda perfecto por `curl` desde el host.
- Timeout de arranque aunque `login` devuelva 200 y `ws-ticket` 401 (vivo, pide sesión).
- Log con `client and Hermes backend are out of sync (different versions)` (ver pitfall: falsa pista).
- Muchas conexiones TCP del cliente al puerto del dashboard sin tráfico útil.

## Prueba única que lo confirma (la más barata)

Comparar **fecha de arranque del proceso** contra **fecha del HEAD del repo**:

```bash
REPO=/host/root/hermes-agent-legacy-docker      # el checkout real del host
cd "$REPO" && echo "HEAD: $(git rev-parse --short HEAD) $(git log -1 --format=%ci)"
# PID del dashboard (host o contenedor, según dónde corra):
for p in /host/proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null); \
  case "$c" in *"hermes dashboard"*) echo "$(basename $p) start=$(ps -o lstart= -p $(basename $p)) $c";; esac; done
```

Proceso arrancado **antes** del commit del HEAD → sirviendo código viejo. Confirmado.

## Arreglo

1. Matar el proceso del dashboard por **PID exacto** (nunca `pkill -f hermes` a ciegas: se lleva
   gateways y perfiles).
2. Relanzar **desacoplado** sobre el HEAD actual:
   ```bash
   cd "$REPO" && setsid nohup hermes dashboard --host 0.0.0.0 --port 9112 \
     >> /opt/hermes-agent-data/logs/dashboard-relaunch.log 2>&1 &
   ```
3. Verificar de punta a punta, no solo "arrancó":
   ```bash
   curl -s -o /dev/null -w 'login=%{http_code}\n' http://<ip-tailnet>:9112/login
   curl -s -X POST http://<ip-tailnet>:9112/api/model/options | head -c 300   # debe listar modelos
   ```
4. Recién entonces pedir al usuario que reconecte la app.

## Pitfalls (todos costaron tiempo real)

- **Lanzar el dashboard con la tool `terminal` y timeout corto lo mata** (es un servidor que nunca
  termina). El timeout deja un "no sirve" autoinfligido. Siempre `setsid nohup … &` + verificar con `curl`.
- **`out of sync (different versions)` en un probe WS propio es falsa pista**: aparece cuando el
  método RPC enviado no existe. Comprobar que el método real responda antes de culpar al version skew.
- **Prueba de MTU mal planteada**: `ping -s 1200` OK y `-s 1400` 100% pérdida **no** prueba pérdida
  de paquetes si `tailscale0` tiene MTU 1280 (1400 excede el MTU local y muere por DF por diseño).
  Un frame de ~37 KB "atorado" es un **cliente que no lee** (socket zombi), no MTU.
- **N conexiones abiertas del cliente ≠ cliente sano**: un bucle de reconexión deja sockets
  zombis (abiertos, sin tráfico).
- **`curl` desde el host a la IP del tailnet no prueba la ruta del cliente.**
- Un **guard cron** (`dashboard-stale-guard`, cada 15 min, silencioso salvo staleness) es la
  mitigación correcta, pero antes de prometer protección verificar `enabled=true` en `jobs.json`:
  puede quedar deshabilitado por "reemplazo" y nadie avisa del siguiente stale.

## Prevención estructural

- Relanzar el dashboard como parte del **mismo paso** que hace `git pull`/update, no en un proceso
  que sobrevive al deploy.
- Guard (avisa) + auditoría semanal (explica).

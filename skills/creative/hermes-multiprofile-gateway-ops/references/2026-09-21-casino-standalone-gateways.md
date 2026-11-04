# Runbook — gateways standalone de casino (PROD) + watchdog con aviso a Discord

Verificado en vivo el **2026-09-21** en PROD (`vmi3513784` / `169.58.189.222`), perfiles
`golden-game` (bridge 3001) y `lucky-club` (bridge 3002). Corrige la idea de que un perfil con
**celular propio** puede vivir en el gateway multiplexado.

## 1. Por qué standalone (y por qué `--force`)

- `gateway/run_adapters.py:983` — bajo gateway multiplexado **no se arrancan adaptadores WhatsApp
  de perfiles secundarios** ("shared process-level ingress under multiplex; a secondary would
  retry-loop"). El número propio del cliente nunca se conecta.
- Sin `--force`, la unidad s6 de un perfil servido por el multiplexer termina con **exit 78** y s6
  **deja de reintentar**: el celular queda sordo **sin avisar a nadie** (así estuvo `lucky-club`
  ~27 h, 19–20 sep 2026).
- `hermes_cli/container_boot.py:114` — `should_start = not multiplex_profiles and ...` deja **todo**
  slot de perfil en `down` y **re-renderiza el `run` sin `--force`** en cada boot del contenedor.
  Cualquier arreglo manual se pierde en el siguiente reinicio ⇒ el backstop tiene que vivir FUERA
  del contenedor.
- El slot debe quedar **propiedad de `hermes`**: `run`, `finish`, `log/`, `supervise/control`. Un
  slot root-owned ni siquiera se puede consultar como hermes (`Permission denied`) y nadie lo
  revive.
- `desired_state: running` en `profiles/<perfil>/gateway_state.json` (autostart) y
  `API_SERVER_PORT` distinto por perfil (golden 8643 / lucky 8644) para no chocar con el listener
  compartido 8642.

Registro del slot en runtime (sin reiniciar el contenedor):
`S6ServiceManager.register_profile_gateway(...)` (ver `hermes-s6-container-supervision`).

## 2. Cadena del backstop (cron del host, cada 5 min)

```
/etc/cron.d/hermes-casino-gateways   */5 * * * * root /usr/local/bin/hermes-casino-gateways.sh >> /var/log/hermes-casino-gateways.log 2>&1
└── /usr/local/bin/hermes-casino-gateways.sh          wrapper (set -uo pipefail, exit 0 SIEMPRE)
    ├── docker exec -e HOME=/opt/data hermes-agent python3 /opt/data/scripts/casino_gateways_watchdog.py
    │      → escribe su salida en /var/lib/hermes-casino-gateways/last-watchdog-output.txt
    │      → exit 0 = sano/reparado · exit 2 = sigue roto
    └── /usr/local/bin/hermes-casino-gateways-notify.py <rc> <archivo-de-salida>
```

- **Contrato del watchdog: silencio si todo está sano.** El aviso es una capa fina aparte, no se
  metió Discord dentro del watchdog, para no romper ese contrato.
- El log del host solo recibe líneas relevantes: el wrapper descarta la línea rutinaria
  `NOTIFY: sano, sin aviso` (antes cada tick ensuciaba el log).
- Secreto fuera del script: `/etc/hermes-casino-gateways.env` (**0600 root**) con
  `DISCORD_WEBHOOK_URL=...`. Webhook dedicado `Watchdog gateways casino (PROD)`
  (id `1551671291877003455`) en `#crons-anuncios` (canal `1542631941583409303`, guild
  `1493354289266167808`).
- Estado/dedup: `/var/lib/hermes-casino-gateways/state.json` (`{"state","signature","sent_at"}`).
  `REPEAT_AFTER = 6 h`: si el problema persiste y la firma no cambia, **no repite**; si cambia
  (avería distinta) o vuelve a empezar, sí avisa.
- Zona horaria de los mensajes: **Bogotá (UTC-5)**.

| Situación | Emoji | Quién lo ve |
|---|---|---|
| Se aplicó una reparación | 🟠 auto-sanado | canal, sin mención |
| Sigue roto tras reparar (`rc=2`) | 🔴 SIN REPARAR | canal + mención al Admin |
| Vuelve a la normalidad tras avería | 🟢 recuperado | canal, sin mención |
| Todo sano y estable | — | nada (solo silencio) |

## 3. Qué repara el watchdog

`casino_gateways_watchdog.py` (`PROFILES = {"golden-game": {"port": 3001}, "lucky-club": {"port": 3002}}`,
`SCANDIR=/run/service`):

1. re-registra el slot s6 como `hermes` si falta o está roto;
2. re-añade `--force` al `run` si alguien lo quitó;
3. borra el marcador `down`;
4. `s6-svc -u` y espera hasta 60 s (12 × 5 s);
5. verifica que el proceso bridge del celular exista y que el puerto responda.

## 4. Cómo se probó (sin downtime y con evidencia ajena)

1. **6 casos de forma** del notificador con su propia salida simulada: sano→silencio;
   reparación→🟠 entregado (HTTP 204); misma reparación→deduplicada; roto→🔴 entregado; mismo
   roto→deduplicado; vuelta a sano→🟢 entregado. Mensajes comprobados **releyendo el canal por API**
   (autor `Watchdog PROD`), no por el `200` del POST.
2. **E2E real sin corte**: se quitó `--force` del `run` de `gateway-golden-game` con
   `sed -i "s/ --force//" /run/service/gateway-golden-game/run` (**editar el archivo no reinicia el
   servicio**) y se corrió el wrapper real del cron. Resultado: `WATCHDOG-REPAIR golden-game: run
   script sin --force -> parcheado`, aviso 🟠 entregado y **PID 71261 intacto** (uptime continuo,
   cero downtime).
3. **Ticks del cron** confirmados en syslog (21:05/21:10/21:15) y **sin escribir nada en el log
   cuando está sano**.
4. Backup del wrapper previo (versión muda):
   `/root/hermes-backups/casino-watchdog-20260921/hermes-casino-gateways.sh.pre-notify`.

Fuente en DEV: `/opt/data/drafts/casino-watchdog/{hermes-casino-gateways.sh,hermes-casino-gateways-notify.py}`.
Doc de negocio: `brain/ops/gateways-casinos-standalone-2026-09-20.md` (+ sección 21-sep).

## 5. Cabos sueltos

- `WHATSAPP_ALLOW_ALL_USERS=true` sigue activo en el `.env` de ambos perfiles (el bot contesta a
  cualquiera que escriba a ese celular): **decisión del Admin pendiente** (mantener vs acotar con
  `WHATSAPP_ALLOWED_USERS`).
- El multiplexer sigue listando a ambos en `served_profiles` (contabilidad interna). En v0.21.3 no
  hay lista de exclusión (`multiplex_profile_allowlist` fue retirado; `GATEWAY_MULTIPLEX_PROFILES`
  es booleano): quitarlos exigiría sacar su home de `profiles/` y eso **rompe** `hermes -p <perfil>`
  y su cron. Sin pelea real ⇒ se deja.
- `gateway_state.json` de golden conserva un `api_server: fatal` **obsoleto** (hoy está
  deshabilitado en ambos).
- **Hazard**: no crear cron jobs dentro de esos dos perfiles — el ticker del multiplexer y el suyo
  podrían duplicarlos. Hoy ambos tienen `cron/jobs.json` vacío.
- El watchdog de casino existe en PROD; DEV tiene el suyo con el mismo patrón. PROD **no** tiene
  watchdog de flota (DEV sí).

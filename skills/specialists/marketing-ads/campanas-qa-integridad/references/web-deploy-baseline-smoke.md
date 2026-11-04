# Deploy de superficie web de campaña — baseline + smoke (protocolo Roshi)

Aplica cuando el equipo publica o reemplaza una superficie web de campaña en prod
(galería de reels, portal de campañas, landings de cliente). Origen: deploy del
Portal de Campañas a reels.neuralcrewlabs.com (02/sep/2026). La fase de línea base
está validada en vivo; el smoke es el checklist a ejecutar cuando el deploy aterriza.

## Topología que hay que respetar (regla fija del usuario)

- Servidor .250 = SOLO desarrollo: nada público sale de ahí; el portal en staging
  se sube al .222 por Tailscale.
- Servidor .222 = producción: NPM (nginx-proxy-manager, :80/:443) es el ÚNICO dueño
  del tráfico público vía Cloudflare; DNS de subdominios siempre al .222.
- reels-web corre como contenedor en :9020 con docroot `/opt/reels/`.
- Paneles administrativos aislados en Tailscale; CrowdSec vigilando (:6060/:8080).
- Servicios del .250 no comparten puertos con prod (dev :3010/:3020 vs prod :9001-9003/:9020).

## Fase 0 — Línea base (ANTES de tocar prod) [técnica validada]

Sin necesidad de SSH si la URL es pública — capturar por cada URL viva:

```bash
for u in https://reels.neuralcrewlabs.com/ https://reels.neuralcrewlabs.com/lucky/bingo/; do
  echo "== $u"
  curl -s -o /dev/null -w 'HTTP %{http_code} | %{size_download} bytes | %{time_total}s\n' "$u"
  curl -s "$u" | grep -oiE '<title>[^<]*</title>' | head -1
done
```

Registrar: código HTTP, bytes de respuesta, title. Todo el smoke posterior se compara
contra estos valores (ej. línea base real: portada 200 / 3258 bytes / «Galería de campañas»).

## Contrato de URL

- Redeploy de una página viva NO cambia URLs existentes: `/lucky/bingo/` ya está
  compartida e indexada. El deploy añade/reescribe la portada y preserva rutas hijas.
- En el smoke, cada URL de la línea base debe responder el mismo código HTTP que antes.

## Fase 1 — Smoke post-deploy (checklist)

1. Portada nueva: `<title>` cambió al esperado y HTTP 200.
2. Contenido nuevo presente (ej. tarjeta Golden visible en el portal).
3. URLs heredadas intactas: mismos códigos que la línea base.
4. Routing NPM intacto: sin 5xx ni loops de redirect; tamaños coherentes con la base.
5. Reportar al chat del equipo CON evidencia (códigos + títulos), no con un «ya quedó».

## Flujo multi-agente (cómo se reparte)

- Builder (Hermes/builder): monta en staging (.250), luego publica al .222 respetando
  la topología y el contrato de URL.
- Roshi: reclama el QA — captura la línea base ANTES del OK del deploy, espera el aviso
  de deploy aterrizado, ejecuta smoke y reporta.
- Verificación en vivo mientras se espera el deploy: re-curl la portada; si title/bytes
  no cambian, el deploy NO aterrizó — reportar el estado real («prod todavía sirve la
  línea base»), nunca asumir que el deploy pasó o falló sin evidencia.

# CDP WebSocket Multi-Viewport Layout Probe (sin puppeteer/playwright)

Receta verificada en vivo (27-oct-2026, QA de Lucky: detección de CTA tapada por barra legal fija).
Verifica programáticamente qué RENDERIZA una página servida en cada viewport: rects, overlap de
elementos, computed styles — evidencia dura, no inspección visual. Complementa
`dogfood/references/headless-chrome-surface-verification.md` (que cubre CLI + screenshots); esta
receta devuelve JSON estructurado de una sola pasada multi-viewport.

## Cuándo usarla
- Necesitas probar occlusion/overlap (¿la barra fija tapa el CTA?), visibilidad real
  (`width>0`, `display!=none`), o computed styles en N viewports contra un build de DEV.
- No hay puppeteer/playwright instalados en el host y no quieres instalarlos.

## Receta (Node puro, sin dependencias)

Requisito: Chrome/Chromium con `--remote-debugging-port=9223` accesible desde el host que ejecuta
el script. Node ≥ 22 trae `WebSocket` global. Esqueleto completo:

```js
const v = await (await fetch('http://127.0.0.1:9223/json/version')).json();
const ws = new WebSocket(v.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    const q = pending.get(m.id); pending.delete(m.id);
    m.error ? q.reject(new Error(JSON.stringify(m.error))) : q.resolve(m.result);
  }
});
await new Promise((r) => ws.addEventListener('open', r));
const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
  const mid = ++id; pending.set(mid, { resolve: res, reject: rej });
  ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId ? { sessionId } : {}) }));
});

for (const [w, h] of [[390, 844], [360, 740], [1440, 900]]) {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 2, mobile: w < 800 }, sessionId);
  await send('Page.enable', {}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Page.navigate', { url: 'http://127.0.0.1:PORT/ruta' }, sessionId);
  await new Promise((r) => setTimeout(r, 4200)); // espera hidratación/spa

  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }, sessionId);
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 300));
    return r.result.value;
  };

  // Interactuar si el estado a medir está tras un click (abrir modal, etc.)
  await ev(`(() => { const b=[...document.querySelectorAll('button')].find(x=>/Girar/i.test(x.innerText)); if(b) b.click(); return true; })()`);
  await new Promise((r) => setTimeout(r, 2400));

  const res = await ev(`(() => {
    const spin = document.querySelector('.spin-btn');
    const banner = document.querySelector('#age-verification-banner');
    const sr = spin && spin.getBoundingClientRect();
    const br = banner && banner.getBoundingClientRect();
    return { vp: innerWidth+'x'+innerHeight,
      spinFullyVisible: !!(sr && sr.top>=0 && sr.bottom<=innerHeight && !(br && sr.bottom>br.top)),
      spinCoveredByBanner: !!(br && sr && sr.bottom>br.top) };
  })()`);
  console.log(JSON.stringify(res));

  await send('Target.closeTarget', { targetId }); // NO omitir: filtra targets si falta
}
ws.close();
```

## Gotchas verificados
- **`exceptionDetails` se traga si no lo chequeas**: un eval que lanza devuelve `{result:{value:undefined}}` sin error — assertion silenciosa. Siempre revisar `r.exceptionDetails`.
- **`mobile: w<800`** en `setDeviceMetricsOverride` activa viewport móvil real (meta viewport respetado). Sin esto, 390px no es móvil.
- **`returnByValue: true`** imprescindible: sin él recibes un `RemoteObjectId`, no el dato.
- **CSS `:has()`**: verificar con `CSS.supports('selector(:has(*))')` dentro del propio probe antes de asumir que la regla aplicó; y medir `getComputedStyle(el).maxHeight` para confirmar que la regla ganó especificidad (una regla duplicada en un `@media` posterior puede pisarla).
- **`100dvh`**: declarar el fallback `100vh` primero y `100dvh` después (doble declaración); `dvh` corrige las barras dinámicas del navegador móvil.
- **Sticky en panel scrolleable**: `position:sticky; bottom:0` del CTA dentro de un contenedor con `overflow-y:auto` es no-op cuando el contenido cabe — seguro aplicarlo en la regla BASE (todos los viewports), no solo en media queries móviles.
- Ejecutar vía `ssh dev "node script.mjs"` apuntando al puerto CDP del host DEV para probar el build del worktree sin tocar producción.

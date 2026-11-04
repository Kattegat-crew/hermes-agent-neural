---
name: mobile-landing-optimization
description: "Trigger: mobile landing, landing performance, meta ads landing, slow mobile page, drop-off reduction, funnel speed, paid traffic landing. Architecture and optimization patterns for high-converting paid-traffic mobile landing pages."
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
---

# Mobile Landing Optimization (Paid Traffic & Funnels)

Architectural playbook for paid-traffic (Meta Ads / TikTok Ads / Google Ads) landing pages. Paid mobile clicks have a ~10-20% drop-off penalty for every 500ms of latency.

## Critical Funnel Constraints

1. **The 1-Second Cold-Start Target**: A paid mobile click must reach First Contentful Paint (FCP) in < 300ms and Largest Contentful Paint (LCP) in < 1.2s on a 4G connection.
2. **Visual Hierarchy & Zero Glitches**: The Value Proposition (Hero headline + CTA + key visual) must render before any auxiliary elements (chat bubbles, floating mascots, discount timers).

## Architecture Playbook

### 1. Route Bundling: Eager Hero vs Lazy Ancillaries
```jsx
// ❌ WRONG: Lazy loading the main route on a single-page landing causes waterfall + loader flash
const Home = lazy(() => import('./pages/Home'));

// ✅ CORRECT: Eagerly bundle Home for instant hydration
import Home from './pages/Home';

// Lazy-load ONLY ancillary routes & heavy interactive popups
const Terminos = lazy(() => import('./pages/Terminos'));
const InteractiveWheel = lazy(() => import('./components/InteractiveWheel'));
const SlotMachineModal = lazy(() => import('./components/SlotMachineModal'));
```

### 2. Floating Mascot / Chat Widget Deferral
Floating buttons or mascots that mount immediately steal user attention and compete with Hero hydration.
```jsx
// Defer widget mount by 1.5s so hero settles first
const [isReady, setIsReady] = useState(false);
useEffect(() => {
  const timer = setTimeout(() => setIsReady(true), 1500);
  return () => clearTimeout(timer);
}, []);

// Allow external CTA buttons to open it immediately if clicked
useEffect(() => {
  const onOpen = () => { setIsReady(true); setIsOpen(true); };
  window.addEventListener('open-chat', onOpen);
  return () => window.removeEventListener('open-chat', onOpen);
}, []);

if (!isReady) return null;
```

### 3. Responsive Mobile Media Budget
- Never serve desktop backgrounds to mobile devices.
- Define a dedicated `.hero-bg-media` or `<picture>` element serving a WebP under 120 KB for `< 768px`.
- Disable CPU/GPU-heavy WebGL shaders on mobile viewports (`window.innerWidth < 768` or low core counts) to preserve device battery and prevent FPS drops.

### 4. Zero-JS Instant FCP Skeleton
Inject an inline `<style>` inside `<head>` and a skeleton spinner directly inside `#root:empty` in `index.html`.
- Displays branded feedback within 100ms before JavaScript execution starts.
- Dissolves automatically once React mounts `#root`.

### 5. Below-the-Fold CSS Containment
```css
.below-the-fold-section {
  content-visibility: auto;
  contain-intrinsic-size: auto 650px;
}
```
Instructs mobile browsers to skip layout and painting for off-screen sections until the user scrolls toward them.

### 6. CTA Principal Visible en Móvil (causa raíz verificada de conversión cero)

Caso real (Lucky vs Golden, 27-oct-2026): tráfico pagado casi idéntico, webhook y formulario funcionando end-to-end, y AUN ASÍ 0 leads en 14 días. Causa: la CTA principal del header desaparecía en móvil:
```css
/* ❌ La pauta aterriza en móvil y no existe NINGÚN camino visible al formulario */
@media(max-width:860px){ .header-cta .btn{display:none} }
/* y el menú hamburguesa solo tenía: Inicio, Eventos, Sedes, Nosotros, Contacto */
```
La página de campaña `/eventos` donde aterriza la pauta no tenía CTA de bono en el body — solo el botón del header, oculto. Regla invariante:
- En la landing EXACTA donde aterriza la pauta, la CTA de conversión debe ser visible y clicable en viewport 390x844. Si el header colapsa a hamburguesa, la CTA de conversión va en el hero o como botón sticky.
- Verificación con evidencia, no inspección visual: emular móvil (390x844) y listar CTAs con `getBoundingClientRect().width>0 && getComputedStyle(e).display!=='none'`. Un botón presente en el DOM con `width:0` NO existe para el usuario.
- Comparar contra la landing gemela que sí convierte (paridad de builds): diff de reglas `@media` sobre el CSS servido (`grep -o '@media[^{]*{[^}]*\.header-cta[^}]*}' main-*.css`) y del formulario (campos, sede, fricción pre-form).

#### 7. Oclusión de segundo orden: barra fija legal tapa la CTA dentro del modal

Caso real (Lucky, 27-oct-2026, verificado con sonda CDP): la CTA del header ya era visible en móvil, PERO el CTA primario del modal de conversión (botón "¡GIRAR Y GANAR!") quedaba tapado por la barra legal +18 (`position:fixed`, z-index superior al modal) y por debajo del pliegue dentro del panel con scroll. El usuario abría el modal y no veía la acción.

Patrones de fix (todos verificados en 390×844, 360×740 y 1440×900):
- **Reservar la altura de la barra fija en vez de ocultarla**: la barra legal no se quita (obligación legal); se reserva su aire:
  ```css
  body:has(#age-verification-banner) .slot-overlay { padding-bottom: 4.4rem; }
  body:has(#age-verification-banner) .slot-panel {
    max-height: calc(100vh - 5.6rem);
    max-height: calc(100dvh - 5.6rem); /* dvh override: barras de navegador móviles */
  }
  ```
  `:has()` funciona en Chrome headless moderno; guard con `CSS.supports('selector(:has(*))')` si el CSS es crítico.
- **CTA sticky dentro del panel scrolleable, para TODOS los viewports**: poner la regla sticky en la regla base del contenedor de controles, NO solo en un `@media(max-width:640px)` — en desktop el contenido también excedía el `max-height` del panel y el botón quedaba recortado. Sticky es no-op cuando el contenido cabe, así que es seguro en desktop:
  ```css
  .cabinet-controls { position: sticky; bottom: 0; z-index: 40;
    background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.92) 35%, rgba(0,0,0,.98) 100%); }
  ```
- **`white-space: nowrap` en el texto del botón primario** en móvil: el texto partía en dos líneas ("¡GIRAR Y" / "GANAR!"), agrandaba el botón y devoraba el viewport.

Assert programático, no a ojo: `spinFullyVisible = r.top>=0 && r.bottom<=innerHeight && !(banner && r.bottom > banner.getBoundingClientRect().top)`.

## 8. Verification Checklist
- [ ] Mobile payload < 1.0 MB transferred on cold start.
- [ ] No layout shift (CLS < 0.05) when images load (explicit dimensions).
- [ ] Mascot / Chat floats in smoothly 1.5s after hero.
- [ ] Meta Pixel & Conversion API (CAPI) events fire with matching `event_id`.
- [ ] CTA de conversión visible en móvil en la página de aterrizaje de la pauta (botón con `width>0` real, y entrada en el menú hamburguesa si el header colapsa).
- [ ] Formulario alcanzable sin gate pesado (giro/animación de ~4 s antes de mostrar el form reduce conversión; la landing gemela muestra el form de entrada).
- [ ] Al probar headless: `localStorage.clear()` para estado de spin viejo y tab con foco (`document.hidden:false`) — si no, la animación no termina y se reporta un bug falso.

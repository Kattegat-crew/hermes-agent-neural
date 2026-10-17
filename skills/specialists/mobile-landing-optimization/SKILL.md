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

### 6. Verification Checklist
- [ ] Mobile payload < 1.0 MB transferred on cold start.
- [ ] No layout shift (CLS < 0.05) when images load (explicit dimensions).
- [ ] Mascot / Chat floats in smoothly 1.5s after hero.
- [ ] Meta Pixel & Conversion API (CAPI) events fire with matching `event_id`.

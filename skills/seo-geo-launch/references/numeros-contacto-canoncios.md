# Números de contacto canónicos (aprobado 10-nov-2026)

| Marca | Nombre del asistente | WhatsApp / único canal | wa.me | E.164 JSON-LD |
|---|---|---|---|---|
| Golden Game | **Goldie** | +57 304 356 1269 | `wa.me/573043561269` | `+573043561269` |
| The Grand Paradise (Lucky Brothers) | **Lucky** | +57 311 492 5556 | `wa.me/573114925556` | `+573114925556` |

Reglas duras:
- **Un solo número por marca en TODA la superficie** (botones, footer, contacto, términos, política de datos, juego responsable, seoMeta, llms.txt, sedes, JSON-LD). La fija 601 384 3934 y los móviles viejos (316 691 0728, 316 690 9310) están **prohibidos**.
- El JSON-LD publica el número **real** en E.164 (nunca enmascarado con asteriscos: es un dato inválido para Google).
- Los `wa.me` van sin `+` ni espacios; el texto visible sí lleva formato legible `+57 XXX XXX XXXX`.
- Fuente única en código: `src/utils/whatsappCta.js` (`WHATSAPP_NUMBER`). El resto de archivos debe consumirla o replicarla idénticamente.

## CTA de WhatsApp en el shell de TODAS las rutas (10-nov-2026)
El teléfono canónico no puede vivir solo en home y /contacto: los crawlers y las IAs sin JS leen el HTML crudo, y el resto de rutas no ofrecía NINGÚN canal de contacto aunque el usuario final sí lo viera tras montar React.
- `renderShell()` (`src/data/routeShells.js`) cierra con un bloque `class="seo-shell-cta"`: enlace `https://wa.me/<WHATSAPP_NUMBER>` (texto con `encodeURIComponent`, href insertado con `esc()`) + teléfono visible. Consumir la constante, nunca hardcodear el número.
- **Páginas con entrada propia** (`/eventos`): prerender-routes ya NO las preserva con el body vacío — inyecta su shell dentro de `<div id="root">` conservando SU `<head>` (title/og/canonical/JSON-LD propios). Guard de inyección: solo si `ROUTE_SHELL[route]` existe, el HTML aún no contiene `seo-shell` y el root está vacío. Seguro para React: `createRoot` reemplaza el contenido al montar (no hay `hydrateRoot`, sin mismatch de hidratación).
- **Idempotencia**: la inyección opera sobre el archivo que produce postbuild y `npm run build` regenera `dist/` desde cero; el guard del marcador evita acumulación si se re-corre el prerender sobre dist existente.
- Test por repo `tests/shellCta.test.mjs` (comportamiento, no fuente): todo shell de `ROUTE_SHELL` lleva enlace wa.me + teléfono visible + bloque CTA; TODAS las rutas del `sitemap.xml` en `dist/` llevan el enlace; cero números viejos en los HTML de dist. Con build previo también cubre las páginas dedicadas.
- Commits: golden `aa80a29` (rama `fix/shell-cta`), paradise `19c01a8`. Tests verdes: golden 39/0, paradise 48/0.

## Trampas encontradas
- `/eventos` tiene **entrada Vite propia** (`eventos.html` en la raíz): su `<title>`/`<meta>` NO sale de `seoMeta.js`; hay que tocar los dos o el prerender lo pisa.
- `public/` no contiene el HTML de `/eventos`; el build copia `dist/eventos.html` → `dist/eventos/index.html` (postbuild). Verificar en `dist/`, no en `public/`.
- Paradise inyecta `telephone` por sede desde `scripts/prerender.mjs` usando la constante; golden lo lleva hardcodeado en `index.html` (2 bloques: LocalBusiness + Organization).
- `carousel_list_builder.py` tenía `wa.me/goldengame` / `wa.me/paradiseclub` (slugs, no números): un wa.me sin dígitos es un enlace roto.

## Verificación (gate)
- Test por repo `tests/phoneCanonical.test.mjs`: prohíbe números viejos en `src/`, `public/`, `index.html`; exige `wa.me` canónico y constante correcta; golden además exige JSON-LD E.164 real y paradise exige el número en `dist`.
- Test `tests/shellCta.test.mjs` (ver sección CTA arriba): cobertura del CTA en el shell y en el dist completo.
- `qa_landing` **S21** (21 checks SEO): falla con placeholders `[PENDIENTE|TODO|XXX]` y con cualquiera de los teléfonos viejos. RED/GREEN probado.
- Verificación live: recorrer todas las URLs del sitemap y contar ocurrencias viejas = 0, links canónicos > 0, JSON-LD con un único `telephone` por marca.
- GBP queda **pendiente**: cuota 429 + 3 sedes suspendidas; al abrir, actualizar teléfono en 7 fichas Golden y 5 Paradise (y el teléfono faltante de El Carmen).

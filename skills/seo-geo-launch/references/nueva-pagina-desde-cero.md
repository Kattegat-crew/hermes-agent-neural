# Página nueva desde cero — checklist de nacimiento (SEO/GEO/legal)

Objetivo: que una landing nueva **nazca** con todo lo que a Golden y Paradise nos costó 4 rondas de auditoría. Nada de esto es "fase 2": si falta en el build, se paga después con retrabajo y con un gate que da falso verde.

## P0 — debe existir en el primer build

### 1. Shell estático por ruta (el error más caro)
- El prerender NO puede servir el body del home en todas las rutas. Cada ruta del sitemap lleva su propio `h1`, `lead`, `points[]` y `links[]` en `src/data/routeShells.js`.
- Invariante medible: **similitud de tokens contra `/` < 0.5** (Golden pasó de 0.97–1.00 a 0.11).
- Sustitución idempotente entre marcadores de `#root`: dos builds seguidos deben dar el mismo hash.
- Fallback para rutas nuevas: `title`/`description` propio, nunca heredar el home.
- Test: H1 único por ruta + similitud + contenido legal presente en HTML crudo (`Ley 1581` en política de datos, `Coljuegos` en términos).

### 2. Head completo (por ruta, no solo en el home)
- `title` 15–60 con la marca al frente + intención.
- `description` 50–165 (210 chars es un fail real).
- `canonical` absoluto, autorreferente.
- `og:title`, `og:description`, `og:image` **con URL absoluta** (relativa = preview roto en Meta/WhatsApp), 1200×630 real, `og:image:width/height`, `twitter:card`, `twitter:image`.
- Página con entrada Vite propia (p.ej. `eventos.html`): su `<head>` NO sale de `seoMeta.js`; hay que tocar los dos o el build pisa uno.

### 3. JSON-LD verificado, no decorativo
- `Organization` + `LocalBusiness` (o uno por sede): `name`, `address` (PostalAddress), `telephone` **E.164 real** (jamás enmascarado con asteriscos), `areaServed`, `sameAs`.
- `Event` para campañas: `name`, `description`, `startDate`, `endDate` **reales** y espejo de la vigencia publicada.
- `openingHoursSpecification`: **prohibido** si no hay fuente interna confirmada. Un horario inventado en JSON-LD es peor que no tenerlo.
- Test: todos los `telephone` iguales al canónico; parseo JSON válido de cada bloque.

### 4. Datos de negocio desde la fuente canónica
- Direcciones/sedes: entidad del brain + ground-truth del sistema. **Nunca** la tabla de research (en Golden esas eran las contradichas históricas y estaban vetadas por test).
- Horarios: si no existen en la fuente, texto honesto ("consulta por WhatsApp al …"), nunca estimación.
- Un solo número por marca en TODA la superficie: constante en `src/utils/whatsappCta.js`, `wa.me/<digits>` sin `+` ni espacios, formato visible `+57 XXX XXX XXXX`, y test `phoneCanonical` que prohíbe los viejos.
- Fechas de campaña: **una sola fuente** (`eventsData`/`seoMeta`), alineadas en home, TyC, eventos y JSON-LD. Si el cliente dice "arrancó el 9 y el primer sorteo es el 11", se escribe así en todas partes.
- **CTA de contacto en TODAS las rutas del HTML crudo**, no solo en home y /contacto: un crawler o una IA sin JS no ve los botones que monta React. Cada shell cierra con el número visible + `wa.me` (mismo contrato de `text` prellenado y UTMs que los demás CTAs) y un test lo verifica sobre el `dist` real.
- **Páginas con entrada propia** (otro `*.html` de Vite): su `<head>` es suyo, pero el body llega vacío. El prerender debe inyectarle su shell igual que a las demás, o esa ruta queda sin contenido ni CTA en crudo.

### 5. Rastreo y GEO
- `sitemap.xml` con todas las rutas + `robots.txt` con `Sitemap:` (no basta el robots por defecto de Cloudflare).
- `llms.txt` con marca, servicios, sedes, contacto.
- FAQ por sede / quick answers en HTML crudo (no solo en React).
- Consent de cookies y age gate (18+) presentes y no bloqueando el render del crawler.

## P1 — antes de publicar
1. `npm run build` y auditar **dist fresco**: `--project-dir` audita lo que hay en `dist/`, si no reconstruiste auditas el build viejo (falso verde/falso rojo).
2. Gate `scripts/seo_gate.py` (exit 0 solo si READY, sin `critical` y S21 limpio).
3. Recorrer **todas** las URLs del sitemap en producción: 200, cero placeholders, cero números viejos, canonical/OG presentes.
4. Reviewer independiente del que implementó (perfil distinto). Hasta verde.
5. Verificar que el commit desplegado es el que crees: API de deploy con `commit` + `finished_at`.

## P2 — después de publicar
- GBP: NAP consistente, teléfono y horarios reales, links de mapa con `place_id` (no búsqueda por texto).
- Medición AI (GEO): prompts × motores, línea base antes de tocar contenido.
- Cache de HTML en el edge (`s-maxage`), hoy ambos sitios sirven `no-store`.

## Anti-patrones que ya nos costaron caro
| Anti-patrón | Coste real |
|---|---|
| Prerender que copia el home | 10 rutas duplicadas, invisibles en el checklist hasta medir similitud |
| Auditor que valida etiquetas, no valores | 20/20 READY con 18 placeholders en producción |
| `dist/` no reconstruido antes de auditar | GBP 80% fantasma y veredictos contradictorios |
| Investigación (research) como fuente de direcciones | Direcciones vetadas publicadas en producción |
| Horarios "razonables" | Datos inventados en texto **y** en JSON-LD |
| `og:image` relativo | Preview roto en Meta/WhatsApp aunque el HTML "se vea bien" |
| Números de contacto dispersos | 57 ocurrencias en 14 archivos; el cambio se hace por constante |
| Confiar en hooks de Coolify como gate | El post-deploy traga el exit code; el pre-deploy audita el contenedor viejo |

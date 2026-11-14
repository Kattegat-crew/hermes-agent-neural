---
name: modern-web-guidance
description: "Use when writing or auditing HTML/CSS/client-side JS."
tags: [web, html, css, javascript, best-practices, accessibility, performance, security, legacy-scan, chrome]
version: 1.0.0
author: Ragnar (NeuralCrew Labs) — wrapper around GoogleChrome/modern-web-guidance (Apache-2.0)
license: Apache-2.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, html, css, javascript, best-practices, accessibility, performance, security, chrome]
    upstream: https://github.com/GoogleChrome/modern-web-guidance
    related_skills: [senior-frontend, code-review-and-quality]
---

# Modern Web Guidance (wrapper)

Consultas a las 209 guías oficiales de Google Chrome sobre la plataforma web
moderna, vía CLI local con búsqueda semántica offline. Sin red, sin API keys.

- **CLI:** `/opt/hermes-agent-data/tools/mwg/node_modules/.bin/modern-web-guidance`
- **Paquete:** `modern-web-guidance@1.0.0` (fijado en `/opt/hermes-agent-data/tools/mwg/package.json`)
- **Upstream:** https://github.com/GoogleChrome/modern-web-guidance · Apache-2.0

## Cuándo usar

Antes de escribir o modificar HTML, CSS o JS de cliente, cuando el tema sea:

dialogs/modales/popovers, tablas, dark mode, anchor positioning, container
queries, view transitions, scroll-driven animations, parallax/reveals, forms,
validación, autofill, accesibilidad, selects custom, scrollbars, Core Web Vitals
(LCP/INP/CLS), content-visibility, fetch priority, optimización de imágenes,
seguridad de cliente, passkeys, sanitización HTML, web components, fechas/zonas
horarias, built-in AI, WebAssembly, WebMCP, o HTML/CSS/DOM estándar dentro de
cualquier framework.

## Cuándo NO usar

Backend (SQL, ORMs, rutas de API), infraestructura o scripts (CI/CD, Docker,
Actions, Python/Go, Git), o tooling trivial (Vite, tsconfig, ESLint, tests,
renames, copias). No busques guías de front para un cambio de backend.

## Flujo

### 1. Buscar (query de 2–5 palabras, una sola capacidad)

```sh
/opt/hermes-agent-data/tools/mwg/node_modules/.bin/modern-web-guidance search "light dismiss dialog"
```

- Verbos + objeto UI, sin nombres de framework ni de dominio (nada de `React`, `Vue`, `Tailwind`, ni nombres de componente del proyecto).
- Si la intención no nombra la primitiva, tradúcela: "confirmar antes de borrar" → `confirmation modal dialog`; "elegir fecha" → `date picker input`.
- Si el resultado es débil o vacío, reformula **una vez** con el sustantivo concreto (`dialog`, `popover`, `table`, `form`) antes de caer a `list`.

### 2. Recuperar

```sh
/opt/hermes-agent-data/tools/mwg/node_modules/.bin/modern-web-guidance retrieve "animate-to-from-top-layer"
```

- Acepta varios IDs separados por coma.
- Usa el id **exacto** que devolvió `search`: un id inventado falla con
  `No guide found for use case: <id>` y no hay fuzzy matching.
- Si la salida es grande (>9.5 KB) el CLI **no imprime el contenido**: lo deja en
  `/opt/hermes-agent-data/cache/scratch/mwg-guide-*.md` y devuelve la ruta. Leer
  ese archivo completo con `read_file` — nunca con `cat`/`head`.

### 3. Implementar y verificar contra la guía

Aplica los patrones y fallbacks que la guía exige, sin añadir features no
pedidas. Comprueba el resultado contra lo recuperado antes de dar el trabajo por
cerrado.

### 4. Declarar el uso

Al final de la respuesta donde entregas los cambios, añade una sección
`### Modern Web Guidance` con un bullet (≤75 palabras) por guía aplicada,
citando entre comillas la regla o gotcha concreta que evitó el error. Si
buscaste pero ninguna guía aplicó, una sola frase nombrando qué comprobaste y
por qué no aplicó.

## Modernizar un repo (auditoría)

Solo para escaneos amplios de deuda legacy sin feature concreto pedido:

```sh
/opt/hermes-agent-data/tools/mwg/node_modules/.bin/modern-web-guidance legacy-scan /ruta/al/repo
```

Cubre ~20% del corpus con reglas deterministas (33 guías) y sus hallazgos son
**provisionales**: cada uno trae criterios *Keep when / Drop when* que hay que
verificar a mano. No lo corras cuando el pedido es añadir, arreglar o auditar
un componente específico — ahí va `search` + `retrieve`.

## Coste y límites

- Cada llamada levanta Node: **~130 MB RSS pico en search/retrieve (1.4–1.9 s)**;
  `legacy-scan` sobre un repo real midió **253 MB / 3.1 s**. Una o dos llamadas
  por turno es razonable; no encadenes diez búsquedas.
- Funciona con red bloqueada (verificado con proxy muerto): el índice y las
  guías viven en el paquete local.
- Origin Trials y features volátiles están **gateadas**: solo se recuperan si el
  repo tiene `.mwgrc` con `allowOriginTrials` / `allowVolatileFeatures`. No las
  actives en producción de cliente sin autorización explícita.

## Mantenimiento

```sh
cd /opt/hermes-agent-data/tools/mwg && npm install modern-web-guidance@latest --save-exact
/opt/hermes-agent-data/tools/mwg/node_modules/.bin/modern-web-guidance -v
```

Subir de versión solo tras repetir el smoke test (`-v`, `list`, `search`,
`retrieve`, `legacy-scan` sobre un fixture). El paquete no vive en Git: si se
reconstruye el host, reinstalar con el comando de arriba.

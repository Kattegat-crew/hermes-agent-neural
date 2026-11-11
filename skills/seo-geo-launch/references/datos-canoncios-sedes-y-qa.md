# Datos canónicos de sedes + auditoría qa_landing (lecciones 10-nov-2026)

## Fuente canónica de direcciones (Golden)
- **Canónico**: `brain/entities/golden_game.md` (entidad cliente) + `/opt/hermes-agent/plugins/observability/jev_judge/knowledge/casino_ground_truth.json` (conocimiento del sistema).
- **NO canónico**: la tabla de `docs/seo-playbook/keyword-research-2026-11.md` y los briefs F2.2 — sus direcciones son las *contradichas históricas* y están vetadas por `DIRECCIONES_VETADAS` en `tests/geoSedesShell.test.mjs` (Carrera 5 No 2-33, Carrera 3 No 2-37, Carrera 15 No 7-3, Calle 4 No 6-23/6-25, Calle 3 No 8-32, Carrera 6 No 47A-40, Calle 11 No 9-50). Publicarlas = test rojo.
- Direcciones canónicas Golden: Agua de Dios `Calle del Comercio, Zona Centro`; Anolaima `Carrera 4 # 5-67, Centro`; Cachipay `Calle Principal # 12-34`; El Carmen `Avenida Principal # 8-90`; Pacho `Carrera 16 # 7-32, Zona Centro`; San Francisco `Plaza Principal`; Tunja `Calle 18 # 11-45, Centro Histórico`.
- **Horarios**: no existen en ninguna fuente interna (brain/ground truth/inventario GBP) → NUNCA estimar; publicar `Consulta por WhatsApp al +57 316 691 0728` (WhatsApp oficial confirmado en brain).
- og:image: 1200×630 reales (canvas 1200×630, fondo cover+blur oscurecido, pieza cuadrada centrada a 630). Los assets originales son 1254×1254.

## qa_landing: auditoría sin falsos verdes/rojos
- `--project-dir` lee **dist/ local**: si no reconstruiste tras el cambio, auditas el build viejo (GBP 80% fantasma, PENDIENTE fantasma). Auditar SIEMPRE el worktree con build fresco, o `--url` contra producción.
- Desde `a7577b9`: `discover_pages` deduplica fuente↔dist (por ruta relativa, el prerender cambia el HTML) y excluye `*.bak*`, `root-YYYYMMDD`, `.worktrees`; la canibalización solo cuenta entre páginas **dueñas** (keyword en title o H1, no legales); `missing_page=true` cuando ninguna página comercial reclama la keyword (caso real: `bingo millonario` lo gana `terminos-bingo-millonario`).
- `npm test` del landing cuelga (tests PG/tracking): correr `node --test` solo con los archivos estáticos (geoSedesShell, staticSeoShell, prerenderRoutes, seoGeo, whatsappCta).
- `pkill -f "node --test"` se mata a sí mismo: usar `pkill -f "[n]ode --test"`.
- Guard de comandos: no mezclar `git push` y `--ff-only` en la misma línea (matchea deny rule `*git push*-f*`): push como último token.

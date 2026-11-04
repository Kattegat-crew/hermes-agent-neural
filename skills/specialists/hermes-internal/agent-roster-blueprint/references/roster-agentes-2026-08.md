# Roster especialistas 2026-08-26 (registro de sesión)

Plan de 8 agentes especializados NeuralCrew Labs sobre perfiles Hermes. Informe completo: `/opt/data/workspace/plan-agentes/` (INFORME .md + .docx). Concepto brain: `concepts/plan-agentes-especializados.md`.

## Nomenclatura (panteón nórdico, coherente con Ragnar/Mimir/Odín)

| Bot | Módulo | Nombre | Deidad | Razón |
|---|---|---|---|---|
| Connect | Comunicación | **Hermóðr** | Mensajero de los dioses (viajó a Hel por Baldr) | Mensajero multicanal 24/7 |
| Web | Sitios/SEO | **Brokkr** | Enano herrero, forjó Mjölnir | Forja sitios/landings |
| Content | Contenido | **Bragi** | Dios de la poesía | El contenido es palabra |
| Social | Redes | **Freyja** | Diosa del amor/belleza | Redes viven de belleza y engagement |
| Leads | CRM/ventas | **Ullr** | Dios de la caza y el arco | Caza prospectos |
| Ads | Publicidad | **Vili** | Dios de la voluntad (creó el mundo con Odín/Vé) | Publicidad = voluntad de persuadir |
| Analytics | Métricas | **Heimdall** | El Vigilante del Bifröst, todo lo ve/oye | Dashboards y visión de datos |
| Producer | Imagen/video | **Sindri** | Enano forjador de artefactos mágicos | Produce assets mágicos |

Descartes: Odín/Mimir ya ocupados (ai-platform-api, bibliotecario Notion); Loki/Thor carga cultural o sin matiz; Hermes (griego) confunde con la plataforma.

## Funciones (1 línea por bot)
- Connect: recepcionista IA + WhatsApp/multicanal + reseñas + routing + agenda + email.
- Web: landing/webs + SEO técnico + Core Web Vitals + accesibilidad + deploys Coolify/DNS.
- Content: blog SEO + ad copy + guiones + brand voice + anti-slop + calendario.
- Social: scheduling + community + reels 9:16 + monitorización + reportes.
- Leads: captura + scoring + CRM (Twenty) + outbound + nurturing + alertas.
- Ads: estrategia cuentas + variantes A/B + píxeles + optimización ROAS + compliance Colombia.
- Analytics: ETL + dashboards + ROI/atribución + anomalías + forecasting.
- Producer: imagen (flux/ComfyUI/Stable Diffusion) + video 9:16 (pipeline) + brand assets + post.

## Catálogo de skills (125 núcleo + 30 candidatas)
| Bot | Núcleo | Candidatas |
|---|---|---|
| Connect | 15 | 3 |
| Web | 16 | 4 |
| Content | 16 | 3 |
| Social | 16 | 3 |
| Leads | 16 | 3 |
| Ads | 15 | 3 |
| Analytics | 15 | 3 |
| Producer | 16 | 8 |

## Decisiones
- Especialistas = perfiles Hermes (`/opt/data/profiles/<dios>/`), NO contenedores nuevos (ratifica equipo-de-bots 19/08).
- Fase 0 = subagentes on-demand; Fase 1 = perfiles + `gateway.profile_routes`; Fase 2 = contenedor por cliente solo si escala/aisla.
- Acceso: especialistas = Técnico (generan pero NO publican externo sin aprobación Full de Jonathan).
- Pendientes: aprobar nomenclatura (Jonathan) · tokens BotFather × 8 · crear perfiles · cron por módulo · prueba E2E.
---
name: marketing-campaign-pipeline
description: "Use when orchestrating a bot-run marketing campaign."
tags: [campanas, campaigns, pipeline, campaign-yaml, review-gate, orquestacion, drive, marketing]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [campañas, pipeline, campaign.yaml, review-gate, drive, bragi, sindri, roshi, manifest]
    category: marketing
    related_skills: [marketing-campaign, social-media-content-calendar, mapa-de-carpetas, hermes-team-ops, colombia-promociones-docs-multiempresa]
---

# Marketing Campaign Pipeline — producir campañas con el equipo de bots

Cómo se produce una campaña de marketing de punta a punta en NeuralCrew con el equipo de bots (Roshi → fábrica, Bragi → copy, Sindri → visual, Review = Admin/cliente) sobre un contrato único (`campaign.yaml`) y con aprobación humana ANTES de producir. Validado en producción con la campaña Bingo Millonario (Golden + Lucky, sept 2026).

## When to Use

- El Admin pide lanzar una campaña: posters, piezas gráficas, carruseles, reels, guiones.
- Hay que coordinar a los bots Content/Visual/Factory y el gate de aprobación.
- Preguntan "¿cómo lo hacemos / cómo está configurado?" para una campaña.
- Hay que subir entregables a Drive siguiendo el mapa de carpetas.

## Prerequisites

- `campaign.yaml` por empresa/cliente (contrato único): marca, paleta, personaje, sedes, legal, mecánica, `piezas[]` con `estado: draft|listo|aprobada`.
- Fábrica de Roshi (`build_campaign.py` en `roshi/workspace/campaigns/`) → 5 docs (PLAN-MARKETING, GUIONES-REELS, PLAN-EVENTOS, BRIEF-PIEZAS, CALENDARIO) + QA-INTEGRIDAD (OK/REVISAR + JSON).
- Manifest `estado.json` por campaña (etapa, estado por pieza, drive.aprobadas) — el puente de handoff entre bots.
- Estructura Drive por campaña: `Campañas/<slug>/` con `00-contrato/ 01-docs/ 02-guiones/ 03-piezas/ 04-aprobadas/` (registrada en `brain/folder-maps/`, ver skill `mapa-de-carpetas`).

## Pipeline (8 etapas)

| Etapa | Quién | Entrada | Salida |
|-------|-------|---------|--------|
| 0. Brief | Ragnar | Idea del Admin | campaign.yaml por empresa |
| 1. Contrato/fábrica | Roshi | campaign.yaml | 5 docs + QA-INTEGRIDAD + estado.json |
| 2. Copy/guiones | Bragi (Content) | campaign.yaml + plan | hooks, CTAs, guiones v2 |
| 3. Visual | Sindri (Producer) | guiones + identidad | posters, carruseles, stories, banners, tapas |
| 4. **REVIEW GATE** | Admin/cliente | pieza + campaign.yaml + QA | aprobada / requiere-ajustes (registra versión) |
| 5. Publicación | Freyja (Social) | piezas aprobadas | solo `estado=aprobada` |
| 6. Ads | Vili | piezas + presupuesto | Meta Ads (requiere token) |
| 7. Analytics | Heimdall | métricas | dashboard/ROI |
| 8. Funnel | Ullr | landing + leads | Twenty CRM |

## Regla dura: el gate humano ANTES de producir

El Admin aprueba **guiones y diagramación/poster** ANTES de que se produzca nada (lección 26/08: se saltó el gate y el Admin frenó todo: "necesito aprobar los guiones, la diagramación del poster, todas estas cosas"). Secuencia obligatoria:
1. Presentar el **pack de aprobación** (guiones consolidados + diagrama/layout del poster) EN EL CHAT para sí/no/ajustes.
2. Solo tras el OK: marcar `estado=aprobada` en el manifest + mover a Drive `04-aprobadas/` + `aprobada_en`.
3. Sindri produce renders reales; Bragi escribe v2. Nada se publica sin ese sello.

## Tono de copy para el público (preferencia del Admin, 26/08)

Guiones y copys de campaña: **tuteo amable con cariño de pueblo** ("mijo", "a ver si…"), casi coqueto pero **elegante, nunca pasteloso**, +18 mediante. Nada de "usted" formal ni folleto corporativo. El dato del pueblo como hook, conexión con el casino, introducción del bingo con **el premio TEMPRANO** (no al final), CTA memorable. El premio específico (monto) es el gancho — aparece casi desde el título en los diseños que funcionan.

## Research-first para diseño y guiones

Cuando el Admin rechaza el nivel creativo ("mediocre", "no me convencen"): investigar ANTES cómo promocionan ese producto en redes (Instagram/TikTok) y traer patrones, NO re-proponer de memoria. Patrones verificados para bingo/casinos: reacción de ganador real ("¡acabamos de ganar $X!"), programación clara de premios por día/hora, cifra del premio destacada, hashtags+ubicación local, prueba social (gente divirtiéndose). Referencia condensada: `references/promocion-bingo-redes.md`.

## Source of truth: campaign.yaml vs T&C vs realidad

Siempre verificar el contrato contra los documentos legales/fuentes reales antes de generar piezas. Incidente real: el campaign.yaml decía "Viernes 7PM" pero los T&C v3 decían **bingos desde 5PM, escalonados en tandas de 15-20 balotas/hora**; si la fuente de verdad no se sincroniza, las piezas autogeneradas salen con datos viejos. Regla: al crear el contrato, leer los T&C/políticas del cliente y dejar el dato exacto (horario, mecánica, premios, legal) en el YAML. Dato legal `retention_threshold` = premio máximo de la mecánica en COP (no días); `0` = [PENDIENTE] y el QA frena en REVISAR.

### T&C cambió → las piezas ya producidas quedan ILEGALMENTE viejas (protocolo 03/09)

Si cambian los T&C/manual operativo DESPUÉS de que la fábrica generó docs/guiones/clips, lo producido quedó "viejo" aunque el campaign.yaml se actualice. Receta:

1. **Verificar vigencia por mtime** de las piezas ya entregadas en `entregables/` (o `02-guiones/`, `03-piezas/`): si el T&C es posterior al mtime del doc → constante derogada.
2. **Listar las constantes derogadas** (horarios, premios, mecánica, sede, frase) que el T&C nuevo cambió.
3. **Propagar AL MAESTRO DE SERIE** (campaign.yaml + los 5 docs de fábrica + guiones), no solo a la pieza tocada — el maestro es la fuente de la próxima regeneración.
4. **Marcar clips/piezas pendientes de regenerar** (estado en manifest `estado.json`: ejemplo `pending-regen`) — no borrarlas, marcarlas para que el próximo lote las regenera contra el T&C vigente.
5. **Nunca publicar una pieza** cuyo dato visible contradice el T&C vigente, aunque el gate humano la haya ok-ado antes del cambio.
6. Frases literales dichas por el cliente (p.ej. de Jesús en guiones reels) son **intocables y derogatorias**: si un lema nuevo las reemplaza, el lema viejo queda fuera de toda pieza nueva.


## Imprimibles físicos (preimpresa con Pillow, validado 28-oct-2026)

Boletas, tarjetas de sellos, pendones y volantes NO se generan con IA: se generan con un script Pillow (`scripts/print/<campana>_print.py`, CLI `--pieza todas`). Reglas duras aprendidas:

1. **Layout en mm, nunca en píxeles crudos:** `px(mm) = int(mm*300/25.4)`; sangrado 3 mm + área segura 3 mm (canvas = pieza +6 mm); fondos a sangre, contenido dentro del margen seguro; PNG 300 ppp para revisión + PDF (`resolution=300`) para imprenta.
2. **Posiciones mm absolutas, jamás flujo acumulado** (`y = pegar_logo(...); título en y+0.6` se solapa cuando las marcas tienen logos de distinta proporción — Golden 0.76 vs Lucky 0.94 de razón alto/ancho): medir la altura real del logo al ancho elegido para el PEOR caso entre marcas y fijar cada bloque en una Y absoluta con presupuesto vertical cerrado.
3. **QA con `vision_analyze` usando preguntas concretas** ("¿el pie colisiona con SEDE/FECHA?", "¿queda espacio muerto abajo?"): preguntas genéricas devuelven prosa inútil. Convertir cada hallazgo en cambio de coordenadas mm y regenerar; descontar falsos positivos de la visión sobre elementos decorativos contrastándolos contra el código. Revisar SIEMPRE una pieza por marca.
4. **Variable-data anti-error de cajera:** una sola boleta para varios sorteos con casilla `[ ] SEMANAL / [ ] FINAL`; fechas pre-impresas bajo cada casilla de sello (impide sellar jornadas inexistentes); espacio muerto se rellena con función (bloque de canje con firma), no con decoración; pie legal en banda propia separada; pendientes legales marcados dentro de la pieza (`PIE LEGAL PENDIENTE (C6)`) para que no lleguen a imprenta por accidente.
5. **Impresor:** bandas oscuras a sangre = tinta pesada (avisar secado/marcado); lo que parece espacio muerto bajo el marco de corte es sangrado, no eliminarlo.

Nota: existe un intento de skill dedicada `print-ready-production` (dominio propio, no cubierto por este paraguas) cuyo create quedó bloqueado por el hook `guard_autoskill_create.py` fallando cerrado ("unparseable stdout", 28-oct-2026). Si el hook se repara, migrar esta sección a esa skill.

## Pitfalls

- **Subidas a Drive fallan con "Not authenticated" si la sesión corre bajo un perfil.** `google_api.py` deriva `TOKEN_PATH` de `HERMES_HOME` (`get_hermes_home()`); si el HERMES_HOME activo es `profiles/<bot>`, busca el token ahí y no lo encuentra. **Fix: `export HERMES_HOME=/root/hermes-agent-legacy-docker/data` (raíz) antes de subir assets.** Verificado 26/08 con los posters.
- **Ruta canónica del vault de skills es `/root/hermes-agent-legacy-docker/data/skills/`, NO `/opt/data/skills`** (no existe). Los scripts de provisioning que la tengan hardcodeada enlazan 0 skills o grafos de 1 nodo. Ver `hermes-skills-provisioning`.
- **Model IDs en API de OpenCode-Go:** el provider `https://opencode.ai/zen/go/v1` acepta `mimo-v2.5` (sin prefijo); `opencode/mimo-v2.5` da 401 "not supported". El tag con prefijo es del CLI local, no de la API.
- **Los docs "a mano" (T&C, manual de cajeras, guiones v1) NO son los 5 docs de la fábrica** — la fábrica regenera el mismo contenido versionado por contrato; los legales/operativos son insumo aparte. No duplicar, unificar.
- **Carrusel/piezas y guiones son UN SISTEMA**: mismo lenguaje visual (cifra estrella, "VIERNES · DESDE 5PM", balota 53, contador de acumulado) en poster, reel, story y banner — nada de piezas sueltas.

## Verification

- QA-INTEGRIDAD en OK (o solo warnings de hooks/CTAs pendientes = output esperado de Bragi).
- Manifest `estado.json`: pieza marcada `aprobada` + `aprobada_en` y archivo en Drive `04-aprobadas/` ANTES de que Freyja/Vili lo toquen.
- Re-consulta en Drive tras subir (VERIFY del mapa de carpetas).
---
name: specification-handoff
description: >-
  Use when handing a spec plus prompt to an external editor Prepara SPEC/PROMPT para editor de código externo (AGY). hermes: tags: [handoff, specification, code-editor, prompt, repos, entregables]
tags: [spec, prompt, handoff, entrega, repo, agy, especificacion]
version: 1.0.0
author: hermes
license: MIT
metadata:
triggers:
  - "el usuario pide 'prepara un prompt para un editor de código' / 'implementa cambio en el repo' sin acceso de escritura"
  - "repo destino montado read-only (/opt/repos/*) y el trabajo lo ejecuta otro agente"
  - "hay que entregar una especificación estructurada + instrucciones de implementación a AGY/OpenCode/Claude"---

# Specification Handoff — SPEC + PROMPT para editores externos

Patrón validado 2026-08-20 (promo «Ruleta Golden Game» en golden-game-landing).
Usar cuando el cambio lo va a aplicar un editor de código externo (AGY/OpenCode/Claude Code) y
el repo destino está en /opt/repos (montura read-only), o simplemente cuando el cliente
requiere una especificación íntegra y reutilizable de la implementación.

## Cuándo usarlo
- El usuario pide que se ANALICE + PREPARE el trabajo para otro agente de código (no que se ejecute aquí).
- El cambio tiene capas: frontend (componentes/rutas), backend (API), DB (migraciones), links/nav — hay que tocar varios archivos y puntos.
- Hay requisitos no funcionales difíciles de transmitir en un mensaje corto (compliance, payload, evidencia, checklist de aceptación).

## Pasos

### 1. Descubrimiento y auditoría ANTES de escribir nada
- Leer el estado real del código (archivos y LÍNEAS exactas), no basarse en memoria.
- Identificar cada punto de contacto: componentes, páginas, rutas, backend, SQL, textos existentes. Conservar `archivo ~líneas` (p. ej. `InteractiveWheel.jsx ~593-606`).
- Si el proyecto tiene AGENTS.md/skills/legado, leerlo y respetar reglas de marca y secretos.
- Ejecutar `git status/branch` para saber dónde está el working tree y no inventar estado.

### 2. Escribir el archivo SPEC (permanente, versionable)
- Contexto (legal/técnico) en 5-10 líneas.
- Tabla «auditoría actual»: archivo · estado (✅/🟠/🔴) · qué falta.
- Mapa de implementación: dónde va cada pieza, con textos EXACTOS verbatim (nunca «copia del doc X» si el contenido no está en el repo).
- Configuración requerida: estados, validación, payload JSON, SQL `ALTER TABLE`.
- Checklist de criterios de aceptación con casillas verificables.

### 3. Escribir el archivo PROMPT (temporal, autocontenido)
Delimitado entre `## INICIO DEL PROMPT` / `## FIN DEL PROMPT` con:
- «lee primero docs/SPEC-... y AGENTS.md»;
- lista de cambios A..F (frontend/rutas/backend/SQL) con reglas de UI y validación;
- reglas de ejecución: no commit/push salvo orden expresa, no instalar deps innecesarias, NO ejecutar el SQL contra la DB (solo versionarlo), no inventar → señalarlo como pendiente;
- verificación final: `npm run build`;
- ENTREGA FINAL obligatoria con estructura fija (resumen / tabla archivos / checklist ✓-✗ / payload final / build / pendientes);
- «BORRAR este archivo de PROMPT al finalizar; el SPEC se conserva» — reportando su borrado.

### 4. Colocar los entregables
- Los repos en /opt/repos/* están montados read-only intencionalmente en este entorno.
- Escribir SPEC + PROMPT en `/opt/data/entregables/<repo>/docs/...` (replicando la estructura del repo) y enviarlos como MEDIA:path al usuario, indicando que el PROMPT es para pegar/copiar al editor y que el editor debe moverlo al repo si hace falta.

## Pitfalls
- No dejar filas vacías con «...»: todo contenido real o «—».
- Typos en textos legales/web: verificar dominios/nombres (p. ej. `goldengame.com.co`, nunca variantes inventadas).
- No incluir secretos/API keys en SPEC/PROMPT.
- Un prompt gigante no se pega bien: delimitado por marcadores INICIO/FIN.
- Tras pruebas reales: si el editor rechazó un paso, corregir el PROMPT y regenerar entregables.

## Verificación
- El checklist del SPEC tiene items verificables y el PROMPT obliga a marcarlos con evidencia.
- `npm run build` debe ser criterio de aceptación.

## Referencias
- `references/golden-game-consent-checkboxes.md` — ejemplo completo: 4 casillas de consentimiento (no premarcadas), mapa archivo/línea, payload, SQL, checklist y estructura de SPEC/PROMPT entregados a AGY.

<!-- absorbido de software-development/service-agent-code-handoff (censo 2026-09-24) -->
# Service-Agent Code Handoff (SPEC + PROMPT → AGY/OpenCode)


Patrón para externalizar a un editor de código (AGY, OpenCode, Claude Code) la implementación de features
en repos de clientes *sin* que el orchestrator escriba en el repo. Verificado en Golden Game (ruleta) y
The Grand Paradise Club (tragamoneda) — ambos con casillas de consentimiento legal y páginas legales nuevas.

## Resultado (siempre dos entregables)

1. **`SPEC-<ASUNTO>-<CLIENTE>-<FECHA>.md`** — PERMANENTE, queda en `docs/` del repo como auditoría:
   mapa de archivos/estado, textos exactos, payload/API, SQL, checklist de aceptación ✓/✗.
2. **`PROMPT-<ASUNTO>-<FECHA>.md`** — TEMPORAL y autocontenido para pegar entero al editor. El PROMPT exige
   entregar un INFORME FINAL y **borrarse a sí mismo al terminar** (el SPEC se conserva).

## Plantillas

`templates/prompt-handoff.md` — ejemplo de PROMPT autocontenido (4 casillas de consentimiento) para copiar/modificar.
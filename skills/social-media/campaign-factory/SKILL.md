---
name: campaign-factory
description: "Trigger: campaign planning, campaign contract, campaign validation, campaign handoff. Guide safe local campaign work using repository evidence and read-only projections."
license: Apache-2.0
metadata:
  author: "NeuralCrew Labs"
  version: "1.0"
---

# Campaign Factory

## Activation Contract

Use for campaign planning, contract review, local validation, or campaign handoff in this checkout. Read the [portable onboarding guide](../../../docs/agents/README.md) and preserve the selected checkout and campaign path. This skill is repository content, not proof that a runtime registered or loaded it.

## Campaign Folder Contract (canonizado 2026-10-22, commit 67173e1)

Toda campaña nueva usa UNA sola estructura, espejada repo ⇄ Drive. Contrato y
scaffold viven en el repo (`docs/marketing-factory/CAMPAIGN_FOLDER_CONTRACT.md`
y `scripts/campaign_scaffold.py`); leerlos antes de crear cualquier archivo.

- Identificador `YYYY-MM-slug`, idéntico en repo (`planning/<id>/`) y Drive
  (`<carpeta cliente>/<id>/`). El scaffold valida el formato y rechaza
  variantes libres (ej. `10-Octubre-halloween-Lucky` → exit 2).
- Árbol: `00-contrato`, `01-docs/{borradores,finales}`, `02-guiones`,
  `03-piezas/{afiches,banners-tv,carruseles,pendones,posts,reels,stories,volantes,perifoneo,voces}`,
  `04-aprobadas`, `05-metricas`, `_fuentes`.
- Documentos aprobados SOLO en `01-docs/finales` con nombre
  `NN-tipo_vX.Y_YYYY-MM-DD.ext`; una versión aprobada nunca se sobrescribe.
- Nada suelto en la raíz; sin carpetas duplicadas ni artefactos de sync
  (antipatrón real: dos carpetas competidoras con los mismos archivos).
- Aprovisionar con `campaign_scaffold.py --campaign <id> --brands ...` —
  idempotente, no destructivo, `--dry-run` primero. `--create-drive` es
  escritura externa y exige autorización explícita.
- Campañas legacy (`2026-10-halloween`, sep, ago) NO migrar sin orden propia;
  está documentado como deuda.
- Verificar el espejo comparando el set de rutas relativas repo vs Drive
  (sobrantes/faltantes), no a ojo: un reintento de subida duplica archivos y
  el conteo exacto por carpeta es la evidencia.

## Hard Rules

- Treat source records and the applicable `planning/<campaign>/campaign.yaml` as campaign facts; never promote stale memory or proposals to current truth.
- Tras cada reunión del Admin, los docs de planning quedan como BORRADORES: las Notas de Gemini (Drive) son la evidencia de las decisiones. Reconciliar con clasificación literal/derivada/contradicha antes de producir piezas — ver `references/reunion-vs-expediente-auditoria.md` (incluye receta verificada Drive API + Pitfalls).
- No provider calls, paid work, rendering, publication, deployment, real-data migration, or runtime/profile changes without explicit authorization and applicable gates.
- Roles are handoff labels only. They do not spawn agents or grant legal, commercial, spend, or publication approval.
- Keep secrets and unnecessary personal data out of repository files and agent memory.

## Decision Gates

| Need | Action |
| --- | --- |
| Local contract evidence | Run the offline validation and plan commands in the guide with an explicit synthetic fixture or authorized campaign path. |
| Missing source, approval, or stage | Stop affected work and report the gap to its owner. |
| External research or creative execution | Treat as externally gated; do not imply it is part of local validation. |

## Execution Steps

1. Read `AGENTS.md`, the guide, and the applicable campaign records.
2. State checkout, campaign path, stage, knowns, unknowns, allowed capabilities, and blocked side effects.
3. Run only authorized local read-only checks; record exact commands and observed outcomes.
4. Hand off changed paths, evidence, blockers, and next owner without claiming approval or readiness.

## Output Contract

Return the campaign path, source-backed facts, assumptions and blockers, capability labels, commands/results, and next owner. Separate observed local compiler/validator behavior from proposed/not-wired and external/gated capabilities. Never claim end-to-end art-generation readiness from a plan projection.

## References

- [Portable onboarding and memory index](../../../docs/agents/README.md)
- [Campaign document contract](../../../docs/marketing-factory/CAMPAIGN_DOCUMENT_CONTRACT.md)
- [Story-ad methodology](../story-ad-methodology/SKILL.md) — external research workflow, not an offline pilot step.
- [Rollout mensual del calendario](references/calendario-mensual-rollout.md) — procedimiento verificado (sep→oct 2026) para replicar la maquinaria del publicador a un mes nuevo: repoint, wrappers, IDs Drive, E2E, ownership git.
- [Portal /campanas/](references/portal-campanas.md) — cadena calendario.jsonl→portal_sync→rsync aditivo, scope real (redes, no entregables), slug fantasma y diagnóstico en vivo.
- [Producción visual con fal](references/produccion-visual-fal.md) — proveedor de imagen estática (video sigue de-authorized), kit de referencias como collage único, arte a ~1,5 MP nunca al tamaño de impresión, gate de gasto con cap explícito y desbloqueo escalonado del board.

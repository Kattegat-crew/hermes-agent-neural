# Piezas dual-location + manifest de handoff (26/08/2026, campaña real Bingo Millonario)

## PITFALL crítico: `piezas` vive en DOS ubicaciones

La demo del template usa `campaign.piezas` (anidado bajo `campaign:`).
**Los campaign.yaml reales generados por Ragnar pegan `piezas:` a nivel RAÍZ**
del archivo (junto a `campaign`, `company`, `events`, `graphics`), NO dentro de
`campaign:`. Síntoma vivido: la fábrica reportó "piezas: 0" para los 2 yamls del
Bingo Millonario que tenían 9 piezas cada uno — no era la campaña rota, era el
generador leyendo solo `campaign.get("piezas")`.

RESOLUCIÓN (ya aplicada en `template/generate_docs.py` y `build_campaign.py`):
- Helper `_piezas(data, campaign)` → acepta `data["piezas"]` (raíz) O
  `campaign["piezas"]`, en ese orden.
- Helper `_join_plat(p)` → normaliza `plataforma` cuando es lista
  (`[instagram, facebook]` → `"instagram, facebook"`) para tablas/calendario.

Regla: NUNCA asumas una sola ubicación. Antes de reportar "0 piezas" o
"contrato vacío", valida con `data.get("piezas") or campaign.get("piezas")`.
Un QA que ve 0 piezas cuando el YAML tiene 9 es bug del generador.

## Manifest de handoff (Fase E) — `scripts/manifest-estado.py`

El handoff entre bots del pipeline se apoya en un `estado.json` por campaña.
Script en el skill: `scripts/manifest-estado.py` (también en el workspace
`roshi/scripts/manifest-estado.py`).

```bash
python3 scripts/manifest-estado.py <campaign.yaml> --output <campaña>/docs/
```

Salida: `estado.json` con `campaña`, `version_contrato`, `total_piezas` y una
fila por pieza: `{id, tipo, etapa, estado, hook, cta, evidencia, aprobada_en,
publicada_en, updated_at}`.

Etapas del pipeline: `contrato → bragi → sindri → review → freyja → publicada`.
- Bragi escribe hooks/CTAs en el campaign.yaml y el manifest los refleja.
- Review aprueba por pieza (`estado: draft → listo → aprobada`, registra versión).
- Social/Ads solo tocan piezas con `estado: aprobada`.

Smoke verificado 26/08: ambas campañas (Golden + Lucky) generaron manifest con
9 piezas en etapa `contrato`/`draft` y versión v1.0.

## Los warnings del QA no son bugs — son el handoff

En la campaña real el QA salió `REVISAR` con un issue legal
(`LEGAL: Umbral de retención → [PENDIENTE]`, dato Coljuegos que nadie completó)
y warnings de "piezas sin hook/ángulo" y "sin CTA" (las 9 piezas). Eso es el
gate funcionando: los **issues** son input humano que falta en el YAML (jamás
inventar) y los **warnings** marcan exactamente qué produce el siguiente bot
(Bragi escribe hooks/CTAs). Distinguir ambos = no romper el flujo por algo que
no es un bug.

## Lección de proceso

Al recibir campaign.yaml de otro rol (Ragnar/Brief), NO confiar en el resumen
verbal de "9 piezas": validar el YAML con yaml.safe_load y contar
`data.get("piezas") or campaign.get("piezas")` ANTES de correr la fábrica. La
validación rápida de 2 minutos ahorra un ciclo completo de diagnóstico.
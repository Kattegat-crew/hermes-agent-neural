---
name: vendor-skill-corpus-upgrade
description: "Audit & upgrade vendored skill corpora vs upstream (sha256)"
version: 1.0.0
author: Ragnar
triggers:
  - "¿tenemos X? / ¿qué versión tenemos de X? / ¿está actualizado?"
  - drift de skills vendorizadas / comparar con upstream / actualizar corpus
  - gentle-ai / sdd-verify difiere / brew upgrade de tool con skills
---

# Auditoría y actualización de corpus de skills vendorizados

Para tools de terceros que COPIAN skills al catálogo local (gentle-ai, OpenSpec, etc.), la pregunta "¿lo tenemos y en qué versión?" NUNCA se responde leyendo los archivos locales: hay que triangular **3 capas**.

## Método (validado 16-sep-2026 con gentle-ai)

**Capa 1 — Binario/estado local (host):** `binary --version`; ruta real vía symlink (brew: `Cellar/<tool>/<versión>`); `stat` de mtimes de config/state para fechar la instalación y el último uso.

**Capa 2 — Procedencia por hash:** comparar cada skill local contra upstream **por sha256**, no a ojo:
```bash
curl -s -A "Mozilla/5.0 Chrome/126.0" -o up.md \
  https://raw.githubusercontent.com/<org>/<repo>/<tag>/<ruta>/SKILL.md
sha256sum local up.md
```
- Enumerar releases estables vía API (`/releases?per_page=100`, excluir `-rc.`); `releases/latest` da el vigente.
- Si una skill local difiere del tag N pero coincide en estructura interna con una versión posterior, puede ser backport o aplanado — leer el diff antes de etiquetar "outdated".

**Capa 3 — Uso real:** `grep -rl <binario>` en scripts/crons/agent-configs. Un binario sin invocaciones activas baja la urgencia del upgrade (afecta skills consumidas, no producción).

## Reporte de estado (plantilla)
Separar SIEMPRE: binario (versión+fecha) / corpus consumido (idéntico vs difiere, con diff) / config+último uso / releases de atraso / breaking changes del salto.

## Caso de referencia: gentle-ai (DEV)
- Local **2.3.0** (brew, 8-ago-2026) vs upstream **v3.0.1** (16-sep-2026): 11 releases estables de atraso.
- 24 skills copiadas al catálogo: byte-idénticas a v2.3.0 salvo `sdd-verify`/`sdd-apply` (aplanadas: sin secciones duales `model-capable`/`model-small` del frontmatter por-modelo).
- v3.0.0 es BREAKING: retira ~108 paths, saca SDD del camino obligatorio (queda rama opcional), ODD como protocolo default → el upgrade es **re-sync del corpus de skills**, no solo `brew upgrade` del binario.
- Uso local: cero invocaciones en crons/scripts; consume solo el corpus; config para agentes de código del host (opencode managed, plugin engram).

## Pitfalls
- `brew list --versions` puede no listar fórmulas de taps viejos: la versión fiable es la ruta del Cellar vía symlink en `/usr/local/bin`.
- `grep -c` con pipe a `head` dispara BrokenPipeError en Python (falso FAIL): correr sin pipe o con `wc -l`.
- Skills vendorizadas heredan el ownership del curador: si son user-owned (created_by=None), ni el Admin del corpus ni este agente pueden patchearlas localmente — documentar el drift y actualizar vía re-sync del vendor, no a mano.

# Caso real: ambigüedad de nombres de skill (11/09/2026, DEV)

## Síntoma

Dos cron jobs corrieron el 07/09/2026 **sin sus skills**. El artefacto del job lo dice, pero el
job termina `ok` y el `failure_streak` queda en 0 — o sea: invisible para una auditoría que solo
mire `last_status`.

Cita textual del artefacto (`cron/output/ccda53a01d06/2026-09-07_08-04-12.md`):

> `[IMPORTANT: The following skill(s) were listed for this job but could not be found and were skipped: competitor-news-monitor, grounded-citations. Start your response with a brief notice...]`
>
> `## ⚠️ Skills no encontradas y omitidas: competitor-news-monitor, grounded-citations — procedí con búsqueda web directa y verificación de cada fuente.`

## Causa raíz probada

El mismo nombre existía **dos veces** en disco (copia suelta en la raíz + copia categorizada), así
que el loader recolectó 2 candidatos y se negó a adivinar. Evidencia en
`/opt/data/logs/errors.log.1`:

```
2026-09-06 21:29:54 WARNING tools.skills_tool: Skill name collision for 'grounded-citations': 2 candidates — /opt/data/skills/grounded-citations/SKILL.md; /opt/data/skills/research/grounded-citations/SKILL.md
2026-09-04 12:28:09 WARNING tools.skills_tool: Skill name collision for 'hermes-agent': 2 candidates — /opt/data/skills/hermes-agent/SKILL.md; /opt/data/skills/autonomous-ai-agents/hermes-agent/SKILL.md
```

Reproducción en vivo (mismo entorno del gateway, `HERMES_HOME=/opt/data`): `hermes-agent` →
`success=False` + `Ambiguous skill name`; `autonomous-ai-agents/hermes-agent` → `success=True`.

## Escala del problema (no era un caso suelto)

- `73` nombres duplicados en `/opt/data/skills` (raíz vs categoría) y `79` en `/opt/data/home/.hermes/skills`.
- `12` nombres con colisión **registrada en uso real** en los logs: `hermes-agent` (6 eventos,
  último 09-sep), `grounded-citations` (4), `competitor-news-monitor` (4), `google-workspace` (3),
  `github-repo-management` (2), y uno cada uno: `himalaya`, `plan`, `humanizer`, `session-librarian`,
  `popular-web-designs`, `systematic-debugging`, `blocked-page-recovery`.
- Jobs afectados el 07-sep: `competitor-news-digest` (`ccda53a01d06`, lun 8am) y
  `hermes-setup-autoaudit` (`493341e69813`, lun 7am).
- El curator **no** fue quien limpió las copias antiguas: sus reportes dicen `archived 0`,
  `consolidados 0`, `cron_jobs_rewritten 0`.

## Arreglo aplicado (solo jobs, no catálogo)

Se cambiaron las declaraciones a la ruta categorizada, cada una verificada `success=True`:

| Job | Antes | Después |
|---|---|---|
| `hermes-setup-autoaudit` | `hermes-agent` | `autonomous-ai-agents/hermes-agent` |
| `competitor-news-digest` | `competitor-news-monitor`, `grounded-citations` | `research/competitor-news-monitor`, `research/grounded-citations` |

Limpieza del catálogo (archivar las 73 copias sueltas) queda **pendiente de OK del Admin**: es
una pasada del curator con inventario antes/después, no una edición a mano.

## Lecciones

- Auditar un cron por `last_status` **no** detecta esto: hay que abrir el artefacto o mirar
  `Skill name collision` en los logs.
- La ruta categorizada es el arreglo barato y reversible; el catálogo limpio es el arreglo de fondo.
- Cualquier reubicación de una skill puede volver a romper un job que la pinea: verificar después.

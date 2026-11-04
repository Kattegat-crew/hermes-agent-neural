# Mapeo Respuesta → SOUL → Skills (v3 con personalidad)

Para cada bloque del cuestionario, las respuestas alimentan secciones del SOUL.md
y habilitan skills concretas en el perfil del agente.

## Tabla de mapeo

| Bloque | Alimenta en SOUL.md | Skills sugeridas |
|---|---|---|
| 0 · Personalidad | `identidad: nombre/tratamiento`, `voz: tono, ritmo, emojis`, `prohibiciones` | `humanizer`, `grounded-citations`, `decision-autonomy` |
| 1 · Documentos | `documentos: tipos, almacenamiento, capacidades` | `document-reader`, `pdf`, `xlsx`, `docx`, `google-drive-access` |
| 2 · Integraciones | `integraciones: disponibles, deseadas` | `notion`, `google-workspace`, `maps`, `whatsapp-bridge-operations` |
| 3 · Automatizaciones | `automatizaciones: cron, batch, aprobaciones` | `cron-watchdog-scripts`, `persistent-task-manager`, `xlsx` |
| 4 · Acceso | `acceso: nivel, notificaciones, usuarios` | `security-privacy`, `whatsapp-bridge-operations`, `discord-reporter` |
| 5 · Contexto | `voz`, `marca`, `ejemplos`, `reporte de errores` | `document-to-action-items`, `grounded-citations`, `humanizer` |

## Reglas para la recomendación de skills

1. **Solo sugerir skills que existen** en el catálogo del perfil (o instalables
   vía `skills install`). Ver `skill_view`/`skills_list` antes de recomendar.
2. Si el bloque indica integración → ofrecer la skill correspondiente con su
   setup (ej. `google-drive-access` si usa Drive).
3. Si el cliente pide automatizaciones → recomendar `cron-watchdog-scripts` +
   tool `cronjob` (explicar cadencia según Q12).
4. Si el nivel de acceso es "consultar por acceso" (Q16-C) → reforzar
   `decision-autonomy` y las normas de aprobación (Q13) dentro del SOUL.
5. Siempre al final: "¿Quieres que habilite estas skills en tu agente?" → se
   instalan con `hermes skills install <nombre>` (o `skill_manage`) y se
   agregan al config del perfil.

## Ejemplo de salida final (post-validación)

> ✅ SOUL.md actualizado.
> Skills recomendadas (10):
> - document-reader (documentos)
> - xlsx (reportes)
> - cron-watchdog-scripts (automatización)
> - humanizer (voz)
> ¿Habilito estas skills en tu perfil? (sí/no)
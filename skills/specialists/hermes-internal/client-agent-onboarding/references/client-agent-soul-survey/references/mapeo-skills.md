# Mapeo Respuesta → SOUL → Skills (v3 con personalidad)

Por bloque, las respuestas alimentan secciones del SOUL.md y habilitan skills concretas.

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

1. Solo sugerir skills que EXISTAN (ver `skills_list`/`skill_view` antes de nombrar).
2. Si el bloque indica integración → ofrecer la skill con su setup (ej. `google-drive-access` si usa Drive).
3. Si el cliente pide automatizaciones → `cron-watchdog-scripts` + tool `cronjob` (cadencia según Q12).
4. Si el acceso es "consultar por acceso" (Q16-C) → reforzar `decision-autonomy` y normas de aprobación (Q13) en el SOUL.
5. Cerrar con "¿Quieres que habilite estas skills en tu agente?" → instalar con
   `hermes skills install <nombre>` y agregar al config del perfil.

## Formato de validación final (mostrar al dueño antes de escribir SOUL.md)

```
☑️ Esto es lo que entendí de ti:
- Te llamo: <como pida>
- Tono: <cercano/directo/formal>, emojis <sí/no>
- Documentos: <PDF extracción + Excel plantillas>
- Integraciones: <Google Drive + Notion>
- Automatizaciones: <reportes diarios + recordatorios>
- Acceso: <total, sin masivos sin tu OK>
- Notificaciones: <Tú + un reporte semanal>
¿Confirmas para generar tu SOUL.md? (sí/corregir)
```

## Ejemplo de salida final (post-confirmación)

> ✅ SOUL.md actualizado.
> Skills recomendadas (10):
> - document-reader · xlsx · cron-watchdog-scripts · humanizer ...
> ¿Habilito estas skills en tu perfil? (sí/no)
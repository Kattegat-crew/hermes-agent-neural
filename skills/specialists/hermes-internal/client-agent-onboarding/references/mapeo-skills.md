# Mapeo Respuesta → SOUL → Skills (v3 con personalidad)

| Bloque | Alimenta en SOUL.md | Skills sugeridas |
|---|---|---|
| 0 · Personalidad | identidad (nombre/tratamiento), voz (tono, ritmo, emojis), prohibiciones | humanizer, grounded-citations, decision-autonomy |
| 1 · Documentos | documentos: tipos, almacenamiento, capacidades | document-reader, pdf, xlsx, docx, google-drive-access |
| 2 · Integraciones | integraciones: disponibles, deseadas | notion, google-workspace, whatsapp-bridge-operations |
| 3 · Automatizaciones | automatizaciones: cron, batch, aprobaciones | cron-watchdog-scripts, persistent-task-manager, xlsx |
| 4 · Acceso | acceso: nivel, notificaciones, usuarios | security-privacy, whatsapp-bridge-operations |
| 5 · Cierre | voz, marca, ejemplos, reporte de errores | document-to-action-items, humanizer |

Reglas:
1. Solo sugerir skills que existen en el catálogo del perfil (ver skills_list antes).
2. Integración indicada → ofrecer la skill con su setup (p.ej. google-drive-access si usa Drive).
3. Automatización → cron-watchdog + tool cronjob, cadencia según Q12.
4. Acceso "consultar por acceso" (Q16-C) → reforzar decision-autonomy y aprobaciones (Q13).
5. Siempre cerrar: "¿Habilito estas skills en tu agente?" → instalar y agregar al config del perfil.
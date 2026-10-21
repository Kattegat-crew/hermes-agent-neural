---
name: discord-reporter
description: >-
  Use when sending a report or notice to Discord on request. Send status reports, summaries, and notifications to Discord channels. Use when the user wants to send a report, update, or message to a Discord channel or specific user. Triggered on demand — not automatic. hermes: tags: [discord, messaging, reporting, notifications]
tags: [discord, reportes, notificaciones, mensajeria]
version: 1.0.0
author: Ragnar
license: MIT
metadata: {}
---

# Discord Reporter

Enviar reportes, resúmenes y notificaciones a Discord. Se activa **a pedido**, no automáticamente.

## Cuándo Usar

- **A PEDIDO** del usuario → "manda un reporte a Discord"
- **A PEDIDO** → "avisa al equipo en Discord"
- **NUNCA** automáticamente sin que el usuario lo pida explícitamente

## Configuración

Discord ya está conectado. Usar send_message para enviar.

### Enviar a Canal

```python
send_message(
    action='send',
    target='discord:#channel-name',  # o 'discord:1493354289266167808'
    message='Texto del reporte'
)
```

### Enviar a Usuario Directo

```python
send_message(
    action='send',
    target='discord:713538631918157853',  # Jonathan (Dominus)
    message='Mensaje directo'
)
```

### Targets Disponibles

- `discord` → Home channel (1493354289773674760)
- `discord:1493354289266167808` → Server general
- `discord:713538631918157853` → Jonathan (DM)
- `discord:742803595241717840` → Chucho (DM)

## Formato de Reportes

```markdown
## 📊 Reporte — [Título]

**Fecha:** YYYY-MM-DD HH:MM
**De:** Ragnar

[Contenido del reporte]

### Detalles
- Punto 1
- Punto 2
- Punto 3

---
*Enviado por Ragnar — Nexa Labs Orchestrator*
```

## Ejemplos

### Reporte de Estado
```
## 📊 Estado del Sistema

**Fecha:** 2026-04-28 22:46
**De:** Ragnar

✅ Context monitoring activo
✅ Brain Wiki actualizado
✅ Skills instalados: 14
⏳ Obscura: pendiente integración
⏳ Telegram processing: pendiente

Próximas tareas:
1. Configurar Obscura como browser
2. Procesar tweets pendientes
3. [siguiente tarea]
```

### Notificación de Tarea Completada
```
## ✅ Tarea Completada: [Nombre]

**De:** Ragnar

Se completó: [descripción]

Detalles: [qué se hizo]
```

## Reglas

1. **Solo a pedido** — nunca enviar a Discord sin que el usuario lo pida
2. **Formato limpio** — usar markdown, headers, emojis
3. **Conciso** — reports cortos y directos
4. **Sin spam** — un reporte por evento, no múltiples mensajes

## Pitfalls

- **NO** enviar automáticamente sin que el usuario lo pida
- **NO** enviar múltiples mensajes para el mismo reporte
- **NO** usar Discord para cosas que pueden ir por Telegram
- **SI** el usuario pide un reporte, incluir: fecha, estado, próximos pasos

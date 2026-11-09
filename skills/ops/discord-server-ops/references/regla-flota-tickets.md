# Regla de flota: tickets del foro técnico (bloque instalado en AGENTS.md)

Este bloque vive en `/opt/data/AGENTS.md` (mismo inodo que `/opt/hermes-agent-data/AGENTS.md`) y
aplica a Ragnar y a **todos** los perfiles de la flota. Si un rebuild del contenedor regenera ese
archivo y el bloque no está, reinyectarlo tal cual (idempotente: comprobar con `grep -c "vía única obligatoria"`).

## Bloque

```markdown
## Tickets técnicos (foro 🛠️ tickets-tecnicos) — vía única obligatoria
Aplica a Ragnar y a CUALQUIER agente de la flota que abra un ticket en el foro `1554957746980261938`.
- **Prohibido crear tickets a mano** (curl/urllib/POST improvisado). Vía única: `python3 /opt/hermes-agent/skills/ops/discord-server-ops/scripts/crear_ticket.py --titulo ... --responsable <id_numerico> --tipo <Mantenimiento|Implementacion|Incidente> --estado <estado> [--entorno DEV|PROD] --cuerpo <archivo.md> [--dry-run]`.
- El script impone los gates del topic del foro: **tag de tipo + tag de estado + tag del responsable** coherente con la mención `<@id>` real, cuerpo ≤ 2000 chars y secciones `Objetivo` / `Criterios de aceptación` / `Fuera de alcance` obligatorias.
- Post-creación obligatoria: releer el hilo (`GET /channels/{thread}`) y confirmar `name`, `applied_tags` y `mentions` ANTES de reportar el enlace. Un POST 201 no prueba que el ticket quedó bien armado.
- Si el foro cambia de etiquetas, se actualizan en el script; nunca se salta la vía única "porque esta vez es rápido".
```

## Verificación de que quedó instalado

```bash
grep -c "vía única obligatoria" /opt/data/AGENTS.md   # debe devolver 1
python3 /opt/hermes-agent/skills/ops/discord-server-ops/scripts/crear_ticket.py --help | head -3
```

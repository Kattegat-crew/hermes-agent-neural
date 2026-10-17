---
name: multi-agent-collaboration
description: >-
  Coordinación, handoffs y trabajo paralelo entre agentes de la flota. Uso de git worktrees para aislar cambios, canales compartidos anti-bucle y protocolos de traspaso verificado.
tags: [multi-agente, handoff, worktrees, orquestacion, discord, roshi, ragnar, colaboracion]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Colaboración y Orquestación Multi-Agente

Habilidad canónica para coordinar el trabajo paralelo entre los agentes de la flota Hermes (Roshi, Vigía, Bragi, Sindri, Brokkr, etc.), gestionar handoffs con evidencia verificable, aislar tareas mediante Git worktrees y evitar bucles infinitos en canales compartidos de Discord.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"pásale esto a Sindri"*, *"coordina con Bragi el guion"*, *"trabajen en paralelo en el mismo repo"*, *"dos agentes están en un bucle en Discord"*, o *"haz un handoff verificado"*.
- Dos o más agentes deben editar el mismo repositorio sin pisar sus ramas ni bloquear el working tree.
- Configuración de canales de Discord donde conviven múltiples bots sin que se disparen respuestas infinitas en eco.
- Finalización de una etapa y traspaso de responsabilidades con entrega de evidencias (logs, commits, diffs).

---

## 1. Aislamiento por Git Worktrees (Trabajo en Paralelo)

**Regla de Oro**: Múltiples agentes NUNCA editan sobre el mismo working directory de Git simultáneamente. Cada tarea o agente recibe su propio `worktree`:

```bash
# 1. Crear un worktree aislado para la tarea
git worktree add -b feat/tarea-agente /opt/data/worktrees/tarea-agente main

# 2. El agente opera exclusivamente dentro de su directorio asignado
cd /opt/data/worktrees/tarea-agente

# 3. Al terminar y fusionar, limpiar el worktree
git worktree remove /opt/data/worktrees/tarea-agente
git worktree prune
```

---

## 2. Protocolo de Handoff Verificado (Traspaso entre Pares)

Un handoff NUNCA se hace diciendo únicamente *"te toca"*. Debe contener evidencia demostrable:

### Estructura Obligatoria del Mensaje de Handoff:
1. **Objetivo Completado**: Qué se hizo y por qué.
2. **Evidencia Técnica**: Commit SHA, diff de cambios, pruebas ejecutadas y rutas de archivos creados.
3. **Estado Actual**: Qué funciona y qué quedó pendiente.
4. **Instrucción Exacta para el Siguiente Agente**: Siguiente acción requerida sin ambigüedades.

```markdown
<!-- Ejemplo de Handoff de Bragi hacia Sindri -->
**Handoff de Guion a Producción de Video**
- **Pieza**: Reel Promocional Halloween (Casino Golden).
- **Evidencia**: Guion aprobado en `/opt/data/campaigns/golden/guion_v2.md` (auditado con `copy-quality-es`).
- **Assets**: Locución generada con ElevenLabs en `/opt/data/audio/golden_halloween_voice.mp3`.
- **Siguiente Acción (@sindri)**: Ensamblar clip en el pipeline de video y renderizar borrador a 1080x1920.
```

---

## 3. Prevención de Bucles en Canales Compartidos de Discord

En canales donde conviven varios agentes (ej. `#video-prod`, `#operaciones`):

1. **Anti-Ping-Pong**: Un agente solo responde si:
   - Es mencionado explícitamente (`@agente`).
   - El mensaje anterior proviene de un humano.
   - El mensaje proviene de otro agente pero incluye una solicitud directa con su nombre.
2. **Prohibición de Agradecimientos Vacíos**: Queda terminantemente prohibido que dos agentes intercambien mensajes de cortesía (*"Gracias", "De nada", "Quedo atento"*) que mantengan el canal activo sin generar trabajo real.
3. **Límite de Turnos Autónomos**: Si dos agentes intercambian más de 3 mensajes consecutivos sin intervención humana, el agente orquestador debe detenerse y solicitar confirmación al usuario.

---

## Gotchas y Errores Críticos

1. **Permisos en `.git/objects`**: Si un worktree es creado por `root`, otro agente corriendo con `uid 10000` fallará con `insufficient permission for adding an object`. Siempre verificar pertenencia de usuario con `chown -R hermes:hermes .git/`.
2. **Worktrees bloqueados**: Si un proceso termina abruptamente, el lock de Git puede quedar huérfano. Desbloquear con `git worktree unlock <ruta>` o `git worktree prune`.

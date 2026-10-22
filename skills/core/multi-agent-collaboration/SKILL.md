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

### 2.b Buzón inter-agente asíncrono (`agent_exchange`, PROD)

Para encargos/tareas formales a otro agente de la flota (ej. Ragnar→Bob) o escalaciones asíncronas, el canal canónico es el buzón de archivos, no un mensaje de chat:

- **Rutas**: enviar a `/opt/data/inbox/<agente>/pending/ticket-*.json`; el watcher del destino lo reclama en ≤5 min (pasa a `processing/` y cierra en `done/` con `respuesta` y `evidencia`). Los entrantes de otros agentes caen en `/opt/data/inbox/<yo>/from-<remitente>/`.
- **Schema del ticket** (JSON válido obligatorio): `id` (convención `ticket-YYYYMMDD-<agente>-NNN`, secuencia según `done/`), `de`, `asunto`, `tarea` (texto completo del encargo/informe), `archivos: []`, `intentos_fallidos: []`, `canal_entrega`, `prioridad`, `creado_en` (ISO UTC).
- **`canal_entrega`**: prefijos válidos según `agent_exchange.py` → `VALID_DELIVERY_PREFIXES = ("/opt/data/", "whatsapp:", "bot-chat:", "telegram:")`. Para que el resultado le llegue al agente destino en su propio chat usar `bot-chat:<perfil>`; cualquier otro valor es rechazado por el watcher.
- **Verificación de la entrega**: escribir el JSON localmente, validarlo con `json.load`, `scp` al `pending/`, y verificar leyéndolo de vuelta en PROD. Alinear dueño con la convención del buzón (`chown 10000:10000`) — los tickets previos lo usan.
- **Pitfall — buzón entrante pasivo**: NO existe cron que notifique archivos nuevos en `from-<agente>/`; solo se descubren consultando la carpeta (u ofreciendo al usuario un watcher que avise por `bot-chat:<yo>`). Nunca asumir que "no llegó nada" sin listar el directorio.

---

### 2.c Ticket Kanban como canal de handoff durable

Para trabajo que cruza agentes y debe sobrevivir reinicios, requerir decision humana o dejar auditoria: **la tarjeta Kanban** (`kanban_create`), no el chat ni el buzon. Detalle, latencias medidas y pitfalls en `references/kanban-ticket-handoff.md`.

Reglas nucleo:
- `assignee` debe ser un perfil real (`ls /opt/hermes-agent-data/profiles/`); si no existe, el spawn falla y se auto-bloquea por `failure_limit`.
- El hijo hereda `summary` + `metadata` del padre verbatim: el padre cierra con rutas absolutas, hashes, tests y costos.
- Cerrar siempre con `kanban_complete(...)` o `kanban_block(kind=..., reason=...)`; salir sin eso es `protocol_violation`.
- Latencia DEV medida: creada -> reclamada 38 s; padre `done` -> hijo arranca 28 s. El cuello de botella no es el transporte, es coordinar por reloj (crons) o por chat (humano de rele).
- **Regla de Ragnar**: orquesta, pero ejecuta directo cuando es verificacion independiente, trabajo sin dueno en la flota, urgencia de infraestructura, peticion explicita del Admin, o cuando delegar cuesta mas que hacerlo.
- Limite duro: cada worker es un proceso OS completo con su modelo y MCP -> 2-3 concurrentes realistas en DEV (4 cores / 7.9 GB), aunque `derive_default_max_in_progress()` devuelva 8.

---

## 3. Prevencion de Bucles en Canales Compartidos de Discord

En canales donde conviven varios agentes (ej. `#video-prod`, `#operaciones`):

1. **Anti-Ping-Pong**: Un agente solo responde si:
   - Es mencionado explícitamente (`@agente`).
   - El mensaje anterior proviene de un humano.
   - El mensaje proviene de otro agente pero incluye una solicitud directa con su nombre.
2. **Prohibición de Agradecimientos Vacíos**: Queda terminantemente prohibido que dos agentes intercambien mensajes de cortesía (*"Gracias", "De nada", "Quedo atento"*) que mantengan el canal activo sin generar trabajo real.
3. **Límite de Turnos Autónomos**: Si dos agentes intercambian más de 3 mensajes consecutivos sin intervención humana, el agente orquestador debe detenerse y solicitar confirmación al usuario.

## 4. Jerarquía Planner → Sub-planner → Worker y Despertar de Especialistas (s6)

La coordinación a escala no es plana ni peer-to-peer; se organiza en árbol jerárquico donde cada worker opera sobre su contexto/repo aislado y reporta **únicamente a su asignador**:

| Rol | Agente Principal | Responsabilidad |
|-----|------------------|-----------------|
| **Planner** | Ragnar (default) | Entiende el objetivo de negocio, lo descompone en sub-tareas, rutea y agrega el reporte final. |
| **Sub-planner** | Ragnar o delegación anidada | Cuando un bloque se divide en sub-dominios, gestiona y rutea a sus workers. |
| **Worker** | Especialistas (Bragi=contenido, Sindri=dev/video, Freyja=diseño, etc.) | Ejecuta la tarea concreta y devuelve evidencia verificable a su asignador. |

### Ciclo del Planner (7 Pasos Mandatorios)
1. **Entender el objetivo**: Entregable esperado y criterio de aceptación verificable (no tickets monolíticos).
2. **Descomponer**: Tareas de 2-5 minutos con contexto acotado.
3. **Asignar**: Destino (`dominio`), `parent_task` y `dependencias`.
4. **Contexto autocontenido**: El worker NO ve la conversación del planner; inyectar solo insumos necesarios.
5. **Evidencia observable**: Archivo en disco >0 bytes, commit SHA, ID real o salida de comando. Prohibido reportar "listo" sin prueba técnica.
6. **Reporte agregado en bloque**: UN solo informe al usuario al finalizar la fase, no saturar con mensajes intermedios.
7. **Escalar stuck**: Si tras 2 intentos un método falla, cambiar de enfoque o escalar al planner.

### Ledger de Coordinación y Despertar on-demand
- `delegation_state.json`: Registra padre→hijos (`pending` → `run` → `done` con evidencia | `failed`). Idempotente.
- **Servicios s6 de especialistas**: Los gateways de especialistas corren bajo s6 (`gateway-bragi`, `gateway-sindri`, `gateway-freyja`). Se despiertan on-demand cuando son mencionados en Discord/Desktop o cuando el planner activa su tarea asignada.

---

## Gotchas y Errores Críticos

1. **Permisos en `.git/objects`**: Si un worktree es creado por `root`, otro agente corriendo con `uid 10000` fallará con `insufficient permission for adding an object`. Siempre verificar pertenencia de usuario con `chown -R hermes:hermes .git/`.
2. **Worktrees bloqueados**: Si un proceso termina abruptamente, el lock de Git puede quedar huérfano. Desbloquear con `git worktree unlock <ruta>` o `git worktree prune`.
3. **Reportes sin evidencia**: Ningún worker puede marcar una tarea como completada sin proveer evidencia tangible (ruta de archivo, status code, commit SHA).

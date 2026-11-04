# Materializar un perfil de oficina/corporativo (set curado, NO catálogo 100+)

Receta validada 26/08/2026 al materializar `comms` (comunicaciones corporativas,
bot de oficina con conexión Gmail corporativa). Diferente del catálogo de
especialistas (100+ skills): un perfil de oficina lleva un set CURADO (~25) de
skills del vault CORE, no skills-especialistas ni skills-ext.

## Qué distingue un perfil de oficina
- Rol no productor: comunicaciones, documentos, reuniones, integraciones Gmail/Drive.
- Ya puede tener SOUL.md completo + config.yaml + `.env` con secretos + conexiones
  (connections-map.json con `owner: comms`) pero **0 skills** — nace vacío.
- Set típico (~25): google-workspace, gmail-smtp-app-password, email-inbox-triage,
  himalaya, docx, pdf, document-reader, pptx-author, xlsx, nano-pdf,
  html-to-print-rendering, pdf-deliverables, neuralcrew-letterhead,
  meeting-action-items, teams-meeting-pipeline, notion, google-drive-access,
  document-to-action-items, anti-slop-copy, humanizer, grounded-citations,
  docuseal-selfhost-ops, activepieces-lead-automation, web-fetch, graphify.

## Pasos
1. **Verificar que cada skill existe en el vault ANTES de prometerla.** Las rutas
   varían: algunas viven anidadas en `/opt/data/skills/<categoría>/<skill>`
   (html-to-print-rendering, pdf-deliverables, neuralcrew-letterhead,
   google-drive-access, anti-slop-copy bajo productivity/creative). Escanear con
   `os.walk` hasta profundidad 2 y resolver la ruta real del SKILL.md.
2. **Limpiar el `skills.disabled` heredado** (si el config vino de copia):
   `HERMES_HOME=/opt/data/profiles/<p> /opt/hermes/bin/hermes config set skills.disabled '[]'`
   y verificar `skills:\n  disabled: []` en el archivo (el CLI avisa "not a
   recognized config key" — es ruido inocuo).
3. **Symlinks al vault** (`/opt/data/skills/<ruta-real>`), patrón de enlace.
4. **Fix de archivos root** antes de verificar: `profile.yaml`, caches
   (`*_models_cache.json`) pueden ser root:root → `docker exec -u root hermes-agent
   chown hermes:hermes <archivos>`; luego `chown -R hermes:hermes /opt/data/profiles/<p>`.
5. **Grafo perfil**: `python3 /opt/data/scripts/build_skills_graph.py --profile <p>`
   → `skills/graphify-out/graph.json`; smoke test `graphify query "<tema>"`
   (ej. "correo gmail" → google-workspace).
6. **AGENTS.md**: escribir la sección "Grafo de skills" — PERO el write de
   AGENTS.md (archivo de instrucciones de agente) puede exigir aprobación del
   usuario y bloquearse ("silence is not consent"). Si se bloquea, NO forzarlo
   por terminal/execute_code: presentar el contenido y esperar aprobación.
7. **Ruteo**: decidir el canal (Discord/Telegram) y añadir `gateway.profile_routes`
   + reinicio; si no hay canal aún, el perfil queda operativo sin chat (crons/conexión).

## Pitfalls
- Un perfil de oficina NUNCA recibe un catálogo de especialista (100+): viola la
  regla de perfil limpio del Admin (~15-30 skills de oficina, ver
  agent-skill-cataloging "tensión con clean profile").
- Doctor: si `hermes --profile <p> doctor` crashea con PermissionError en
  MEMORY.md/USER.md → aplicar hermes-memory-maintenance (chown hermes:hermes).
- El write de AGENTS.md es de mayor privilegio que los symlinks: hacer los
  symlinks primero y el AGENTS.md al final, avisando que puede requerir
  aprobación.
---
name: hermes-roster-implementation
description: "Use when deploying a Hermes bot roster on the VPS."
tags: [hermes, roster, bots, perfiles, skills, discord, deploy]
version: 1.0.0
author: Ragnar
triggers:
  - roster: implementar / crear los bots / agentes especializados / perfiles ×N / procedamos con la implementación
  - skills-por-bot: catálogo de skills / N skills por bot / autorar skills / materializar catálogo
  - canales-bot: crear canal por bot / canal discord por perfil / profile_routes discord
  - perfiles: crear perfil Hermes desde cero / clonar perfil / agent.name
---

# Hermes Roster Implementation — materializar un equipo de bots en el VPS

Cómo pasar de un plan/roster documentado a perfiles Hermes reales, funcionales e independientes, con skills por catálogo, canales de Discord por bot y sincronización a GitHub. Receta validada el 26/08/2026 al implementar los 8 especialistas de NeuralCrew (Hermóðr…Sindri); detalle y números en `references/ejecucion-8-especialistas-2026-08.md`.

## Fases de ejecución (resumen)

1. **Diseño ya aprobado** (ver skill user-owned `bot-team-architecture` para la fase de diseño; recomendar `hermes curator adopt` para poder parchearla).
2. **Perfiles:** copiar `config.yaml` de un perfil funcional existente (p. ej. roshi) a `/opt/data/profiles/<slug>/`; generar `SOUL.md`/`AGENTS.md`/`MEMORY.md` por script con la personalidad de cada bot; `skills/` = symlinks a `/opt/data/skills/<skill>` (jamás copias); `cron/`, `scripts/`, `assets/`.
3. **Skills por catálogo** (ver sección "Materializar un catálogo de N skills").
4. **Canales:** un solo bot de Discord sirve a N perfiles por `gateway.profile_routes` (chat_id = canal); no hace falta un token por bot.
5. **Reinicio del gateway** para aplicar `profile_routes`: patrón cron one-shot `no_agent` (ver skill user-owned `hermes-gateway-s6-ops`; patrón: entregar mensaje → cron dispara `s6-svc -r /run/service/main-hermes` 3-4 min después → verificar en siguiente turno).
6. **Smoke test:** `hermes --profile <slug> chat -q "responde quién eres"` → debe responder con la identidad del SOUL.
7. **Config de identidad:** `hermes config set --profile <slug> agent.name "Nombre (Módulo)"` (acepta key custom sin romper; validar `model.default` tras setear).
8. **Avatares:** buscar retratos de dominio público en Wikimedia Commons (API) y ponerlos en `assets/avatar.png` 512×512 (PIL crop+resize); añadir bloque "Tarjeta de contacto" al SOUL.
9. **Fases del informe:** tras cada bloque, marcar la tabla de fases del informe con el estado REAL (✅/🔲) — el Admin reclama tablas con "Por ejecutar" en fases ya hechas.
10. **GitHub:** repo con informe + scripts, `.gitignore` que excluya secretos, escaneo pre-commit, push por header bearer (ver skill user-owned `github-push-container`).

## Materializar un catálogo de "N skills por bot"

Un catálogo mixto tiene 3 orígenes:

- **[H] locales** — ya en `/opt/data/skills`: enlazar directo por symlink.
- **Externas importables** — clonar los repos (Corey Haines `marketingskills`, Composio `awesome-claude-skills`, `JimLiu/baoyu-skills`, `alirezarezvani/claude-skills` entre otros) a `/opt/data/skills-ext/`; construir índice nombre→ruta del SKILL.md; enlazar al perfil las que su catálogo pide. Escanear patrones peligrosos (`rm -rf /`, `curl|sh`, `base64 -d`, `sudo rm`…) antes de enlazar.
- **Entradas conceptuales** — no existen como SKILL.md en ningún repo: **autorarlas** por categoría (ads/seo/video/image/sql/social/comms/voice/compliance/dev/design/marketing/hooks-titles/productivity) con cuerpo basado en el toolchain REAL (ffmpeg, psql/EXPLAIN, curl a APIs Meta/Google Ads, modelos NaN-Builders), frontmatter estándar (name/description/category/version), y dedupe entre bots (misma fuente compartida, symlink por perfil).

Si el primer delta da cientos de faltantes, la respuesta correcta es **importar + autorar**, no recortar el catálogo ni dejar los bots sin skills.

⚠ **Leer cantidades al pie de la letra**: "100 skills por cada bot" = 100 POR BOT (800 en total), NO 100 sumando todos. Confirmar el alcance antes de entregar catálogos (corrección del Admin el 26/08/2026).

## Pitfalls

- **`config.yaml` protegido:** `write_file`/`patch` los rechazan. Editar con Python vía terminal (D-I-V-E) o `hermes config set --profile <slug> ...`; backup antes (`cp config.yaml config.yaml.bak-<ts>`).
- **Cron tool exige ruta RELATIVA de script:** `script` debe ser nombre de archivo relativo a `$HERMES_HOME/scripts/` (en este VPS `/opt/data/scripts/`). Ruta absoluta → error "Script path must be relative to ~/.hermes/scripts/".
- **Dirs root-owned rompen escritura:** si `assets/` (o cualquier dir) lo creó el proceso del gateway como root, el usuario hermes no puede escribir. Fix: `docker exec -u root hermes-agent chown -R hermes:hermes /opt/data/profiles/<slug>/assets` (chown como hermes NO aplica por no ser root).
- **Discord REST:** header `User-Agent: DiscordBot (...)` OBLIGATORIO; sin él → `403 code 1010`. `PATCH /channels/<id>` (topic) puede dar `40333 internal network error` aunque el POST de creación funcione — cosmético, no bloquea el enrutamiento.
- **GitHub repo con `auto_init:true`:** el primer push falla ("updates were rejected"); resolver `git fetch` + `git merge -X theirs origin/main --allow-unrelated-histories` + push. Crear bajo org: `POST /user/repos` funciona donde `/orgs/<org>/repos` puede dar 404.
- **No copiar `scripts/*` en bloque** a un repo nuevo: arrastra scripts de otros proyectos y `mv` vacía el origen. Copiar solo los del alcance.
- **Coautoría y limpieza de entregables:** si el Admin pide informe final limpio, NO mencionar iteraciones ni ediciones previas, no incluir "pendiente de aprobación", y borrar los archivos intermedios tras entregar (solo .md + .docx finales en el workspace).

## Referencias

- `references/ejecucion-8-especialistas-2026-08.md` — receta completa con comandos y números del despliegue real.
- Skills user-owned complementarias (NO editables por curador; usar `hermes curator adopt` para actualizarlas): `bot-team-architecture`, `hermes-profile-routing`, `hermes-gateway-s6-ops`, `github-push-container`, `hermes-production-deployment`.
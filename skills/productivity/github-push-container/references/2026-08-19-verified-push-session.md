# Session de push verificada — 2026-08-19

Receta probada en vivo (todos los comandos salieron OK) para empujar los 3 repos.

## Inventario de repos (estado al 19/08)

| Repo | Presente en | Rama default | Privado | Permisos del token Kattegat-crew |
|------|-------------|--------------|---------|-----------------------------------|
| `Jemadiar1/ai-platform` | `/opt/repos/ai-platform` | `main` | público | push ✓ (no admin) |
| `Kattegat-crew/Golden-Game-Casinos` | `/opt/repos/golden-game-landing` | `main` (local `jemadiar`) | privado | push ✓ (admin) |
| `Kattegat-crew/Hermes-casinos` | `/opt/data/hermes-casinos-repo` (clone de trabajo) | `main` | privado | push ✓ (admin) — token YA tiene push (el 16/08 daba 403) |

- `/opt/data/brain` y `/opt/data/skills` NO eran repos git → la solución fue versionarlos DENTRO de Hermes-casinos.

## Comandos que funcionaron

```bash
# 1) Token (sin persistir en remote)
TOKEN=$(sed -n 's/.*oauth_token: //p' ~/.config/gh/hosts.yml | head -1)
AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64)"

# 2) Permisos
sudo chown -R hermes:hermes /opt/repos/ai-platform /opt/repos/golden-game-landing

# 3) ai-platform (remote HTTPS)
git add infra/docker/docker-compose.prod.yml infra/docker/nginx/nginx.conf.template .gitattributes graphify-out/
git commit -m "chore(infra): actualiza compose prod y template nginx; agrega grafo graphify con merge driver"
git -c http.extraheader="$AUTH" push origin main          # 3892cc2..20437c4

# 4) golden-game-landing (remote SSH → push a URL https explícita)
git add src/components/AiChatWidget.jsx src/pages/Home.jsx src/style.css
git commit -m "feat(chat): pulido widget AiChat, hero y estilos (speech bubble + FAB compacto)"
git -c http.extraheader="$AUTH" push https://github.com/Kattegat-crew/Golden-Game-Casinos.git jemadiar:jemadiar   # 9585e0b..91c66de

# 5) Hermes-casinos (clone en /opt/data/hermes-casinos-repo)
#   copiar brain estructural + 22 skills propias → README + .gitignore ampliado → commit → push
git -c http.extraheader="$AUTH" push origin main          # acc66b..f975b2d  (272 archivos)
```

## Qué incluir / excluir al versionar brain en un repo

- INCLUIDO en Hermes-casinos: `brain/` (entities, concepts, tasks, archive, analysis,
  *.md raíz incl. AGENTS.md, raw/*.md ligeros) y `skills/` (22 propias: brain-knowledge-base,
  knowledge-absorption, ssot-context-document, wiki-entry-creation, persistent-task-manager,
  decision-autonomy, identity-cleanup, discord-reporter, engram-memory-system, github-repo-ingestion,
  document-reader, google-docs-api, local-vision-toolkit, pip-install-broken-env, graphify-codebase-graph,
  ecosystem-setup, system-onboarding, hermes-production-deployment, browser-backend-replacement,
  agent-reach, mapa-de-carpetas, spec-driven-development).
- EXCLUIDO: `brain/raw/` pesado (Vent 54 MB: bendabal 18M, golden_game 16M, lucky 13M, digital_expressions 7M),
  `brain/graphify-out/` (1.4M generado), `*.bak`, skills de terceros (~100).
- Nota: `ai-platform` SÍ trackea `graphify-out/` intencionalmente (merge driver `graphify` vía `.gitattributes`), y el hook de graphify corre en commit (warning si no está el Python, no es error).

## Secretos escaneados antes del commit (patrón correcto)

```bash
git diff --cached | grep -ioE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE)' | sort -u
# resultado: vacío → commit OK
```

## Observaciones

- La SSH key `~/.ssh/id_ed25519_github` existe pero GitHub la rechaza (publickey) — no usarla.
- El repo Hernes-casinos originalmente se documentó con guion final `Hermes-casinos-` (nota del 16/08):
  el nombre REAL es `Hermes-casinos` sin guion. Verificar siempre con API `repos/...` y `permissions`.
- Tras crear el skill: agregar también a `brain/log.md` si el flujo vuelve a ejecutarse en otra sesión.
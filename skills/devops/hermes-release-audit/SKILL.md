---
name: hermes-release-audit
version: 1.0.0
description: "Use when auditing a Hermes release vs fleet's live configs."
tags: [hermes, auditoria, release, version, config, plugins, features]
author: Ragnar
metadata:
  hermes:
    category: devops
    tags: [hermes, release-notes, gap-analysis, config, plugins]
---

# Hermes Release Audit — qué trae la versión nueva vs lo que ya usamos

Comparar una release upstream de Hermes contra la config VIVA de la flota y
producir un informe de brechas con plan de adopción priorizado. El entregable
que Plon espera: (1) features nuevas no usadas que podemos activar, (2) cosas
que ya hacíamos y la versión nueva mejora, (3) deuda/mal-configuración propia
que la auditoría destapa.

## Procedimiento

1. **Confirmar la versión real en cada entorno** — `hermes --version` / imagen
   Docker en PROD / `git log` del repo local. Nunca asumir la versión desde
   memoria o del chat. En cada entorno chequear DOS capas: gateway
   (`:8642/health`) Y dashboard (`:9112/api/health` + `/api/status` →
   `config_version` vs `latest_config_version`) — el dashboard es un proceso
   separado que sobrevive al upgrade viejo y puede servir versión y config
   anteriores aunque el gateway ya esté actualizado.
2. **Leer las notas de la release** — `web_extract` sobre las release notes
   upstream (o `website/docs/` del repo local si está actualizado) +
   `https://hermes-agent.nousresearch.com/docs/llms.txt` como índice de
   features. Destilar la lista de features a una tabla corta antes de tocar
   config.
3. **Extraer el estado vivo de la flota** — greps sobre `/opt/data/profiles/*/config.yaml`
   por cada feature candidata (keys de config reales), no desde memoria. Incluir
   cuántos perfiles la tienen y con qué valor.
4. **Triage del estado operativo en paralelo** — antes de proponer nada nuevo,
   revisar si lo que YA corre está sano: `task_runs` de `kanban.db` (crashes
   recientes), `hermes pm status`, crons activos. Las brechas más valiosas
   suelen salir de aquí, no de las release notes (ej. dispatchers en carrera,
   venv incompleto). Si la auditoría sigue a un upgrade, correr primero el
   checklist de `references/post-upgrade-smoke-checks.md` (empezando por
   `hermes pm repair`) — un install incompleto imita bugs de la versión nueva.
5. **Comparar el catálogo de plugins** — catálogo local (`plugin-catalog/*.yaml`:
   `tier`, `description`, `requires_hermes`) contra los instalados. Filtrar por
   los que resuelven dolores REALES de la flota, no por novedad.
6. **Clasificar cada feature** — activable ya / activable con costo / no
   aplica (ej. features de Desktop cuando la flota es headless WhatsApp).
7. **Informe con orden de ataque** — lista priorizada por impacto/costo,
   cada ítem reversible y marcado con su nivel de impacto (muta config =
   requiere aprobación antes de ejecutar). El informe se ARCHIVA en el ticket
   del foro (abrir uno si no existe: el foro es el hogar del trabajo, el chat
   solo el aviso) — raíz corto con el plan y el detalle completo (hallazgos +
   evidencia) en mensajes siguientes del hilo, nunca solo en chat o archivos
   temporales.

## Pitfalls

- **Nunca responder "Hermes puede/no puede X" desde memoria** — verificar contra
  `llms.txt`, docs o el repo. La ausencia en el skill/docs no prueba que la
  feature no exista.
- **La config por defecto engaña en flotas multi-perfil**: muchos defaults son
  por-perfil (ej. `kanban.dispatch_in_gateway`), así que "el default es X" no
  dice nada hasta grepear los N configs reales.
- **Un default razonable en un solo agente puede ser tóxico en una flota** (ej.
  dispatchers duplicados, intervals agresivos). Evaluar cada feature contra el
  tamaño real de la flota, no contra el caso de un usuario solo.
- **Separar features de producto de deuda propia**: si algo falla, primero
  descartar causa local (venv, dispatcher, config stale) antes de culpar a la
  versión nueva.
- **Tras un upgrade, `hermes pm repair` antes de culpar a la versión** — sin
  dependency environment committed, TODO worker muere `exit 1` antes de
  arrancar y el síntoma se lee como bug de la release cuando es install
  incompleto; el error real solo aparece en `hermes pm repair` o en el log del
  worker.
- Todo cambio que salga del informe es D-I-V-E: backup → cambio → verificación,
  y presentado para aprobación, no ejecutado en el mismo turno del análisis.

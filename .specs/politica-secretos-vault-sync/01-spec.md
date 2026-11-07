# Spec — Política de Secretos · Fase 1: sincronizador con merge preservativo (SSOT del código)

- **Estado:** Approved por el Admin (2026-11-07: «arranca fase por fase, en un worktree separado»)
- **Autor:** Ragnar · **Fecha:** 2026-11-07 · **Fuente:** `docs/POLITICA-SECRETOS-Y-SERVICIOS.md` §6.1 y §6.5
- **Worktree:** `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/politica-secretos` · **Rama:** `feat/politica-secretos-vault-sync`

## 1. Contexto y problema

`vault-sync.timer` corre `/opt/vault/timer/sync-env.py` cada 30 min en DEV y PROD. Medido hoy (7-nov-2026):

| | DEV `147.93.3.250` | PROD `100.73.30.29` |
|---|---|---|
| sha256 `sync-env.py` | `72ed8190…` (161 líneas) | `fe6549ff…` (143 líneas) |
| Guard de directorio padre | ✅ `SKIPPED` | ❌ `open()` sin guard → un target muerto tumba el run (`set -euo pipefail`) |
| `SUMMARY: ok=/skipped=/failed=` | ✅ | ❌ |
| `owner` por target (chown) | ✅ | ❌ |
| Restart solo si cambió | ❌ siempre | ✅ |
| Fallback `notes` como `.env` | ❌ | ✅ |
| Escritura atómica | ❌ `open(w)` (trunca) | ❌ `open(w)` (trunca) |
| Preserva comentarios / claves ajenas | ❌ se reescribe como puro `k=v` | ❌ igual |

Dos versiones divergentes, **ninguna en Git** (`git -C /opt/vault status` → `fatal: not a git repository`
en ambos hosts): se viola el protocolo de repositorios vivos. Además ninguna hace merge a nivel de línea.

## 2. Historias de usuario

- **US-1:** Un comentario humano (`# generado a mano por Plon`) en un `.env` debe sobrevivir a 100 corridas.
- **US-2:** UN solo `sync-env.py` (SSOT en Git) desplegado en los dos hosts: un fix no puede vivir en un host y no en el otro.
- **US-3:** Un target caído se cuenta `SKIPPED`/`FAILED` sin tumbar la cola.
- **US-4:** El servicio se reinicia **solo** si el contenido cambió.
- **US-5:** El `.env` nunca queda a medio escribir.

## 3. Requisitos funcionales

- **RF-1 (merge preservativo):** partir del texto actual; conservar **byte a byte** toda línea que no sea un `KEY=` con `KEY` en `mappings` (comentarios, blancos, claves ajenas, `export `, orden, fin de línea por línea).
- **RF-2:** clave mapeada presente → valor reemplazado **en sitio**, conservando prefijo, fin de línea y comentario en línea.
- **RF-3:** clave mapeada ausente → añadida al final con fin de línea correcto.
- **RF-4:** clave mapeada duplicada → todas sus ocurrencias con el valor nuevo (cero rastros viejos).
- **RF-5 (paridad):** el canónico incluye las 6 capacidades: guard de padre, captura de `OSError`, `SUMMARY`, `owner` con aviso si no existe, restart solo si cambió, fallback `notes`.
- **RF-6 (atómico):** temporal en el mismo directorio → `chmod` al modo del target → `chown` opcional → `os.replace`; ante fallo el original queda intacto y el target cuenta `FAILED`.
- **RF-7:** exit `1` solo si `failed>0 and ok==0`. **Nota de compatibilidad (hallazgo H8):** esa es la semántica del script actual de **DEV**; el de **PROD** hoy termina siempre en `0`, así que en PROD este exit 1 es **comportamiento nuevo**: aborta el wrapper `vault-sync.sh` antes de su `bw logout`, y el logout forzado ocurre al inicio del run siguiente (comportamiento aceptado y verificado en ambos wrappers).
- **RF-8:** `bw list items` con timeout 30s; ante error exit 1 sin escribir nada.

## 4. Non-goals (Fases posteriores)

- Ampliar `vault-to-env-map.json` → **Fase 2**; verificación server-side → **Fase 3**; cuenta solo-lectura `/etc/hermes/vault-bot.env` → **Fase 4**; `SOUL.md` 6.3 + skill `vault-access` 6.4 → **Fase 5**. Rotaciones, ítems y colecciones de Vaultwarden: **nunca** (§7).

## 5. Criterios de aceptación

- **AC-1** `.env` con comentario + clave ajena + clave mapeada → los dos primeros byte-idénticos, la mapeada con valor del vault.
- **AC-2** clave mapeada ausente → aparece al final con `\n` final correcto.
- **AC-3** padre inexistente → `SKIPPED` + resto procesado + `SUMMARY` correcto.
- **AC-4** `os.replace` lanza `OSError` → `.env` original byte-idéntico y target `FAILED`.
- **AC-5** dos corridas idénticas → la segunda no reinicia.
- **AC-6** clave duplicada → ninguna copia con valor viejo.
- **AC-7** `env -u PYTHONPATH python3 -m unittest -v tests/scripts/test_vault_sync_env.py` → green.

## 6. Casos límite

Valor con `=`, comillas, `$`, espacios (split en el primer `=`); archivo sin `\n` final; archivo vacío/inexistente; `owner` inexistente → WARNING; comentario en línea ` #...` → **se conserva**; fin de línea `\r\n` → conservado por línea.

## 7. Skill audit

`.skills/python-patterns`, `.skills/python-testing-patterns`, `.skills/code-review-and-quality` (según `.atl/skill-registry.md`). Guardrail aplicable: `.agents/rules/02-vps-guardrails.md` §2 → fixtures de test sin secretos reales.

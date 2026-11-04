# Recuperación forense de trabajo perdido en un worktree

Procedimiento verificado en operación (03-nov-2026, DEV): un worktree con trabajo NO commiteado (módulo nuevo, tests, specs, wiring) desapareció del filesystem y de git (sin rama, sin stash rastreable, sin reflog). Se reconstruyó **byte-exacto** desde el historial de sesiones del perfil.

## Fuente de verdad: `state.db` del perfil

Los `tool_calls` completos (payloads de `write_file`/`patch`) sobreviven en la BD de sesiones del perfil que ejecutó el trabajo:

```bash
# Solo lectura (RO). DB del perfil implementador:
sqlite3 "file:/opt/hermes-agent-data/profiles/<perfil>/state.db?mode=ro" \
  "SELECT session_id, tool_calls FROM sessions WHERE ..."
```

1. Identificar las sesiones del trabajo (por fechas/rutas en los payloads).
2. **Replay determinista en orden cronológico** de los payloads `write_file` (contenido completo) y `patch` (old/new). Omitir duplicados generados por compactación de contexto (aparecen repetidos: contar y saltar).
3. Reconstruir cada archivo aplicando la secuencia completa de ediciones.

## Verificación de integridad (obligatoria, sin esto no es recuperación)

- **SHA-256 contra hashes registrados históricamente**: si una sesión anterior ejecutó `sha256sum` o registró hashes en un handoff, el reconstruido debe coincidir exacto (ej. módulo 17973 B = `0ecdb3b9…eb026`).
- **Blobs de git como corroboration**: un `git stash` posterior (aunque el stash se pierda) deja el blob en el object store: `git cat-file <sha>` o buscar por contenido (`git rev-parse <blob>`). Solo cubre archivos que llegaron a stash/index; los **untracked puros no dejan rastro en git**.
- **Dead ends conocidos** (no perder tiempo): reflog/stash vacíos, barrido de filesystem (`/opt /root /home /var/tmp /tmp`), attachments de Kanban, backups de releases (solo contienen la base, no el trabajo).

## Restauración

- Reconstruir en la **ruta canónica** con mecanismo oficial (checkout/branch nueva desde la base correcta, archivos escritos byte-exacto); 0 commits, no tocar el repo raíz.
- Validar con el **runner oficial** del proyecto (`scripts/run_tests.sh`, nunca bare pytest) sobre el checkout recuperado y comparar contra el baseline previo.
- Preservar un snapshot duradero privado del artefacto (tar + hashes) mientras no haya permiso de commit, para evitar una segunda pérdida.
- **No es licencia** para reconstruir código "desde el relato" ni guardar fuente en MEMORY: solo payloads exactos corroborados por hash.

## Rol del orquestador

El implementador recupera; el orquestador verifica hashes en vivo (ssh) y re-encadena la revisión con tarjetas sustitutas de workspace neutro (ver SKILL.md §2.d), sin completar la tarjeta original ni liberar fases siguientes hasta veredicto real del reviewer.

# Auditar un replay de parches hecho por otro agente

Cuando el upgrade `vX.Y.Z` lo ejecuta un agente externo (Agy/antigravity, Claude
Code, otro perfil de Hermes) sobre un worktree, su informe de cierre NO es
evidence. Este documento es la receta para auditarlo con comandos propios y
negar el cutover con pruebas, no con impresiones.

## 1. Localizar la sesión y su transcript

Agy guarda la conversación en `~/.gemini/antigravity-cli/brain/<conversation-id>/`.
El archivo útil es el transcript JSONL, legible aunque la DB sea de otro usuario:

```
/root/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript_full.jsonl
```

- Un objeto JSON por línea, campos `step_index`, `source` (user / planner / tool),
  `content`, `created_at`.
- El `planner` contiene el plan y los informes de cierre; los pasos `tool`
  contienen la evidencia real.
- `conversations/<id>.db` y `conversation_summaries.db` son del usuario que lanzó
  `agy`: desde otro account `cp` a `/tmp` y abrir ahí (`sqlite3 file:...?mode=ro`
  falla por permisos). `raw_summary` viene comprimido → `zlib.decompress`.

Extraer sin inundar el contexto:

```python
import json
rows=[json.loads(l) for l in open(PATH) if l.strip()]
print(rows[76]['source'], rows[76]['content'][:2000])   # el plan
print(rows[-1]['source'], rows[-1]['content'][:2000])   # el informe final
```

## 2. Tablero de estado del worktree (30 s)

```bash
W=/opt/hermes-agent-worktrees/upgrade-vX.Y.Z
cd $W
git tag -l 'backup*'                 # el respaldo del HEAD anterior DEBE existir
git config --get rerere.enabled      # true = reusa resoluciones de conflictos
git rev-list --count vX.Y.Z..HEAD     # commits realmente aplicados
git log -3 --format='%h %ci %s'
ls .git/CHERRY_PICK_HEAD .git/sequencer 2>/dev/null   # replay detenido/conflicto
git status --porcelain | grep -cE '^(UU|AA|DD|AU|UA|DU|UD)'  # sin resolver
```

## 3. Cobertura del replay: ¿están TODOS los commits propios?

Un informe puede decir «21 commits re-aplicados» y ser cierto pero incompleto.
Comparar por subject (el `-x` preserva subject) y **normalizar `\r`** — sin el
`tr -d '\r'` el `comm` no encuentra coincidencias y el conteo miente:

```bash
cd /opt/hermes-agent
MB=$(git merge-base feat/rama vX.Y.Z)
git log --reverse --format='%s' $MB..feat/rama -- agent hermes_cli gateway tools plugins cron \
  | tr -d '\r' | sort > /tmp/own.txt
cd $W && git log --format='%s' vX.Y.Z..HEAD | tr -d '\r' | sort > /tmp/rep.txt
comm -23 /tmp/own.txt /tmp/rep.txt   # faltantes — DEBE salir vacío
```

Caso real (nov-2026): 57 commits de código propios, 22 aplicados → el informe
«replay completado» ocultaba 35 faltantes, entre ellos la trie semántica
(`agent/semantic_triage.py`), el utillaje de skills on-demand
(`scripts/f3_valida_configs.py`, `master_skills_consolidation.py`) y los 5
commits del worker Jev.

## 4. Paridad funcional, no contabilidad de commits

Un commit puede sobrar si upstream ya trae la feature, y puede faltar aunque el
subject exista con otro nombre. Verificar por palabra clave en dos revisiones del
mismo repo (excluyendo tests y docs para no inflar):

```bash
cd $W
for kw in on_demand index_char_limit skill_route lock_default_in_config DSML semantic_intent; do
  printf '%-24s main=%s nuevo=%s\n' $kw \
    "$(git grep -l $kw <HEAD-viejo> -- ':!tests' ':!*.md' | wc -l)" \
    "$(git grep -l $kw HEAD -- ':!tests' ':!*.md' | wc -l)"
done
```

Un `0` en la columna nueva donde la vieja tenía ≥1 es pérdida funcional: buscar
el archivo por nombre (`git ls-tree -r --name-only HEAD | grep -i <modulo>`) y
revisar si el test asociado siquiera existe en la rama nueva.

## 5. ¿La «suite» que dice haber corrido es la suite?

`pytest` deja su rastro, aunque el agente no lo pegue:

```bash
cat $W/.pytest_cache/v/cache/lastfailed           # vacío = verde en la última corrida
python3 -c "import json;d=json.load(open('$W/.pytest_cache/v/cache/nodeids'));print(len(d));print(d[:3])"
git -C $W ls-tree -r --name-only HEAD | grep -cE '^tests/.*test_.*\.py$'
ls $W/scripts/run_tests.sh                        # ¿existe y nunca se ejecutó?
```

Caso real: «154 tests, 5 archivos, VERDE» sobre un repo con 7.244 archivos de
test — cobertura ~2 %, y el `.pytest_cache` de la última corrida mostraba 101
tests de 2 archivos. Verde ≠ verificado: pedir `scripts/run_tests.sh` completo.

## 6. Dos agujeros que el agente no reporta

- **Conflictos `modify/delete` que borran archivos del fork.** Si upstream eliminó
  un archivo que el fork mantiene (`PROJECT_MEMORY.md`, `.skills/`), la resolución
  natural del `cherry-pick` toma la versión upstream (borrado) y el replay queda
  «verde» sin ese contenido. Verificar:

  ```bash
  comm -23 <(git -C /opt/hermes-agent ls-tree -r --name-only HEAD | sort) \
           <(git -C $W ls-tree -r --name-only HEAD | sort) | head -30
  ```

  En el caso real desapareció `PROJECT_MEMORY.md` (51.834 bytes) y `.skills/`
  quedó vacío: rompe el protocolo SDD que exige leerlos antes de tocar código.

- **Trabajo sin commitear no viaja.** `cherry-pick` solo mueve commits; lo que
  está en el working tree del checkout de origen se pierde o bloquea el `switch`
  del cutover. Contarlo y decidirlo ANTES de autorizar:

  ```bash
  git -C /opt/hermes-agent status --porcelain | awk '{print $1}' | sort | uniq -c
  ```

  Caso real: 38 modificados + 40 sin rastrear (incluye `gateway/run.py`,
  `plugins/platforms/whatsapp/adapter.py`, `scripts/whatsapp-bridge/bridge.js`).

## 7. Veredicto y bloqueo

Autorizar el cutover solo si: (a) `comm -23` de commits propios sale vacío o cada
faltante tiene justificación verificada (upstream lo trae / obsoleto declarado y
comprobado); (b) no hay pérdida de paridad funcional; (c) `scripts/run_tests.sh`
corrido y su salida a la vista; (d) archivos propios restaurados; (e) cambios sin
commitear resueltos (commit temporal o parche exportado); (f) respaldo del runtime
(`/opt/hermes-agent-data` o el `data/` equivalente) hecho. Si falta cualquiera,
decir qué falta con el comando que lo prueba — nunca «parece que va bien».

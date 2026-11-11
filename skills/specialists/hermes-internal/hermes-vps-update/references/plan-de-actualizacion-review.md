# Revisar un plan de actualización antes de autorizarlo

Un plan de upgrade se revisa de dos formas y ambas son obligatorias:
**(A)** recalcular cada métrica que declara, **(B)** ejecutar en seco cada comando
que propone. Un plan puede tener cifras perfectas y ser inejecutable; eso es lo
habitual cuando lo escribe un agente que no lo corrió.

---

## A. Recalcular las métricas (nunca aceptar cifras heredadas)

```bash
cd <repo>
MB=$(git merge-base HEAD <tag-destino>)
echo "MB=$MB"
echo "faltan=$(git rev-list --count HEAD..<tag-destino>) propios=$(git rev-list --count <tag-base>..HEAD)"
git diff --name-only $MB..<tag-destino>  > /tmp/up.txt
git diff --name-only $MB..HEAD          > /tmp/lo.txt
comm -12 <(sort /tmp/up.txt) <(sort /tmp/lo.txt) > /tmp/ov.txt
# separar código de activos: skills/ops/docs/tests/.agents no son "código"
grep -vE '^(skills|ops|docs|tests|\.agents|\.specs|scripts)/' /tmp/ov.txt > /tmp/ovc.txt
echo "solape_total=$(wc -l < /tmp/ov.txt) solape_codigo=$(wc -l < /tmp/ovc.txt)"
git diff --shortstat $MB..HEAD -- $(tr '\n' ' ' < /tmp/ovc.txt)
git diff --shortstat $MB..<tag-destino> -- $(tr '\n' ' ' < /tmp/ovc.txt)
git log --oneline $MB..HEAD -- $(tr '\n' ' ' < /tmp/ovc.txt) | wc -l
```

Si una sola cifra no coincide, el resto del plan queda bajo sospecha: se midió
sobre otro árbol o sobre otro momento.

---

## B. Probar la ejecutabilidad de cada paso

### B1. ¿El cambio de rama es posible?

```bash
git merge-base --is-ancestor <rama-propia> <tag-destino>; echo $?   # 1 = NO
```
Un `--ff-only` exige que nuestra rama sea ancestro del destino. En un replay
nunca lo es (el tag nace de upstream, no de nuestra historia) → el paso aborta
con los servicios ya detenidos.
**Patrón válido:** `git switch -C <rama-propia> <rama-upgrade>` con rama de
respaldo creada antes. `reset --hard` solo si la política del repo lo permite.

### B2. ¿El destino trae nuestros activos?

```bash
git ls-tree -r <tag-destino> --name-only | grep -c 'SKILL.md'      # vs las nuestras
git ls-tree -r <tag-destino> --name-only | grep -c '^scripts/hooks/'
git ls-tree -r <tag-destino> --name-only | grep -c '^ops/'
```
Si el tag trae menos skills/hooks que nosotros, el plan **tiene** que copiar el
árbol propio (`rsync -a --delete`) además del replay. Un plan que solo menciona
«cherry-pick de parches» pierde cientos de skills y todos los hooks.

### B3. ¿Cada comando citado existe?

Ejecutar `--help` de cada subcomando que el plan invoca antes de aprobarlo:

```bash
hermes <cmd> --help | head -5          # p.ej. hermes pm --help
hermes gateway run --help | grep -i port
systemctl show -p TimeoutStartUSec --value <unidad>
command -v pytest; ls scripts/run_tests.sh
```
Sospechas típicas: subcomandos inventados por analogía (`pm sync` cuando el real
es `pm environment`), flags que no existen (`gateway run --port`), y `pytest`
suelto en vez del runner canónico (intérprete equivocado → falso verde).

### B4. Cobertura de respaldo de datos

```bash
ls -1 $HERMES_HOME/*.db $HERMES_HOME/cron/*.db   # inventariar TODAS
```
Respaldar solo `state.db` deja fuera cron, proyectos, kanban, shared-state,
idempotencia y evidencias → el rollback «restaura» a un estado incoherente.
Exigir también copia del entorno de runtime (el lock nuevo reconstruye el venv
y pisa el viejo) y un ensayo de migración de esquema **sobre copia**, midiendo
tiempo.

### B5. ¿El canario aísla de verdad?

Requisitos mínimos del canario: `HERMES_HOME` propio, `platforms.*.enabled:
false`, `cron/jobs.json` = `{"jobs": []}`, puerto del API fijado **en el YAML**
(no por flag), y **≥2 perfiles copiados**: los perfiles se descubren del
directorio `profiles/`, no de `config.yaml`, así que un home vacío arranca un
solo perfil y nunca ejerce la reconciliación multi-perfil que rompe en producción.

---

## C. Regla de cobertura de commits: lo que NO choca también hay que replayar

```
total_propios − propios_que_tocan_solape = commits_sobre_archivos_sin_conflicto
```
Ese resto es donde suele vivir el valor propio (guards de agente, triage
semántico, transporte MCP, archivos nuevos que upstream no tiene). Su
cherry-pick no da conflictos: omitirlos es pérdida segura y silenciosa.
Un plan que enumera solo los módulos en conflicto está incompleto.

Agrupar el replay por tandas temáticas (`agent/ tools/`, `gateway/ plugins/`,
`scripts/ ops/`, `locales/ docs/ .gitignore`), con `rerere` activo,
`--empty=drop`, `git status` limpio y el runner canónico verde entre tandas.
Los activos que no son código (skills, `.agents/`, hooks, docs) se copian, no
se cherry-pickeanean.

---

## D. Criterios de aceptación que el plan debe traer escritos

- health HTTP 200 en el puerto real del API
- `Connected as <bot>` y nº de plataformas por perfil (antes vs después)
- nº de jobs cron (antes vs después) y que tickeen tras `resume`
- nº de tools/servers MCP
- `0 Traceback` en `gateway.log` y `errors.log` desde el arranque
- `NRestarts=0`, `hermes doctor` sin fallos, `git status` limpio
- `PRAGMA quick_check` de la DB migrada = `ok`
- **endpoint del dashboard** (`9119` o el que aplique) en `200`/`302` — un plan
  que solo mide el gateway deja el panel caído y nadie lo nota
- **decisión sobre `session_reset`** tomada y aplicada (plugin instalado o cambio
  aceptado y documentado); su retirada del core no emite error, solo un aviso de
  `doctor`, así que el reset se pierde en silencio
- **en Docker: hash de 4 archivos del contenedor == árbol del repo** (si difieren,
  la imagen no salió de ese checkout y el build es una regresión)

Sin esto, «verde» es una opinión.

---

## E. Banderas rojas en el texto del plan

| Frase | Por qué es señal de alarma |
|---|---|
| «re-aplicar los parches indispensables» | indefinido: nadie sabe qué queda fuera |
| «la base de datos no se toca» | el código nuevo migra al arrancar |
| «rollback en menos de N minutos» | no cuenta restauración de DB ni arranque real |
| «decisión: evaluar / verificar» en la tabla | el dato que decide el replay debía estar resuelto |
| «100 % seguro» para las fases sin corte | el rebuild del entorno ya tumba adapters |
| métricas sin el comando que las produjo | no es medible por un tercero |

---

## F. Auditoría de quien ejecutó (no solo del plan)

Al revisar los arreglos de otro agente, leer el **commit padre** y no `HEAD`:

```bash
git show <sha>^:<ruta> | grep -c '<símbolo>'   # estado ANTES de su cambio
git log -1 --format='%ad %s' --date=iso <sha>
```
Leer `HEAD` después de que el otro agente commiteó hace que un arreglo real
parezca un no-op. Y verificar con qué intérprete/usuario corrió la suite: `.pyc`
`cpython-312` de propietario `root` en el árbol delatan que corrió como root con
el Python del sistema, no con el runtime del install-state — su «verde» no es
el verde que sirve.

### G. Localizar el informe cuando «la terminal activa» no existe

Un agente CLI no deja su respuesta final en un `.md` ni en el log: el informe es
un paso dentro de la base de conversación. Si no hay tmux/screen al que
adjuntarse, leerlo del disco (ejemplo Antigravity `agy`):

```bash
D=~/.gemini/antigravity-cli
ls -1t $D/conversations | head -3        # conversación más reciente primero
tail -3 $D/history.jsonl                 # prompts: qué se le pidió
DB=$D/conversations/<uuid>.db
sqlite3 -header -column "$DB" "select idx, step_type, status, length(step_payload) bytes from steps order by idx desc limit 8;"
mkdir -p /tmp/agy_steps
for i in $(sqlite3 "$DB" "select idx from steps order by idx desc limit 4;"); do
  sqlite3 "$DB" "select writefile('/tmp/agy_steps/$i.bin', step_payload) from steps where idx=$i;" >/dev/null
done
strings -n 25 /tmp/agy_steps/<idx>.bin | head -60
```

`step_type 15` = salida del modelo (el informe), `132` = llamada/resultado de
herramienta (los comandos que corrió: eso es lo que se audita). El payload es un
BLOB protobuf, no texto: `writefile` + `strings -n 25` recupera la prosa (los
acentos salen deformados, se lee alrededor). Otros deltas útiles:
`conversation_summaries.db` (resúmenes buscables), `crashes/crash_<pid>_<uuid>.log`
(una corrida que crasheó no tiene informe: mirar ahí antes de concluir que no
produjo nada), y `ps -o pid,etime,args -p <pid>` para saber cuánto lleva vivo.

# Actualizar un fork divergente sin perder los parches propios

Aplica cuando `git rev-list --count $(git merge-base HEAD upstream/main)..HEAD` > 0
(caso real `/opt/hermes-agent`, fork NeuralCrew: 56 commits de código propios,
base v0.22.0, 9.000 commits detrás de v0.22.6).

## Regla de oro

**Nunca `git merge upstream/main` ni `reset --hard`.** Con miles de commits y
miles de archivos movidos, el merge es un conflicto masivo e irresoluble. El
modelo correcto es *replay de parches*: partir del tag limpio y re-aplicar solo
lo nuestro.

## 1) Medir la divergencia (antes de prometer nada)

```bash
cd /opt/hermes-agent
git fetch upstream --tags --prune
MB=$(git merge-base HEAD upstream/main)

# última estable: SOLO tags v0.X.Y
git tag -l 'v0.*' | sort -V | tail -1          # v0.22.6

git rev-list --count HEAD..v0.22.6              # 9000 → commits que nos faltan
git rev-list --count $MB..HEAD                  # 193 → commits propios totales
git log --oneline $MB..HEAD -- agent hermes_cli gateway tools plugins cron | wc -l   # 56 → código
```

**Riesgo real = solape, no volumen upstream:**

```bash
git diff --name-only $MB..v0.22.6 | sort > /tmp/up.txt
git diff --name-only $MB..HEAD    | sort > /tmp/lo.txt
comm -12 /tmp/up.txt /tmp/lo.txt              # archivos donde se pelea
comm -12 /tmp/up.txt /tmp/lo.txt | grep -vE '^(skills|docs|tests|\.agents|\.specs|ops)/'   # de código
```

Interpretación (calibrada en el caso real): ≤15 archivos de código y ≤25
commits → riesgo bajo; ≤35 archivos → medio; más → alto, plan por fases.

## 2) ¿Upstream ya implementó nuestra feature?

Antes de re-aplicar, comprobar feature por feature. Ahorra trabajo y detecta
parches obsoletos:

```bash
for kw in DSML glm5.3-flash index_char_limit "ephemeral progress" "flood brake" lock_default_in_config skill_route; do
  echo "$kw -> $(git grep -l \"$kw\" v0.22.6 -- ':!tests' ':!*.md' | wc -l) archivos"
done
```

0 archivos = solo nuestra, hay que re-aplicarla. >0 = upstream la trae, evaluar
si nuestro parche se puede soltar.

> Cuidado con el `git grep` sobre un tag: verificar con un patrón conocido
> (`git grep -l hermes v0.22.6 -- hermes_cli | wc -l` → ~752) que el tag se lee
> bien antes de concluir "no existe upstream".

## 3) Replay de parches

```bash
cd /opt/hermes-agent
git config rerere.enabled true          # recuerda resoluciones entre updates
git tag backup/pre-v0.22.6 HEAD
git switch -c upgrade/v0.22.6 v0.22.6

# orden cronológico, -x deja el sha original en el mensaje
git log --reverse --format=%h $MB..HEAD -- agent hermes_cli gateway tools plugins cron \
  | xargs -n1 git cherry-pick -x
```

En cada conflicto: resolver conservando la **intención** del parche (no el texto),
`git add -A && git cherry-pick --continue`. Agrupar por área
(agent → gateway → tools → cron) y correr tests entre grupos, no al final.

## 4) Skills, docs y config

- `skills/`: copiar nuestro árbol completo encima (`cp -a`), luego adoptar
  selectivamente skills nuevas de upstream. Nuestro repo pesa 1.694 archivos
  propios en `skills/`: es el grueso del diff y NO se cherry-pickea.
- `config.yaml`, `.env`, MCP, perfiles viven en `/opt/data` (fuera del repo):
  no se tocan. Verificar `HERMES_HOME` explícito.

## 5) Verificación y cutover

1. Suite local + smoke en puerto canario (gateway y dashboard: login,
   `model/options`, `gateway.ready`).
2. Cutover con rollback listo: sha anterior + venv anterior.
3. Informe final: sha nuevo, tests corridos, riesgos residuales, parches
   soltados y por qué.

## 6) Cadencia y autorización

El estudio se corre **semanal (lunes 6:30)** y se entrega en un hilo del foro
`🖥️・sistema-servers`; cada informe cierra con la frase de autorización
(`AUTORIZO ACTUALIZAR vX.Y.Z`). El replay + tests se ejecutan con esa
autorización; el **despliegue a producción exige un segundo OK**. Separar las
dos autorizaciones evita que "actualizar" implique cortar el servicio.

Script listo: `scripts/hermes_upstream_review.py` (informe ≤1900 chars para un
mensaje de Discord, detalle completo en
`/opt/data/logs/hermes-upstream-review-latest.md`).

## Pitfalls verificados

- **Tags de fecha `v2026.9.24` no son versiones.** Un regex `v(\d+)\.(\d+)\.(\d+)`
  los toma como "la última estable" y el informe concluye falsamente
  "0 commits por detrás". Filtrar `^v0\.(\d+)\.(\d+)$`.
- **`git describe --tags --abbrev=0 HEAD`** da la base real (`v0.22.0`) incluso
  si HEAD está en una rama feature: es la referencia para "cuánto llevamos".
- **El volumen upstream no es el riesgo.** 10.303 archivos movidos por upstream
  vs 67 de solape: lo que duele es la intersección.
- **`merge-base` con `upstream/main`, no con el tag.** El tag se mueve; el punto
  común es estable y es lo que hace comparables ambas listas de archivos.
- **Cherry-pick sin `rerere`** repite el mismo conflicto en cada actualización.
- **No re-aplicar parches que upstream ya trae**: revisar (2) primero.

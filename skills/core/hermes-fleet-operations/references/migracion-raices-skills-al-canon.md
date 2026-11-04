---
name: migracion-raices-skills-al-canon
description: Use when migrating Hermes skill write-roots onto the versioned canon (one-tree model), or when a profile config falls back to defaults.
---

# Migración de raíces de escritura al canon (modelo de árbol único)

Caso absorbido desde el paraguas `hermes-fleet-operations`. Preserva el
procedimiento completo de la migración F3 del 23-sep-2026.

## Cuándo usar

- Al migrar una instancia Hermes para que la raíz de **escritura** de skills sea
  el árbol versionado del repositorio (y no una copia fuera de git).
- Al diagnosticar un perfil que "ignora sus overrides" (proveedores, cadena de
  fallback, modelo) porque su `config.yaml` no parsea.

## Los dos hechos que gobiernan el problema

1. `get_skills_dir() == get_hermes_home() / "skills"`. Con `hermes -p <perfil>`
   el `HERMES_HOME` pasa a `/opt/data/profiles/<perfil>`, así que cada perfil
   escribe en su propio directorio. Montar el canon en
   `skills.external_dirs` da **lectura**, nunca escritura.
2. El curador EXCLUYE de su universo todo `skills.external_dirs`
   (`agent/curator.py`, regla dura). Mientras el canon sea externo, el curador
   no puede curarlo: no hay F4 posible.

## Procedimiento

1. **Medir antes**: inventario de cada raíz de escritura
   (`for d in /opt/data/skills /opt/data/profiles/*/skills`), contando SKILL.md.
   En la migración del 23-sep las 12 raíces tenían 0 SKILL.md salvo la del
   default (3 instalaciones de hub con uso cero).
2. **Respaldar** los 12 configs + compose + `.gitignore` con sha256 conjunto.
3. **Archivar —nunca borrar—** el estado runtime de cada raíz
   (`.hub`, `.usage.json*`, `.curator_*`, `.bundled_manifest`) y las
   instalaciones de hub que queden en la raíz.
4. **Quitar `skills.external_dirs`** de los 12 configs con validación
   estructural obligatoria (ver el pitfall abajo).
5. **Montar el canon** en las rutas de escritura:
   `./skills:/opt/data/skills` y `./skills:/opt/data/profiles/<p>/skills`.
   Trece bind mounts del MISMO directorio ⇒ un solo inodo.
6. **Restaurar el historial del curador** (`.curator_ledger.jsonl`,
   `.curator_state`) DENTRO del árbol: si se deja en el archivo, el curador
   arranca sin historia.
7. **Recrear** con tag de imagen previo, verificación y rollback automático.
8. **Verificar**: mismo inodo en las 13 rutas · SKILL.md alcanzables ==
   versionados en git · write-probe como el uid del runtime · `external_dirs`
   en 0 configs.

## PITFALL — el recorte textual de YAML rompe el perfil entero (23-sep-2026)

El ítem de lista de `external_dirs` aparece indentado de dos formas distintas
en la misma flota:

```yaml
skills:
  disabled: []
  external_dirs:          # ← cabecera
  - /opt/hermes/skills    # ← ítem a 2 espacios (10 de 11 perfiles)
  on_demand: true
```
```yaml
skills:
  disabled: []
  external_dirs:
    - /opt/hermes/skills  # ← ítem a 4 espacios (root y roshi)
```

Un recorte que solo consume ítems de 4 espacios borra la cabecera y **deja el
ítem huérfano** ⇒ YAML inválido ⇒ el runtime cae al **config por defecto** e
ignora TODOS los overrides del perfil, en silencio salvo una línea de warning.
Pasó en 10 perfiles y duró hasta que el CLI se negó a escribir un config roto.

Reglas que quedaron:
- Consumir ítems con indentación **>= la de la clave**, cortando en la primera
  línea que no sea ítem de lista.
- **Validar estructuralmente**: parsear antes y después y exigir que el
  documento sea idéntico salvo la clave eliminada. Si eso no se cumple, no se
  escribe nada.
- La validación de sintaxis debe correr **antes** del reload del runtime, no
  después.

## Otro pitfall: host y contenedor no ven el mismo `/opt/data`

El compose monta `./data:/opt/data`, así que la ruta del host es
`/root/hermes-agent-legacy-docker/data/...`. Un script que opere `/opt/data` **en el host**
está tocando otro árbol (legado). Separar siempre *ruta host* de *ruta
contenedor* en los scripts de migración.

## Prueba real de aceptación (mandato M4)

Un `patch` del runtime sobre una skill canónica debe aparecer como diff en el
repo:

```bash
# como uid del runtime, dentro del contenedor
printf '\n<!-- prueba -->\n' >> /opt/data/skills/core/skill-library-ops/SKILL.md
# en el host
git status --porcelain skills/    # -> M skills/core/skill-library-ops/SKILL.md
git checkout -- skills/core/skill-library-ops/SKILL.md   # reversión
```

## Job de higiene diaria

`scripts/f3_higiene_diaria.py` reemplaza al vigilante canon ⇄ copia: vigila el
inodo único, la ausencia de `external_dirs`, la validez de los 12 configs, la
integridad del catálogo contra git, el árbol sucio, la aduana, el curador, el
ledger del gate y las recreaciones. Si hay ediciones sin versionar, atribuye
cada ruta a perfil + sesión consultando los `state.db` y commitea y empuja.

La atribución declara su propia confianza y **no inventa autoría**: si hay cero
candidatos, o varias sesiones distintas en la ventana, la marca baja a `baja` o
`sin rastro`. Un `except: continue` mudo sobre la consulta SQL ocultó un bug de
construcción de parámetros durante la primera corrida: los errores de consulta
se acumulan y se publican en el informe, nunca se descartan en silencio.

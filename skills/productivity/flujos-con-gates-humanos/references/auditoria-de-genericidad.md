# Auditar si un flujo por etapas es genérico (y si está conectado)

Receta read-only, general. Sirve para responder "¿esto nos va a servir para la próxima instancia o solo
para la de hoy?" sin adivinar y sin tocar nada.

## 1. Constantes clavadas (la instancia metida en el código)

```bash
cd <repo>
# datos, fechas, ids y rutas de UNA instancia dentro del código
grep -n -i "<mes-año>\|<nombre-campaña>\|<cliente>\|<premio>\|<mecanica>" scripts/<maquina>.py
grep -n "= REPO_ROOT / \"" scripts/<maquina>.py        # rutas de datos/calendario hardcodeadas
* grep de la lista de valores permitidos (`choices=[...]`) del CLI: ¿cuántas instancias admite hoy?
```

Reportar cada hallazgo como `archivo:línea` — un auditoría sin líneas no sirve para planificar.

## 2. Quién escribe, quién aprueba, quién bloquea

```bash
grep -n "def cmd_\|def main\|_exigir\|raise .*Error" scripts/<maquina>.py | head -40
```

Comprobar: ¿cada comando de escritura valida la etapa anterior? ¿la aprobación exige firma y congela con
hash? ¿las etapas con costo exigen candado/presupuesto?

## 3. ¿Está conectado con el pipeline real?

```bash
grep -rn "<maquina>\|<planner>" --include="*.py" --include="*.sh" . | grep -v __pycache__ | grep -v "^./tests/"
```

Si el único resultado son el script y sus tests, **el handoff no existe**: el artefacto que produce no lo
consume nadie. Verificar además el contrato real del consumidor (endpoint, payload, modo dry-run).

## 4. Qué devuelve el pipeline a la máquina

Preguntar explícito: ¿la máquina sabe qué se generó, cuánto costó, si quedó aprobado y si se publicó?
Si no hay retorno, decirlo como "no hay cierre de ciclo" y no venderlo como cableado.

## 5. Prueba de genericidad

Crear una instancia **ficticia** (otro mes, otra mecánica, sin los elementos particulares de hoy) y
correr la máquina completa en dry-run. Las constantes clavadas se delatan como fallos o como datos
default equivocados en esa corrida.

## Ejemplo real (auditoría del 12-sep-2026, repo marketing-campaign-generator)

Veredicto: **esqueleto genérico, capa de contexto no**. Clavado a la campaña de septiembre:
`guion_session.py:56` (`data/datos-duros.yaml` = T&C de ESA campaña), `:57` (ruta `planning/calendario-sep2026/`),
`:477`/`:511` (producto y jornadas literales), `:259-270` (personajes), `:866`/`:883` (solo dos marcas);
veto por defecto de la campaña en `guion_lint.py`. El handoff al motor
(`scene_plan.py` → `brief.json` → worker `:8090` → `reel_engine.py`) existe y funciona, pero **cero
invocadores** desde el repo: las etapas pagas del script son contabilidad.
Propuesta aceptada como punto de partida: contrato por instancia + filtros iniciales en el CLI.

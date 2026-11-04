---
name: capability-claim-verification
description: "Use when verifying a config or capability claim"
version: 1.0.0
author: curator-ragnar
triggers:
  - "ya esta configurado"
  - "ya quedo configurado"
  - "como funciona para que ustedes puedan X"
  - "tienen la key de Y"
  - "verificar si algo esta configurado"
  - "acceso a secretos desde el contenedor"
tags: [verificacion, read-only, claim, gate, auditoria, config, evidencia, audit]

---

# Capability Claim Verification — verificar «ya está configurado» (read-only, sin costo)

Clase de tarea: alguien (a menudo el CEO/CTO) afirma que una capacidad o credencial **ya quedó configurada** y pide confirmación o pregunta por qué no funciona. El trabajo NO es leer el YAML y decir «sí está»: es producir evidencia de que la capacidad **ejecuta**, o el hallazgo exacto de dónde se rompe la cadena. Construida 11-sep-2026 (caso: «¿Roshi tiene key de Vault? ¿cómo generan imágenes con GPT?»).

Regla base: **habilitado (aparece en la config/summary) ≠ disponible (el gate de runtime pasa) ≠ usado (alguien lo llamó con éxito)**. Reporta siempre en cuál de los tres niveles está el claim.

## 1. Lee el consumidor, no el YAML

Antes de declarar una clave «configurada», abre el plugin/tool que la consume y confirma qué campos lee de verdad:

- ¿Qué env var o clave resuelve? (aquí: `get_secret("OPENAI_API_KEY")` → `<HERMES_HOME>/.env` del perfil).
- ¿Instancia el cliente con `base_url` o sin él? (aquí: `openai.OpenAI(api_key=...)` **sin** base_url ⇒ un `base_url` en config se ignora).
- ¿Qué pasa si el valor no es válido? (aquí: un `model` desconocido degrada al default **sin error**).

Una clave presente pero ignorada es un hallazgo típico («el bloque existe, pero es inerte»). Cita `archivo:linea`.

## 2. El gate real de un toolset es su `check_fn`

`hermes tools --summary` muestra *habilitación* de toolsets, no disponibilidad. Un perfil puede exhibir `🎨 Image Generation ✓` y estar apagado. El gate verdadero es la función de chequeo del tool (imágenes: `check_image_generation_requirements()`), y se lee sin gastar nada:

```bash
cd /opt/hermes && HERMES_HOME=/opt/data /opt/hermes/.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "/opt/hermes")
from tools.image_generation_tool import (check_image_generation_requirements as c,
    _read_configured_image_provider as p, _read_configured_image_model as m, check_fal_api_key as f)
print("provider=", p(), "model=", m(), "fal_key=", f(), "available=", c())
PY
```

Para barrer la flota: `scripts/image_gen_probe.sh [slug ...]` (mismo probe por perfil).

**CLIs que exigen TTY**: `hermes tools` y `--summary` fallan con `requires an interactive terminal` cuando se pipean desde una sesión headless. Envuelve en `script`:

```bash
script -qc '/opt/hermes/.venv/bin/hermes -p <slug> tools --summary' /dev/null | head -30
```

## 3. Verificar un claim sobre SECRETOS / Vault

«¿Tiene key para el vault?» casi siempre revela una confusión de niveles: en esta casa **no existe credencial de vault por perfil**, el acceso es host-level.

- Dentro del contenedor `hermes-agent` **no hay `vw` ni `bw`** y ningún `.env` de perfil tiene `BW_*`: es diseño, no desconfiguración. No reportes eso como fallo.
- Ruta real: SSH al host, donde vive el helper y su credencial root-only (`/root/.bw-bot.env`, 0600):

```bash
ssh -o BatchMode=yes dev '/usr/local/bin/vw list Hermes'              # solo nombres = seguro
ssh -o BatchMode=yes dev '/usr/local/bin/vw get "<item>" -f <CAMPO>'  # pide UN campo
```

- `default`, `roshi` y los especialistas comparten esa misma ruta. Si te piden «la key de vault de <agente>», la respuesta es la ruta, no un item con su nombre.
- Antes de decir «no tiene acceso», reproduce el entorno del perfil sin tocar su sesión: `tr '\0' '\n' < /proc/<pid>/environ | grep -E '^(HOME|HERMES_HOME)='` y exporta ese `HOME` (Roshi corre con `HOME=/opt/data`): `HOME=/opt/data ssh -o BatchMode=yes dev '/usr/local/bin/vw list Hermes'`.
- Inventario: `vw list` (nombres) sirve para afirmar «existe la key FAL / no existe ninguna de OpenAI» sin exponer nada.
- **PITFALL de fuga**: `vw get "<item>"` imprime los VALORES en claro. Si solo necesitas los nombres de campos, enmascara: `... | sed -E 's/:.*/: <oculto>/'`. Nunca pegues la salida cruda en informes ni en chat; si se te escapó, avísale al usuario en la misma respuesta (pasó el 11-sep-2026 con `FAL - API key`).
- La skill `vault-access` es **bundled** (no editable por curador) y describe `vw` como si estuviera en el PATH del contenedor: para agentes dentro de Hermes vale esta sección.

## 4. Cero costo para verificar

Prohibido disparar una generación/locución/llamada de pago «para comprobar». Config + código del consumidor + gate de disponibilidad son evidencia suficiente. Si el usuario además quiere una prueba en vivo, cita el costo unitario del proveedor y pide OK explícito **antes**. (Regla dura de la casa: proveedores de pago solo con autorización humana previa.)

## 4.1 Preguntas de inventario («¿qué APIs de X tenemos para Y?»)

Pregunta típica (11-sep-2026): «mira en el vault la API de fal.ai y dime qué APIs de GPT tenemos para generar imágenes». La respuesta correcta separa SIEMPRE tres capas, porque se mezclan a propósito en la pregunta:

1. **Qué existe upstream** — catálogo en vivo del proveedor, gratis y sin key: `GET https://fal.ai/api/models?keywords=<kw>` (público; `items[]` trae `id`, `category`, `publishedAt`, `modelFamily`, `pricingInfoOverride`; params `page`/`size`). Filtra en Python por `id`/`modelFamily` y no vuelques el JSON crudo. La API de plataforma `api.fal.ai/v1/models` exige una key válida en `Authorization: Key <FAL_KEY>`, así que para descubrimiento usa el catálogo público.
2. **Qué soporta NUESTRA herramienta** — la tabla `_MODELS` del consumidor (`tools/image_generation_tool.py` para `image_gen`). Un endpoint nuevo puede existir en el proveedor y no estar en la tabla ⇒ la tool no lo puede pedir.
3. **Qué alcanza NUESTRA credencial** — de dónde sale la key y a quién apunta de verdad (ver pitfall de prefijos).

Entregable: endpoints disponibles + qué soporta Hermes nativo + qué exigiría curl directo o patch de código. No recomiendes «el más nuevo»: recomienda el que ya es soportado.

## 4.2 «Tenemos la api de X y el gate de gasto» — verificar un gate de gasto

Segunda capa de la misma pregunta (caso 11-sep-2026, repo `marketing-campaign-generator`): el usuario afirma que existe la integración **y** el gate. El trabajo es demostrar **qué línea evalúa el gate y desde qué entrypoint**, no encontrar el archivo.

- **Un archivo de gate puede ser decorativo.** `grep -rn "\.<name>-gate\|\.<name>-gate.json" --include="*.py" --include="*.sh" .` — si no devuelve consumidores, el gate es inerte y hay que reportarlo como hallazgo (caso real: `.monid-gate.json` existía y **nadie lo leía**; el gate real de Monid vivía dentro de `reel_engine.py` como `approved_to_spend` + `max_cost_usd` del brief).
- **Barre los entrypoints que pueden gastar**, no solo el canónico: `for f in scripts/*.py; do grep -ciE 'gate|approved_to_spend|max_cost' $f; done`. Los scripts ad-hoc suelen gastar con solo tener la key en el entorno (aquí 7 de 9 scripts Monid con 0 hits de gate; el cliente de imágenes flux, 0).
- **Los gates viven en tres capas**: código (`fal-client.py:54-96` → `.fal-gate.json`, TTL 6 h, rechaza `approved_by` ∈ {agent, ragnar, assistant}, `sys.exit(3)` antes del POST), datos (schema del contrato: `approved_to_spend`, `max_cost_usd`) o ninguna.
- **Gate vencido = gate cerrado**: lee `expires_at` del archivo y dilo; un run live aborta. Y un `--dry-run` que retorna antes del gate no prueba que el gate pase.
- **Drift de relocalización** (auditoría de estado del repo): tras mover un repo, revisa (a) units systemd con rutas absolutas — `systemctl is-active` = `activating (auto-restart)` + restart counter alto + `WorkingDirectory` inexistente ⇒ servicio caído aunque el README diga «activo ✅»; (b) rutas viejas hardcodeadas en tests/scripts ⇒ fallos de suite que NO son regresiones; (c) `__pycache__`: los `.pyc` conservan la ruta de compilación y el traceback muestra la ruta vieja — confirma en el fuente.
- **Correr la suite de un repo**: desde DEV por SSH (`ssh dev 'cd <repo> && python3 -m pytest tests/ -q'`): el contenedor no tiene `pytest` y los venvs del repo tampoco. Los tests son offline; reporta el conteo exacto y separa fallos de entorno de los funcionales.

Detalle completo del caso: `references/spend-gate-and-repo-state-audit.md`.

## 4.3 «¿Ya estamos listos para operar X?» — readiness de un pipeline multi-servicio

Cuando el claim no es «está configurado» sino «¿podemos empezar a producir?», la evidencia debe recorrer la cadena completa (idea → guión → prompts → escenas → voz → publicación) y nombrar **el primer eslabón roto**. Caso 11-sep-2026: campaña `bingo-sep2026` / generador de reels (worker systemd, engine, ActivePieces, portal, calendario).

Método que funcionó:

1. **Mapea tú primero** (≤5 lecturas batcheadas) y reparte por subsistema: 2–4 subagentes read-only en paralelo, uno por subsistema (scheduler/AP, portal, guión→escenas). Dales rutas exactas, los hechos ya establecidos («no los repitas, úsalos como base») y la lista de prohibiciones.
2. **Los hijos recogen, tú reconcilias.** Sus resúmenes son self-reports: re-verifica por tu cuenta cada afirmación que sostenga la decisión. Anticipa la atribución cruzada — un hijo reportó mi propio job de prueba como «otro auditor»: di cuáles corridas fueron tuyas.
3. **Un reviewer fresco con TUS claims** (no un checklist genérico), pidiéndole falsificar: veredicto por afirmación `[CONFIRMADO|REFUTADO|PARCIAL|NO VERIFICABLE]` + comando exacto + dato crudo. Plantilla: `templates/fanout-audit-reviewer-prompt.md`.

Sonda decisiva y gratuita: **corre la ruta real de producción con el paso pago simulado** —`POST /jobs` al worker con `dry_run` como campo de PRIMER NIVEL (no dentro del contrato)—. Recorre refine→TTS→mix→audit→concat sin costo y el último éxito registrado es el punto de ruptura. Escribe artefactos en el repo y en `jobs.jsonl` (gitignored): decláralo y límpialo.

Para localizar la causa, **A/B del input sospechoso** (mismo job con y sin el campo): el log del servicio trunca el traceback del subproceso, así que la arqueología de logs no cierra el diagnóstico.

Cierre: costo por corrida (con la advertencia de tarifa NO verificada si el proveedor cobra distinto de lo documentado), qué bloquea una decisión humana y qué bloquea dinero.

Detalle del caso, la receta de la sonda y los tres defectos que encontró: `references/pipeline-readiness-audit-2026-09-11.md`.

## 4.4 La sonda E2E gratuita: cómo se hace bien (y cómo se escapó a live el 11-sep-2026)

La sonda decisiva de 4.3 tiene un modo de fallo caro, documentado por el propio autor del plan:

- **`dry_run` hay que ponerlo EXPLÍCITO como campo de primer nivel** del payload del worker. Omitirlo **no** cae en dry-run: la corrida sale **LIVE**. Primer chequeo antes de dejar correr nada: la primera línea de `logs.jsonl` → `job_started {"mode": "dry_run"|"live"}`. Si dice `live`, ya estás en la ruta de pago.
- **`approved_to_spend` es el gate de VALOR del contrato, no el de gasto** — y desde 11-sep-2026 su semántica es **LIVE-only**: en `dry_run` NO aplica (exigirlo ahí impedía verificar el pipeline sin firmar: corregido en `reel_engine.run_brief` a `if not dry_run and brief.get("approved_to_spend") is not True`). En live sí lo exige, y el gasto real lo cierra el gate **FÍSICO** en el choke point del POST. Si el dry-run de un repo aborta con `SpendGateError` por `approved_to_spend=false`, es la versión vieja del chequeo: la corrección es exactamente esa condición. Confundir los dos gates es el agujero que la sección 4.2 ayuda a encontrar — no lo introduzcas tú al probar.
- **El payload del worker ES el brief**, con `dry_run`/`live` como campos de PRIMER NIVEL (no anidados): `{**brief, "dry_run": true}`. Enviar `{"dry_run": true, "brief": {…}}` devuelve **400** y, si además extraes mal el `job_id` de la respuesta, ves `status: None` en bucle — parece «el job no arranca» cuando en realidad el POST fue rechazado. Confirma el contrato en `reel_worker.py:_handle_post_jobs` antes de culpar al engine, y verifica con el log que el engine deja en disco.
- **Forense de gasto: pregúntale al proveedor, no a tu log.** `GET https://api.monid.ai/v1/runs?limit=25` (Bearer `MONID_API_KEY`) → `items[].{runId,createdAt,status,endpoint,cost}`. «0 corridas con la fecha de hoy» es evidencia verificable de cero cargo; `/v1/credits|balance|usage` dan 404. Con eso se cierra la pregunta «¿me gastó dinero el intento?» sin especular. El mismo endpoint es la **fuente de verdad del precio real**: seedance-2.0-mini 6 s cobró $0,68–$0,99/clip mientras la tabla del repo decía $0,456 (subestima 1,5–2×) ⇒ presupuesta desde el historial, no desde la tabla.
- Reporta cualquier escape a live **en la misma respuesta**, con la evidencia y sin adornos: un intento live no autorizado es un incidente aunque el cargo sea $0.

Receta completa (payload, token, verificación del modo, A/B del campo sospechoso, lectura del historial del proveedor): `references/worker-dry-run-and-charge-forensics.md`.

## 4.5 Del hallazgo al plan: unidades de trabajo verificables

Una auditoría que termina en un informe se pierde. El entregable que el usuario pide después («diseña un plan quirúrgico para dejar el repo impecable») tiene forma fija:

1. **Definición de "hecho" con condiciones numeradas y verificables** (no adjetivos). P. ej. «un solo intérprete», «cero rutas muertas», «cero ramas huérfanas» — cada una con el comando que la prueba.
2. **Hallazgos priorizados** (P0 bloquea producción / P1 fiabilidad / P2 higiene), cada uno con su evidencia y su `archivo:linea`.
3. **Unidades `WU-nn`** agrupadas en fases, cada una con: objetivo · entregable · **criterio de aceptación** · **evidencia (comando + salida esperada)** · riesgo y mitigación. La evidencia no puede ser tautológica («correr el script que arreglé»); tiene que poder fallar.
4. **Secuencia y camino crítico** explícitos: qué desbloquea a qué (suele haber UNA unidad prerequisito de casi todo: el entorno reproducible).
5. **No-goals** para acotar («no se toca X, no se gasta sin firma»).
6. **Riesgos globales con mitigación** y, cuando el cambio toca producción, el backup y el rollback.
7. **Verificación del plan ANTES de ejecutarlo**: pasar el plan a un modelo externo con un prompt que le prohíba elogiarlo y le exija huecos, errores de orden, riesgos mal mitigados, criterios débiles y un top-5 de cambios. Plantilla: `templates/plan-review-prompt.md`; **runner listo**: `scripts/nan_review_stream.py`. Incluye en el prompt los hechos ya verificados («no los cuestiones, úsalos») para que no gaste el presupuesto re-verificando lo que ya sabes, y pídele que diga explícitamente lo que NO puede juzgar en vez de inventarlo.

   **Revisar CODIGO (no solo el plan) en 3 tajadas paralelas** (11-sep-2026, `glm5.3-flash` x3 sobre el repo de reels: veredictos 5/10, 6/10, 6,5/10 -> 1 CRITICO + 5 ALTOS + 13 MEDIO/BAJO que el autor no habia visto). El modelo no ejecuta comandos: juzga lo que le pegas, asi que reparte el material (~40-50 KB por revisor) y lanza los tres a la vez:
   1. **Codigo nuevo** (archivos completos + su contrato + sus tests) -> pide bugs reales, **FALSOS VERDES** (¿puede decir OK con algo roto?), casos limite, que falta para produccion.
   2. **Cadena de gasto/seguridad** (el diff + el modulo del gate completo) -> pide "vias de gasto: via -> ¿gate? -> linea exacta" y combinaciones de flags que producen gasto real.
   3. **Claims vs evidencia** (tu LISTA DE AFIRMACIONES + la EVIDENCIA CRUDA pegada) -> veredicto por afirmacion. **Es la tajada que mas incomoda**: ahi se detecta que una afirmacion propia («0 archivos con dueno ajeno») la invalida la evidencia nueva que tu mismo aportas.
   Runner generico: `python3 /opt/data/scripts/nan_reviewer.py <prompt.md> <out.md> [max_tokens]` (>=20000, `temperature 0.2`, streaming obligatorio). Plantillas listas de las 3 tajadas: `templates/code-review-slices-prompt.md`; caso completo (slicing, tiempos medidos, taxonomia de los 19 hallazgos y como cerrar el ciclo): `references/independent-code-review-slices.md`.

   **Diseña bien el corte:** la tajada 3 devolvio "insuficiente" para los claims sobre el gate porque **el codigo del gate estaba en la tajada 2**. Si una afirmacion depende de codigo, pega el fragmento minimo en su tajada o dile al revisor que eso lo audita otro.

   Tres trampas del modelo de razonamiento (verificadas 11-sep-2026 con `glm5.3-flash` vía `api.nan.builders`):
   **sin `stream: true`** Cloudflare corta a los 120 s (**HTTP 524**); el pensamiento viaja en **`delta.reasoning_content`** (respuesta final en `delta.content`) y **consume `max_tokens`** — con 20 u 8000 tokens devuelve **texto vacío con `finish_reason: length`**, usa ≥40000; y el modelo contesta en el idioma del prompt (pide español explícitamente o revisará en inglés. Medido: 178 s, 13.462 caracteres de informe + 42.021 de razonamiento). Con `stream: true` y `max_tokens: 40000` funciona a la primera; el script deja la respuesta y el razonamiento en dos ficheros separados.

   **El revisor externo se lee, no se obedece:** devuelve 2-3 correcciones que cambian el plan (p. ej. «con push al final, el servicio seguiría corriendo el código viejo durante la producción» → añade una unidad de integración/despliegue **antes** del hito, como excepción explícita a la regla). Incorpora cada una como cambio concreto en el plan y deja la trazabilidad de lo aplicado.
8. **Detalle de implementación atado al artefacto real**, no a un ideal: si el plan incluye un parser, describe la anatomía real del fichero que va a parsear (cabeceras y columnas exactas, verificadas leyendo un ejemplar real).

Si el plan es paralelizable, la capa de aislamiento se describe aparte: ver la skill `agent-worktree-orchestration`.

## 4.6 «¿Está conectado el orquestador?» — auditoría read-only de ActivePieces

Cuando el claim es «el pipeline automático ya funciona», separa **estructura** de **tráfico real**: un flow puede estar `ENABLED` con versión publicada válida y **no haber corrido nunca**. No son lo mismo «está montado» y «está operando».

- La fuente es la **DB, no la UI**: contenedor **`ap-db`** (no `ap-postgres`), `psql -U postgres -d activepieces`.
- Las columnas son **camelCase** (`"publishedVersionId"`, `"flowVersionId"`, `"displayName"`, `"logsFileId"`) → en SQL van **entre comillas dobles** o la consulta falla con `column does not exist`.
- Las tres tablas que deciden el veredicto: `flow.status` (`ENABLED`/`DISABLED`), `flow_version.valid` (¿la publicación es válida?) y `flow_run` (¿corrió?, ¿con qué resultado?).
- **El historial manda**: agrupa `flow_run` por flow y estado con su última fecha. Si el único flow con corridas de hoy es otro (caso 11-sep-2026: solo el de pagos Bre-B), el resto está muerto *aunque diga `ENABLED`* — y un flow con `valid = f` es un zombi que nadie debería poder disparar.
- `trigger` es un **objeto** jsonb, no un array (`jsonb_array_length` revienta): usa `v.trigger->>'name'` y `jsonb_pretty(v.trigger->'settings')`.
- Todo webhook es un **gatillo cargado**: enumera triggers desde la DB, nunca sondees la URL (un GET lo dispara).
- Los pasos del flow **no** están en `flow_version.actions` (esa columna no existe en esta versión): si necesitas el destino de un paso HTTP, léelo del estado serializado del flow o de los logs del run.

Receta SQL exacta, quoting, la trampa del heredoc y el snapshot de la flota: `references/ap-flow-db-audit.md`.

## 4.7 De la auditoría a la implementación: cerrar una unidad de trabajo

Cuando el usuario pasa de «audita» a «procede con el plan», la mitad del trabajo (construir) no está en el informe. Lo que se verifica igual que antes es cada `WU`, y el orden no es negociable: **primero lo que desbloquea todo, después lo gratis, y solo al final lo que cuesta**.

1. **Mide gratis lo que el proveedor cobraría caro.** Un guión puede declarar 60 s y narrar 105 s y nadie lo nota hasta el montaje. Se detecta antes de producir: sintetiza la locución con `edge-tts` (gratis) y mide con `ffprobe`. Umbrales que funcionan: narración que excede su ventana en **> 0,75 s** = error (dando los segundos exactos de exceso y el % de aceleración que lo arreglaría); < 55 % de la ventana = aviso de aire muerto. Caso real 11-sep-2026: G2 Tunja declaraba 60 s y medía **105,2 s** (escena 3: 56,1 s en una ventana de 26 s).
2. **Antes de los clips pagos, el animatic gratis.** Renderiza el draft 3D (three.js) por escena para validar encuadre y ritmo a coste $0; su `keyframe.jpg` alimenta además al refiner como imagen base. Requisito real: un chromium que funcione headless — el del sistema puede ser un *snap* inútil headless (receta y pitfall en `references/free-preview-before-spend.md`).
3. **El planner NUNCA abre el gasto.** El brief que genera el puente sale con `approved_to_spend=false` y `max_cost_usd=0` por defecto: si alguien corre el motor sin subir el tope, no puede gastar. La firma sigue siendo humana y física.
4. **Convierte el puente guión → brief en código, no en copy-paste.** Parsea el guión real, normaliza sus formatos vivos, valida contra el contrato del motor y emite el brief. Cuando el lint falla, el puente **se niega a generar** (exit 1) — ese «no» es la prueba de que el guardia funciona, así que enséñalo como evidencia.
5. **Verifica por el SERVICIO, no solo por el CLI.** Reinicia el worker, postea el job (`dry_run`) y comprueba manifest + log del engine. Son dos afirmaciones distintas: «el CLI produce el reel» y «el servicio corre este código» (fecha de arranque del PID vs hash del repo). Reiniciar es obligatorio: un worker no recarga el código que arreglaste.
6. **La salida runtime no ensucia el repo.** Si el `base` del worker vive dentro del árbol (aquí `assets/`), cada job deja carpeta nueva y `git status` se llena: añade reglas de `.gitignore` **por patrón de proyecto** y comprueba en el mismo turno que los **inputs** siguen rastreados (`git check-ignore -v assets/<marca>/view/front.png` debe NO devolver nada).
7. **Higiene de ramas con precondición probada.** Antes de borrar una rama (local o remota): `git merge-base --is-ancestor <tip> main` **y** `git rev-list --count main..<rama>` = 0. Ambas, no una. Cita el hash del tip antes de borrar.
8. **Un default invertido es una regresion silenciosa: audita TODOS los llamadores.** Caso real 11-sep-2026: al pasar el motor a `dry-run` por defecto, el worker dejo de pasar el modo y **un job `live: true` corria dry en silencio** (manifest `simulation: true`, sin error). Reglas: (a) el modo viaja **siempre explicito** por el borde (`--live` / `--dry-run`); (b) conflicto de flags = error del que llama (400), nunca "el ultimo gana"; (c) test de contrato en el borde que afirme el flag exacto ("un job live DEBE llevar `--live`"); (d) `--dry-run` **gana** sobre `--live` si vienen juntos (fail-safe).
9. **Cuando el bueno es un parser, prueba el caso que corrompe en silencio.** Una celda de tabla markdown con un `|` sin escapar se partia en columnas extra y el parser **descartaba el resto sin avisar** (el pie legal llegaba cortado al artefacto final). Regla: si sobran columnas, **recomponer + avisar**; nunca descartar texto en silencio. En general: para todo campo opcional por item, prueba el caso AUSENTE y el MALFORMADO, no solo el feliz.

Caso trabajado completo (formatos de guión, mapeo de beats y el runner de medición): `references/guion-brief-bridge.md`.

## 5. Forma del entregable

1. Veredicto por claim, en la primera línea: «X sí (ruta Y) / Z no, en ningún perfil».
2. Evidencia por claim: comando + salida (provider/model/gate, `archivo:linea` del consumidor, inventario del vault).
3. Qué NO se hizo: «no se cambió config, no se ejecutó ninguna llamada de pago».
4. Opciones de arreglo con costo, una recomendación concreta y la pregunta puntual que desbloquea el cambio (impacto alto ⇒ esperar «Dale»).

Tono: escéptico y específico. Un claim no verificado se reporta como no verificado, nunca como OK.

## 6. Cuando el usuario pregunta «¿ya quedó?»

Corolario de la regla base, y el error más caro de esta clase de tarea: **nunca redondees hacia arriba**.

- Responde con un **cuadro hecho/pendiente**, cada línea con su evidencia (hash de commit, comando, salida) — y si falta algo, dilo **antes** de cualquier logro: «No, todavía no». El usuario detecta el maquillaje y a partir de ahí desconfía de todo el informe.
- Cada pendiente lleva **qué bloquea** en una línea (no solo que falta): así la lista se vuelve decisiones, no inventario.
- **Push por bloques verificados.** «Solo ediciones locales, luego hacemos push» **no** significa retener todo hasta el final: significa no ensuciar `main` con trabajo a medias. Con el árbol limpio (0 ficheros sin registrar) y la suite verde, el bloque se pushea — el usuario acabó pidiéndolo explícito («pushea hasta ahora lo que hiciste») después de haber dicho «cuando esté todo listo». Un push de un bloque cerrado es reversible; un commit que se queda meses en local, no.
- **Nunca cierres con superlativo antes de que un tercero lo haya intentado romper.** 11-sep-2026: reporte «656 tests verdes, repo impecable» y el reviewer independiente tumbo 19 cosas, incluido un bug ALTO que yo mismo habia introducido en ese cambio. Si el usuario tiene como estandar el reviewer independiente, ofrecelo TU antes de decir «listo», y usa «verificado por mi: X» en vez de adjetivos absolutos.
- **Mide con el MISMO usuario/proceso que va a sostener el estado.** Corri la suite como root y afirme «0 archivos con dueno ajeno»; mis propias corridas root posteriores crearon 5 archivos root e **invalidaron mi afirmacion**. Convencion: `setpriv --reuid=hermes --regid=10000 --clear-groups env HOME=/tmp/hermes-home TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/ -q --basetemp=/tmp/pytest-hermes`. Y avisa de los tests NO hermeticos: uno que verifica `~/.config/...` del HOME de root falla al correr como el servicio (depende de HOME por diseno, no es una regresion).
- **Aprobación de gasto por etapas, no en bloque.** Ante una producción que cuesta dinero el usuario suele aprobar por fases («no firmo, vamos paso a paso: primero los gratis, luego las imágenes, y ahí sí las escenas»). Estructura el trabajo para que **cada etapa tenga un artefacto que él pueda mirar** (draft gratis → still barato → clip pago) y pide firma **por etapa y con monto acotado** — nunca un presupuesto global de una vez.
- Separa siempre **lo que el actor hizo** de **lo que el sistema observó**: «commit local hecho» y «servicio sirviendo ese commit» son dos afirmaciones y se prueban distinto (fecha de arranque del PID vs hash del repo).

## Pitfalls

- **Un GET a un webhook de ActivePieces DISPARA el flow.** Nunca sondees un webhook «para ver si está vivo» (un subagente lo hizo y produjo 2 corridas). Los triggers se enumeran desde la DB (`flow_version.trigger`), y toda URL de webhook es un gatillo cargado.
- **Dos intérpretes, dos juegos de dependencias.** Un servicio puede correr `.venv/bin/python` mientras el operador escribe `python3`; el módulo que falta en el OTRO es la caída real. Chequea en ambos: `for py in python3 .venv/bin/python; do $py -c "import X"; done`.
- **Un `.venv` INCOMPLETO no es un `.venv` FALSO** (corrección de mi propio diagnóstico, 11-sep-2026). Un venv legítimo tiene `bin/python` como **symlink al intérprete base** (`python3 → /usr/bin/python3.12`): eso es lo normal, **no** un wrapper, y confundirlo lleva a cirugía innecesaria. Lo que decide es (a) `cat .venv/pyvenv.cfg` (¿existe?) y (b) **probar el import con CADA intérprete candidato**: `for py in python3 .venv/bin/python /usr/bin/python3; do $py -c 'import X'; done`.
  Modos reales vistos: (i) venv legítimo cuyo **único** paquete de terceros era `edge_tts` porque **no existía ningún manifiesto** — sin `requirements.txt`/`pyproject.toml` las deps no están declaradas en ninguna parte, y eso explica de golpe por qué «falta una dependencia distinta en cada intérprete» y por qué ningún worktree de orquestador puede correr el pipeline; (ii) venv del contenedor con `site-packages` de 3.12 y un intérprete 3.13 → no importa nada.
  Arreglo completo (medir la superficie con AST → `requirements.txt` fijado → `bootstrap.sh` con modo `--check` que verifica imports **y binarios de sistema**): `references/python-runtime-reproducibility.md`.
- **Un cliente que acepta `--image` puede estar mandando una RUTA LOCAL como `image_url`.** El éxito local no prueba nada: lee el payload builder y confirma que el proveedor recibe una URL alcanzable. Clase de defecto que pasa todos los tests y falla en la primera corrida live.
- **Prueba el caso AUSENTE de los campos opcionales por ítem.** Campos «requeridos si vienen» (`edits`, `cover`, `audio`) revientan el pipeline cuando se omiten; el síntoma observable es un job que nunca obtiene manifest (`GET /jobs/<id>` → 404 «manifest aún no disponible»), que se lee como «el job desapareció» y no como «el engine murió».
- **Subagentes: `write_file` fuera de `HERMES_WRITE_SAFE_ROOT` (`/host:/opt/data`) se rechaza** y el hijo reportará ese check como fallido. Instruyelos a trabajar read-only en vez de dejar archivos temporales en `/tmp`.
- **`platform_toolsets` ausente NO implica falta de toolsets** (corrige el diagnóstico de 09/09/2026): verificado 11-sep-2026 en `roshi` (config sin ese bloque) → 17/27 con Terminal, Code Execution, File, Image Gen, Browser, Cron, Delegation ✓. La ausencia cae a los presets `hermes-<plataforma>` (core tools). Nunca inyectes `platform_toolsets` para «arreglar» un perfil sin medir antes con `hermes -p <slug> tools --summary`.
- **APIs detrás de Cloudflare**: `GET /models` sin UA de navegador devuelve 403 — eso es el WAF, no la key. Reintenta con UA Chrome antes de concluir que la credencial murió.
- **No confundir el modelo de imagen con el proveedor**: que el catálogo del proxy tenga un modelo de imagen no significa que el plugin sepa usarlo (y viceversa).
- **Colisión de prefijos de key**: el `.env` puede declarar `OPENAI_API_KEY` con el prefijo de OTRO proveedor (caso real: `sk-JzB…` = NaN-Builders, que solo sirve `flux-2-klein`). Antes de afirmar «tenemos OpenAI», compara el prefijo con el de las keys conocidas y busca `OPENAI_BASE_URL` en el mismo archivo. Y si la línea está **comentada** (`# FAL_KEY=`), el entorno NO tiene esa key: la fuente real es el vault. Un `grep -l` de presencia no distingue activa de comentada — lee la línea.
- **Vault de secretos ≠ vault de documentación**: «mira en el vault» puede significar Vaultwarden (`vw list`, host-level) o `/opt/vault/*.md` (docs). Son fuentes distintas y pueden divergir: al 11-sep-2026 `/opt/vault/APIS-INTEGRACIONES.md` no mencionaba fal.ai aunque la key existe en Vaultwarden. Revisa ambas y dilo si divergen.
  **Y la bóveda de docs es de SOLO LECTURA** en el runtime del contenedor (`mount` ext4 `ro`; además `write_file` la bloquea por estar fuera de `HERMES_WRITE_SAFE_ROOT` = `/host:/opt/data`). No intentes escribir documentación nueva ahí: va al **repo del proyecto** (`docs/arquitectura/<TEMA>.md` + `docs/arquitectura/assets/…`) o a `/opt/data/`. Si ya escribiste una ruta de la bóveda en memoria/chat, corrígela en la misma respuesta.
- Si la capacidad depende de un script de repo (p. ej. el pipeline de reels usa `scripts/nan_client.py` con `NAN_API_KEY`) y no del toolset de Hermes, dilo explícitamente: son dos cadenas distintas y el claim suele mezclarlas.

## Soporte

- `scripts/image_gen_probe.sh` — probe read-only de disponibilidad de `image_gen` por perfil (sin generación, sin costo).
- `scripts/nan_review_stream.py` — runner del revisor externo (documento → informe + razonamiento crudo) con las
  tres trampas de los modelos de razonamiento resueltas (streaming, canal de razonamiento, `max_tokens`).
- `templates/fanout-audit-reviewer-prompt.md` — prompt del reviewer independiente para auditorías multi-servicio (claim por claim, falsificación, prohibiciones, formato de veredicto).
- `references/image-gen-backends-20260911.md` — caso trabajado: semántica de `image_gen` (plugins openai/fal, tiers y precios), por qué un bloque apuntando a NaN es inerte, y el estado real de la flota.
- `references/spend-gate-and-repo-state-audit.md` — caso trabajado: inventario de gates de gasto de un repo (gate físico vs gate inerte vs gate en datos), estado del repo tras relocalización y cómo correr su suite desde DEV.
- `templates/plan-review-prompt.md` — prompt del reviewer externo (modelo sin herramientas) para demoler un plan técnico antes de ejecutarlo: veredicto, huecos, orden, riesgos, criterios débiles y top-5 de cambios.
- `references/worker-dry-run-and-charge-forensics.md` — caso trabajado: sonda E2E gratuita contra un worker HTTP (payload con `dry_run` de primer nivel, verificación del `mode` real, A/B del campo sospechoso) y forense de gasto contra el historial de corridas del proveedor cuando la prueba se escapa a live.
- `references/pipeline-readiness-audit-2026-09-11.md` — caso trabajado: readiness de extremo a extremo del generador de campañas/reels (worker, engine, ActivePieces, portal, calendario), con la sonda E2E gratuita y los tres defectos que bloquean la generación de escenas.
- `references/python-runtime-reproducibility.md` — caso trabajado: cómo diagnosticar y cerrar un runtime incompleto (venv real vs falso, matriz de imports por intérprete, superficie de deps medida por AST, contrato de `bootstrap.sh`, unit del servicio apuntando al venv).
- `references/spend-gate-implementation.md` — caso trabajado: cómo se implementa (no solo se audita) un gate de gasto físico — choke point HTTP dentro de cada cliente pagado, import perezoso con fallback de `sys.path`, provider declarado, exit 3 antes de la red, default fail-safe a dry-run y test de exhaustividad.
- `references/ap-flow-db-audit.md` — caso trabajado: auditar un orquestador ActivePieces por DB (flota de flows, `valid` vs `ENABLED`, historial de `flow_run`, triggers) y el patrón de consulta que sobrevive al quoting de `ssh + docker exec`.
- `references/guion-brief-bridge.md` — caso trabajado: puente guión → `brief.json` (los dos formatos de guión vivos, mapeo estructura-de-serie ↔ 7 beats, reglas del linter, umbral de voz y comando de medición).
- `references/free-preview-before-spend.md` — caso trabajado: preview gratis antes de pagar — draft 3D con three.js (chromium headless real, pitfall de arquitectura) y medición de locución con edge-tts.
- `references/independent-code-review-slices.md` — caso trabajado: revisión independiente de CÓDIGO en 3 tajadas (corte del material, tiempos medidos, los 19 hallazgos agrupados y su arreglo, y cómo cerrar el ciclo sin disfrazar los límites de diseño).
- `templates/code-review-slices-prompt.md` — prompts listos (encabezado común + una tajada por bloque) para auditar código con un modelo sin herramientas, con foco en falsos verdes y fallos silenciosos.

---
name: sesion-pieza-por-pieza
description: "Use when producing a campaign video piece-by-piece."
tags: [campanas, reels, gates, costo, produccion, sesion, orquestacion]
version: 1.0.0
author: Roshi
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [campanas, reels, guiones, gates, costo, roshi]
    related_skills: [guion-video-campana, character-sheet-locking, campanas-qa-integridad, gws-shared-access]
---

# Mesa de trabajo pieza-por-pieza (sesión interactiva)

Método para producir cada video de campaña (Golden Game / The Grand Paradise Club) **con Yisus
en el chat**, etapa por etapa: cada etapa cierra con un artefacto barato revisable y **solo se paga
(imagen, clip, audio) cuando todo está congelado**. No es un pipeline autónomo: es un pipeline con
freno de mano humano.

Documento de diseño completo: `workspace/sesiones/DISENO-SESION-INTERACTIVA.md`

## Herramientas (workspace de Roshi)

| Archivo | Qué hace |
|---|---|
| `workspace/sesiones/sesion.py` | Máquina de estados por pieza: `nueva · status · proponer · ok · cambio · candado · gasto · etapas` |
| `workspace/sesiones/datos-duros.yaml` | Candado de datos: mecánica T&C v6 por marca, sedes, vetos, cifras permitidas |
| `workspace/sesiones/lint_texto.py` | Linter gratis de guiones/copys contra el T&C (cifras, frases vetadas, pie legal, duración) |
| `workspace/sesiones/piezas/<pieza_id>/` | Estado + artefactos + bitácora de cada video |
| `workspace/tools/drive_ls.py` | Drive con las credenciales materializadas de ActivePieces (`ls/find/get/export`) |

```bash
cd /opt/data/profiles/roshi/workspace/sesiones
PY=/opt/data/.venv/bin/python   # python3 del sistema NO tiene PyYAML (instalado 12-sep-2026)
$PY sesion.py nueva <pieza_id> --marca golden --tipo reel --slot 2026-09-14T11:00 --deadline 2026-09-13
python3 sesion.py proponer <pieza_id> 0 --nota "..." --archivo piezas/<pieza_id>/00-datos.md
python3 sesion.py ok <pieza_id> 0 --por Yisus --nota "sede = Tunja"     # congela con sha256 del artefacto
python3 sesion.py cambio <pieza_id> 2 --motivo "cambia la sede"          # reabre y avisa qué se regenera y cuánto cuesta
python3 sesion.py candado <pieza_id> --concepto keyframes --usd 0.80 --por Yisus
python3 sesion.py gasto <pieza_id> --concepto keyframes --usd 0.24 --aprobado-por Yisus
$PY lint_texto.py ../piezas/<pieza_id>/02-guion.md --marca golden
```

## Flujo canónico: `scripts/guion_session.py` (repo, 12-sep-2026)

El repo `marketing-campaign-generator` ya trae la **sesión guiada** y es la vía canónica para **CREAR un
guion nuevo** (esto NO modifica guiones existentes: `guion` falla si el archivo ya existe). El `sesion.py`
de este perfil queda como histórico — no duplicar estado en dos máquinas.

```bash
ssh dev; cd /root/marketing-campaign-generator; PY=.venv/bin/python
$PY scripts/guion_session.py nueva <pieza> --marca golden [--sede X]   # precarga del calendario
$PY scripts/guion_session.py sedes --marca golden                       # válidas (marca las CERRADAS)
$PY scripts/guion_session.py refs  <pieza>                              # set de imágenes de guía + faltantes
$PY scripts/guion_session.py concepto|guion|lint|plan <pieza>           # etapas 1-3 ($0)
$PY scripts/guion_session.py confirmar <pieza> <etapa> --por QUIEN [--nota "..."]
$PY scripts/guion_session.py candado  <pieza> --etapa 5 --usd 0.60 --por QUIEN   # obligatorio si es pagada
$PY scripts/guion_session.py reabrir  <pieza> <etapa> --motivo "..."
$PY scripts/guion_session.py estado [<pieza>]
```

**Lo que el script impone (no es opción):** el **personaje va PRIMERO** en el set de generación (la primera
referencia conserva más textura); el **logo va al final con `fase=post`** porque se **compone**, no se
adjunta al modelo; las etapas **5/8/9 exigen `candado` firmado** antes de tocar cualquier API (y el script
nunca llama a una API paga); `confirmar` firma con **sha256** (soporta carpetas: árbol estable) y exige
firma humana; los datos salen de **`data/datos-duros.yaml`** (T&C v6), nunca inventados.

**Runtime:** siempre el venv del repo en el host (`ssh dev`). Tests: `tests/test_guion_session.py` (21 casos).
Sesiones versionadas en `sessions/<pieza>/` del repo.

## Las 12 etapas (0-4, 6-7, 10-11 GRATIS; 5, 8, 9 PAGAS)

0 datos · 1 concepto · 2 guion · 3 escenas · 4 prompts-imagen → **5 keyframes ($)** →
6 post-imagen (overlays) · 7 prompts-video → **8 clips ($)** → **9 audio ($)** → 10 ensamble → 11 QA+publicación.

Reglas duras: (1) no se avanza si la etapa anterior no está aprobada; (2) toda etapa paga exige
`candado` con presupuesto máximo antes de cualquier llamada a API; (3) un cambio posterior se **reabre**
con `cambio` (nunca se parchea por encima) y el CLI dice si la corrección cuesta $0 o qué hay que regenerar;
(4) cada aprobación va a `bitacora.md` (append-only) — es la materia prima del reporte de producción.

## Regla de oro

**La corrección más barata es la que se hace antes de gastar.** Concepto, guion, escenas y prompts se
aprueban antes de la primera imagen paga. Corregir la locución después de animar el clip = pagar el clip otra vez.
En cada cierre de etapa entregar en el chat: qué se produjo, cuántas piezas pagas harán falta, costo estimado
y la pregunta "¿OK, ajuste o STOP?".

## Pitfalls (aprendidos)

- **Los tests y el linter del repo NO corren con el python del contenedor.** El `.venv` del repo está
  atado al host (su `bin/python` apunta al python 3.12 del host): invocado desde el contenedor revienta
  con `ModuleNotFoundError: No module named 'encodings'`. Para lint/brief/tests: `ssh dev` y
  `/root/marketing-campaign-generator/.venv/bin/python` (o `./scripts/run-tests.sh`). El bundle
  `drive_ls.py` y `sheets_registry.py`
  sí corren con `/opt/data/.venv/bin/python` porque solo usan stdlib.
- **Intérprete obligatorio:** `sesion.py` importa `yaml`; el `python3` del sistema (3.13) no lo tiene → `ModuleNotFoundError: No module named 'yaml'`.
  Correr SIEMPRE con `/opt/data/.venv/bin/python` (PyYAML instalado ahí el 12-sep-2026 con `uv pip install --python /opt/data/.venv/bin/python pyyaml`).
  Síntoma de que se corrió mal: el CLI muere antes de imprimir el estado y la pieza parece "no existir".

- **El guion puede estar desfasado del T&C vigente.** Los guiones de Golden G1-G4 y L0-L1 se escribieron
  antes del T&C v6 (31/08) y dicen "dos bingos por noche" y "$100.000 se reparten igual" si no cae en 53:
  eso es la mecánica DEROGADA (v6 = tres bingos, sin premio de consolación, tabla plástica con créditos activos).
  Correr `lint_texto.py` sobre cualquier guion viejo ANTES de reutilizarlo.
- **`lint_texto.py` revisa solo el texto que va al aire** (celdas de narración y "en pantalla" + bloques citados),
  no las notas: en las notas se nombran los vetos y generaba falsos positivos. Con `--todo` revisa el documento completo.
- Hay **dos formatos de guion vivos**: tabla por tiempo (`| Tiempo | Visual | Narración | En pantalla |`) y
  tabla por campos (`| **Texto en pantalla** | … |`). El linter soporta ambos; los pipes escapados (`\|`) del pie
  legal hay que des-escaparlos antes de partir la fila.
- **Cifras en `K`** ($50K, $100K, $400K): normalizarlas a pesos antes de comparar contra el T&C.
- **Duración vs narración completa:** un guion de 60s puede incluir la narración larga (~104s) con el recorte
  indicado en notas. La duración es AVISO, no ERROR; el ERROR de cumplimiento es cifra/frase/pie legal.
- **El pie legal tiene que estar EN PANTALLA** (celda "Texto en pantalla"), no solo mencionado en las notas.
- El token Drive compartido (`/opt/data/google_token.json`, cuenta de Jonathan) se revoca cada ~7 días:
  usar `workspace/tools/drive_ls.py <tenant> …` con `/opt/data/secrets/<tenant>-drive.json` (refresh_token
  de ActivePieces) en vez de re-autenticar. Tenants: golden, lucky, jonathan, helmer, jacqueline, nancy.
- El estado de las piezas pagas se firma con nombre; Jonathan (Admin) aprueba TODO antes de publicar y su OK
  es el último gate (etapa 11), después del QA-INTEGRIDAD.

## Mapa de assets de referencia (F0 ejecutada 12-sep-2026)

La precisión de una imagen generada depende de las **imágenes de guía**. Ya NO hay que resolverlas a
ojo: están registradas y versionadas.

| Necesidad | Dónde vive | Estado |
|---|---|---|
| Logo oficial | repo `assets/sheets/<marca>/logo/` — golden: `golden-game-casino.png`; lucky: `grand-paradise-club.png` | **locked**. **SOLO los entregados por el dueño** (12-sep-2026): no usar otras versiones ni variantes |
| Personaje | repo `assets/sheets/{golden,lucky}/view/{front,side,back}.png` + `expressions.png` + los character sheets oficiales del dueño en `<marca>/brand/` | **locked** |
| Ambiente de la sede | fuente PRIMARIA: Drive **`Marketing <marca>/Fotos Locales/<Sede>`** (material 2026, fotos **y videos**); `assets/sedes/index.json` guarda IDs y conteos; carpetas 2020-2025 = `fotos_extra` | 311 fotos + 21 videos en 13 sedes ✅ / **sheet de ambiente `missing`** (F1) |
| Producto (cartón/bolinero) | — | `missing` |

**Sedes verificadas (12-sep-2026):** Golden 7 (Pacho 11, Tunja 56, Agua de Dios 8, Carmen 12, Anolaima 15,
Cachipay 12, San Francisco 8) · Grand Paradise 6 (Chiquinquirá 1 = 11, Chiquinquirá 2 = 13, La Calera = 36,
**Calera Gardens = 44** [sede nueva], Tunja = 13, Funza = 72). Raíces: `Marketing Golden`
`1tE9VPKJrwpfLPerLVnHEKgzzhsrgtPBJ` · `Marketing Lucky` `1dsNfnm4go8JzBtwJsOqvOJfkyM5xpBvK`.

**Nota de resolución:** el logo de Golden entregado mide 416×315 px — para overlay en 1080×1920 puede
quedar corto (declarado como `gaps`); el archivo viejo del repo (`assets/golden/Logo final transparente.png`,
500×500, mismo diseño) se conserva **solo** para reproducir el reel v04.

**Regla canon de la placa de Goldie (12-sep-2026):** los rótulos fijos son `GOLDIE` (marquesina superior),
`GG` (emblema inferior) y la pantalla facial (sin letras). El **único variable** es la **placa de nombre**
(etiqueta negra entre la cara y los rodillos): lleva el **nombre del local promocionado** o, si la pieza es
**general de marca**, **las pintas de las cartas** (♠ ♥ ♦ ♣). Sans-serif mayúsculas tracking amplio,
ámbar sobre negro. **Nunca texto inventado por el modelo**: se compone en post-producción; si se genera,
solo el nombre exacto + QA de OCR. Los rodillos (p.ej. `7-7-7` con ♣ ♥ ♣) se declaran por pieza.

**Otras reglas verificadas:** el **logo nunca se genera** (se compone; cartas ENCIMA de la cinta `CASINO`,
el fallo de Pacho salió al revés). Las fotos de sede son **referencia, no material**: traen marcas de
terceros, personas y COVID → de ellas sale un **sheet de ambiente vacío por sede**. Los **landmarks del
pueblo** (plaza, iglesia) se buscan en **internet con fuente** y jamás muestran el local.

**Hueco de contrato:** `contracts/brief.schema.json` NO tiene `reference_images`; hoy el motor acepta UN
`input_image` (recortar/anotar) o `prompt_image` (texto→imagen). Plan y fases en el repo:
`docs/planes/PLAN-REFERENCIAS-Y-ASSETS-2026-09-12.md`.

**Herramientas (perfil):** `workspace/tools/drive_get_media.py <tenant> <file_id> <out>` baja imágenes
(el `export` de drive_ls.py da 403: solo Docs nativos); `drive_upload.py <tenant> <folder_id> <file>`
sube (permiso de escritura **verificado** en la credencial de ActivePieces).

## Arranque desde la campaña (piezas del calendario)

Las piezas del calendario **no se crean a mano**: `sesion.py nueva` acepta el prefijo que ya usa el
`calendario.jsonl` del repo (`golden-0914-reel-nuevo`, `lucky-0914-reel-nuevo`) y la etapa 0 hereda los
pendientes reales (sede, dirección, desajuste de mecánica). Al 12-sep-2026 existen dos sesiones en etapa 0
(`golden-0914-reel-nuevo`, `lucky-0914-reel-nuevo`, slots 14-sep 11:00/11:30) — son el punto de arranque
natural del flujo asistido, no hay que inventarlas.

## Referencias

- `creative/guion-video-campana` — página de producción, prompts Seedance, pitfalls de despliegue.
- `creative/character-sheet-locking` — consistencia de personaje por assets, no por prompts.

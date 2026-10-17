---
name: mapa-de-carpetas
description: >-
  Use when choosing where a file or folder must live Escanea carpetas y regula dónde va qué (VPS, repos, Drive).
tags: [carpetas, folder-map, drive, ruteo, vps, documentos, organizacion, convenciones]
version: 1.0.0
author: Ragnar
triggers:
  - carpeta: mapear / mapa de carpetas / dónde va / estructura de carpetas / folder map
  - escribir: antes de guardar un documento / crear archivo / subir a Drive / colocar informe
  - cliente: deploy agente para cliente / autoconfiguración / onboarding de agente / drive del cliente
  - orden: consistencia / carpetas genéricas / desorganizado / archivo perdido
---

# Mapa de Carpetas — escanear, mapear, rutear, verificar

## Qué resuelve

Archivos guardados en la carpeta equivocada, carpetas nuevas con nombres
genéricos, informes de cliente en un directorio sin propósito. Esta skill
hace que ANTES de escribir cualquier cosa el agente consulte un mapa de
carpetas (fuente única de verdad de rutas) y respete sus reglas.

## Activación (cómo se dispara)

La skill se activa por 3 vías (defensa en profundidad):

1. **Trigger directo** — cuando el usuario menciona "mapa de carpetas / dónde va / folder map / estructura".
2. **Enlace cruzado desde skills de creación** — esta skill está referenciada en: `docx`, `xlsx`, `powerpoint`, `pdf`, `google-workspace` (subida a Drive), `google-drive-access`, `ssot-context-document`, `wiki-entry-creation` y `knowledge-absorption`. Cuando se carga cualquiera de esas para crear un documento, su contenido ordena consultar el mapa antes de guardar → se carga esta skill junto.
3. **Regla global en AGENTS.md** (workspace brain) — "antes de escribir cualquier archivo, consultar el mapa de carpetas". Cubre el caso en que ninguna skill de escritura coincida (p. ej. scripts, notas sueltas, cron output).

Para agentes de cliente desplegados: la skill viene en el perfil limpio y la autoconfiguración le da su mapa de cliente en el primer arranque (ver sección 4).

## Flujo de 4 fases (obligatorio)

```
1. SCAN     → escanear la raíz: carpeta local / repo / Drive (por ID)
2. MAP      → generar/refrescar el mapa: árbol + tabla anotada
3. RULES    → aplicar reglas de ruteo: tipo de documento → carpeta destino
4. VERIFY   → después de escribir: read-back y confirmar ruta correcta
```

## 1. ESCANEAR (backends)

### Local / VPS (árbol de carpetas)
```bash
python3 <SKILL_DIR>/scripts/scan_tree.py /ruta/raiz
# -t solo carpetas (default) · -f incluye archivos · --depth N
# Salida: árbol + rutas absolutas + warning de nombres "genéricos" (nueva, final, copia, sin nombre)
```
`<SKILL_DIR>` = `/opt/data/skills/productivity/mapa-de-carpetas/`

### Repos de código
- `scan_tree.py` para el árbol.
- Si existe grafo: `graphify query --graph /ruta/al/graph.json "listar módulos, paquetes y directorios del repo"` para el propósito de cada carpeta.
- Grafos ya generados de golden-game-landing y ai-platform (ver `REPOS-ARQUITECTURA.md` en `/opt/vault/`).

### Google Drive (por ID de carpeta raíz)
```bash
export DRIVE_TOKEN=/opt/data/google_token.json   # o --token <ruta>
python3 <SKILL_DIR>/scripts/drive_map.py --folder FOLDER_ID
# => árbol de carpetas (+ archivos con --files)
```
- El ID de carpeta es la cadena de la URL de Drive (algunos ya registrados en
  `brain/entities/*.md` de cada cliente: Golden Game, Bendabal, Digital
  Expressions, Guaya Racing).
- Si el cliente no tiene ID registrado → pedirlo antes de escanear.

## 2. MAP (dónde vive el mapa)

Cada mapa vive en **dos lugares**:
- **Manifest en la raíz:** `carpetas.md` dentro de la propia carpeta que describe
  (p. ej. `/opt/data/brain/carpetas.md`).
- **Registro central:** `/opt/data/brain/folder-maps/<raiz>.md` (un archivo por raíz).
  El registro central es el que se consulta SIEMPRE antes de escribir.

Formato del mapa (plantilla en `templates/mapa-carpetas.md`):

```md
# 📁 Mapa de carpetas — <Raíz / Cliente>
## Árbol
<árbol generado>
## Carpetas
| Ruta / ID | Propósito | Qué va aquí | Qué NO va | Ejemplos |
|-----------|-----------|-------------|-----------|----------|
## Reglas de ruteo
| Tipo de documento | Carpeta destino | Regla de nombre |
|-------------------|-----------------|-----------------|
## Prohibiciones
```

## 3. RULES (las reglas de la casa)

1. **Antes de escribir CUALQUIER archivo/documento → consultar el registro:**
   leer el mapa de la raíz destino en `/opt/data/brain/folder-maps/`. Prohibido inventar rutas.
2. **Un documento de cliente → carpeta del cliente.** Golden → carpetas Golden,
   Lucky → Lucky, Bendabal → Bendabal, y así para cada cliente. JAMÁS en carpeta genérica.
3. **BLOQUEO drástico de carpetas nuevas:** si la carpeta no existe en el mapa →
   **NO crearla.** Pedir autorización al Admin: ruta propuesta, propósito, ejemplos.
   Solo después de aprobación se crea y se registra en los dos lugares del mapa.
4. **Nombres descriptivos (kebab-case):** `AAAA-MM-DD_tipo_cliente_descripcion.ext`
   Ejemplo: `2026-08-19_informe_golden_landing.docx`. Prohibidos: "nuevo", "final2",
   "copia", "sin nombre", "aqui".
5. **Un cambio legítimo de estructura → se registra el mapa ANTES de mover archivos.**
6. **Verificar el resultado:** si el archivo quedó fuera del mapa (p. ej. autocompletado
   al /tmp, en HOME, en otra carpeta) → MOVERLO a la ruta correcta y anotar el error
   en el log del mapa para corregir la causa.

## 4. Multiagente / autoconfiguración (agentes de cliente desplegados)

`mapa-de-carpetas` es **parte del perfil limpio** de cada agente de cliente
(lista de ~15 skills en skill `hermes-production-deployment`). En la autoconfiguración
(onboard), el agente nuevo en su primer arranque EJECUTA:

1. Recibe `DRIVE_ROOT_ID` del cliente (se pide durante onboarding).
2. Corre `drive_map.py --folder DRIVE_ROOT_ID` y escribe su propio `carpetas.md`
   en el perfil (p. ej. `/opt/data/profiles/<cliente>/carpetas.md`).
3. Escribe 3-5 reglas de ruteo específicas del cliente derivadas del árbol real.
4. Desde entonces TODA escritura del agente pasa por su mapa.

Regla de clientes: carpeta Drive/ por cliente; el mapa también cubre rutas locales
sensibles (`.env`, credenciales) que jamás se suben a Drive.

## Pitfalls

- **Token de Google Drive:** no usar token crudo con urllib (401); usar
  `googleapiclient` (refresca solo). Token en `/opt/data/google_token.json`.
- **`gws` puede no estar instalado:** usar el script `drive_map.py` (patrón probado de
  google-drive-access) o `google_api.py drive search "'<FOLDER_ID>' in parents"`.
- **Duplicados en Drive** (carpeta/archivo en 2+ ubicaciones): el mapa se genera desde
  la raíz del cliente; si hay duplicados, listarlos y marcar cuál es el oficial.
- **No reescanear todo en cada respuesta:** SCAN al inicio de un proyecto, en la
  autoconfiguración o cuando algo no está en el mapa — no por defecto.
- **Estructuras NO-FS (wikis, Notion, BD):** el mapa también cubre colecciones de
  Outline. Antes de crear docs: escanear el árbol real con la API (`documents.list`),
  registrar el mapa doc→lugar en la wiki misma (doc hijo del hub de arquitectura),
  y aplicar ruteo estricto. Pitfall probado 2026-08-27 (wiki.neuralcrewlabs.com):
  resolver hubs por substring hace que "VPS" matchee "VPS Producción — Inventario"
  y `documents.move` devuelve 400 al anidar un doc bajo sí mismo → usar
  matching EXACTO normalizado (minúsculas, sin acentos, sin puntuación).
- **Carpeta host root-owned (p. ej. `/opt/data/brain/folder-maps/`):** `write_file`
  la deniega y docker `-v` sobre el archivo NO persiste en el host → escribir el
  mapa en la herramienta destino (wiki/Drive) y anotar el bloqueo de permisos.
---
name: campaign-script-revision
description: "Use when revising campaign scripts with client feedback."
tags: [guiones, revision, revision, feedback, campanas, vetos, locucion, state.db]
---

# Revision de guiones y copy de campaña (ciclo con feedback del cliente)

Clase de tarea: el cliente (p. ej. Jemadiar/Gescom en Bingo Millonario) manda apuntes de revisión por rondas ("cambia X por Y", "mejora el guion", "no estás usando tus skills", "entregá la versión final en .md"). Este skill define el ciclo completo, de la reconstrucción de la versión vigente a la entrega verificada.

## Pasos

1. **Cargar skills ANTES de reescribir.** `neuralcrew-campaign-content` + `humanizer` + `anti-slop-final-check` (y su `references/` de campaña). Este cliente audita explícitamente el uso de skills y lo reclama cuando se salta — no es opcional.

2. **Reconstruir la última versión aprobada desde el historial de chat, no solo del archivo.** Los .md en `plans/` pueden quedar atrás del texto que se mostró en la ronda anterior. Receta que funcionó (lectura del state.db del perfil, modo solo-lectura):
   ```python
   import sqlite3
   conn = sqlite3.connect("file:/opt/data/profiles/<perfil>/state.db?mode=ro", uri=True)
   rows = conn.execute("SELECT id, role, content FROM messages WHERE session_id=? ORDER BY id ASC", (sid,)).fetchall()
   ```
   - La columna `timestamp` (epoch) existe; `created_at` NO — falla la consulta.
   - Filtrar por `role in ("user","assistant")` y truncar con `substr()` antes de imprimir: las filas `tool` contienen blobs enormes que inundan el output.
   - El `session_id` de la sesión activa se ve con `session_search`; los mensajes entrantes del chat llevan `[Nombre]` como prefijo del autor.
   - Reconstruir así toda la cadena de feedback (v2 → tono amable → voz del local → regla de fechas → vetos) antes de tocar una palabra.

3. **Aplicar los vetos en TODOS los masters, no solo en la respuesta del chat.** Grep programático (`plans/`, `workspace/`) del término vetado + variantes ("pana"/"panas", "bote"), reemplazar, y re-grep con límite de palabras (`\bbote\b`) hasta que quede en cero. Distinguir en el reporte: menciones *como nota del veto* (permitidas) vs dentro del texto del guion (falla).

4. **Verificar duración de locución calculando, nunca asumiendo.** Contar palabras por bloque de narración y dividir a ~2.6 palabras/segundo (ritmo cálido de locución en español). Los tiempos de la tabla del archivo suelen estar mal heredados de versiones cortas — si el conteo no cuadra, recalcular la tabla o dejar explicitada la versión recortada (qué frases caen), sin tocar nunca fechas ni cifras de premios.

5. **Entregar como archivo .md propio en `plans/`** (`GUION-<sigla>-<pueblo>-FINAL.md`) con esta anatomía, en orden:
   - Header: campaña · pieza/formato/duración · versión + fecha · **changelog de cambios de esta versión** (el cliente los pidió explícitos)
   - Estructura de serie (4 tiempos validados)
   - Ficha del pueblo con fuentes (dato verificable o no va)
   - Tabla escena por escena: Tiempo | Visual | Narración | En pantalla
   - Bloque de narración copiable para locución (con tiempos)
   - Notas de producción: recorte a 30s, overlays compartidos con posters, música, hashtags (3-5), **lista de vocabulario vetado**
   - Cumplimiento: constantes T&C (horario, escalonado, cartón condicionado) + pie "+18 Juego responsable | Regulado por Coljuegos" intacto
   - Cierre: pieza interna, nada se publica externo sin aprobación Full.
   Enviar el archivo como MEDIA en el chat.

6. **Persistir el veto donde sobreviva la sesión.** Memoria de marca (reglas de voz + palabras vetadas). Si la skill de campaña es root-owned y el write es rechazado, la memoria es el respaldo legítimo — reportar el fallo de permiso al usuario sin convertirlo en regla permanente.

## Pitfalls

- **Los ejemplos del revisor son targets de tono, no ediciones literales** ("No tomes las líneas como cambios literales a realizar"). Analizar el tono (primera persona del local, tuteo cercano, como atender en el mostrador) y reescribir con esa voz.
- **Expresiones artificiales ya corregidas por el cliente (Jemadiar 28/08) — no repetir en ningún guion nuevo:** "no te dejo tirar en/de la máquina" → "no pares de jugar en tu máquina"; "si tu cartón canta" → "si completas tu cartón antes o en la balota 53". Criterio general: que hable como el cliente real del mostrador, no como reglamento ni como metáfora de copywriter.
- Fechas SIEMPRE explícitas en cada mención (viernes 4, 11, 18, 25/09 + final 02/10); "todos los viernes" suena a ciclo infinito y fue corregido.
- Formato de cifra que pidió el cliente para el tope: `$1'600.000` (apóstrofo), y la forma larga del acumulado: "un acumulado que puede llegar a alcanzar el $1'600.000 en nuestra última jornada".
- No confiar en la duración rotulada en el archivo; recalcular con conteo de palabras (paso 4).
- Al corregir un archivo que se leyó paginado, leerlo completo antes de sobreescribirlo; para cambios puntuales, `patch` con contexto único.
- Verificación final programática antes de entregar: assert de que los vetos no aparecen en el texto del guion y de que cada constante T&C (fechas, $400.000, $100.000, 53 balotas, pie legal) está presente.
- `skill_manage(action='patch')` con `file_path` requiere igualmente el argumento `name` de la skill; omitirlo da "Skill '' not found".

## Verificación

Entregable = archivo .md escrito y verificado (hash ok), grep de vetos en cero sobre todos los masters, asserts de constantes, y en el chat: los cambios aplicados con antes/después + ruta del archivo + la decisión pendiente que le toca al cliente.

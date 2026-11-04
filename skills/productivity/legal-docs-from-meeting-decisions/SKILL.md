---
name: legal-docs-from-meeting-decisions
description: "Use when legal docs track mutating meeting decisions."
tags: [legal, docx, reuniones, transcripciones, versionado, drive, verificacion]
version: 1.0.1
author: hermes
license: internal
metadata:
  hermes:
    tags: [legal, docx, reuniones, transcripciones, versionado, drive, verification, campañas]
triggers:
  - "actualizar T&C / política / documento legal de una campaña a partir de las notas o transcripción de una reunión"
  - "el cliente cambió de opinión varias veces y no podemos poner información errónea en los archivos"
  - "regenerar versión nueva de documentos legales y borrar/retirar las obsoletas"
  - "verificar que un .docx generado contiene/excluye frases exactas sin falsos positivos"
---

# Documentos legales derivados de decisiones de reunión que mutan

## When to Use

- El contenido de un entregable legal (T&C, políticas, bases de promoción) debe actualizarse a partir de notas/transcripción de una reunión con el cliente.
- La campaña acumula reversiones de decisiones entre versiones y hay riesgo de generar desde una decisión obsoleta.
- Hay que publicar la nueva versión (Drive, carpetas de otros agentes) y retirar las viejas de forma trazable.
- Hay que verificar que un .docx generado contiene/excluye frases exactas sin falsos positivos de regex.

Clase de tarea: el contenido de un entregable legal (T&C, políticas, bases de promoción) no lo
dicta un spec fijo sino decisiones tomadas en reuniones con el cliente, donde las decisiones
se revierten de una sesión a la siguiente. El riesgo real no es la redacción: es **generar
desde una decisión obsoleta o de un resumen automático que dice lo contrario de lo acordado**.
Validado en Bingo Millonario (Golden + Lucky), agosto-septiembre 2026, 3 reversiones en 1 semana.

Para la sustancia jurídica colombiana cargar `colombia-juegos-promocionales`; para calidad de
producción del .docx, `documentos-legales-entregables`. Ambas son user-owned — si están
desactualizadas no parcharlas: recomendar `hermes curator adopt` y mantener la mecánica vigente
en las `references/` de ESTA skill.

## Flujo (orden estricto)

1. **Leer transcripción COMPLETA + notas automáticas por separado.** Los resúmenes automáticos
   (Gemini «Decisiones», Meet notes) pueden resumir LO CONTRARIO de lo acordado (caso real:
   resumen decía «el acumulado continuará acumulándose sin fecha de pago»; la transcripción
   00:39 y las cláusulas que el operador dejó intactas al revisarlas probaban «se paga sí o sí»).
   La transcripción manda. Las frases que el operador NO tocó al corregir una cláusula son
   evidencia de aprobación implícita.
2. **Rastrear reversiones.** Cuando la mecánica cambió entre versiones, listar qué cambió y
   cuándo fue la última palabra. Nada de versiones previas se reutiliza sin confirmar vigencia —
   copys y piezas viejas derivan de mecánica obsoleta y reinfectan documentos nuevos.
3. **Contradicciones → preguntar ANTES de generar.** El Administrador lo pidió explícitamente
   («analiza muy bien cuáles fueron las decisiones finales... pregúntame cualquier cosa que no
   te quede clara antes de pasar a realizar los documentos»). Usar clarify con opciones plausibles
   y la lectura recomendada marcada primero; UNA segunda ronda solo si surgen ambiguos de segundo
   orden. Entregar el análisis de decisiones finales ANTES de los archivos.
4. **Generar desde un builder parametrizado** (dict de config por empresa para campañas
   multi-operador) y versionar el número en el propio texto del documento («Versión: N.0»).
5. **Verificación programática sin falsos positivos** (pitfall abajo) antes de reportar.
6. **Publicar y retirar:** subir la nueva versión a las carpetas Drive del cliente, dar permiso
   «reader» a quien tenga el link, mandar a papelera las versiones anteriores en Drive, limpiar
   los archivos obsoletos locales donde se pueda (algunos mounts quedan read-only — anotarlo,
   no forzar), y actualizar la carpeta de consulta para otros agentes (p. ej. `agy-docs/` con
   LEEME.md + versiones .md legibles) borrando las versiones viejas.
7. **Actualizar la referencia de esta skill** con la mecánica vigente en cuanto se confirma.
   La referencia desactualizada es el riesgo #1 de reinfección.

## Pitfalls

- **Dirección inversa T&C→creatividades (03/09):** las piezas de marketing (posters, guiones, reels, copies) se derivan de la mecánica legal, NO al revés. Si el T&C cambia, las creatividades que citan la mecánica vieja quedaron **ilegalmente viejas** (ver protocolo en `marketing-campaign-pipeline`). Dirección correcta: T&C (fuente) → campaign.yaml → piezas.
- **El nombre del script NO indica la versión del doc:** `builder v7` puede emitir un archivo `_v6.docx` si el contador de versión va dentro del texto/documento y no se sincroniza con el builder. Siempre verificar la línea "Versión: N.0" DENTRO del docx generado, no asumir por el nombre del script. Verificar con `docx-render-verification`/pdftotext la línea de versión real antes de declarar el número.
- **Falsos positivos en verificación negativa:** un regex tipo `consolación[^.]*100\.000`
  cruza ítems de lista distintos cuando ambos aparecen en el anexo («premio de consolación
  ELIMINADO» + «$100.000» del bingo corto legítimo). Anclar cada check a SU ítem/frase
  (buscar la frase completa: `no existe premio de consolación ni premio parcial` es OK;
  `100\.000[^.]*consolación` NO). Si un check falla, imprimir el match con contexto antes
  de concluir que el documento está mal.
- **`execute_code` sandbox no tiene python-docx**: correr el builder y el validador con
  `uv run --with python-docx python3 - <<'EOF' ... EOF` desde terminal.
- **Archivos creados por root en mounts compartidos** (p. ej. `/opt/data/brain/folder-maps/`):
  no escribibles desde sesiones hermes aunque el directorio lo sea. No forzar chmod de archivos
  ajenos; dejar el registro de vigencia en una ruta propia y anotarlo.
- **Versiones viejas zombies:** borrar solo donde hay permiso; en Drive usar trash (`trashed:
  true`) en vez de delete permanente. Declarar en el reporte qué quedó en papelera y con qué id.
- DOCX renombrado a .pdf sigue siendo DOCX (ver skill de entregables).

## Referencias

`references/bingo-millonario-mecanica-v6.md` — mecánica VIGENTE + rastro de reversiones
de la campaña que validó este flujo; usar como fuente de verdad hasta que el Admin confirme
un cambio posterior.

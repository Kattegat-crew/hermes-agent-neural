---
name: docx-generacion-verificacion
description: "Use when generating or verifying DOCX deliverables."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
metadata:
  hermes:
    tags: [docx, python-docx, verificacion, entregables, qa]
    category: creative
    related_skills: [campaign-ops, docx-render-verification]
---

# Generación y auto-verificación de DOCX entregables

Clase: cualquier DOCX entregado a cliente o Admin (propuestas, cuentas de cobro, planes, membretes)
generado con `python-docx`, y el paso de QA que garantiza que el archivo en disco cumple las reglas
de negocio cerradas con el cliente.

## Regla 1 — extraer TODO el texto, no solo párrafos

**`doc.paragraphs` NO incluye las celdas de tablas.** Un verificador solo-párrafos da falsos
negativos (o falsos positivos) según dónde quedó el texto. Receta de extracción completa:

```python
texts = [p.text for p in doc.paragraphs] \
      + [c.text for t in doc.tables for r in t.rows for c in r.cells]
```

Todo check (assert, búsqueda de frase vetada, conteo de volumen, presencia de decisión) corre sobre
esa lista combinada. Caso que lo originó: `falta volumen de contenido` sobre un dato que vivía en la
tabla "Contenido del mes" de la propuesta final (21-sep-2026). Detalle en
`references/docx-tablas-vs-parrafos.md`.

## Regla 2 — el generador lleva sus asserts de negocio

Cada decisión cerrada con el cliente = un check booleano embebido en el script generador que falla
RUIDOSAMENTE (AssertionError con el nombre de la regla) si el DOCX no la cumple: permanencia,
volumen de contenido, exclusiones, fechas, ausencia de marcadores `[POR CONFIRMAR]`. Cierre del
script: `OK parrafos=N tablas=M bytes=X`. Así una regeneración nunca deja caer una decisión en silencio.

## Regla 3 — re-verificación en frío contra el archivo en disco

Después de regenerar, re-verificar el `.docx` real con python-docx (párrafos + celdas, Regla 1),
no la memoria del script: checklist item por ítem (`permanencia: OK`, `excluye personal: FALTA`…).
Un ítem en FALTA es hallazgo abierto — la entrega no se declara completa hasta repararlo.

## Workflow clase: decisiones en bloque → entregable → estándar → estructura

Cuando el cliente/Admin cierra varias decisiones de golpe:
1. Lista numerada de decisiones (dato duro, no transcripción cruda).
2. Regenerar el entregable con los asserts embebidos (Regla 2).
3. Si el patrón se va a repetir (carpetas, assets, jerarquía): PRIMERO fijar el estándar en
   `docs/arquitectura/ESTANDAR-*.md` y LUEGO instanciar la estructura desde el estándar. Nunca carpetas ad-hoc.
4. Commitear los artefactos juntos para que el diff sea auditable.

## Pitfalls

- `AssertionError: falta volumen de contenido` con el texto visible en el DOCX ⇒ check corriendo
  solo sobre párrafos (Regla 1).
- No declarar "verificado" desde la corrida del generador: la evidencia es la re-lectura en frío del
  archivo en disco (Regla 3).
- Los paraguas que absorben entregables de campaña (campaign-ops) viven en `skills.external_dirs` y
  no aceptan escritura autónoma; este skill cubre la parte técnica reutilizable.


---

## Procedencia

Absorbido por F3 el 20260923-055337 desde la autoskill `data/skills/specialists/docx-generacion-verificacion` (sin versión en git hasta hoy).
El procedimiento se conserva íntegro; el paraguas `informes-cliente-pipeline` es su punto de entrada.


---
name: improve-codebase-architecture
description: >-
  Auditoría y escaneo de módulos superficiales en el repositorio. Generación de reportes visuales en HTML con Mermaid y Tailwind para proponer refactorizaciones hacia módulos profundos.
tags: [arquitectura, auditoria, refactorizacion, deep-modules, reporte, calidad]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
license: MIT
platforms: [linux, macos, windows]
---

# Auditoría y Profundización de Arquitectura de Código

Habilidad canónica para escanear un repositorio en busca de fricción estructural y proponer **oportunidades de profundización**: refactorizaciones quirúrgicas que transforman módulos superficiales y dispersos en módulos profundos, altamente cohesivos y testeables.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"audita la arquitectura de este proyecto"*, *"encuentra código espagueti o mal estructurado"*, *"dónde tenemos deuda técnica modular"*, o *"genera un reporte de arquitectura"*.
- Repositorios con alta tasa de cambios recientes donde se percibe aumento de complejidad accidental (*software entropy*).
- Preparación previa a una iniciativa mayor en SDD (fase de descubrimiento técnico antes de `01-spec.md`).
- Sesiones de mantenimiento preventivo o revisión periódica de salud del código.

---

## Proceso de Auditoría y Detección de Fricción

### 1. Exploración Basada en Hotspots de Git
No escanees el repositorio a ciegas: aplica el principio YAGNI y prioriza las zonas de cambio activo.
- Si el usuario especificó un módulo o directorio, enfócate directamente en él.
- Si no hay dirección previa, analiza los últimos 30-50 commits (`git log --oneline -50`) para identificar las áreas con mayor frecuencia de cambios y colisiones.

### 2. Detección de Síntomas de Superficialidad
Busca activamente:
- **Módulos superficiales**: Clases o archivos con muchas firmas públicas pero lógica insignificante (pasarelas redundantes).
- **Falta de localización**: Funciones que obligan a los consumidores a coordinar 4 o 5 llamadas en un orden estricto para lograr una sola acción de negocio.
- **Fugas a través de costuras (seam leaks)**: Módulos supuestamente aislados que acceden directamente a estructuras internas de otros componentes.
- **Dificultad de testeo**: Zonas del sistema que no cuentan con tests o cuyos tests requieren mocks excesivos.

Aplica el **test de eliminación**: Si al borrar el módulo la complejidad desaparece, era código superficial prescindible; si la complejidad se dispersa en los consumidores, merecía consolidarse como módulo profundo.

---

## Generación del Reporte Visual en HTML

Para no contaminar el repositorio con archivos temporales, el reporte se genera como un archivo autónomo en `/tmp/architecture-review-<timestamp>.html`.

El reporte utiliza:
- **Tailwind CSS** vía CDN para maquetación limpia y legible.
- **Mermaid.js** vía CDN para diagramas de dependencias, secuencias y flujo de llamadas.
- Estructura de tarjetas con:
  - **Archivos involucrados**: Rutas exactas en monoespacio.
  - **Problema detectado**: Una frase concreta sobre la causa de fricción.
  - **Solución propuesta**: Descripción clara del módulo profundo resultante.
  - **Ganancias**: Beneficios en apalancamiento, localización y reducción de tests.
  - **Diagrama comparativo Antes / Después**: Visualización lado a lado de la simplificación.
  - **Nivel de recomendación**: `Fuerte`, `Vale la pena explorar`, o `Especulativa`.

Para los detalles de plantilla HTML y estilos, consulta [`HTML-REPORT.md`](HTML-REPORT.md).

---

## Flujo de Grilling y Enlace con SDD

Una vez que el usuario revisa el reporte y selecciona un candidato:
1. Conduce una entrevista técnica rápida (*grilling*) sobre invariantes, interfaces deseadas y dependencias a encapsular.
2. Si la refactorización es aprobada para ejecución en un repositorio con SDD, formula la iniciativa en Git bajo `.specs/<nombre-iniciativa>/` (`01-spec.md` → `02-design.md` → `03-tasks.md`).
3. Registra la decisión arquitectónica en Engram con `engram save --type architecture`.

---
name: ssot-context-document
description: "Use when consolidating project context into one doc."
tags: [ssot, contexto, documentacion, drive, consolidacion, informe, empresa]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [ssot, drive, consolidation, context, documentation, informe]
    category: productivity
    related_skills: [client-landing-onboarding, informe-maestro-update, brain-knowledge-base, gdrive-ingestion, google-workspace]
---

# SSOT Context Document — Single Source of Truth desde Múltiples Fuentes

Crear un documento integral que consolide TODO lo que se sabe sobre un proyecto/empresa en un solo archivo markdown, subido al Drive.

**Cuándo usar:**
- "haz un doc con todo el contexto de NeuralCrew Labs"
- "pon todo lo que sabemos de X en un solo documento"
- "crea un resumen integral del proyecto"
- "quiero un informe completo de todo lo que tenemos"

**NO usar cuando:**
- Es un cliente nuevo específico → usar `client-landing-onboarding`
- Es una actualización incremental del Informe Maestro → usar `informe-maestro-update`
- Es solo para el agente (no humano) → usar `brain-knowledge-base`

---

## Pipeline

### Fase 1: Inventario de Fuentes

Identificar TODAS las fuentes disponibles antes de escribir una línea:

1. **Google Drive** — leer el folder indicado listando archivos con Drive API vía requests + google_token.json
2. **Memoria persistente** — leer MEMORY.md vía `memory` tool y `read_file`
3. **Brain Graph** — consultar con `python3 /opt/data/tools/memory_graph.py "<pregunta>"`
4. **Session history** — `session_search()` para sesiones previas relevantes
5. **Documentos clave en Drive** — descargar .docx/.md y parsear con `document-reader` skill

### Fase 2: Extracción y Parseo de Documentos

Usar `document-reader` skill para cada documento encontrado:

```bash
python3 /opt/data/skills/document-reader/scripts/parse_document.py /ruta/al/archivo.docx --format text
```

Para Google Docs nativos, exportar como texto plano usando `google_api.py`.

Guardar todo el contenido extraído en `/opt/data/tmp/` para referencia durante la compilación.

### Fase 3: Compilación del Documento SSOT

Estructura probada para documentos integrales de empresa/proyecto:

1. **Identidad Corporativa** — qué es, misión/visión, equipo humano, ecosistema de logos
2. **Guía de Estilo** — paleta de colores (HEX), tipografías, efectos UI
3. **Catálogo de Productos/Servicios** — tabla con módulos, qué hace cada uno, problema que resuelve
4. **Infraestructura Tecnológica** — servidores, Docker, plataforma base, dominios
5. **Clientes Activos** — tabla con datos clave de cada cliente
6. **Producto Principal** — spec técnica, arquitectura del sistema, estructura de repos
7. **Inventario de Documentación Creada** — qué archivos existen y dónde
8. **Decisiones Clave Tomadas** — tabla con fecha, decisión, justificación
9. **Roadmap** — corto, mediano y largo plazo
10. **Métricas de Éxito** — KPIs definidos
11. **Canales de Comunicación** — plataformas activas
12. **Reglas Operativas Clave** — principios que rigen la operación

**Reglas de estilo:**
- Usar tablas siempre que haya datos comparables (3+ filas)
- HEADER de nivel 1 solo para el título del documento
- Secciones con ##, subsecciones con ###
- Nada de markdown fancy — solo tablas, listas, bold
- Fecha de generación y fuentes al final

### Fase 4: Subida a Drive

**Antes de subir:** consultar la skill `mapa-de-carpetas` — el destino (`Carpeta/Destino/`) debe existir en el mapa de la carpeta de Drive del cliente, con nombre descriptivo; no crear carpetas nuevas sin autorización.

```bash
python3 /opt/data/skills/productivity/google-workspace/scripts/upload_drive.py \
  /ruta/al/archivo.md \
  "Nombre_Del_Documento.md" \
  --folder "Carpeta/Destino/"
```

**Cuidado con scopes:** El script `upload_drive.py` refresca el token y puede sobrescribir scopes. Si después de subir fallan Calendar/Gmail, hay que revocar y re-autorizar el token desde cero con todos los servicios. Ver google-workspace skill para el procedimiento.

---

## Ejemplo Real: NeuralCrew Labs SSOT

**Fuentes consultadas (7 ago 2026):**
- Drive folder `1yjLxB4lEZe3n79QKK8vlnladPv4FtM7w` (12+ subcarpetas, 20+ archivos)
- Drive folder `1UtKOiuS-Qk_AlboWpBuEfeloAQsh2jns` (archivos ya subidos por el agente)
- MEMORY.md (~9,800 chars de notas persistentes)
- USER.md (~2,000 chars de perfil de usuario)
- Brain Graph (1,708 nodos)
- Session history (15+ sesiones previas)
- Documentos parseados: Manual Maestro v1, Estructura AI Platform, plan ejecutivo casinos

**Resultado:** `NeuralCrew_Labs_Contexto_Completo.md` — 18KB, 12 secciones, archivo en Drive NeuralCrew Labs

---

## Pitfalls

- **No confiar ciegamente en una sola fuente** — si Drive dice X y memoria dice Y, verificar cuál está más actualizada
- **El upload de Drive puede romper scopes** — verificar después de subir que Calendar/Gmail sigan funcionando
- **No incluir datos inventados** — si un cliente no tiene misión/visión, marcarlo como PENDIENTE
- **La memoria puede estar desactualizada** — siempre cruzar con documentos frescos de Drive
- **El document-reader puede fallar en docx complejos** — verificar el output antes de confiar
- **No sobreescribir archivos existentes en Drive** — usar nombre nuevo
- **No preguntar antes de entregar** — el usuario pidió el doc, entregarlo completo. Si faltan datos, marcarlos como pendientes.
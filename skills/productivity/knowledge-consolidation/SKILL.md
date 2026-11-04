---
name: knowledge-consolidation
description: "Use when consolidating raw brain files into scored tables."
tags: [brain, knowledge, tablas, docx, research, consolidacion, archivo]
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [knowledge, brain, consolidation, tables, research]
    category: research
---

# Knowledge Consolidation — de raw/ a tablas accionables

Cuando el usuario pide "consolidar el brain", "haz una tabla con los tweets /
tiktoks / repos que tengo en memoria", o "quiero poder buscar qué herramienta
vimos para X": quiere UN documento con entradas clasificadas y puntuadas, NO
un listado de archivos. Preferencia explícita (16/08/2026): cada fila lleva
enlace, autor, fecha, de qué sirve y puntuación ⭐.

## Workflow

### 1. Clasificar la fuente cruda

En `/opt/data/brain/raw/`, separar por prefijo del filename:

| Prefijo | Tabla destino |
|---------|---------------|
| `twitter-*`, `xfeed_*` | Tweets |
| `tiktok-*` | TikToks |
| `github-*` | Repos |
| `instagram-*` | Instagram |
| carpetas (`golden_game`, `lucky_brothers`...) | Clientes — NO tocar |

Contar primero (ej: 75 tweets · 32 repos · 4 tiktoks) y mostrar el total en el
documento. No asumir que todos los archivos empiezan con los prefijos
esperados — revisar la lista real antes de clasificar.

### 2. Extraer campos (script, no lectura manual)

Leer `head -40` de cada archivo y extraer con regex:
- **URL**: primer `https?://...` (o campo `url:` del frontmatter si existe)
- **Autor**: del filename (`twitter-<autor>`, `github-<repo>`, `tiktok-<creador>`)
- **Fecha**: del prefijo `YYYY-MM-DD`
- **Descripción**: primera línea no-vacía tras el frontmatter
- **⭐**: regex `[⭐🌟✨]\s*(\d+(?:\.\d+)?)`
- **Categoría**: keywords sobre contenido (`hermes`→Hermes Agent,
  `agent`→Agentes IA, `crm`→CRM, `seo`→SEO, `model`→Modelos LLM,
  `video`→Video, `secur`→Seguridad, `cron`→Cron/Jobs, `gui`→GUI/UI)

Hacerlo con execute_code + terminal en lotes, NO archivo por archivo.

### 3. Entregar como .docx (preferencia del usuario)

Los datos estructurados se entregan como Word con python-docx; el .md es para
el repo técnico. Estructura del documento:

1. Título + totales (`75 Tweets · 32 Repos · 4 TikToks`)
2. Tabla Tweets — `[#, Fecha, Autor, Tema, Descripción, Enlace, ⭐]`
3. Tabla Repos — misma estructura
4. Tabla TikToks — `[#, Fecha, Autor, Descripción, Enlace]`
5. Otras entradas (clientes, Instagram, estrategia)
6. Insights: top autores (Counter), distribución por categoría, entradas con
   mayor ⭐, recomendaciones de acción

### 4. Consolidación física posterior

- Mover one-shots irrelevantes a `brain/archive/` (NO borrar directo)
- Promover los útiles de `raw/` a `entities/` o `concepts/`
- El objetivo es searchable a demanda: "qué herramienta vimos que sirve para X"

## Pitfalls

- **No borrar nunca directo**: mover a `archive/` primero. El usuario quiere
  poder recuperar y decidir después.
- **No gastar contexto leyendo 100+ archivos**: usar execute_code con lotes
  (25 archivos por batch) y guardar JSON intermedio en /tmp.
- **Definir `add_bullet` y helpers antes de usarlos** en los scripts de
  generación .docx — un NameError a mitad del script corta la generación.
- **El repo de GitHub del cliente puede ser privado**: sin credenciales
  (deploy key SSH o PAT), el contenedor no puede clonarlo. Ver
  `hermes-production-deployment` skill para el flujo de acceso.

## Related

- `brain-knowledge-base` (user-owned) — implementación del wiki en sí
- `hermes-production-deployment` — despliegue de perfiles con las tablas de
  conocimiento consolidadas

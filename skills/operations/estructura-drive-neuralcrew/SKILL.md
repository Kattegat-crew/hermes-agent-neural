---
name: estructura-drive-neuralcrew
description: Use for any NeuralCrew Drive folder create/organize task.
tags: [drive, estructura, golden, lucky, neuralcrew, clientes]
version: 1.0.0
author: Ragnar
---

# Estructura canónica de Drive (NeuralCrew Labs)

## When to Use

Cargar SIEMPRE antes de crear, mover, renombrar o reorganizar cualquier carpeta o
archivo en el Google Drive de NeuralCrew (clientes o agencia). Prohibido crear
carpetas random fuera de la estructura; si un caso no encaja, proponer a Plon.

**REGLA DURA (Plon, 04-nov-2026): PROHIBIDO crear, añadir o dejar carpetas random.**
Toda carpeta nueva debe encajar en la numeración canónica. Si un caso no encaja,
NO crear nada: proponer la estructura a Plon y esperar su OK.

## Estructura de clientes (idéntica para todo cliente actual y futuro)

```
<Cliente>/            ← Golden (11_0J6plN_FAAtQbpXYf7yT_6Yti27qPk), Lucky (1VqEJY7ZjS2MBTGEpiN6uvQcvkZW5ey3z)
├── 01-contratos/
├── 02-facturacion/<año>/
├── 03-recursos/            (logos, fotos locales, biombos, manual juego responsable)
├── 04-asistente/           (Goldie / Lucky-assistente, character sheets)
├── 05-informes/
│   ├── datos-ventas/       (hojas de ventas — fuente de facts de rendición)
│   └── rendicion-de-cuentas/YYYY-MM/   ← docs + videos del mes; TODO entregable de rendición vive aquí
├── 06-Campañas/            ← carpetas por campaña (YYYY-MM-nombre); marketing viejo NO
├── 07-<landing o sitio>/   ← solo si el cliente tiene repo de landing en Drive
└── 08-Marketing <Cliente> archivo/   ← marketing viejo, solo archivo
```

## Neural Crew Labs (carpeta de la agencia, id 1yjLxB4lEZe3n79QKK8vlnladPv4FtM7w)

```
Neural Crew Labs/
├── Clientes/         ← NO renombrar (links compartidos con clientes); Golden y Lucky viven aquí
├── 01-marca/         (logos NCL, manual de marca, membrete, presentación)
├── 02-finanzas/
├── 03-agentes/       (Hermes-Ragnar, Ragnar-archivos, Workspaces, despliegue de agentes)
├── 04-produccion/    (impresiones, audios, piezas sueltas)
├── 05-informes/      (exploración de mercado, paquetes de rendición anuales)
├── 06-proyectos/     (proyectos internos: calculadora, conmutador, Openclaw Viejo)
└── 07-archivo/       (docs históricos; carpetas gemelas viejas)
```

## Reglas de operación

- Mover/renombrar en Drive vía API: `addParents`/`removeParents` son **QUERY PARAMS** del PATCH, no body (en el body se ignoran con 200 OK). Tras cada reparent RELEER `fields=id,parents`: un 200 sin los padres esperados es fallo silencioso (reparent entre carpetas de dueños distintos puede necesitar permiso y no da error claro).
- Nunca borrar archivos al reorganizar: mover y archivar (`07-archivo` / `08-Marketing ... archivo`).
- Rendición mensual: ver skill `rendicion-mensual-golden-lucky`; subida solo con `APPROVED=1`.
- Meses en rendiciones con formato `YYYY-MM` (se ordenan solos).
- Antes de una migración grande: escanear el árbol con la API y reportar el plan a Plon; mover con verificación de árbol antes/después.
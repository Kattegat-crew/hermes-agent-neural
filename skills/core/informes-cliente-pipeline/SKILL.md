---
name: informes-cliente-pipeline
description: "Use when generating and delivering client reports"
version: 2.0.0
author: NeuralCrew
tags: [informes, reports, clientes, pdf, docx, email, render, entregables]

---

# Informes Cliente Pipeline

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `admin-reporting`
- `data-driven-team-reports`
- `docx-render-verification`
- `email-report-cron-aggregator`
- `email-report-ingestion`
- `html-to-print-rendering`
- `informe-mensual-sheet-pdf`
- `informes-ventas-cliente`
- `kassiuss-informe-parser`
- `local-headless-rendering`
- `pdf-deliverables`
- `pil-ffmpeg-rendering`
- `pipeline-informes-ventas-multimarca`

- `docx-generacion-verificacion`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **admin-reporting**: Ver [references/admin-reporting.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/admin-reporting.md)
- **data-driven-team-reports**: Ver [references/data-driven-team-reports.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/data-driven-team-reports.md)
- **docx-render-verification**: Ver [references/docx-render-verification.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/docx-render-verification.md)
- **email-report-cron-aggregator**: Ver [references/email-report-cron-aggregator.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/email-report-cron-aggregator.md)
- **email-report-ingestion**: Ver [references/email-report-ingestion.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/email-report-ingestion.md)
- **html-to-print-rendering**: Ver [references/html-to-print-rendering.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/html-to-print-rendering.md)
- **informe-mensual-sheet-pdf**: Ver [references/informe-mensual-sheet-pdf.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/informe-mensual-sheet-pdf.md)
- **informes-ventas-cliente**: Ver [references/informes-ventas-cliente.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/informes-ventas-cliente.md)
- **kassiuss-informe-parser**: Ver [references/kassiuss-informe-parser.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/kassiuss-informe-parser.md)
- **local-headless-rendering**: Ver [references/local-headless-rendering.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/local-headless-rendering.md)
- **pdf-deliverables**: Ver [references/pdf-deliverables.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/pdf-deliverables.md)
- **pil-ffmpeg-rendering**: Ver [references/pil-ffmpeg-rendering.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/pil-ffmpeg-rendering.md)
- **pipeline-informes-ventas-multimarca**: Ver [references/pipeline-informes-ventas-multimarca.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/pipeline-informes-ventas-multimarca.md)
- **docx-generacion-verificacion**: generar y auto-verificar un DOCX entregable: extraer tambien las celdas de tabla, asserts de negocio embebidos y re-verificacion en frio contra el archivo en disco — ver [references/docx-generacion-verificacion.md](file:///root/hermes-agent-legacy-docker/skills/core/informes-cliente-pipeline/references/docx-generacion-verificacion.md)
- **entorno-de-generacion**: receta verificada para instalar docx/pdf libs al vuelo en este contenedor — ver [references/entorno-generacion-docx-pdf.md](references/entorno-generacion-docx-pdf.md)

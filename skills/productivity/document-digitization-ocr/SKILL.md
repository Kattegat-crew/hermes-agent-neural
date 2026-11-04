---
name: document-digitization-ocr
description: "Use when OCRing or digitizing scans or PDFs."
tags: [ocr, digitalizacion, pdf, paperless, stirling, pymupdf]
---

# Document Digitization & OCR (routing + servicios self-hosted)

Trigger: llega un documento (PDF, scan, captura) y hay que **convertirlo a texto legible** o **digitalizar un lote de escaneados**. El objetivo es elegir la vía correcta — no prometer OCR donde no hay motor, y no ahogar el contexto leyendo imágenes una por una cuando hay un servicio que lo hace en batch.

## Mapa de capacidad (verificado 09/09/2026)

- **In-stack (DEV):** `pymupdf` (en `.venv`) extrae **solo capa de texto** — instantáneo y exacto, pero NO hace OCR. **No hay motor OCR local** (sin tesseract / ocrmypdf / marker / easyocr / paddleocr). `vision` (visión del modelo) lee páginas escaneadas, pero **una imagen por llamada** → no escala en volumen ni en contexto.
- **Self-hosted en PROD (Tailscale 100.73.30.29):**
  - **Paperless-ngx** → `:3040` (webserver healthy). OCR con **Tesseract, idiomas `spa+eng`**, más gotenberg + tika. Volumen de ingesta: `/opt/paperless/consume` (compose en `/opt/paperless/docker-compose.yml`). DB `paperless/paperless` (`PAPERLESS_DBPASS` en `/opt/paperless/.env`).
  - **Stirling-PDF** → `:3041` (healthy). OCR/manipulación PDF. Su API pide **API key** (`/api/v1/info` → 401 sin credencial).
- Ambas APIs web requieren auth (Paperless `/api/` redirige a login; Stirling 401). La vía **sin token** para ingerir es el **consume folder**.

## Ruteo (elegir por caso)

| Caso | Vía | Por qué |
|---|---|---|
| PDF **con capa de texto** | `pymupdf` (DEV) | Exacto e instantáneo; nada de OCR. |
| **Scan**, pocas páginas | render a PNG + `vision_analyze` | Directo, sin montar pipeline. |
| **Lote grande de escaneados** | **Paperless consume** (PROD) | Batch, automatizado, indexado, buscable; no consume contexto |
| Fallback de Stirling | Stirling-PDF `:3041` | Si Paperless falla; requiere API key |

## Ingesta sin token (Paperless consume)

`ssh prod`, copiar el archivo a `/opt/paperless/consume/`; el consumer lo procesa solo (polling 60s) y OCRa. El texto extraído queda en la DB de Paperless — leerlo por `psql` en `paperless-db` o vía API con un token. (La ruta completa subir→OCR→leer está **configurada y verificada a nivel de servicio**; el round-trip punta a punta aún no se ha ejercitado — confirmar con un doc de prueba antes de depender de él.)

## Por qué no usar OCR nativo para lotes

Sin motor OCR local, "OCR nativo" = el modelo leyendo cada imagen: lento y satura el contexto. Para digitalización masiva, el servicio self-hosted gana en velocidad y escala, y deja el material consultable (búsqueda full-text).

## Relacionadas

- `ocr-and-documents` (bundled) — extracción local pymupdf / marker-pdf, tablas, ecuaciones.
- `document-reader` — parseo de .docx/.xlsx/.pdf varios.

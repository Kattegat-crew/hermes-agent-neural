---
name: coljuegos-research
description: "Use when researching Coljuegos slot manufacturers and METs."
tags: [coljuegos, colombia, casinos, tragamonedas, mets, datos-abiertos]
---

# Coljuegos Research

Investigar el portal de Coljuegos (Gobierno de Colombia, regula juegos de suerte y
azar) para clientes de casinos de NeuralCrew (Golden Game, The Grand Paradise Club, etc.).
Cubre: catálogo de fabricantes/marcas de tragamonedas (METs), país de origen, y datos abiertos.

## Casos de uso
- "Busca en coljuegos el archivo de códigos de cada país de las máquinas" (para etiquetar METs).
- "¿Qué fabricantes/marcas de tragamonedas están autorizados?"
- Consultar datos de operadores, contratos de concesión, loterías, juegos localizados.

## Fuentes y cómo acceder (VERIFICADO 2026-08-19)
- **Portal:** `https://www.coljuegos.gov.co` — responde a `curl` directo con User-Agent
  de navegador (sin el UA bloquea algunas rutas). También funciona por Jina Reader
  (`https://r.jina.ai/<url>`) para HTML, y los PDFs se bajan por `loader.php`.
- **Juegos Localizados:** `/publicaciones/306301/juegos-localizados/` → hay descargas del
  tipo `loader.php?lServicio=Tools2&lTipo=descargas&lFuncion=descargar&idFile=<N>&id_comunidad=portal`.
- **Lista oficial de fabricantes y marcas MET (lo más actualizado):** id `308283`
  → baja `Lista Fabricantes y Marcas MET <MES> <AÑO>.pdf` (ej. "julio 2026", 5 págs).
  Columnas: `CÓDIGO MARCA ACTUAL | NOMBRE MARCA ACTUAL | CÓDIGO MARCA EQUIVALENTE | CÓDIGO FABRICANTE | NOMBRE FABRICANTE`.
- **Datos abiertos:** catálogo Socrata de `datos.gov.co` (API `api.us.socrata.com/api/catalog/v1?domains=datos.gov.co&q=...`):
  dataset `nyam-s74` (juegos localizados/operadores, NO trae país por máquina), `6qgp` (contratos), loterías, etc.

## PITFALL clave: NO existe archivo público de país de origen por máquina
Revisadas las páginas de METs, trámites, "Acerca de los Juegos Localizados", Marcas
Coljuegos y los datasets de datos.gov.co → **Coljuegos NO publica un archivo con código
de país de procedencia por máquina.** El dato vive en su sistema interno (SCLM), no es
público. El listado de fabricantes sí incluye el nombre del fabricante (que suele revelar
la sede, ej. "Aristocrat Technologies Australia") pero no un código país.

**Qué entregar entonces:** mapear país por FABRICANTE desde la lista oficial de fabricantes
(conocido: Aristocrat→Australia, Novomatic→Austria, Zitro→España, Konami→EE.UU.,
Pockaj→Eslovenia, etc.) y marcar los candidatos no confirmados como "verificar" — NUNCA
inventar un código ISO. Si el cliente necesita el código exacto, solicitarlo a Coljuegos.

## Firma de descarga de PDFs
```bash
# 1. Sacar idFile desde la página deseada (grep 'idFile=[0-9]+')
curl -sL -A "Mozilla/5.0" "https://www.coljuegos.gov.co/loader.php?lServicio=Tools2&lTipo=descargas&lFuncion=descargar&idFile=<ID>&id_comunidad=portal" -o archivo.pdf
# 2. Extraer texto:
python3 -c "import pdfplumber, sys; [print(p.extract_text() or '') for p in pdfplumber.open('archivo.pdf').pages]"
```

Recetas concretas de la sesión y URLs exactas en `references/coljuegos-fetch.md`.
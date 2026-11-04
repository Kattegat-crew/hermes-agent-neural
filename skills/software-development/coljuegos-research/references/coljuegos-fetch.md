# Coljuegos — recetas de fetch y URLs exactas (VERIFICADO 2026-08-19)

## Páginas del portal
- Inicio: `https://www.coljuegos.gov.co/`
- Juegos Localizados (hub con las descargas): `https://www.coljuegos.gov.co/publicaciones/306301/juegos-localizados/`
- Trámites para Juegos Localizados: `https://www.coljuegos.gov.co/publicaciones/juegos_localizados__pub`
- Acerca de los Juegos Localizados ("Qué son..."): `https://www.coljuegos.gov.co/publicaciones/localizados_pub`
- METs: `https://www.coljuegos.gov.co/publicaciones/300598`
- Marcas Coljuegos: `https://www.coljuegos.gov.co/publicaciones/marcas_coljuegos_pub` (a veces da ERR_CONNECTION_REFUSED por http; usar https)

## Descarga directa de archivos (loader.php)
Patrón global:
```
https://www.coljuegos.gov.co/loader.php?lServicio=Tools2&lTipo=descargas&lFuncion=descargar&idFile=<ID>&id_comunidad=portal
```
Con `-A "Mozilla/5.0"` y `curl -sL`. La respuesta trae `Content-Disposition: attachment; filename="<nombre>.pdf"`.

IDs verificados la sesión del 2026-08-19:
- `308283` → **"Lista Fabricantes y Marcas MET julio 2026.pdf"** (archivo OFICIAL más actualizado de fabricantes/marcas de tragamonedas; 5 páginas). Es el que se busca para etiquetar máquinas por marca/fabricante.
- `306282` → pago / contrato (no relevante para países).
- `296426` → manual identidad visual marca Coljuegos.
- `305494` → cartón bingo.
- `276528` → requerimientos técnicos SCLM Plus.
- `276851` → contratos de concesión vigentes (2022).

Para AVERIGUAR el idFile de una página: bajar el HTML con un grep de `idFile=[0-9]+`.

## Datos abiertos (Socrata datos.gov.co)
- Catálogo por query: `https://api.us.socrata.com/api/catalog/v1?domains=datos.gov.co&q=<termino>&limit=20`
- Dataset "Juegos localizados (operadores)": id `nyam-s74i` → columnas: codigo_dane, municipio, depto, cod_local, local, est_direccion, nit, operador, contrato. **NO trae país por máquina.**
- `6qgp-wich` = Contratos de concesión de juegos de suerte y azar. `2zg4-ahca`, `usa4-yg4a` = loterías/transferencias.

## Lease del PDF de marcas
Columnas: `CÓDIGO MARCA ACTUAL | NOMBRE MARCA ACTUAL | CÓDIGO MARCA EQUIVALENTE | CÓDIGO FABRICANTE | NOMBRE FABRICANTE`.
El "código de país" NO aparece: los códigos de fabricante son secuenciales (1, 2, 3...) y agrupan marcas. Para país de origen hay que mapear el FABRICANTE (ver SKILL.md).

## Extraer texto de un PDF Coljuegos
Requiere `pdfplumber` (instalado). Los PDFs usan encoding con diacríticos (Ã, Â) — normal.

## Herramientas de red
- `curl` directo por HTTPS funca con UA de navegador.
- `https://r.jina.ai/<url>` (Jina Reader) devuelve el HTML como markdown limpio — útil cuando el sitio bloquea o para leer artículo. No sirve para listas de descargas densas: usar curl directo.
---
name: rube-mcp-api-automation
description: "Use when automating a third-party API via Rube MCP"
tags: [rube, mcp, composio, api, automatizacion, zoho, slackbot, metaads]
requires:
  mcp: [rube]
---

# Automatización de APIs de terceros vía Rube MCP — paraguas de clase

Clase de skill para automatizar **cualquier** API de terceros que tenga toolkit en
Composio, usando Rube MCP. Los casos concretos por proveedor viven en
`references/`, cada uno con su procedimiento íntegro.

## Criterio de decisión

| Si la tarea es… | Usa |
| --- | --- |
| Operar una API de un proveedor **ya cubierto** (Zoho, Slackbot, OneSignal, MetaAds) | el `references/<proveedor>.md` correspondiente |
| Operar un toolkit **nuevo** (sin referencia) | este `SKILL.md`, y al terminar añade su `references/<proveedor>.md` |
| Descubrir qué toolkits o conexiones hay | `RUBE_SEARCH_TOOLS` / `RUBE_MANAGE_CONNECTIONS` |

## Prerequisites

- Rube MCP conectado (`RUBE_SEARCH_TOOLS` disponible)
- Conexión **ACTIVE** del toolkit del proveedor vía `RUBE_MANAGE_CONNECTIONS`
- **Siempre** llamar `RUBE_SEARCH_TOOLS` primero: los esquemas cambian

## Setup

**Obtener Rube MCP:** añadir `https://rube.app/mcp` como servidor MCP. Sin API keys.

1. Verificar que `RUBE_SEARCH_TOOLS` responde
2. `RUBE_MANAGE_CONNECTIONS` con el toolkit del proveedor
3. Si la conexión no está ACTIVE, seguir el enlace de auth que devuelve
4. Confirmar estado ACTIVE antes de ejecutar cualquier workflow

## Patrón de trabajo (idéntico en todos los proveedores)

### 1. Descubrir herramientas

```
RUBE_SEARCH_TOOLS
queries: [{use_case: "<tarea concreta>", known_fields: ""}]
session: {generate_id: true}
```

### 2. Verificar conexión

```
RUBE_MANAGE_CONNECTIONS
toolkits: ["<toolkit>"]
session_id: "your_session_id"
```

### 3. Ejecutar

```
RUBE_MULTI_EXECUTE_TOOL
tools: [{tool_slug: "TOOL_SLUG_FROM_SEARCH",
         arguments: {/* esquema devuelto por la búsqueda */}}]
memory: {}
session_id: "your_session_id"
```

## Pitfalls conocidos (valen para todos los proveedores)

- **Buscar primero**: los esquemas cambian; nunca fijar slugs ni argumentos sin `RUBE_SEARCH_TOOLS`
- **Comprobar la conexión**: `RUBE_MANAGE_CONNECTIONS` debe mostrar ACTIVE antes de ejecutar
- **Cumplir el esquema**: nombres y tipos exactos de los resultados de la búsqueda
- **Parámetro memory**: incluir siempre `memory` en `RUBE_MULTI_EXECUTE_TOOL`, aunque sea `{}`
- **Reuso de sesión**: reutilizar el `session_id` dentro de un workflow; generar uno nuevo por workflow
- **Paginación**: revisar tokens de paginación y seguir hasta completar

## Proveedores cubiertos

| Proveedor | Toolkit | Doc del toolkit | Referencia |
| --- | --- | --- | --- |
| Zoho | `zoho` | composio.dev/toolkits/zoho | `references/zoho.md` |
| Slackbot | `slackbot` | composio.dev/toolkits/slackbot | `references/slackbot.md` |
| OneSignal | `onesignal_rest_api` | composio.dev/toolkits/onesignal_rest_api | `references/onesignal_rest_api.md` |
| MetaAds | `metaads` | composio.dev/toolkits/metaads | `references/metaads.md` |

## Quick Reference

| Operación | Cómo |
| --- | --- |
| Encontrar herramientas | `RUBE_SEARCH_TOOLS` con el caso de uso del proveedor |
| Conectar | `RUBE_MANAGE_CONNECTIONS` con el toolkit |
| Ejecutar | `RUBE_MULTI_EXECUTE_TOOL` con los slugs descubiertos |
| Operaciones masivas | `RUBE_REMOTE_WORKBENCH` con `run_composio_tool()` |
| Esquema completo | `RUBE_GET_TOOL_SCHEMAS` para herramientas con `schemaRef` |

---
*Paraguas de clase creado por F6 lote 1 el 2026-09-23 a partir de 4 skills de una sola
técnica (R15: condensar sin borrar). Las originales, íntegras, en
`data/archive/F6_lote1_20260923-151210/absorbidas/`.*


## Referencias absorbidas
- `references/slackbot.md` — absorbida desde `productivity/slackbot-automation` el 2026-09-23 (F6 lote 1, R15: condensar sin borrar).
- `references/zoho.md` — absorbida desde `productivity/zoho-automation` el 2026-09-23 (F6 lote 1, R15: condensar sin borrar).
- `references/onesignal_rest_api.md` — absorbida desde `software-development/onesignal_rest_api-automation` el 2026-09-23 (F6 lote 1, R15: condensar sin borrar).
- `references/metaads.md` — absorbida desde `specialists/marketing/metaads-automation` el 2026-09-23 (F6 lote 1, R15: condensar sin borrar).


<!-- absorbido de specialists/marketing/googleads-automation (censo 2026-09-24) -->
# Google Ads Automation via Rube MCP


Access Google Ads data through Google Analytics integration, run performance reports, list linked Ads accounts, and analyze campaign metrics using Rube MCP (Composio).

**Toolkit docs**: [composio.dev/toolkits/googleads](https://composio.dev/toolkits/googleads)

### 1. List Google Ads Links for a Property

Use `GOOGLE_ANALYTICS_ANALYTICS_ADMIN_PROPERTIES_GOOGLE_ADS` to retrieve all Google Ads account links configured for a GA4 property.
```
Tool: GOOGLE_ANALYTICS_ANALYTICS_ADMIN_PROPERTIES_GOOGLE_ADS
Parameters:
  - parent (required): Property resource name (format: "properties/{propertyId}")
  - pageSize: Max results (1-200, default 50)
  - pageToken: Pagination token
```

### 2. Run a GA4 Performance Report

Use `GOOGLE_ANALYTICS_RUN_REPORT` to run customized reports with dimensions, metrics, date ranges, and filters.
```
Tool: GOOGLE_ANALYTICS_RUN_REPORT
Parameters:
  - property (required): Property resource (format: "properties/{property_id}")
  - dimensions: Array of dimension objects (e.g., [{"name": "sessionCampaignName"}, {"name": "date"}])
  - metrics: Array of metric objects (e.g., [{"name": "sessions"}, {"name": "totalRevenue"}])
  - dateRanges: Array with startDate and endDate (e.g., [{"startDate": "2025-01-01", "endDate": "2025-01-31"}])
  - dimensionFilter: Filter by dimension values
  - metricFilter: Filter by metric values (applied after aggregation)
  - orderBys: Sort results
  - limit: Max rows to return (1-250000)
```

### 3. Check Dimension/Metric Compatibility

Use `GOOGLE_ANALYTICS_CHECK_COMPATIBILITY` to validate dimension and metric combinations before running a report.
```
Tool: GOOGLE_ANALYTICS_CHECK_COMPATIBILITY
Description: Validates compatibility of chosen dimensions or metrics
  before running a report.
Note: Call RUBE_SEARCH_TOOLS to get the full schema for this tool.
```

### 4. List GA4 Accounts

Use `GOOGLE_ANALYTICS_LIST_ACCOUNTS` to enumerate all accessible Google Analytics accounts.
```
Tool: GOOGLE_ANALYTICS_LIST_ACCOUNTS
Parameters:
  - pageSize: Max accounts to return
  - pageToken: Pagination token
  - showDeleted: Include soft-deleted accounts
```

### 5. List GA4 Properties Under an Account

Use `GOOGLE_ANALYTICS_LIST_PROPERTIES` to list properties for a specific GA4 account.
```
Tool: GOOGLE_ANALYTICS_LIST_PROPERTIES
Parameters:
  - account (required): Account resource name (format: "accounts/{account_id}")
  - pageSize: Max properties (1-200)
  - pageToken: Pagination token
  - showDeleted: Include trashed properties
```

### 6. Get Available Dimensions and Metrics

Use `GOOGLE_ANALYTICS_GET_METADATA` to discover all available fields for building reports.
```
Tool: GOOGLE_ANALYTICS_GET_METADATA
Description: Gets metadata for dimensions, metrics, and comparisons
  for a GA4 property.
Note: Call RUBE_SEARCH_TOOLS to get the full schema for this tool.
```

## Common Patterns


- **Discover then report**: Use `GOOGLE_ANALYTICS_LIST_ACCOUNTS` to find account IDs, then `GOOGLE_ANALYTICS_LIST_PROPERTIES` to find property IDs, then `GOOGLE_ANALYTICS_RUN_REPORT` to pull data.
- **Validate before querying**: Use `GOOGLE_ANALYTICS_CHECK_COMPATIBILITY` to validate dimension/metric combinations before running reports to avoid 400 errors.
- **Campaign performance**: Run reports with dimensions like `sessionCampaignName`, `sessionSource`, `sessionMedium` and metrics like `sessions`, `activeUsers`, `totalRevenue`.
- **Ads link discovery**: Use `GOOGLE_ANALYTICS_ANALYTICS_ADMIN_PROPERTIES_GOOGLE_ADS` to find which Google Ads accounts are linked to each GA4 property.
- **Field discovery**: Use `GOOGLE_ANALYTICS_GET_METADATA` to list all available dimensions and metrics before constructing complex reports.

## Known Pitfalls


- **Dimension/metric compatibility**: The GA4 API has strict compatibility rules. Not all dimensions can be combined with all metrics. Demographic dimensions (e.g., `userAgeBracket`, `userGender`) are often incompatible with session-scoped dimensions/filters (e.g., `sessionCampaignName`, `sessionSource`).
- **`dateRange` is NOT a dimension**: Do not include `dateRange` in the dimensions array. Use `date`, `dateHour`, `year`, `month`, or `week` instead.
- **`exits` is NOT valid**: Neither `exits` as a dimension nor as a metric is valid in GA4.
- **Property ID format**: Must be `properties/{numeric_id}` (e.g., `properties/123456789`). Do not use Google Account IDs (long OAuth IDs).
- **Account ID format**: Must be `accounts/{numeric_id}` where the numeric ID is 6-10 digits.
- **Filter separation**: Use `dimensionFilter` only for dimension fields and `metricFilter` only for metric fields. Mixing them will cause errors.
- **Max 9 dimensions and 10 metrics** per report request.



<!-- absorbido de software-development/googlebigquery-automation (censo 2026-09-24) -->
# Google BigQuery Automation via Rube MCP


Run SQL queries, explore database schemas, and analyze datasets through the Metabase integration using Rube MCP (Composio).

**Toolkit docs**: [composio.dev/toolkits/googlebigquery](https://composio.dev/toolkits/googlebigquery)

### 1. Run a Native SQL Query

Use `METABASE_POST_API_DATASET` with type `native` to execute raw SQL queries against your BigQuery database.
```
Tool: METABASE_POST_API_DATASET
Parameters:
  - database (required): Metabase database ID (integer)
  - type (required): "native" for SQL queries
  - native (required): Object with "query" string
    - query: Raw SQL string (e.g., "SELECT * FROM users LIMIT 10")
    - template_tags: Parameterized query variables (optional)
  - constraints: { "max-results": 1000 } (optional)
```

### 2. Run a Structured MBQL Query

Use `METABASE_POST_API_DATASET` with type `query` for Metabase Query Language queries with built-in aggregation and filtering.
```
Tool: METABASE_POST_API_DATASET
Parameters:
  - database (required): Metabase database ID
  - type (required): "query" for MBQL
  - query (required): Object with:
    - source-table: Table ID (integer)
    - aggregation: e.g., [["count"]] or [["sum", ["field", 5, null]]]
    - breakout: Group-by fields
    - filter: Filter conditions
    - limit: Max rows
    - order-by: Sort fields
```

### 3. Get Query Metadata

Use `METABASE_POST_API_DATASET_QUERY_METADATA` to retrieve metadata about databases, tables, and fields available for querying.
```
Tool: METABASE_POST_API_DATASET_QUERY_METADATA
Parameters:
  - database (required): Metabase database ID
  - type (required): "query" or "native"
  - query (required): Query object (e.g., {"source-table": 1})
```

### 4. Convert Query to Native SQL

Use `METABASE_POST_API_DATASET_NATIVE` to convert an MBQL query into its native SQL representation.
```
Tool: METABASE_POST_API_DATASET_NATIVE
Parameters:
  - database (required): Metabase database ID
  - type (required): "native"
  - native (required): Object with "query" and optional "template_tags"
  - parameters: Query parameter values (optional)
```

### 5. List Available Databases

Use `METABASE_GET_API_DATABASE` to discover all database connections configured in Metabase.
```
Tool: METABASE_GET_API_DATABASE
Description: Retrieves a list of all Database instances configured in Metabase.
Note: Call RUBE_SEARCH_TOOLS to get the full schema for this tool.
```

### 6. Get Database Schema Metadata

Use `METABASE_GET_API_DATABASE_ID_METADATA` to retrieve complete table and field information for a specific database.
```
Tool: METABASE_GET_API_DATABASE_ID_METADATA
Description: Retrieves complete metadata for a specific database including
  all tables and fields.
Note: Call RUBE_SEARCH_TOOLS to get the full schema for this tool.
```


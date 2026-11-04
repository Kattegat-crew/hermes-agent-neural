---
name: twenty-crm-lead-ops
description: "Use when extending Twenty CRM schemas, views or leads."
tags: [twenty, crm, rest-api, metadata, select, views, sql, leads]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Twenty CRM Lead Ops & Schema Automation

Production engineering guide for extending schemas, customizing views, and automating lead lifecycles in self-hosted Twenty CRM.

## Hard Rules

1. **SELECT Field Defaults Must Be Single-Quoted**: In `POST /rest/metadata/fields`, string defaults for `SELECT` enums must be formatted as `"'DEFAULT_VALUE'"` (e.g. `defaultValue: "'NUEVO'"`). Unquoted or double-quoted values fail with `Invalid string default value`.
2. **Multi-Tenant Workspace Isolation**: Always resolve `workspaceId` and object `id` per workspace (`core."workspace"`). Never share Bearer API keys between distinct workspaces.
3. **Search Vector Limitations**: Standard `GET /rest/people?search=<term>` indexes name, email, and phone fragments. When searching by phone, pass clean 7–10 digits without country code prefix. Fall back to email search if phone is missing or unindexed.
4. **View Column Ordering**: Column display order in the UI is governed by `core."viewField".position`. Reorder critical operational columns (`name`, `phones`, `sede`, `status`) to positions 0–4 for instant operational visibility.

## Metadata API Patterns

### 1. Adding a Custom SELECT Field
```bash
POST /rest/metadata/fields
Content-Type: application/json
Authorization: Bearer <TWENTY_API_KEY>

{
  "objectMetadataId": "<person_object_metadata_id>",
  "type": "SELECT",
  "name": "status",
  "label": "Estado",
  "options": [
    { "value": "NUEVO", "label": "Nuevo", "color": "yellow", "position": 0 },
    { "value": "CONTACTADO", "label": "Contactado", "color": "blue", "position": 1 },
    { "value": "REDIMIDO", "label": "Bono Redimido", "color": "green", "position": 2 },
    { "value": "NO_CONTESTA", "label": "No Contesta", "color": "gray", "position": 3 }
  ],
  "defaultValue": "'NUEVO'"
}
```

### 2. Updating Lead Status (PATCH)
```bash
PATCH /rest/people/<person_id>
Content-Type: application/json
Authorization: Bearer <TWENTY_API_KEY>

{
  "status": "REDIMIDO",
  "phones": { "primaryPhoneNumber": "3114490523", "primaryPhoneCountryCode": "CO" }
}
```

### 3. Reordering Columns in View
Update `position` on `core."viewField"` joining on `core."fieldMetadata"`:
```sql
UPDATE core."viewField" vf
SET position = CASE f.name
  WHEN 'name' THEN 0
  WHEN 'phones' THEN 1
  WHEN 'sede' THEN 2
  WHEN 'bonusAmount' THEN 3
  WHEN 'status' THEN 4
  WHEN 'createdAt' THEN 5
  ELSE vf.position + 10
END
FROM core."fieldMetadata" f
WHERE vf."fieldMetadataId" = f.id AND vf."viewId" = '<view_id>';
```

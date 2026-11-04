---
name: oauth-connection-verification
description: Use when verifying/fixing an ActivePieces OAuth connection
---

# Verificación y reparación de conexiones OAuth (ActivePieces)

Clase: confirmar qué cuenta y qué scopes tiene REALMENTE una conexión OAuth
de la agencia (Gmail/Drive/Calendar vía ActivePieces), extender scopes,
corregir el mapa de conexiones en dev+prod y leer la API con el token.

## Principio rector
El mapa (`connections-map.json`) es una AFIRMACIÓN, no evidencia: los campos
`cuenta`, `cuenta_verificada` y `scopes` pueden ser placeholders o estar
viejos (caso real 16-sep-2026: decía jonathaun124@gmail.com y 4 scopes; la
API vivía en captain@neuralcrewlabs.com con gmail.modify). La única fuente
de verdad es una llamada viva al proveedor con el token.

## Verificar identidad y scopes (Google)
1. Descifrar el valor de la conexión en la DB de AP y materializar el secret
   local (chmod 600); nunca pegar tokens en chat.
2. Identidad: `GET gmail/v1/users/me/profile` → `emailAddress` real.
3. Scopes del TOKEN: `GET oauth2.googleapis.com/tokeninfo?access_token=…`.
   OJO: el array `scopes` de AP es una CONSTANTE de la pieza (Gmail fija 4)
   y puede decir MENOS de lo que el token trae. Un verificador que lea ese
   campo miente; reportar ambas listas y la diferencia.

## Extender un scope (ej. gmail.modify)
- Reconectar LA MISMA conexión con el scope extra en la URL de consent.
  Google acepta ampliar scopes en un cliente existente (validar HTTP 200 y
  ausencia de invalid_scope ANTES de pedir el click humano). El
  connection_id y ap_token_version se conservan.
- Tras el consent: tokeninfo ANTES de documentar; documentar en la nota del
  mapa la diferencia scopes-registrados vs scopes-reales.

## Corregir el mapa en dev+prod
Receta completa: references/oauth-map-correction-recipe.md. Reglas duras:
- Archivos DISTINTOS: dev `/opt/data/connections-map.json`, prod
  `/opt/connect-neuralcrew/connections-map.json` (nombre distinto).
- El fragmento de prod NO es copia del de dev (campos extra como
  `ap_external_id`, `connected_at` distinto): extraer el fragmento de prod
  verbatim y construir el reemplazo desde ese texto.
- Backup con timestamp + replace con guard `count==1` + `json.load` tras
  escribir.
- Payload por ssh SIEMPRE base64 por stdin (`ssh host python3 -`); los
  heredocs con comillas anidadas fallan en silencio.

## Inventario de buzón (solo metadatos)
Receta y snippets: references/gmail-metadata-inventario.md. Pitfalls
verificados: `metadataHeaders` va como parámetro REPETIDO en la query
(urlencode con lista lo rompe en silencio); retry obligatorio en lectura
masiva (~19% de 5xx transitorios); NUNCA confiar en `resultSizeEstimate` de
`messages.list` (dijo 201 sin leer >30 días; verdad: 176 totales, 8 sin
leer). Contar mensaje a mensaje desde la lista paginada.

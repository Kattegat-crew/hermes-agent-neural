# Versionado de identidad de marca — dónde debe quedar explícito

Regla del Admin (Lucky, hoja de personaje v2): cuando cambia la BASE de identidad
 desde la que se genera todo el arte de una marca (no la campaña puntual), el cambio
 debe quedar explícito en TODAS las superficies del ecosistema. Las campañas pasadas
 NO se tocan: lo que se versiona es la base.

## Las 5 superficies (verificadas en orden)

| # | Superficie | Qué actualizar |
|---|-----------|----------------|
| 1 | Repo de campañas (`/opt/marketing-campaign-generator`) | `registry.json` del activo (versión nueva + previas marcadas), master prompt de campaña, prompts de print/reel si fijan rasgos |
| 2 | Contexto de Hermes (`/opt/data/brain/`) | notas de entidad del cliente que describan el personaje/identidad |
| 3 | Drive — bible de marca | carpeta de caracter sheet del cliente: docs actualizados IN SITU, versiones previas a `_versiones-anteriores/<fecha>/`, hoja nueva en la carpeta de logos/activos con el naming de esa carpeta |
| 4 | Drive — carpeta de campaña vigente | assets de la campaña actual (la campaña anterior queda como se entregó) |
| 5 | Portal de producción | la galería/referencia que sirve el servidor |

## Convención de versionado dentro de la bible

- Los docs de la bible se editan EN SITU (mismo nombre, mismo lugar): el bible es
  un documento vivo. Los archivos binarios aprobados (hojas, logos) se conservan:
  la versión nueva entra con sufijo de versión y fecha, la anterior se archiva.
- `_versiones-anteriores/<YYYY-MM-DD>/` guarda byte a byte lo que estaba antes.
- En el registro de activos: activo nuevo = `APPROVED / CURRENT`; los que reemplaza
  = `SUPERSEDED <fecha> (motivo)` — nunca se borra la entrada, se marca.
- Cuidado con la coherencia interna: tras actualizar la sección principal, revisar
  el resto del documento por referencias viejas (jerarquías de referencias, listas
  de preservación de rasgos, reglas del system prompt del agente de imagen).

## Verificación de cierre

- Conteo de archivos Drive por API igual al local.
- Tamaños byte a byte de los docs editados (Drive == local).
- Links públicos de las carpetas tocadas en la respuesta al Admin.
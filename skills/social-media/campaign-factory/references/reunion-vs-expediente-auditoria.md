# Reconciliación reunión vs. expediente de campaña (verificado 22-oct-2026)

Problema recurrente: los documentos en `planning/<campaign>/` (00-HECHOS, 01-PLAN, 02/03-TERMINOS, …) son BORRADORES. Cada reunión del Admin aprueba cambios en vivo y el expediente queda obsoleto. Producir piezas desde el expediente viejo ya causó un incidente real (publicidad de $2M emitida a sedes que quedaron en $1M).

## Fuente de verdad de una reunión: Notas de Gemini en Drive

El acta vive como Google Doc `"Reunión iniciada a las ... - Notas de Gemini"` (título con fecha/hora). Receta verificada:

1. Credenciales: JSON con `client_id`/`client_secret`/`refresh_token` desde `/opt/data/secrets/` (nunca hardcodear ni copiar tokens a repos).
2. Refrescar: `POST https://oauth2.googleapis.com/token` con `grant_type=refresh_token`.
3. Listar: `GET /drive/v3/files?q="trashed=false and name contains '...'"&orderBy=modifiedTime desc` para ubicar el acta.
4. Leer: `GET /drive/v3/files/<id>/export?mimeType=text/plain`. Las notas tienen secciones Resumen/Decisiones/Próximos pasos/Detalles y luego el marcador literal `📖 Transcripción` — partir ahí: notas arriba, transcript con timestamps abajo.
5. Citar decisiones con quote + timestamp (`00:41:08`) como evidencia, nunca solo con el resumen automático.

## Clasificación de cada decisión (obligatorio antes de producir)

| Clase | Ejemplo real | Tratamiento |
|---|---|---|
| **Literal** | «final el 16 de diciembre», «San Francisco y Agua de Dios, 1 millón» | Aprobada, pasar a expediente |
| **Derivada** | «seis sellos» NO fue dicho nunca: se deduce de seis miércoles previos a la final; el transcript habla de «ocho, seis, cuatro sellos» | Marcar como PENDIENTE de confirmación; no imprimir/plantear como aprobado |
| **Contradicha con lo ya publicado** | docs de octubre decían $2M para TODAS las Golden; en reunión se reasignó $1M a Agua de Dios/San Francisco que ya recibieron publicidad de $2M | Requiere conciliación de lo ya anunciado — decisión de empresa, no edición unilateral del expediente |

## Pitfalls

- El resumen automático de Gemini atribuye tareas con STT imperfecto (nombres mal transcritos: «barito», «el barito» ≈ Álvaro; «LUCKY BROTHERS S.A.S.» es el interlocutor de la otra empresa). No convertir cada línea del resumen en asignación definitiva: distinguir compromiso expreso vs. participación por confirmar.
- Timestamps del transcript > resumen: el resumen puede fijar números (p. ej. «máximo de seis») que el transcript nunca dice así.
- Al auditar ejecución por sede, clasificar en tres estados: **realizado con evidencia / realizado sin soporte / no realizado** — la falta de evidencia sola NO prueba que no se hizo.
- Pedir evidencias en el GRUPO oficial (no privado): reportes dispersos por privado es el fallo original que motivó la auditoría.
- Privacidad (Ley 1581): pedir fotos de urnas/boletería SIN datos personales legibles; cédulas y boletas nominadas van por canal autorizado, no al grupo.
- Presupuestos: calcular con terminal, nunca a mano (ej. verificado: 6 semanas × [$50k+$100k+$200k] + final $2M = $4.1M/sede general; $3.1M/sede con final $1M).

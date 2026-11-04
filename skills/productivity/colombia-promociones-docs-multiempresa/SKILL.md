---
name: colombia-promociones-docs-multiempresa
description: "Use when one campaign needs legal docs per company."
tags: [colombia, legal, promociones, multiempresa, docx, compliance, casinos]
version: 1.0.0
metadata:
  hermes:
    tags: [colombia, legal, compliance, casinos, promociones, multiempresa, docx]
triggers:
  - "T&C / términos y condiciones / política de datos / aviso de privacidad para una campaña que agrupa DOS o más empresas (p. ej. Golden + Lucky)"
  - "documentos legales separados por operador en una promoción con componente de azar"
  - "build python-docx que genera varios .docx desde un dict de config por entidad"
---

# Paquetes legales por empresa en promociones colombianas multi-operador

Para la sustancia jurídica (qué exige Ley 643/Coljuegos/Ley 1581 etc.) consultar las skills user-owned `colombia-juegos-promocionales` y `colombia-promociones-legales`; para la mecánica de .docx profesional, `documentos-legales-entregables`. Esta skill captura la parte QUE AQUELLAS NO CUBREN: **cómo producir documentos íntegros legales SEPARADOS por empresa cuando una misma campaña agrupa varios operadores** (patrón validado con Bingo Millonario Golden + Lucky, 24/08/2026).

## Regla dura: un documento completo por empresa

Si dos o más empresas comparten una campaña, **cada una recibe su propio paquete** (T&C, Política de Datos, Aviso, textos de formulario). Nunca un documento compartido, aunque el domicilio y el representante legal coincidan (en el caso: ambos CL 174 #45-38 Bogotá y rep. Helmer Alexis Parra Guzmán — aun así, separados). Es corrección explícita del Administrador: «no pueden compartir documentos».

## Mecanismo probado (builder por dict de config)

```python
CFG_A = { 'razon':..., 'nit':..., 'domicilio':..., 'replegal':...,
          'contacto':..., 'sedes':[...], 'confirmados':[...], 'abiertos':[...], 'accent':'8B0000' }
CFG_B = { ... }                     # segundo dict, con sus propios sedas/contactos
build_doc(CFG_A, '/out/PAQUETE_A_v1.docx')
build_doc(CFG_B, '/out/PAQUETE_B_v1.docx')
```

Un único builder parametrizado genera los N documentos. Ventajas: un solo cambio de plantilla actualiza a todos; cada `cfg` se revisa independiente.

## Pitfalls de generación (vistos en producción 24/08)

- **No nombres el dict como la constante de color ya usada** (`GOLD = {...}` sombrea `GOLD = RGBColor(...)`). Usa `CFG_GOLD`. Si no, `run.font.color.rgb = GOLD` falla con `ValueError: rgb color value must be RGBColor object, got <class 'dict'>`.
- **`add_table(rows=N, cols=M)`: N incluye el encabezado** → `rows = len(datos)+1`, o `IndexError` en la última fila.
- Con build multiempresa, verifica que **cada key que usa la función exista en TODOS los dicts** (`replegal` vs `reple` por typo → `KeyError` solo en la 2.ª empresa, el 1.º pasó).
- **No «generes PDF» renombrando la extensión**: python-docx escribe OOXML; `X.pdf` salvado por él sigue siendo DOCX. Convertir a PDF es paso aparte.
- Al escanear huecos con regex usa `\b` (`\bPENDIENTE\b`): sin word-boundary, «INDEPENDIENTE» (regla del acumulado po local) da falso positivo.

## Verificación de aislamiento (obligatoria)

Para cada doc: (a) contiene sus claves duras (NIT, sedes, contacto); (b) **NO contiene** las de la otra empresa (lista `no_contiene`). Esto atrapa fugas entre documentos — verifiqué que Golden no mencionara Chiquinquirá/La Calera/Grand Paradise ni al revés.

## Nota sobre la decisión regulatoria

Si el operador (y su asesoría) resuelve que SU promoción NO requiere autorización previa adicional (marketing sin componente de licencia), **su decisión gana** sobre el texto estándar. Redacta la cláusula conforme a esa decisión y deja en «Estado del documento» una nota de rastreo con la advertencia técnica (juego de azar con premio en dinero puede caber en Ley 643 art. 5; si la autoridad lo requiere, se adelanta antes de divulgar). Esa nota es trazabilidad, no un hueco del documento.

## Referencias
`references/bingo-millonario-2026-septiembre.md` — decisiones confirmadas y entregables de la campaña que validó este patrón.
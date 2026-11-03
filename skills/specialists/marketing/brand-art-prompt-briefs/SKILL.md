---
name: brand-art-prompt-briefs
description: "Use when writing image prompt briefs for multi-brand work."
tags: [prompts, image-gen, brand, briefs, multi-marca, producer, vision]
---

# Brand Art Prompt Briefs (multi-marca)

Clase de trabajo: redactar desde Content los prompts/briefs de imagen que ejecuta el producer (Sindri) para campañas con varias marcas de clientes (caso real: Bingo Millonario — Golden Game + Lucky Brothers).

## Reglas duras (aprendidas a golpes)
1. **Una marca por hero.** No meter las mascotas de dos clientes en un mismo render salvo orden explícita del user. El negativo excluye explícitamente a la otra marca: `no second character, no robot, no slot machine`.
2. **Verificar el arte oficial con `vision_analyze` ANTES de escribir el bloque de personaje.** Las fichas/docs pueden describir mal el arte vigente (caso real: la ficha decía trébol "con cara" estilo Pixar; el logo oficial es un trébol de 4 hojas SIN CARA). El PNG real del logo es la fuente de verdad — pedir hex aproximados, forma y "¿con cara o sin cara?".
3. **Logos = capa del compositor, jamás quemados** (`no logos burned in`). El brief especifica zonas de aire libres para las capas de texto/logo (p.ej. arriba ~35% oscuro limpio, rincón inf-izq 36%x18% despejado).
4. **Override banner al cambiar alcance a mitad de campaña:** cuando el user corrige, NO basta con archivo nuevo — poner al tope del archivo viejo `> ⚠️ OVERRIDE <fecha>: <qué cambia> → ver <ruta nueva>`. El producer lee archivos del workspace, no solo chat; sin el banner el prompt obsoleto se re-dispara.
5. Una sola variable por render (el motor); dirección de arte idéntica entre variantes.
6. **Arte base antes que piezas derivadas.** Primero aprobar el key visual limpio (sin texto, sin logo) de la campaña; solo después derivar boleta/tarjeta/afiche recortando y componiendo tipografía en local. Saltar directo a una pieza específica fue corrección explícita del Admin (29-oct, campaña El Aguinaldo de la Suerte).

## Estructura de un entregable de prompts
- Cabecera: corrección/alcance + fuentes verificadas (ruta del PNG analizado).
- Bloque de personaje DERIVADO DEL LOGO REAL (descripción física con hex, sin cara si el logo no la tiene).
- Prompts numerados por formato (1:1, 9:16, vector flat) con COMPOSITION CONSTRAINTS y NEGATIVE fijos.
- Sección "Overlay del compositor": qué capas llevan texto/logo (lo único con texto).
- Regla de línea al pie: qué NO hacer en futuras piezas de esa marca.

## Pitfalls del entorno
- Assets subidos al chat por root pueden dar `[Errno 13] Permission denied` a `vision_analyze`. Fix: copiarlos a una ruta propia escribible del perfil y analizar desde ahí; o `docker exec hermes-agent chown -R 10000:10000 <ruta>`.

See `references/multi-brand-render-briefs.md` for the canonical case (Lucky trébol, paletas, negativos exactos).

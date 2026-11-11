---
name: product-research-sourcing
description: Use when finding, comparing or verifying products online.
---

# Investigación y sourcing de productos online

Flujo para encontrar, comparar y verificar productos físicos (regalos, gadgets, accesorios) y entregar candidatos con precio verificado y link directo.

## Reglas permanentes
- Precio "verificado" SOLO si se leyó del propio retailer en esta sesión. Precios que vienen de buscadores o agregadores se reportan al usuario como "no verificado", sin excepción.
- Si el usuario pivota a compra local ("busquemos en Colombia"), el objetivo pasan a ser retailers colombianos con precio en COP y entrega local; el marketplace internacional (AliExpress/Amazon) queda solo como comparación de precio.
- Entregar siempre: producto, precio vigente (y "antes X" solo si el precio de lista es real), evidencia de reseñas cuando exista, y link directo al producto — nunca el link de búsqueda.
- Cerrar con UNA recomendación (elegida y justificada), no una lista sin ganador.

## Flujo
1. Fijar restricciones en UNA pregunta batch (presupuesto, modelo/variante exacta, imprescindibles). No ejecutar con supuestos: el modelo/variante (p. ej. cuál consola) cambia por completo el set de productos.
2. Shortlist con web_search (2-3 queries con variantes del nombre). Los agregadores de precios devuelven tarjetas con varios merchants locales + precios: úsalas para DESCUBRIR candidatos y tiendas locales, jamás como fuente final del precio.
3. Verificar cada candidato directamente en el retailer (recetas por tienda en references/retailer-access.md).
4. Cerrar con recomendación + links + pregunta de cierre solo si falta el dato que cambia el resultado (modelo, talla, variante).

## Pitfalls
- En Falabella el JSON-LD trae DOS offers (venta y lista): reporta la menor como precio vigente y la otra como "antes X". Nunca infieras descuentos que el JSON no muestra.
- Si un retailer sirve challenge anti-bot a curl, no insistas ni quemes turnos: entrega el link con precio marcado "no verificado" y avanza con los candidatos sí verificables. Nombrar el bloqueo concreto al usuario.
- Los tamaños/medidas del título del listing (43×61, 82×59) son parte del criterio de elección: dos "mapas para raspar" pueden diferir 5× en tamaño de pared. Contrasta medidas, no solo precio.

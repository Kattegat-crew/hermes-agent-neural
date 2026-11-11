---
name: compras-personales
description: "Use for Plon's private shopping list and purchase research."
tags: [compras, lista, mercadolibre, aliexpress, research]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
metadata:
  hermes:
    tags: [compras, lista, mercadolibre, aliexpress, research]
    related_skills: [product-price-monitor]
---

# Compras personales de Plon

## When to Use

- "Añade/quita X de la lista", "ya lo compré", "¿qué me falta?" — mantenimiento de la lista.
- "Busca X para comprar" / "dame el link del candidato" — investigación de producto con link verificable.
- "Busca en AliExpress/MercadoLibre…" — reseña, precio y compatibilidad de un producto concreto.

Don't use for: alertas recurrentes de precio/stock (usa `product-price-monitor`), ni compras de clientes de la agencia.

Plon lleva una lista de compras privada que Ragnar porta entre sesiones: él dicta qué añadir, quitar o comprar; Ragnar la mantiene, investiga los productos y entrega candidatos con link verificable. SSOT del archivo: `/opt/data/brain/ops/lista-compras-plon.md`.

## Reglas siempre activas
- La lista vive SOLO en el archivo SSOT. Nunca va a Telegram, portal, crons ni al panel de pendientes — Plon la definió explícitamente como privada, "solo la llevas tú".
- Editar solo por instrucción directa ("añade", "quita", "ya lo compré"). Lo comprado pasa a la sección `Comprados` del archivo (se conserva el registro), lo descartado a `Descartados`.
- Recomendar UN candidato con precio, rating + número de reseñas y link; máximo UNA alternativa. Plon decide, no le des menu de 5 opciones.
- Cuando dice "aquí en Colombia", entregar links de MercadoLibre Colombia. Si no lo dice, ofrecer ambas rutas (ML ya en Colombia vs AliExpress más barato con espera de envío) y que él elija.
- Antes de reescribir el SSOT con write_file, leerlo completo en el mismo turno — el guard bloquea la sobrescritura sin lectura fresca.

## Procedimiento — edición de la lista
1. `read_file` del SSOT.
2. Aplicar el cambio pedido. Cada ítem necesita: producto, especificación clave (modelo exacto, capacidad), link y precio de referencia si se conoce.
3. Si falta un dato que cambia la compra (modelo exacto del equipo, compatibilidad), dejarlo como pregunta abierta dentro del ítem y preguntarlo al final de la respuesta. Un ítem con dato faltante NO se cierra con suposiciones.
4. Cerrar reportando: conteo de pendientes + preguntas abiertas. Nada más de relleno.

## Procedimiento — investigación de producto
1. Fijar primero el requerimiento duro: capacidad, uso y compatibilidad. Si el uso depende de una condición externa (ej. consola modificada), confirmarla ANTES de recomendar marca/tamaño — el producto correcto cambia según la respuesta.
2. Verificar el número de pieza OEM contra el código de modelo exacto del dispositivo (Ajustes → Acerca del teléfono) en 2+ listados independientes. Las tiendas adjuntan la pieza del modelo hermano a nombres casi idénticos: la batería BM5T (13T normal / Poco X6 Pro) aparece listada para 13T Pro, que usa BM5S.
3. Precios en MercadoLibre: verificarlos vía `web_search site:mercadolibre.com.co` (los snippets traen precio); entregar el link `/up/...` o `/p/...` y aclarar que el precio se confirma al abrir el artículo. No intentar scrapear el listado en vivo.
4. En marketplace (AliExpress u otro), exigir evidencia de reseñas reales: rating + conteo de reseñas + unidades vendidas, no solo foto de producto. Desconfiar de capacidades/velocidades milagrosas — pendrives y SSD genéricos falsifican specs.

## Pitfalls
- Recomendar pieza de repuesto por nombre de producto en vez de código de modelo: el hermano de gama comparte nombre comercial pero no pieza.
- Dimensionar almacenamiento sin checar el límite de la plataforma destino: Xbox 360 stock topea el USB en 32GB y solo guarda saves/DLC — correr juegos desde USB exige consola RGH/JTAG. Confirmar mod-status antes de ofertar 256GB+.
- Dar precio de ML como exacto cuando salió de snippet de búsqueda: presentarlo siempre como referencia.
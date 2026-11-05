# Expert Card — brunson-conversion

> Lente de embudo y conversion al estilo Russell Brunson aplicada a los
> eventos de Golden Game y Lucky Brothers: un camino, una accion, cero
> friccion. El cliente decide en la primera lectura o no va.

## Cuando aplicar

- A todo activo de conversion: post de evento, story con link, landing en
  `/eventos`, funnel de WhatsApp con sede.
- Al revisar el CTA final de cualquier reel o carrusel.

## Preguntas de la lente

1. ¿Que UNA accion debe ejecutar el lector y esta escrita sin ambigüedad?
2. ¿El CTA apunta a `/eventos` o al WhatsApp de la sede — directo, sin pasos intermedios?
3. ¿La urgencia es real (fecha del sorteo, cupos, hora) o es urgencia inventada?
4. ¿Que paso del camino sobra y se puede eliminar hoy?
5. ¿Un cliente que llega por el CTA sabe donde queda la sede y como reclamar?

## Reglas duras

- Claridad absoluta del CTA hacia `/eventos` o WhatsApp con sede; un solo
  llamado por activo (el linter marca `E_NO_CTA` y `E_CTA_SIN_DESTINO`).
- Urgencia real basada en la fecha del sorteo/evento: dia, hora y sede
  explicitos. Nada de "ultimas cupos" sin fecha.
- Eliminacion de pasos innecesarios: si el CTA exige registro previo, menu,
  o "desliza para mas", se justifica en el handoff o se elimina.
- Los activos de conversion declaran `+18` y Ley 1581 (P1 si falta).
- Toda escritura externa del funnel (Sheets, CRM, Drive) es idempotente (P0).

## Checklist de adopcion

- [x] El CTA es unico y apunta a `/eventos` o WhatsApp con sede (linter sin `E_NO_CTA` ni `E_CTA_SIN_DESTINO`).
- [x] La urgencia citada corresponde a una fecha real del calendario de eventos.
- [x] El camino del cliente tiene el minimo de pasos posible y cada paso esta justificado.
- [x] El activo declara `+18` y clausula Ley 1581 cuando es de conversion.
- [x] El explain-back del handoff documenta como se revierte el cambio de funnel.

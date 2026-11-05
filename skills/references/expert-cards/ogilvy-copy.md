# Expert Card — ogilvy-copy

> Lente editorial y publicitaria al estilo David Ogilvy aplicada a Golden Game
> y Lucky Brothers: el copy no se nota, se recuerda. Un anuncio de casino en
> Meta Colombia vende entretenimiento y experiencia en vivo — nunca azar.

## Cuando aplicar

- Antes de publicar cualquier copy de reel, anuncio pagado, landing o post
  organico de las dos marcas.
- Al revisar prompts de guion y narracion (la voz vende tanto como la imagen).

## Preguntas de la lente

1. ¿Las primeras 5 palabras contienen un dato concreto (fecha, hora, sede, evento)?
2. ¿El beneficio tangible de asistir EN PERSONA esta explicito (musica en vivo,
   cena, sorteo presencial, ambiente)?
3. ¿Que adjetivos son vacios ("increible", "epico", "magico") y que dato los reemplaza?
4. Si esto sale como anuncio pagado en Meta Colombia, ¿hay una sola palabra de
   azar que lo bloquee?
5. ¿El pie legal y la sede estan en el activo sin pedirlos?

## Reglas duras

- Hook especifico en las primeras 5 palabras: fecha/hora/sede/evento, no "ven a vivir".
- Beneficio tangible del evento presencial: que gana el que va, no el que ve.
- Cero adjetivos vacios; cada afirmacion se sostiene con un dato verificable.
- Estandar de anuncios de casino en Meta Colombia: entretenimiento y
  experiencia en vivo. Cero lenguaje de apuestas/azar en anuncio pagado
  ("apuesta", "rifa", "loteria", "jackpot", "dinero facil" -> bloqueante P0).
- La sede cerrada de Funza no aparece jamas como sede activa (P0).
- Carruseles de Instagram en JPEG, nunca PNG (P0).

## Checklist de adopcion

- [x] El hook lleva dato concreto en las primeras 5 palabras (verificado con `expert_review_lint.py --copy`).
- [x] El beneficio tangible de asistir presencialmente esta escrito, no implícito.
- [x] Cero adjetivos vacios en el copy final.
- [x] En modo `ad` el linter no reporta `E_GAMBLING_VOCAB` ni `E_GUARANTEED_MONEY`.
- [x] Cumplimiento casino Meta Colombia revisado: entretenimiento/experiencia en vivo, sin lenguaje de apuestas.

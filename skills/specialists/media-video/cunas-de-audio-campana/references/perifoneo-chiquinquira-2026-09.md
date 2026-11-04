# Cuña de perifoneo · Chiquinquirá — ruleta nueva + Bingo Millonario (sept 2026)

Caso de **cuña de doble mensaje**. Guion entregado: `/opt/data/plans/GUION-CHIQUINQUIRA-PERIFONEO.md` (v1 borrador).

## La corrección que originó el paso 0.5
El pendiente del backlog decía "guion ruleta perifoneo" (sin sede) y el Admin pidió "el perifoneo de Funza". Se redactó y entregó el guion completo de Funza (3 cuñas, datos del afiche y banners de Funza) y el Admin corrigió: *"No Ragnar, el anuncio del Perifoneo es para Chiquinquirá"*, con el mensaje real: **el local estrena una ruleta extra → único local de Chiquinquirá con dos ruletas, ruleta último modelo del año, última tecnología, grandes acumulados**, más el mejor servicio y atención. El guion de Funza se conservó marcado como ARCHIVADO (sus datos están verificados y sirven si vuelven a pedirlo) y se abrió el documento nuevo.

**Lección:** cuando el ítem del backlog no nombra sede, confirmar la sede en una línea antes de escribir. Y cuando la novedad está en una sola de las sedes del municipio (Chiquinquirá tiene Cra. 9 No. 17-51 y Cra. 8 No. 17-40), pedir la dirección antes de grabar.

## Datos verificados del evento (fuente: banners de TV de Lucky, ya aprobados/publicados)
Bingo Millonario **Especial Amor y Amistad** · The Grand Paradise Club:
- Viernes **04 · 11 · 18 · 25 de septiembre** + **Gran Final 02 de octubre**.
- **Desde las 5:00 p.m.**
- **Acumulado hasta $1.600.000 en efectivo**, se paga íntegro en la gran final.
- **Participación gratuita** · "¡Ven a jugar y recibe tu cartón!".
- Sedes: **Tunja · Calera · Chiquinquirá · Funza**.
- Pie legal: +18 · Juego responsable · Autoriza Coljuegos.

Afiche de sedes (v3): marca The Grand Paradise Club CASINOS · "EL PALACIO DE LA SUERTE" · sedes Tunja · La Calera · Chiquinquirá.

## Atributos de la novedad (dictados por el Admin, sin cifras)
Segunda ruleta en el local · último modelo de este año · última tecnología · acumulados que crecen · el mejor servicio, la mejor atención, mucha diversión y suerte. La cuña **no** pone montos de la ruleta: no hay cifra verificada.

## Set entregado y duraciones reales
| Cuña | Palabras | Rango |
|---|---|---|
| A mixta (ruleta + bingo) | 104 | 40-47 s |
| B solo ruleta | 46 | 18-21 s |
| C solo bingo | 58 | 22-26 s |

## Ruta de recuperación de material (verificada)
- Cuenta NC (credencial `secrets/jonathan-drive.json`; también `nancy/helmer/jacqueline/neuralcrew`): carpeta **`Funza`** → `Afiche funza.png`, `Banners TV's/TV1..TV6.png`, `Reel 3- Funza ya listo/reel funza .mp4`.
- Lucky `03-piezas` (`1FY-8Gyvcr5SxfPqDaQs1libTPhTYNbvG`): carpetas `Afiche` (`afiche sedes lucky v2/v3.png`), `Banners TV's` (`1..7.png`), `Funza`, `Reels`, `Volante bingo`.
- Formato de referencia del cliente: **`Guion cuña ruleta.docx`** (Golden Game · Tunja · ruleta Gold Club, carpeta `Viejo` de NC) — líneas de ambiente entre corchetes + locución corrida.
- `vision_analyze` sobre afiche/banners con "transcribe literalmente TODO el texto" devuelve evento, fecha, premios, dirección y pie legal sin transcribir el mp4.
- Los banners de TV de Lucky (`.png` de 14-16 MB) son la fuente más completa del evento vigente; el afiche de sede puede traer mecánica vieja (caso Funza: 4 bingos + "cartón" contra el T&C v6 de 3 bingos + tabla con registro → avisar antes de grabar).

## Pendientes al cerrar
1. Dirección del local con la doble ruleta (bloqueante).
2. ¿La ruleta ya está instalada? (verbo "llegó" vs "estrena").
3. Voz: locutor humano o voz Lucky (TTS).
4. Humanización regional: 4 subagentes de investigación dialectal lanzados el 10/09 (glosario con fuente, patrones orales, límites/clichés, contexto de Chiquinquirá) — aplicar dosis de 1-2 marcadores y pasar por `humanizer`.

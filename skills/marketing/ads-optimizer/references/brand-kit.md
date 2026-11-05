# Kit de marca «Imagen de marca» (modal de Ads Manager) — receta y valores verificados

Cuando el Admin arma el kit de marca de un anuncio (modal «Imagen de marca»: logo, fuente, colores, tono del texto, estilo visual, palabras restringidas), NO improvisar los campos: cada valor sale de una fuente canónica del repo o del sitio en producción.

## Fuentes por campo (procedimiento)

1. **Logo**: usar el asset aprobado del repo, nunca un logo cargado previamente en la cuenta. Verificar SIEMPRE qué logo está cargado en el modal antes de dar OK — en la cuenta de Lucky estaba cargado un logo ajeno («The Bread Paradise»); un OK así guarda identidad ajena como predeterminada de la marca. Logo Lucky aprobado como archivo: `assets/sheets/lucky/logo/grand-paradise-club.png` (en revisión de fuente según brand-profile; no regenerar con IA).
2. **Colores**: extraer los hex REALES del CSS de producción de la landing destino, no del manual de marca (los docs nombran colores sin hex). Comando:
   `grep -rhoE "\-\-[a-z0-9-]+\s*:\s*#[0-9a-fA-F]{3,8}" --include=*.css <repo-landing> | sort -u`
3. **Fuente**: leer `font-family` / link de Google Fonts del sitio. Si la fuente display del sitio (ej. Cinzel) no aparece en la lista del modal, usar la del cuerpo (ej. Montserrat).
4. **Tono del texto y Estilo visual**: redactarlos desde el sistema de marca (`docs/clientes/<marca>/brand-profile.md`, `docs/Reference input/Lucky/03_PARADISE_CLUB_BRAND_SYSTEM.md`) y VERIFICAR el contador ≤300 caracteres con Python antes de entregarlos (los borradores iniciales suelen pasar de 300).
5. **Palabras restringidas**: el kit pide una lista propia, MÁS amplia que el vocabulario prohibido de copy: cubre azar (`apuesta`, `apostar`, `ruleta`, `tragamonedas`, `slot`, `jackpot`, `giros gratis`, `sorteo`), canal (`online`, `en línea`, `app`, `descarga`, `desde casa`), dinero (`depósito`, `recarga`, `retiro`, `dinero fácil`, `gana dinero`), promesas (`garantizado`, `millones de pesos`) y ofertas (`oferta`, `descuento`, `reembolso`, `gratis`, `bono de bienvenida`). Para Lucky añadir promesas de suerte propias del personaje: `suerte asegurada`, `trébol de la suerte` (el trébol tienta a la IA generativa a prometer suerte).

## Valores verificados Lucky / The Grand Paradise Club (19-oct-2026)

Paleta real (CSS de `paradiseclubcasinos.com.co`, repo `/opt/paradise-casino/paradise-casino-landing`):

- Esmeralda profundo `#064E3B` · esmeralda `#059669` · glow `#10B981`
- Oro `#D4AF37` · oro suave `#F3D079` · oro brillante `#FFF6B8` · oro oscuro `#8C6500`
- Midnight `#0D080A` · soft `#140C10` · raised `#1C1017`
- Rojo `#A81630` · deep `#6E0B1D` · vibrant `#B91C1C` · marfil `#FDFBF7`

Para el kit (máx ~3-5 slots): esmeralda `#064E3B`, oro `#D4AF37`, midnight `#0D080A` (+ opcionales rojo `#A81630`, marfil `#FDFBF7`). Fuentes del sitio: Cinzel (display) + Montserrat (body).

Tono (297 chars) y Estilo (291 chars) aprobados en sesión están en el chat del 19-oct-2026; si se necesitan de nuevo, regenerarlos con el procedimiento de arriba y validar ≤300.

## Plataforma: verificar ANTES de cargar campos

El modal «Imagen de marca» existe en Meta Ads y en Google Ads con UI casi idéntica. Si es Google Ads, la pauta de apuestas exige certificación de gambling del anunciante en la cuenta: el copy limpio NO basta y la campaña se rechaza igual. Confirmar plataforma (y estado de certificación si es Google) antes de invertir en creatividades.

## Pitfall del sitio Golden (verificado en bundle de producción 19-oct-2026)

`goldengame.com.co` acepta `?sede=` / `?ciudad=` pero la personalización solo vive en la **home y `/bono`** (función `ha()` del bundle): **`/eventos` ignora esos parámetros**. No prometer landing personalizada por sede con destino `/eventos` hasta que el sitio lo soporte.

Decisión del Admin (19-oct-2026): todos los adsets de Golden Halloween caen en `https://goldengame.com.co/eventos` genérico, con los UTMs de campaña a nivel de CAMPAÑA (Meta concatena campaña+adset+anuncio; un solo nivel para no duplicar parámetros). La identidad de sede queda en el nombre del adset, el reporte nativo de Meta, el `fbclid` y el campo sede del formulario — no en la URL. Revisitar este pitfall si se parchea el sitio.

`paradiseclubcasinos.com.co/eventos` (Lucky) sí es `venue_safe_verified` según el manifiesto.

# Recibo BBVA Bre-B — formato real y parsing (verificado 10/09/2026)

Fuente: buzón `luckybrothers.sas@gmail.com`, remitente `notificacionesBreB@bbva.com`.
Asunto siempre igual: **"Recibiste dinero en tu cuenta a través de Bre-B."**

## Campos del cuerpo (texto plano, tras quitar HTML)

| Campo | Ejemplo | Regex |
|---|---|---|
| Fecha y hora | `2026/09/10 11:13` | `Fecha y hora\s+(\S+)` |
| Valor recibido | `$ 80.000,00` | `Valor recibido\s+\$\s*([\d\.,]+)` |
| Persona que envía | `WILSON ORLANDO IBANES ORTIZ` | `dinero que (.+?) envi[oó] a tu llave` |
| Tipo de llave | `Código de comercio` | `Tipo de llave\s+(.+?)\s+Cuenta` |
| Cuenta destino | `*****2682` | `Cuenta destino\s+\*+(\d+)` |
| Código de operación | `11965262248745084739310299657726395` | `C[oó]digo de operaci[oó]n\s+(\d+)` |

Detalles que importan:

- La **fecha/hora del encabezado del correo es UTC** (`Thu, 10 Sep 2026 16:14:07 +0000`) mientras que la del **cuerpo es hora local Colombia** (11:13) → usar la del cuerpo para el aviso.
- El **código de operación es único por pago** → llave natural de idempotencia.
- La **cuenta destino es siempre la misma** para todas las sedes (una sola cuenta BBVA) → el correo no permite separar por local.
- Tipo de llave `Código de comercio`: es la llave Bre-B del comercio, no un dato por sede.
- El valor viene con separador de miles `.` y decimales `,` → `float(v.replace('.','').replace(',','.'))`.

## Extracto real del cuerpo (limpio)

```
Tu dinero ya está disponible
Lucky Brothers Sas, ya está disponible en tu Cuenta BBVA el dinero que
WILSON ORLANDO IBANES ORTIZ envió a tu llave de Código de comercio.
Ingresa a nuestros canales digitales para confirmar tu nuevo saldo.

Detalles de la operación
Fecha y hora     2026/09/10 11:13
Valor recibido   $ 80.000,00
Persona que envía   WILSON ORLANDO IBANES ORTIZ
Tipo de llave    Código de comercio
Cuenta destino   *****2682
Código de operación   11965262248745084739310299657726395
```

## Volumetría observada (7 días)

- 119 recibos leídos de ~120 (1 fallo puntual por rate limit).
- Por día: 28 (07/09), 41 (08/09), 46 (09/09) → **~40-46/día**.
- Valores: mínimo $20.000, máximo $700.000, promedio ~$122.000.
- 56 pagadores distintos, con repetidores de hasta 7 pagos/semana → tratar por código de operación, no por nombre.
- 119 códigos de operación para 119 recibos → sin duplicados en la muestra.

## Limpieza del cuerpo

El HTML de BBVA trae CSS embebido en el `<body>` (x-apple-data-detectors, media queries).
Quitar tags (`re.sub(r'<[^>]+>', ' ', html)`), normalizar `&nbsp;`/`&amp;` y colapsar espacios basta para que los regex funcionen. Si hay varias partes MIME, recorrer `payload.parts` recursivamente y quedarse con todo el texto disponible.

# Alta de acceso API a Meta Ads: una app, N clientes

Runbook verificado en producción el 19-oct-2026 (Golden Game / Lucky Brothers).

## Regla de oro: NO se crea una app por cliente

Una sola app de la agencia sirve para **todos** los Business Managers. Lo que cambia por
cliente no es la app, es el **token**: cada Business Manager tiene su propio System User
y su propio token.

```
App de la agencia (Live, una sola)
   └── BM Cliente A ── System User A ── token A ── /opt/data/secrets/meta_ads_cliente-a.env
   └── BM Cliente B ── System User B ── token B ── /opt/data/secrets/meta_ads_cliente-b.env
```

El acceso NO lo da la app: lo da el rol del usuario dueño del token sobre cada cuenta
publicitaria. Con acceso **Standard** (sin revisión de Meta) alcanza mientras el usuario
del token sea administrador o partner de las cuentas que gestionamos.

## Requisitos de la app (una sola vez)

1. developers.facebook.com/apps → la app de la agencia (ej. `Golden Game Feed` 1349398776805033).
2. Producto **Marketing API** agregado.
3. **Configuración → Básica** completa: correo, categoría, ícono 1024×1024 y URL de
   política de privacidad (`https://connect.neuralcrewlabs.com/privacy` responde 200).
4. Interruptor **En vivo**. Sin esto, `POST /adcreatives` devuelve `code 100 /
   error_subcode 1885183` ("la publicación se creó con una app en modo de desarrollo").

## Alta por cliente

1. **BM del cliente → Usuarios → Usuarios del sistema → Agregar** (`neuralcrew-ads-api`, rol Administrador).
2. **Asignar activos** al System User:
   - Cuentas publicitarias → *Control total* (sin esto, `ads_management` no aplica).
   - Páginas → *Control total* (el creativo se publica con identidad de página).
   - Cuentas de Instagram → *Control total* (si se pauta en IG).
3. **Generar token nuevo** → elegir la app de la agencia → permisos
   `ads_management`, `ads_read`, `business_management` → **Caducidad: nunca**.
4. Guardar en `/opt/data/secrets/meta_ads_{cliente}.env` con permisos 600:
   ```
   META_ADS_TOKEN=EAAG...
   META_AD_ACCOUNT=act_000000000000000
   ```
   Nunca en el repositorio, nunca en el chat, nunca en MEMORY.md.

## Verificación obligatoria del token (antes de usarlo)

No usar curl con el token en la URL: queda en el historial y en los logs. Usar el
operador, que lee el token del archivo de secretos y valida contra la cuenta:

```bash
python3 /opt/data/scripts/ads/finish_halloween_ads.py     # modo auditoría, sin escribir
```

Si responde `Session has expired` o `Invalid OAuth access token`, el token no sirve:
no seguir y regenerarlo.

## Cuándo NO reusar la app de la agencia

- El cliente exige contractualmente que sus datos no pasen por una app de terceros.
- Se va a construir un producto que opere cuentas de clientes **sin** que el dueño del
  token sea administrador de esas cuentas → requiere *Advanced Access* y revisión de Meta.

## Alternativa Composio: solo lectura

El toolkit `metaads` de Composio sigue sirviendo para leer (campañas, adsets, insights),
pero **no para crear creativos**: su app está en dev-mode y devuelve el mismo `1885183`.
Para escritura, token propio.

## Pitfalls con evidencia (no re-descubrir)

| Síntoma | Causa real | Fix |
|---|---|---|
| `1885183` al crear creativo | app en modo desarrollo | pasar la app a En vivo |
| `Param instagram_actor_id must be a valid Instagram account id` | id del manifest inventado u obsoleto | leerlo con `GET /{page_id}?fields=instagram_business_account` (exige `pages_read_engagement`) o **omitir el campo** |
| presupuesto 10.000× mayor al autorizado | cuenta COP con offset 1 y se enviaron centavos | enviar COP enteros: `lifetime_budget=56000` |
| `lifetime_budget` de campaña `300000` con gasto `239802` | así se ve offset 1 (unidades mayores) | calibrar con `min_daily_budget` de la cuenta (COP: 3184) |
| adset no entrega tras activar | `start_time` quedó en el pasado | ajustar `end_time`; Meta hace pacing del lifetime restante |

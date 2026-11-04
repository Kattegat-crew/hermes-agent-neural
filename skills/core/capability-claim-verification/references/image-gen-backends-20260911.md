# Auditoría «ya está configurado»: imágenes con GPT y key de Vault (11-sep-2026)

Caso: el CTO preguntó si Roshi tenía key para el vault y cómo se generaban imágenes «con GPT», añadiendo que Jonathan ya había configurado ambas cosas. Veredicto de la auditoría read-only: **Vault sí (host-level, no por perfil) / imágenes con GPT no, en ningún perfil**.

## Imágenes — semántica leída en el código de esta instalación (v0.21.0)

| Pieza | Archivo | Hecho |
|---|---|---|
| Selección de provider | `tools/image_generation_tool.py:1594` | lee la clave raíz `image_gen.provider` |
| Gate de disponibilidad | `tools/image_generation_tool.py:1470` | `check_image_generation_requirements()` = False ⇒ tool apagado en runtime |
| Plugin OpenAI | `plugins/image_gen/openai/__init__.py:53` | `API_MODEL = "gpt-image-2"`, tiers `gpt-image-2-low/medium/high` (default medium) |
| `is_available()` | `:176-178` | exige `get_secret("OPENAI_API_KEY")` |
| Cliente | `:275` | `openai.OpenAI(api_key=api_key)`, **sin base_url** → `api.openai.com` |
| Resolución de tier | `:85-119` | solo lee `image_gen.openai.model` / `image_gen.model`; valor desconocido ⇒ default **sin error** |
| Tiers FAL | `tools/image_generation_tool.py:263-333` | `fal-ai/gpt-image-1.5` $0.034/imagen; `fal-ai/gpt-image-2` $0.04–0.06/imagen (quality medium); edits `fal-ai/gpt-image-1.5/edit`, `openai/gpt-image-2/edit` |

Consecuencias:

1. `image_gen.openai.api_key` / `image_gen.openai.base_url` **no se usan** ⇒ un bloque apuntando a un proxy OpenAI-compatible (NaN) es inerte. Única redirección posible del plugin: la env `OPENAI_BASE_URL`.
2. NaN-Builders no puede servir GPT: `GET /v1/models` (con UA de navegador; sin UA → 403 Cloudflare, que no es problema de key) devuelve 12 modelos y **un solo** modelo de imagen: `flux-2-klein`.
3. La vía Flux operativa del pipeline **no** es el toolset sino el script del repo: `marketing-campaign-generator/scripts/nan_client.py` (`DEFAULT_MODEL = flux-2-klein`, `POST /v1/images/generations`, `NAN_API_KEY` en `/root/marketing-campaign-generator/.env` y `~/.config/akari-video/credentials.env`).
4. Un toolset `✓` en `hermes tools --summary` es habilitación, no disponibilidad: los dos perfiles lo mostraban y ambos tenían `available=False`.

## Estado verificado (11-sep-2026)

```
default   provider=openai   model=None   fal_key=False   available=False
roshi     provider=None     model=None   fal_key=False   available=False
```

- `default`: bloque `image_gen` con `provider: openai` + api_key/base_url de NaN + `model: flux-2-klein` ⇒ inerte por (1) y (2).
- `roshi`: sin bloque `image_gen`; **sí** tiene los toolsets core (17/27 con Terminal, Code Execution, Image Gen ✓) — la ausencia de `platform_toolsets` no le quita capacidades en v0.21 (corrige el diagnóstico de 09/09/2026).
- Los `.env` de perfil/global contienen la línea `OPENAI_API_KEY` pero **comentada** y con la key de **NaN-Builders** (`sk-JzB…`), no una de OpenAI: ver «Fuentes de la key» abajo (corrige la lectura previa «ningún .env tiene OPENAI_API_KEY»).
- El vault tiene `FAL - API key` (campo `FAL_KEY`) y `Terceros/NAN - API Key`, pero **no** hay item de OpenAI.

## Opciones propuestas (sin cambios aplicados; requieren decisión del usuario)

1. **GPT real vía FAL**: `image_gen.provider: fal` + tier `fal-ai/gpt-image-2`, usando el `FAL_KEY` que ya está en el vault (inyectar `FAL_KEY` al `.env` de cada perfil que deba generar). Camino más barato a imágenes GPT con una key existente.
2. **OpenAI directo**: crear `OPENAI_API_KEY` real + `image_gen.model: gpt-image-2-medium`.
3. **Seguir con Flux**: sin GPT; se queda en `scripts/nan_client.py` con `NAN_API_KEY`.

## Catálogo GPT Image en fal.ai (verificado 11-sep-2026, costo cero)

Obtenido con el catálogo público `GET https://fal.ai/api/models?keywords=gpt-image` (200, sin auth) — **12 endpoints**:

| Endpoint | Tipo | Publicado |
|---|---|---|
| `openai/gpt-image-2.5/{flare,sunburst}/text-to-image` y `.../edit` | t2i + edit | 08-sep-2026 |
| `openai/gpt-image-2` y `openai/gpt-image-2/edit` | t2i + edit | 21-abr-2026 |
| `fal-ai/gpt-image-1.5` y `fal-ai/gpt-image-1.5/edit` | t2i + edit | 16-dic-2025 |
| `fal-ai/gpt-image-1-mini` y `/edit` | t2i + edit | 21-oct-2025 |
| `fal-ai/gpt-image-1/text-to-image` y `/edit-image` | t2i + edit | 23-abr-2025 |

- La tabla `_MODELS` de Hermes soporta solo **gpt-image-1.5** y **gpt-image-2**; `gpt-image-2.5` requiere curl directo a `queue.fal.run` o patch a la tabla (no lo puede pedir la tool tal cual).
- El plugin `plugins/image_gen/fal/__init__.py` existe y queda disponible cuando `FAL_KEY` está en el entorno (`is_available()`), listando modelos desde `_it.FAL_MODELS` (la misma tabla).
- Pricing 2.5 (fal, texto literal del `pricingInfoOverride`): texto $5/1M in y $10/1M out; imagen $8/1M in y $30/1M out, con `quality` default **high** ⇒ el costo escala fuerte con quality. No comparar 2.5 contra los $/imagen planos de 1.5/2 sin decirlo.

## Fuentes de la key y trampas de procedencia (11-sep-2026)

- Vaultwarden: item `FAL - API key` (campo `FAL_KEY`) = única fuente de la credencial. **No hay item de OpenAI.**
- `/opt/data/.env` (idéntico a `/root/hermes-agent-legacy-docker/data/.env` del host, mismo md5 `f0bb2e91…`): la línea `FAL_KEY` está **comentada** (`# FAL_KEY=`) y `OPENAI_API_KEY` también está comentada y vale `sk-JzBTUf…`, o sea la key de **NaN-Builders** (mismo prefijo que la del proxy). Conclusión: no existe key OpenAI real en el entorno.
- `/root/marketing-campaign-generator/.env` **ya no existe** en DEV y `~/.config/akari-video/credentials.env` no trae `FAL_KEY` ⇒ la key de fal vive solo en el vault (inyectar al `.env` del perfil antes de activar `image_gen.provider: fal`).
- Hueco de documentación: `/opt/vault/APIS-INTEGRACIONES.md` **no menciona fal.ai** (solo NaN-Builders, Telegram/WhatsApp/Discord, Google Workspace, Coolify, crons). «Mira en el vault» puede ser Vaultwarden o el vault de docs: revisa los dos.

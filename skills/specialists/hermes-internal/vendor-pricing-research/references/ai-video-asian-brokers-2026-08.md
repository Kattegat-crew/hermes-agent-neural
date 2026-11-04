# Precios video I2V asia/brokers — 6s 720p 9:16 (verificado 19/08/2026)

Precios reales extraídos de páginas oficiales (browser CDP + fetch). Tipo de cambio: 1 USD ≈ 7.10 CNY.

## ⚠️ Kluster.ai — FUERA DE SERVICIO
- Adquirida por MITO; **servicios retirados el 9/jun/2026**. kluster.ai redirige a mito.ai.
- No proponerlo para nada.

## SiliconFlow (siliconflow.cn)
Fuente: `/pricing` (JS).
- Wan2.1 ya NO está; hostean **Wan2.2-T2V-A14B** e **Wan2.2-I2V-A14B**.
- **Wan2.2-I2V-A14B = ¥2.00 por generación** (flat, "输出价格（/个）", no por segundo).
- Max ~5s por toma → para 6s = 2 generaciones + unión ≈ ¥4.00 ≈ **$0.56/6s**. Sin audio.

## Together.ai (`/pricing` → pestaña VIDEO)
- **Wan 2.2 I2V = $0.31/video** — es "lowest resolution/duration"; 720p/6s sube (≈ $0.45–0.60/día estim).
- Otras precios/video (minimum setting): ByteAccel Seedance 2.5 **$0.115** · Seedance 2.0 **$0.16** · HappyHorse 1.1 I2V **$0.14** · Kling 2.1 Standard **$0.18** · FLU3 **$0.17** · Sora 2 **$0.80** · Veo 3 +Audio **$3.20**.

## Volcengine Ark / doubao-seedance (docs.volcengine.com/docs/82379/1544106 = "模型价格")
- Cobro **por token**: `tokens = (duración input + output) × W × H × fps / 1024`; `precio = token单价 × tokens / TKos`.
- Seedance 2.0 mini I2V 720p (sin video de entrada): ¥23/M token · promo 4折 → ¥9.2/M.
  → **720p ≈ ¥0.50/s normal · ¥0.20/s promo** → 6s ≈ **¥3.0 (~$0.42)** normal · **¥1.2 (~$0.17)** promo.
- Tabla oficial (720p, 16:9, 5s): seedance-2.0 ¥4.97 (¥0.99/s) · 2.0-fast ¥4.00 (¥0.80/s) · 2.0-mini ¥2.84 (¥0.50/s) · 2.5 ¥7.56 (¥1.51/s).
- **Promos ago.–p2026**: seedance 2.0 mini 4折 (hasta 14-sep), 2.0-fast 75折, 2.5 1080p 72折.
- Audio: seedance-1.5-pro se factura por 有声/无声 (sí soporta). 2.0-mini mudo por defecto.

## Alibaba Model Studio / DashScope (www.alibabacloud.com/help/en/model-studio/model-pricing)
- Cobro **por s de salida**: `Coste = precio/s × duración`.
- Modelos image-to-video ($/s, 720p):
  - `wan2.2-i2v-flash` (silent): **$0.036/s** → **$0.216/6s** ← el más barato
  - `wan2.6-i2v-flash`: **$0.025/s silent · $0.05/s audio** → **$0.15/$0.30/6s** ← mejor con audio
  - `wan2.5-i2v-preview`: **$0.10/s**
  - `wan2.6-i2v`: **$0.10/s** · `wan2.7-i2v`: **$0.10/s** (audio)
- T2V baratos: `wan2.1-t2v-turbo` $0.036/s · `wan2.2-t2v-plus` $0.02/s (480p).

## Ránking solo $/clip 6s 720p (I2V)
1. **Volcengine Seedance 2.0 mini (promo)** ≈ $0.17
2. **Alibaba wan2.2-i2v-flash** (silent) ≈ $0.22
3. **Alibaba wan2.6-i2v-flash** ≈ $0.30 (audio) / $0.15 (silent)
4. **Together Wan 2.2 I2V** ≈ $0.31–0.60
5. **SiliconFlow Wan2.2-I2V** ≈ $0.56
6. **Alibaba wan2.7-i2v** ≈ $0.60

**5 clips (6s)**: Seedance mini promo ≈ **$0.85** · DashScope wan2.2-flash ≈ **$1.10** · wan2.6-flash audio ≈ **$1.50** · Together ≈ $2.25 · SiliconFlow ≈ $2.80.

## Nota
La hoja del skill `ai-video-model-costing/references/video-model-pricing-2026-08.md` cubre MiniMax/Hailuo/Monid (default de producción). Esta referencia es la vista de grupo asiático/brokers baratos cuando el brief pide minimizar costo de clip.
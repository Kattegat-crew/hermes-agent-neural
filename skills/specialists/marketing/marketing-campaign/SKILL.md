---
name: marketing-campaign
description: "Use when generating monthly casino marketing plans (.docx)."
tags: [marketing, campana, docx, guiones, calendario, casino]
---

# Marketing Campaign Skill

## Qué hace

Genera **5 documentos Word (.docx)** profesionales de marketing para **cualquier empresa**:

1. **PLAN-MARKETING** — concepto de campaña, cronograma mensual, estructura de premios y KPIs medibles
2. **GUIONES-REELS** — scripts completos de video por segundo (reels 9:16, 20-30s)
3. **PLAN-EVENTOS** — evento semanal por día + coordinación con equipo de sala (bingos, sorteos, galas)
4. **BRIEF-PIEZAS** — especificaciones técnicas de piezas gráficas (post, story, carrusel, banners, tapas de reel)
5. **CALENDARIO-PUBLICACION** — matriz completa día×plataforma×sede×tipo de pieza×promo activa

## Workflow (paso a paso)

### Paso 1 — Leer el archivo de la empresa

Verificar si existe el `empresa.yaml` de la empresa objetivo. Si no existe, copiar uno de los ejemplos:

```
cp <skill-dir>/examples/golden.yaml ./empresa.yaml
```

o crear uno nuevo desde cero usando el formato definido más abajo.

### Paso 2 — Preguntar al usuario

Confirmar estos datos antes de generar:

1. **Sedes del mes**: ¿cuáles participan este mes? (campo `campaign.featured_sedes`)
2. **Promoción especial**: ¿hay alguna promoción nueva este mes? (campo `campaign.promotion`)
3. **Fechas**: ¿cuándo empieza el mes? (campo `campaign.start_date`)
4. **Cantidad de videos**: por defecto 4 (uno por quincena). Campo `campaign.videos_per_month`.
5. **Tema de campaña**: campo `campaign.theme`. Ej: "Cada pueblo tiene su historia".

### Paso 3 — Generar los 5 documentos

```bash
python3 <skill-dir>/generators/generate_docs.py \
    empresa.yaml \
    --output ./docs/
```

Esto crea 5 archivos `.docx` en el directorio `./docs/`.

### Paso 4 — Auditar con el checklist

Usar el **Checklist de Validación** (siguiente sección). Verificar cada punto antes de entregar.

### Paso 5 — Entregar

El cliente recibe los 5 documentos .docx listos para producción.

## Checklist de Validación (CRÍTICO)

Antes de entregar NUNCA, verificar TODO lo siguiente:

### 1. Estructura general
- [ ] Los 5 documentos fueron generados (existen y tienen contenido)
- [ ] **TODOS** tienen la nota: `Documento generado el AAAA-MM-DD — Plan aprobado por el cliente`
- [ ] Cada documento tiene al menos 2 páginas o 10 párrafos de contenido no trivial
- [ ] El nombre del archivo coincide con el título (PLAN-MARKETING → Plan Marketing)

### 2. Legal — obligatorio en todos los documentos
- [ ] Incluye **"Juego responsable +18"** en todas las piezas visibles
- [ ] Menciona al **regulador** (Coljuegos o el que corresponda en el YAML)
- [ ] Menciona el **umbral de retención** (valor numérico del campo `legal.retention_threshold`)
- [ ] Incluye aviso de "**Solo mayores de 18 años**" donde corresponda
- [ ] **NUNCA** inventar un número de regulador o umbral si está vacío

### 3. Idioma — Español neutro (Colombia/Latam)
- [ ] **Sin voseo rioplatense** → "Ven" y NUNCA "Veni"
- [ ] **Sin typos** → "responsable", "campaña", "ruleta", "tragamonedas" escritos bien
- [ ] Voz cercana y cálida, NUNCA burocrática
- [ ] Consistencia en uso de "tú" o "usted" (en redes sociales default: "tú")

### 4. Fechas y días de la semana
- [ ] Las fechas son correctas (coinciden con el día de la semana real)
- [ ] Los eventos están en los días correctos (miércoles≠sábado≠domingo)
- [ ] El mes coincide con `campaign.month`

### 5. Datos del YAML (fuente de verdad)
- [ ] **NO inventar nada** que no esté en `empresa.yaml`
- [ ] Campos vacíos marcados como **"[PENDIENTE DE CONFIRMAR]"**
- [ ] Sedes listadas son exactamente las del YAML
- [ ] Colores y fuentes del YAML usadas correctamente

### 6. Validación automática del script
- [ ] Ejecutar el generador con `--validate` y verificar salida de validación
- [ ] Verificar con python-docx que cada archivo abre y tiene contenido

## Estructura del empresa.yaml

El archivo `empresa.yaml` es la fuente de verdad para toda la campaña.

### Campos obligatorios

```yaml
# ---- EMPRESA ----
company:
  name: "Nombre comercial"            # Nombre del público
  legal_name: "Razón social"          # Nombre legal
  founded: 2020                       # Año de fundación
  mascot: "Lucky"                     # Mascota (si aplica)
  mascot_type: physical | digital     # Tipo de mascota
  website: "www.ejemplo.com"          # Sitio web
  brand:
    colors:
      primary: "#ddc316"              # Color principal (hex)
      secondary: "#ab0f15"            # Color secundario (hex)
      dark: "#1a1a1a"                 # Color oscuro (hex)
    fonts:
      display: "DM Serif Display"     # Para títulos
      body: "DM Sans"                 # Para cuerpo
  bonus:
    amount: 20000                     # Valor del bono (COP)
    mechanism: ruleta | tragamonedas  # Mecanismo
    prize_description: "Descripción"
    web_url: "www.site.com/bonus"
  sedes:
    - name: "Sede Principal"
      department: "Departamento"
      is_flagship: true
    - name: "Segunda Sede"
      department: "Departamento"
  contact:
    whatsapp: "+57 3XX XXX XXXX"
    email: "correo@ejemplo.com"
    instagram: "@usuario"
  legal:
    regulator: "Coljuegos"
    min_age: 18
    retention_threshold: 2514000

# ---- CAMPANA ----
campaign:
  month: "agosto"
  year: 2026
  start_date: "2026-08-15"
  videos_per_month: 4
  format: reels
  platforms: [instagram, facebook, tiktok]
  featured_sedes: ["Sede1", "Sede2"]
  theme: "El tema de la campaña"
  promotion:
    name: "Promoción activa este mes"       # o [PENDIENTE DE CONFIRMAR] si no tiene
    description: ""
    prize_amount: 0
    start_date: ""
    end_date: ""
```

### Eventos semanales (opcional)

Si se quieren eventos automáticos:

```yaml
events:
  - day: "miércoles"
    name: "Sorteo de Máquina"
    prize_min: 20000
    prize_max: 50000
    mechanism: "Selector al azar..."
  - day: "viernes"
    name: "Bingo de la Casa"
    prize_min: 150000
    prize_max: 300000
    mechanism: "Cartones gratis..."
  - day: "mensual"
    name: "Noche de Gala"
    prize_min: 1000000
    prize_max: 2000000
    mechanism: "Boletas: 1 visita..."
```

## Sistema de Eventos (configuración estándar)

### Miércoles — Sorteo de Máquina
- **Dinámica**: Selector al azar de máquina activa. Cliente debe estar jugando.
- **Premio**: Monto aleatorio entre `prize_min` y `prize_max` del YAML.
- **Público**: Presencial.
- **Coordinación**: Personal verifica y paga; sala avisa por megafonía.

### Viernes — Bingo de la Casa
- **Dinámica**: Cartones gratis con jugada mínima. 2 rondas por noche.
- **Premio**: Acumulado entre `prize_min` y `prize_max`.
- **Público**: 18+, presencial.
- **Coordinación**: Equipo de Bingo activa.

### Mensual — Noche de Gala
- **Dinámica**: Boleta física por visita (1 visita = 1 boleta). +3 boletas por interacción IG.
- **Premio**: Grandioso, entre `prize_min` y `prize_max`.
- **Coordinación**: Decoración especial, DJ, equipo de salón completo.
- **Promo paralela**: Teaser de video + story countdown 7 días antes.

### Domingo — Libre (por defecto)
- Se puede customizar definiendo un evento para domingo en el YAML.

### Personalización
Para cambiar cualquier evento, modificar el campo `events` del `empresa.yaml`.

## Formato de Scripts (Guiones de Reels)

### Estructura por segundo (30 segundos total)

| Segmento | Tiempo    | Contenido                              |
|----------|-----------|----------------------------------------|
| Hook     | 0–3s      | Gancho que detiene el scroll.           |
| Historia | 3–15s     | Contexto, experiencia del cliente.      |
| Casino   | 15–22s    | Mostrar el salón, máquina, premio.      |
| CTA      | 22–30s    | Llamado a la acción claro y directo.    |

### Formato de entrega
- **1 archivo .docx** por guión con tabla por segundo
- **Duración**: 20–30 segundos (default 30s)
- **Formato**: 9:16 vertical
- **Plataformas**: Instagram Reels, Facebook Reels, TikTok
- **Cantidad por mes**: 4 (o según `videos_per_month`)

### Contenido por segundo
Cada celda de la tabla incluye:
- **Tiempo**: rangos de 3s por fila
- **Visual**: qué se muestra (plano general, primer plano, etc.)
- **Narración**: texto que se habla en off
- **Texto en pantalla**: subtítulo o frase visible
- **B-Roll**: material de apoyo (ruleta, chips, gente, etc.)
- **Hashtags**: recomendados

## Especificaciones de Piezas Gráficas

| Tipo            | Formato     | Tamaño (px)    | Cantidad/mes |
|-----------------|-------------|-----------------|-------------|
| Post cuadrado   | 1:1         | 1080 × 1080     | 4            |
| Story           | 9:16        | 1080 × 1920     | 8            |
| Carrusel        | 4 slides    | 1080 × 1080     | 2 (8 imgs)   |
| Tapa Reel       | 9:16        | 1080 × 1920     | 4            |
| Banner TV       | 16:9        | 1920 × 1080     | 6            |
| Aviso evento    | 1:1         | 1080 × 1080     | 4            |

### Datos por pieza (en el brief)
- Dimensiones exactas
- Texto principal y secundario
- Colores del branding (`brand.colors`)
- Tipografía (`brand.fonts`)
- Uso (feed, story, pantalla TV, impreso)
- Legal: siempre "+18 juego responsable"
- CTA (llamado a la acción)

## Calendario de Publicación

### Matriz de planificación
```
Fecha (dd/mm) | Plataforma   | Formato    | Sede       | Promo activa
```

### Recomendaciones
- 1 Reel por quincena (mínimo 4/mes)
- 2 posts + 4 stories por video lanzado
- 1 banner TV cada 2-3 días (rotar en pantalla del casino)
- 1 carrusel por quincena
- Avisos de evento: 2/semana (miércoles y viernes)
- Evitar publicar en domingos (excepto con evento)
- Publicaciones nocturnas (7-10 PM) mejor performance

## Generador automático

### Instalación
```bash
pip3 install python-docx pyyaml
```

### Ejecución
```bash
python3 <skill-dir>/generators/generate_docs.py \
    empresa.yaml \
    --output ./docs/
```

### Validación automática
El script al final imprime:
```
VALIDACION → 5/5 documentos generados y verificados
Legal OK | Fechas OK | Contenido OK | Archivos OK
```

## Notas importantes
- NUNCA inventar datos que no estén en el empresa.yaml
- Legal siempre: "+18 juego responsable", regulador, umbral de retención
- NUNCA "Veni" → "Ven" (audiencia colombiana)
- Las fechas deben ser correctas (día de la semana)
- Tono: cálido, cercano, profesional

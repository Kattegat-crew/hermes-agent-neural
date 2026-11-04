---
name: wizard
description: >-
  Generación de scripts bash interactivos guiados paso a paso para operaciones manuales humanas (provisionamiento, dashboards externos, Meta CAPI, secretos y cutover).
tags: [automatizacion, bash, wizard, hitl, operaciones, secretos, devops]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
license: MIT
platforms: [linux, macos, windows]
---

# Scripts Interactivos Asistidos (Wizards Human-in-the-Loop)

Habilidad canónica para generar scripts interactivos en Bash que guían a un operador humano paso a paso a través de procedimientos manuales que no pueden ser automatizados directamente por un agente (ej. login en dashboards con 2FA, creación de credenciales en Meta Business Manager, vinculación de OAuth o corte de servicios críticos).

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- El operador debe realizar tareas en un navegador externo donde el agente no tiene acceso: *"cómo configuro el token de Meta CAPI"*, *"ayúdame a crear las credenciales de Google Workspace"*, o *"guíame para rotar la clave de Vaultwarden"*.
- Procedimientos complejos propensos a errores humanos: pasos que requieren copiar valores sensibles (API keys, IDs de píxel, tokens de acceso) e inyectarlos de forma segura en archivos `.env` o en Vault.
- Migraciones o transiciones de infraestructura que requieran puntos de confirmación explícita antes de ejecutar acciones destructivas o irreversibles.
- Evitar redactar bloques enormes de texto en el chat que el usuario deba interpretar manualmente: en su lugar, se entrega un script ejecutable que abre URLs y solicita las entradas interactivamente.

---

## Arquitectura de un Wizard (`template.sh`)

La experiencia de usuario ya está resuelta y estandarizada en [`template.sh`](template.sh). Incluye de forma nativa:
- Progreso etapa por etapa con contador visual (`Etapa X de N`).
- Apertura automática de URLs en el navegador del operador (compatible con Linux, macOS y WSL).
- Captura de secretos oculta en terminal (`ask_secret`) para no exponer contraseñas ni tokens en pantalla ni en logs.
- Persistencia idempotente de variables clave-valor en el archivo `.env` objetivo (`write_env`).
- Puntos de confirmación obligatorios (`confirm`) antes de cualquier paso crítico.
- Limpieza de pantalla (`_clear`) en cada etapa para mantener el foco en la instrucción actual.

> **Regla de Oro**: La librería superior de `template.sh` (antes del marcador `# STAGES`) es inmutable y común a todos los scripts. El agente **únicamente** redacta las etapas específicas del procedimiento al final del archivo.

---

## Procedimiento de Construcción de un Wizard

### 1. Definir el Alcance y las Variables
Antes de generar código, determina:
- Qué archivos de configuración se modificarán (ej. `/opt/hermes-agent-data/.env` o el `.env` local del repositorio).
- Lista ordenada de variables a capturar (ej. `META_ACCESS_TOKEN`, `META_PIXEL_ID`).
- Si la variable es pública (`ask`) o secreta (`ask_secret`).

### 2. Mapear la Ruta Exacta en el Dashboard
Para cada etapa, documenta la ruta visual exacta sin ambigüedades:
- URL de entrada directa.
- Menús exactos a pulsar: ej. *"Configuración del negocio → Orígenes de datos → Conjuntos de datos → Píxeles → Generar token de acceso"*.
- Indicación precisa de qué campo copiar.

### 3. Generar el Script a partir de `template.sh`
Copia la plantilla al destino temporal o de scripts (ej. `/tmp/setup-meta-token.sh` o `scripts/setup-service.sh`) y redacta las etapas:

```bash
# Ejemplo de etapa configurada
stage "Generación del Token de Meta Conversions API"
say "Abre el Administrador de Eventos de Meta en el navegador:"
open_url "https://business.facebook.com/events_manager2"
step "1. Selecciona la cuenta publicitaria de Casino Golden."
step "2. Ve a Configuración y busca la sección 'API de conversiones'."
step "3. Haz clic en 'Generar token de acceso' y copia el valor largo."
ask_secret "Pega aquí el Token de Acceso generado" META_CAPI_TOKEN
write_env "META_CAPI_TOKEN" "$META_CAPI_TOKEN"
```

### 4. Verificación y Entrega
1. Valida la sintaxis con `bash -n <ruta-del-script>`.
2. Asigna permisos de ejecución: `chmod +x <ruta-del-script>`.
3. Informa al usuario el comando exacto para ejecutarlo en su terminal (nunca lo ejecutes en background de forma desatendida, ya que requiere input humano).

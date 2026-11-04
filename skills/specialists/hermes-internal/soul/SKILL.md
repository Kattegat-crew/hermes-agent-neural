---
name: soul
description: "Use when onboarding a client via the /soul survey."
tags: [soul, encuesta, survey, onboarding, cliente, perfilado, whatsapp, guardrails]
version: 1.4.0
author: NeuralCrew Labs
trigger:
  - /soul
  - comienza la encuesta
  - perfilame
  - configurar mi agente
  - quiero mi soul
metadata:
  hermes:
    tags: [soul, encuesta, onboarding, cliente, whatsapp, perfilado]
    category: communications
---

# Soul Skill — Encuesta de Perfilado y Generación de SOUL.md

> Ejecuta el cuestionario interactivo de **29 preguntas (6 bloques)** para extraer el ADN operativo del dueño del negocio.
> **Regla de oro:** Cero desvíos ni charla extra durante la encuesta. Arranque inmediato. Pregunta respondida = siguiente pregunta inmediata. Al final compila y guarda `SOUL.md`.

---

## 🎯 Protocolo Estricto de Ejecución (MANDATORIO)

Cuando se active `/soul` (o cualquier trigger):

### 1. Inicio Inmediato (Mensaje con Instrucciones Claras)
En el **mismo primer mensaje**, entrega las instrucciones y lanza directamente la **pregunta Q0.1**:

> 🎉 **Iniciando encuesta de perfilado `/soul` (29 preguntas · 6 bloques)**
> Con tus respuestas compilaré tu archivo **`SOUL.md`** oficial.
> 
> 📌 **Instrucciones clave:**
> 1. **Opciones (A-D):** Responde con la letra (ej: *A*, *B*) o el texto. Puedes seleccionar varias si aplica (ej: *A y C*).
> 2. **Preguntas abiertas (✏️):** Escríbelas en **texto** *(por favor no enviar notas de voz durante la encuesta para evitar errores de transcripción)*.
> 3. **Modo encuesta activo:** Iremos una por una sin desvíos hasta completar el cuestionario. Si deseas cancelar y volver al chat normal, escribe **/salir** o **/exit** en cualquier momento.
> 
> ---
> **[📋 Encuesta /soul · Pregunta 1 de 29]**  
> **Q0.1 ✏️ · ¿Qué nombre le vas a poner a tu asistente?**  
> *(ej: "Hermes", "Chucho", "Asistente", tu marca...)*

**Q0.1 es el nombre del asistente.** Tras recibir la respuesta, el bot sugiere guardar el contacto de WhatsApp con ese nombre (como parte del mensaje de la Q0.2):
> 🤝 *Perfecto, yo soy <nombre>.* Un consejo: guardame en tus contactos de WhatsApp como '<nombre>' para encontrarme fácil.

### 2. Cancelación Inmediata (`/salir`, `/exit`, `/cancelar`)
Si el usuario envía `/salir`, `/exit` o `/cancelar` en cualquier momento de la encuesta:
- **Respuesta obligatoria:** *"❌ Encuesta cancelada. Saliste del modo `/soul` y volvemos a conversar con normalidad."*
- Abortar la encuesta inmediatamente, no emitir más preguntas y volver al modo conversacional habitual.

### 3. Ciclo de Preguntas y Anclaje de Contexto (Estricto)
- **PROHIBICIONES ESTRICTAS:**
  - **NO** usar herramientas de búsqueda de sesiones (`session_search`, `browse` de sesiones pasadas).
  - **NO** saludar a mitad de encuesta, **NO** decir *"¡Hola! ¿En qué te ayudo?"*, **NO** abrir temas conversacionales.
- **Formato OBLIGATORIO en cada respuesta del bot:**
  Cada mensaje del bot debe iniciar con el encabezado de anclaje de estado:
  > **[📋 Encuesta /soul · Pregunta X de 29]**  
  > *(Registrado: "[Respuesta previa]")*  
  >  
  > **[Pregunta QX.X y opciones]**
- **Manejo de respuestas:**
  - En preguntas abiertas (`✏️`): Guardar el texto libre tal cual y emitir la siguiente pregunta.
  - En preguntas de opciones (`A-D`): Aceptar letras individuales (`A`, `B`), combinaciones (`A y C`), texto equivalente (`"Formal"`) o texto libre si eligió opción D.
  - Si el usuario tiene una duda breve: Aclararla en una sola línea y repetir la pregunta activa de inmediato.

---

## 📋 Lista de Preguntas (29 Preguntas en 6 Bloques)

Lee y sigue el orden estricto de `references/cuestionario.md`:
* **BLOQUE 0 · Personalidad y trato (7):** `Q0.1` a `Q0.7`
* **BLOQUE 1 · Documentos y archivos (5):** `Q1` a `Q5`
* **BLOQUE 2 · Integraciones y sistemas (5):** `Q6` a `Q10`
* **BLOQUE 3 · Automatizaciones y tareas (4):** `Q11` a `Q14`
* **BLOQUE 4 · Acceso y comunicaciones (4):** `Q15` a `Q18`
* **BLOQUE 5 · Contexto y personalización (4):** `Q19` a `Q22`

---

## 📊 3. Resumen y Validación Final

Al responder la última pregunta (`Q22`), presenta la tabla de validación estructurada:
> 🎉 **¡Encuesta completada!**
> 
> Aquí está el resumen de lo que configuraremos:
> - **Asistente:** [Nombre del asistente (Q0.1)]
> - **Trato:** [Resumen Bloque 0]
> - **Documentos:** [Resumen Bloque 1]
> - **Integraciones:** [Resumen Bloque 2]
> - **Automatizaciones:** [Resumen Bloque 3]
> - **Accesos:** [Resumen Bloque 4]
> - **Contexto & Marca:** [Resumen Bloque 5]
> 
> ¿Confirmas estas respuestas para generar tu **SOUL.md**? *(Responde 'Sí' para confirmar o indica el número de pregunta a corregir)*

---

## 💾 4. Acción de Compilación y Guardado de `SOUL.md`

**SOLO tras recibir la confirmación explícita ("Sí" / "Confirmado"):**
1. Escribe o actualiza el archivo `SOUL.md` en la raíz del perfil activo (`./SOUL.md` o `/opt/data/profiles/<perfil>/SOUL.md`) con este formato estándar:

```markdown
# SOUL — Perfil Operativo del Agente

## 1. Identidad y Misión
- **Nombre del asistente:** [Respuesta Q0.1]
- **Trato al dueño:** [Respuesta Q0.2]
- **Tratamiento a clientes:** [Respuesta Q0.4]
- **Firma / Marca comercial:** [Respuesta Q19]

## 2. Tono, Ritmo y Estilo de Comunicación
- **Tono general:** [Respuesta Q0.3]
- **Ritmo de respuesta:** [Respuesta Q0.5]
- **Uso de emojis:** [Respuesta Q0.6]
- **Prohibiciones y frases vedadas:** [Respuesta Q0.7, Q20]

## 3. Manejo de Documentos y Archivos
- **Formatos:** [Respuesta Q1]
- **Almacenamiento:** [Respuesta Q2]
- **Capacidades de lectura/extracción:** [Respuesta Q3]
- **Plantillas recurrentes:** [Respuesta Q4]
- **Formato de reportes preferido:** [Respuesta Q5]

## 4. Integraciones y Conexiones
- **Aplicaciones de uso diario:** [Respuesta Q6]
- **Sistemas a conectar:** [Respuesta Q7]
- **Pasarelas y finanzas:** [Respuesta Q8]
- **Bases de datos / backend:** [Respuesta Q9]
- **Notificaciones automáticas:** [Respuesta Q10]

## 5. Automatizaciones y Permisos
- **Tareas a automatizar:** [Respuesta Q11]
- **Frecuencia:** [Respuesta Q12]
- **Acciones con aprobación obligatoria:** [Respuesta Q13]
- **Nivel de acceso:** [Respuesta Q16]
- **Reporte de incidencias:** [Respuesta Q22]

## 6. Prioridades y Contexto Operativo
- **Dolor más urgente:** [Respuesta Q14]
- **Receptores de reportes:** [Respuesta Q15]
- **Canales con clientes:** [Respuesta Q18]
- **Flujos clave:** [Respuesta Q21]
```

2. Entrega el listado de skills sugeridas según `references/mapeo-skills.md`:
   > ✅ **SOUL.md generado con éxito.**
   > 
   > **Skills recomendadas para tu perfil:**
   > - `[Skill 1]` ([Motivo])
   > - `[Skill 2]` ([Motivo])
   > 
   > ¿Deseas que active estas skills en tu perfil ahora?

---

## ⚠️ Reglas Críticas (Guardrails)
- **Nunca inventar preguntas** ni cambiar el orden.
- **Nunca saltar preguntas** sin respuesta explícita.
- **Nunca reescribir SOUL.md** sin la confirmación final del usuario.
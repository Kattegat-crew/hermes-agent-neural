"""Questions catalog for /soul onboarding survey."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class QuestionType(Enum):
    OPEN = "open"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"

@dataclass
class Question:
    id: str
    block_id: int
    block_name: str
    title: str
    type: QuestionType
    options: Optional[List[str]] = None
    hint: Optional[str] = None

QUESTIONS: List[Question] = [
    # BLOQUE 0 · Personalidad y trato (7)
    Question(
        id="Q0.1",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Qué nombre le vas a poner a tu asistente?",
        type=QuestionType.OPEN,
        hint="Escribe el nombre que quieras (ej: Hermes, Chucho, Asistente, tu marca...)"
    ),
    Question(
        id="Q0.2",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Cómo quieres que el agente te llame a ti?",
        type=QuestionType.OPEN,
        hint="Escribe el nombre o trato (ej: Jefe, Don Jesús, Chucho, Yisus, por tu nombre...)"
    ),
    Question(
        id="Q0.3",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Qué tono quieres para el agente al hablar contigo?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Formal y respetuoso",
            "B) Cercano / colombiano",
            "C) Ejecutivo y breve (al grano)",
            "D) ✏️ Personalizado (escríbelo)"
        ]
    ),
    Question(
        id="Q0.4",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Tratamiento con tus clientes: de 'tú' o de 'usted'?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Tú (cercano)",
            "B) Usted (respetuoso)",
            "C) Según contexto (formal montos/legal, tú diario)",
            "D) ✏️ Otro"
        ]
    ),
    Question(
        id="Q0.5",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Cómo prefieres el ritmo del agente?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Directo: respuesta clara y sin rodeos",
            "B) Conversacional: saluda, contexto, luego respuesta",
            "C) Mezcla: directo pero con buen trato",
            "D) ✏️ Otro"
        ]
    ),
    Question(
        id="Q0.6",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Te gusta que el agente use emojis?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Sí, con moderación",
            "B) Muy pocos (formal)",
            "C) No, ninguno",
            "D) ✏️ Otro"
        ]
    ),
    Question(
        id="Q0.7",
        block_id=0,
        block_name="Personalidad y trato",
        title="¿Hay frases o palabras que el agente NO debe usar jamás?",
        type=QuestionType.OPEN,
        hint="Escribe palabras prohibidas (ej: jerga, 'cliente premium', extranjerismos) o escribe 'Ninguna'."
    ),

    # BLOQUE 1 · Documentos y archivos (5)
    Question(
        id="Q1",
        block_id=1,
        block_name="Documentos y archivos",
        title="¿Con qué tipo de documentos trabaja tu negocio?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) PDF (contratos, informes, estados de cuenta)",
            "B) Excel / Sheets (planillas, presupuestos, listas)",
            "C) Word / Docs (cartas, oficios)",
            "D) ✏️ Otros (imágenes, CSV, etc.)"
        ]
    ),
    Question(
        id="Q2",
        block_id=1,
        block_name="Documentos y archivos",
        title="¿Dónde guardas estos documentos?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Google Drive",
            "B) Servidor local / Computadora",
            "C) WhatsApp (se reciben y guardan ahí)",
            "D) ✏️ Otra plataforma"
        ]
    ),
    Question(
        id="Q3",
        block_id=1,
        block_name="Documentos y archivos",
        title="¿Te gustaría que el agente lea/extraiga datos de esos documentos?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Sí — resumir PDFs y extraer datos",
            "B) Sí — editar/llenar plantillas (Excel/Word)",
            "C) Solo leer y confirmar contenidos",
            "D) No por ahora"
        ]
    ),
    Question(
        id="Q4",
        block_id=1,
        block_name="Documentos y archivos",
        title="¿Tienes plantillas de documentos que se repiten con frecuencia?",
        type=QuestionType.OPEN,
        hint="Escribe cuáles (ej: recibo de pago, formato de cotización) o escribe 'Ninguna'."
    ),
    Question(
        id="Q5",
        block_id=1,
        block_name="Documentos y archivos",
        title="¿Qué formato prefieres para recibir reportes y resúmenes?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) PDF estructurado",
            "B) Excel / CSV (para procesar)",
            "C) Mensaje de texto en WhatsApp",
            "D) ✏️ Otro"
        ]
    ),

    # BLOQUE 2 · Integraciones y sistemas (5)
    Question(
        id="Q6",
        block_id=2,
        block_name="Integraciones y sistemas",
        title="¿Qué aplicaciones o sistemas usas a diario?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Google Workspace (Drive, Docs, Sheets, Calendar)",
            "B) Notion / Base de conocimiento",
            "C) CRM de ventas",
            "D) ✏️ Otras aplicaciones"
        ]
    ),
    Question(
        id="Q7",
        block_id=2,
        block_name="Integraciones y sistemas",
        title="¿Qué te gustaría conectar con el agente?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Google Drive / Sheets (compartir archivos)",
            "B) Google Calendar (agendar citas/recordatorios)",
            "C) WhatsApp del equipo (notificaciones)",
            "D) ✏️ Otro sistema"
        ]
    ),
    Question(
        id="Q8",
        block_id=2,
        block_name="Integraciones y sistemas",
        title="¿Usas herramientas de pago o finanzas?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Mercado Pago / Nequi / Daviplata",
            "B) Pasarela de pago (Wompi, PSE, Stripe)",
            "C) Solo en efectivo",
            "D) ✏️ Otra pasarela"
        ]
    ),
    Question(
        id="Q9",
        block_id=2,
        block_name="Integraciones y sistemas",
        title="¿Hay alguna base de datos o backend al que el agente deba acceder?",
        type=QuestionType.OPEN,
        hint="Escribe detalles (ej: PostgreSQL, MySQL, API de ventas) o escribe 'No'."
    ),
    Question(
        id="Q10",
        block_id=2,
        block_name="Integraciones y sistemas",
        title="¿Qué notificaciones automáticas te gustaría recibir?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Alertas de nuevos pedidos / leads",
            "B) Recordatorios de pendientes operativos",
            "C) Resumen diario / semanal de actividad",
            "D) ✏️ Otras alertas"
        ]
    ),

    # BLOQUE 3 · Automatizaciones y tareas (4)
    Question(
        id="Q11",
        block_id=3,
        block_name="Automatizaciones y tareas",
        title="¿Cuáles tareas de tu día se repiten y quisieras automatizar?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Enviar respuestas/mensajes frecuentes a clientes",
            "B) Generar documentos/reportes desde datos",
            "C) Seguimiento de pagos y cobros",
            "D) ✏️ Otras tareas"
        ]
    ),
    Question(
        id="Q12",
        block_id=3,
        block_name="Automatizaciones y tareas",
        title="¿Con qué frecuencia debería el agente correr esas automatizaciones?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Cada hora / tiempo real",
            "B) Diario (una vez al día)",
            "C) Semanal",
            "D) Bajo demanda (cuando yo lo pida)"
        ]
    ),
    Question(
        id="Q13",
        block_id=3,
        block_name="Automatizaciones y tareas",
        title="¿Qué tareas requieren tu APROBACIÓN siempre antes de ejecutarse?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) Enviar WhatsApp masivo a clientes",
            "B) Realizar pagos o transacciones",
            "C) Publicar en redes sociales",
            "D) ✏️ Otras acciones sensibles"
        ]
    ),
    Question(
        id="Q14",
        block_id=3,
        block_name="Automatizaciones y tareas",
        title="¿Qué es lo más urgente que te duele hoy y quieres resolver esta semana?",
        type=QuestionType.OPEN,
        hint="Escribe el principal cuello de botella actual."
    ),

    # BLOQUE 4 · Acceso y comunicaciones (4)
    Question(
        id="Q15",
        block_id=4,
        block_name="Acceso y comunicaciones",
        title="¿Quién más debe recibir notificaciones/reportes además de ti?",
        type=QuestionType.OPEN,
        hint="Escribe nombres/roles de socios o equipo (o escribe 'Solo yo')."
    ),
    Question(
        id="Q16",
        block_id=4,
        block_name="Acceso y comunicaciones",
        title="¿Qué nivel de acceso tendrá el agente en tus sistemas?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Total (uso confiado y autónomo)",
            "B) Usuario de solo lectura",
            "C) Consultarme antes de cada acceso",
            "D) ✏️ Acceso segmentado"
        ]
    ),
    Question(
        id="Q17",
        block_id=4,
        block_name="Acceso y comunicaciones",
        title="¿Tienes manuales, catálogos o archivos de productos para entrenar al agente?",
        type=QuestionType.OPEN,
        hint="Escribe qué material tienes disponible (o escribe 'No por ahora')."
    ),
    Question(
        id="Q18",
        block_id=4,
        block_name="Acceso y comunicaciones",
        title="¿Qué canales de comunicación usas principalmente con tus clientes?",
        type=QuestionType.MULTI_CHOICE,
        options=[
            "A) WhatsApp (canal principal)",
            "B) Instagram / Facebook",
            "C) Correo electrónico",
            "D) ✏️ Otro canal"
        ]
    ),

    # BLOQUE 5 · Contexto y personalización (4)
    Question(
        id="Q19",
        block_id=5,
        block_name="Contexto y personalización",
        title="¿Qué marca o nombre debe usar el agente para firmar en WhatsApp?",
        type=QuestionType.OPEN,
        hint="Escribe el nombre de la empresa / marca (ej: NeuralCrew Labs, Golden Game...)."
    ),
    Question(
        id="Q20",
        block_id=5,
        block_name="Contexto y personalización",
        title="¿Tienes preferencias específicas sobre el vocabulario o estilo?",
        type=QuestionType.OPEN,
        hint="Escribe modismos preferidos o escribe 'Estándar profesional'."
    ),
    Question(
        id="Q21",
        block_id=5,
        block_name="Contexto y personalización",
        title="¿Tienes algún ejemplo de conversación real que quieras que aprenda?",
        type=QuestionType.OPEN,
        hint="Pega un fragmento breve de ejemplo o escribe 'Ninguno'."
    ),
    Question(
        id="Q22",
        block_id=5,
        block_name="Contexto y personalización",
        title="¿Cómo debe informarte el agente cuando detecte una anomalía o error?",
        type=QuestionType.SINGLE_CHOICE,
        options=[
            "A) Avisar de inmediato por WhatsApp",
            "B) Incluirlo en el resumen al final del día",
            "C) Solo si es un fallo crítico",
            "D) ✏️ Otro esquema"
        ]
    ),
]

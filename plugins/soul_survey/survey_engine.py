"""Deterministic State Machine Engine for /soul survey."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .questions import QUESTIONS, Question, QuestionType

logger = logging.getLogger("hermes.plugins.soul_survey")

CACHE_DIR = Path("/opt/data/cache/soul_survey")
PROFILES_DIR = Path("/opt/data/profiles")


def _get_clean_id(chat_id: str) -> str:
    return str(chat_id or "").replace("@", "_").replace(":", "_").replace("+", "")


def get_state_file(chat_id: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"state_{_get_clean_id(chat_id)}.json"


def load_state(chat_id: str) -> Optional[Dict[str, Any]]:
    path = get_state_file(chat_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load soul survey state: %s", e)
        return None


def save_state(chat_id: str, state: Dict[str, Any]) -> None:
    path = get_state_file(chat_id)
    try:
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to save soul survey state: %s", e)


def clear_state(chat_id: str) -> None:
    path = get_state_file(chat_id)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


async def send_question(adapter: Any, chat_id: str, index: int, prev_answer: Optional[str] = None) -> None:
    if index >= len(QUESTIONS):
        return

    q: Question = QUESTIONS[index]
    num = index + 1
    total = len(QUESTIONS)
    
    header = f"*[📋 Encuesta /soul · Pregunta {num} de {total}]*"
    if prev_answer and index > 0:
        prev_q = QUESTIONS[index - 1]
        header += f"\n_({prev_q.id} guardado: \"{prev_answer[:40]}\")_\n"
    else:
        header += "\n"

    # Q0.1 (nombre del asistente) respondida → sugerir guardar el contacto de WhatsApp
    if index == 1 and prev_answer:
        header += (
            f"🤝 *Perfecto, yo soy {prev_answer}.* Un consejo: guardame en tus contactos "
            f"de WhatsApp como '{prev_answer}' para encontrarme fácil.\n"
        )

    # Try sending native WhatsApp poll if closed question
    if q.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE) and q.options:
        selectable_count = len(q.options) if q.type == QuestionType.MULTI_CHOICE else 1
        clean_question = f"{q.id} · {q.title}"
        if len(clean_question) > 250:
            clean_question = clean_question[:247] + "..."

        if hasattr(adapter, "send_poll"):
            try:
                if prev_answer:
                    await adapter.send(chat_id=chat_id, content=header)
                res = await adapter.send_poll(
                    chat_id=chat_id,
                    question=clean_question,
                    options=q.options,
                    selectable_count=selectable_count,
                )
                if res and getattr(res, "success", False):
                    return
                logger.warning("Native WhatsApp poll failed, falling back to text: %s", getattr(res, "error", "unknown"))
            except Exception as e:
                logger.warning("Error calling send_poll, falling back to text: %s", e)

        # Text fallback for options
        opts_text = "\n".join(f"- {opt}" for opt in q.options)
        multi_hint = " _(puedes elegir varias opciones)_" if q.type == QuestionType.MULTI_CHOICE else ""
        content = f"{header}\n*{q.id} · {q.title}*{multi_hint}\n\n{opts_text}\n\n_Responde con la letra (ej: A, B o A y C) o escribe tu respuesta libre._"
        await adapter.send(chat_id=chat_id, content=content)
    else:
        # Open question
        hint_text = f"\n_{q.hint}_" if q.hint else "\n_Escribe tu respuesta en texto._"
        content = f"{header}\n*{q.id} ✏️ · {q.title}*{hint_text}"
        await adapter.send(chat_id=chat_id, content=content)


def generate_soul_markdown(answers: Dict[str, str], profile: str) -> str:
    q0_0 = answers.get("Q0.1", "Hermes")
    q0_1 = answers.get("Q0.2", "Chucho")
    q0_2 = answers.get("Q0.3", "Cercano / colombiano y ejecutivo")
    q0_3 = answers.get("Q0.4", "Tú (cercano)")
    q0_4 = answers.get("Q0.5", "Directo y al grano")
    q0_5 = answers.get("Q0.6", "Sí, con moderación")
    q0_6 = answers.get("Q0.7", "Ninguna")

    q1 = answers.get("Q1", "PDF, Excel / Sheets")
    q2 = answers.get("Q2", "Google Drive / WhatsApp")
    q3 = answers.get("Q3", "Sí, resumir PDFs y extraer datos")
    q4 = answers.get("Q4", "Plantillas operativas estándar")
    q5 = answers.get("Q5", "Mensajes de texto en WhatsApp y PDF")

    q6 = answers.get("Q6", "Google Workspace, Notion")
    q7 = answers.get("Q7", "Google Drive/Sheets, Calendar, WhatsApp")
    q8 = answers.get("Q8", "Pasarelas estándar (Nequi, Daviplata, Wompi)")
    q9 = answers.get("Q9", "Sin base de datos externa directa")
    q10 = answers.get("Q10", "Alertas de pedidos, recordatorios y resumen diario")

    q11 = answers.get("Q11", "Respuestas frecuentes y generación de reportes")
    q12 = answers.get("Q12", "Diario / Bajo demanda")
    q13 = answers.get("Q13", "Envíos masivos y movimientos de dinero")
    q14 = answers.get("Q14", "Automatizar el flujo diario de atención y perfilado")

    q15 = answers.get("Q15", "Solo el dueño principal")
    q16 = answers.get("Q16", "Total con consultas en acciones sensibles")
    q17 = answers.get("Q17", "Catálogos y manuales disponibles")
    q18 = answers.get("Q18", "WhatsApp principal")

    q19 = answers.get("Q19", "NeuralCrew Labs")
    q20 = answers.get("Q20", "Español natural profesional")
    q21 = answers.get("Q21", "Atención fluida y soporte técnico")
    q22 = answers.get("Q22", "Avisar de inmediato por WhatsApp si hay error")

    return f"""# SOUL — Perfil Operativo del Agente ({profile})

## 1. Identidad y Misión
- **Nombre del asistente:** {q0_0}
- **Trato al dueño:** {q0_1}
- **Tratamiento a clientes:** {q0_3}
- **Firma / Marca comercial:** {q19}
- **Misión:** Asistente técnico y operativo de alta fidelidad, mano derecha de {q0_1}.

## 2. Tono, Ritmo y Reglas de Comunicación
- **Tono general:** {q0_2}
- **Ritmo de respuesta:** {q0_4}
- **Uso de emojis:** {q0_5}
- **Prohibiciones y filtros estrictos:** {q0_6} (No usar frases vedadas ni desviar el foco).
- **Estilo de vocabulario:** {q20}

## 3. Manejo de Documentos y Archivos
- **Formatos con los que trabaja:** {q1}
- **Almacenamiento:** {q2}
- **Capacidades requeridas:** {q3}
- **Plantillas recurrentes:** {q4}
- **Formato preferido para reportes:** {q5}

## 4. Integraciones y Conexiones
- **Herramientas de uso diario:** {q6}
- **Sistemas a conectar:** {q7}
- **Pasarelas y finanzas:** {q8}
- **Bases de datos / backend:** {q9}
- **Notificaciones automáticas deseadas:** {q10}

## 5. Automatizaciones y Permisos
- **Tareas a automatizar:** {q11}
- **Frecuencia de ejecución:** {q12}
- **Acciones que requieren APROBACIÓN obligatoria:** {q13}
- **Nivel de acceso:** {q16}
- **Reporte de incidencias y fallos:** {q22}

## 6. Prioridades y Contexto Operativo
- **Foco / Dolor principal actual:** {q14}
- **Destinatarios de reportes:** {q15}
- **Disponibilidad de material de entrenamiento:** {q17}
- **Canales con clientes:** {q18}
- **Ejemplos de conversaciones:** {q21}
"""


async def handle_survey_message(event: Any, gateway: Any) -> Optional[Dict[str, Any]]:
    source = event.source
    chat_id = source.chat_id
    text = (event.text or "").strip()
    profile = getattr(source, "profile", None) or "ragnarcho"
    adapter = gateway._adapter_for_source(source) if hasattr(gateway, "_adapter_for_source") else None
    if not adapter and hasattr(gateway, "adapters"):
        adapter = gateway.adapters.get(source.platform)

    if not adapter:
        return None

    state = load_state(chat_id)
    text_lower = text.lower()

    # Trigger start
    is_start_trigger = text_lower in {"/soul", "soul", "comienza la encuesta", "perfilame", "configurar mi agente", "quiero mi soul"}
    
    if not state:
        if not is_start_trigger:
            return None

        state = {
            "chat_id": chat_id,
            "profile": profile,
            "current_step": 0,
            "status": "in_progress",
            "answers": {}
        }
        save_state(chat_id, state)

        welcome = (
            "🎉 *Iniciando encuesta de perfilado /soul (29 preguntas · 6 bloques)*\n"
            "Con tus respuestas compilaré tu archivo *SOUL.md* oficial.\n\n"
            "📌 *Instrucciones clave:*\n"
            "1. *Opciones (A-D):* Marca en pantalla o responde con la letra (ej: *A*, *B* o *A y C*).\n"
            "2. *Preguntas abiertas (✏️):* Escríbelas en *texto* (sin notas de voz).\n"
            "3. *Modo exclusivo:* Iremos una por una hasta terminar. Escribe */salir* o */exit* en cualquier momento para cancelar.\n"
        )
        await adapter.send(chat_id=chat_id, content=welcome)
        await send_question(adapter, chat_id, index=0)
        return {"action": "skip", "reason": "soul_survey_started"}

    # Handle Cancellation
    if text_lower in {"/salir", "/exit", "/cancelar", "salir", "cancelar"}:
        clear_state(chat_id)
        await adapter.send(
            chat_id=chat_id,
            content="❌ *Encuesta cancelada.* Saliste del modo `/soul` y volvemos a conversar con normalidad."
        )
        return {"action": "skip", "reason": "soul_survey_cancelled"}

    status = state.get("status", "in_progress")

    if status == "in_progress":
        step = state.get("current_step", 0)
        if step < len(QUESTIONS):
            current_q = QUESTIONS[step]
            state["answers"][current_q.id] = text
            next_step = step + 1
            state["current_step"] = next_step

            if next_step < len(QUESTIONS):
                save_state(chat_id, state)
                await send_question(adapter, chat_id, index=next_step, prev_answer=text)
                return {"action": "skip", "reason": f"soul_survey_q_{next_step}"}
            else:
                state["status"] = "awaiting_confirmation"
                save_state(chat_id, state)

                ans = state["answers"]
                summary = (
                    "🎉 *¡Encuesta completada con éxito! (29/29)*\n\n"
                    "📋 *Resumen de configuración registrado:*\n"
                    f"• *Nombre del asistente:* {ans.get("Q0.1", "-")}\n"
                    f"• *Trato al dueño:* {ans.get("Q0.2", "-")}\n"
                    f"• *Tono y ritmo:* {ans.get("Q0.3", "-")} · {ans.get("Q0.5", "-")}\n"
                    f"• *Documentos:* {ans.get("Q1", "-")} en {ans.get("Q2", "-")}\n"
                    f"• *Integraciones:* {ans.get("Q6", "-")} ➔ {ans.get("Q7", "-")}\n"
                    f"• *Automatizaciones:* {ans.get("Q11", "-")} ({ans.get("Q12", "-")})\n"
                    f"• *Aprobaciones:* {ans.get("Q13", "-")}\n"
                    f"• *Firma / Marca:* {ans.get("Q19", "-")}\n\n"
                    "¿Confirmas estas respuestas para compilar y guardar tu *SOUL.md*?\n"
                    "👉 Responde *Sí* o *Confirmar* para guardar (o indica qué pregunta corregir)."
                )
                await adapter.send(chat_id=chat_id, content=summary)
                return {"action": "skip", "reason": "soul_survey_summary"}

    if status == "awaiting_confirmation":
        if any(w in text_lower for w in ["sí", "si", "confirmar", "confirmo", "ok", "adelante", "dale", "guardar", "listo"]):
            soul_content = generate_soul_markdown(state["answers"], profile)
            
            target_profile_dir = PROFILES_DIR / profile
            target_profile_dir.mkdir(parents=True, exist_ok=True)
            target_soul_file = target_profile_dir / "SOUL.md"
            target_soul_file.write_text(soul_content, encoding="utf-8")
            
            if profile == "default" or profile == "main":
                Path("/opt/data/SOUL.md").write_text(soul_content, encoding="utf-8")

            clear_state(chat_id)

            final_msg = (
                f"✅ *¡SOUL.md compilado y guardado con éxito en el perfil `{profile}`!* 🚀\n\n"
                "🧰 *Skills recomendadas para tu perfil:*\n"
                "• `document-reader` (Lectura y extracción de PDFs)\n"
                "• `xlsx` (Generación de planillas y reportes Excel)\n"
                "• `cron-watchdog-scripts` (Automatización de tareas programadas)\n"
                "• `humanizer` (Optimización de tono natural y empático)\n\n"
                "El agente ha quedado configurado con tu ADN operativo. Ya puedes conversar normalmente con él."
            )
            await adapter.send(chat_id=chat_id, content=final_msg)
            return {"action": "skip", "reason": "soul_survey_saved"}
        else:
            msg = (
                "Por favor responde *Sí* o *Confirmar* para guardar tu SOUL.md, "
                "o escribe */salir* si deseas descartar la encuesta."
            )
            await adapter.send(chat_id=chat_id, content=msg)
            return {"action": "skip", "reason": "soul_survey_await_confirm"}

    return None

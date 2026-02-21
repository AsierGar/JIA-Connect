"""
================================================================================
PATIENT_BOT.PY - Chatbot Asistente para Pacientes
================================================================================

Este módulo implementa un chatbot inteligente que responde a las dudas
de los pacientes sobre su tratamiento y medicación.

CARACTERÍSTICAS:
- Guardrails de seguridad para derivar urgencias al médico
- Respuestas específicas para dosis olvidadas de cada medicamento
- Integración con RAG para consultar guías médicas
- Extracción de medicación actual del historial del paciente

PRIORIDADES DE RESPUESTA:
1. Guardrails: Detectar emergencias y derivar
2. Dosis olvidadas: Respuestas específicas por medicamento
3. Medicación actual: Extraer del plan de tratamiento
4. Citas: Información sobre gestión de citas
5. RAG: Consultar guías médicas para preguntas generales
6. Fallback: Derivar al médico si no hay respuesta

MEDICAMENTOS SOPORTADOS:
- Metotrexato (MTX)
- Ácido Fólico
- Ibuprofeno / Naproxeno
- Prednisona
- Biológicos: Adalimumab, Tocilizumab, Etanercept
================================================================================
"""

import streamlit as st
import os
import re

# Intentar importar el motor RAG (puede no estar disponible)
try:
    from rag_engine import cargar_conocimiento, consultar_rag
    RAG_DISPONIBLE = True
    print("✅ RAG Engine importado correctamente.")
except ImportError as e:
    print(f"❌ ERROR CRÍTICO IMPORTANDO RAG: {e}")
    RAG_DISPONIBLE = False
except Exception as e:
    print(f"❌ ERROR DESCONOCIDO EN RAG: {e}")
    RAG_DISPONIBLE = False

# Caché del vectorstore en sesión (para no recargarlo cada vez)
if "vectorstore_cache" not in st.session_state:
    st.session_state.vectorstore_cache = None


def _extraer_medicaciones_del_plan(plan_texto):
    """
    Extrae las medicaciones del plan de tratamiento y las formatea.
    
    Busca patrones de medicamentos conocidos en el texto del plan
    y extrae información de dosis y frecuencia cuando está disponible.
    
    Args:
        plan_texto: Texto del plan de tratamiento
        
    Returns:
        list: Lista de strings formateados con cada medicación
              Ej: ["💉 **Metotrexato** 15 mg (semanal)", "💊 **Ácido Fólico** 5 mg (diario)"]
              None si no se encontraron medicaciones
    """
    if not plan_texto:
        return None
    
    texto_lower = plan_texto.lower()
    medicaciones = []
    
    # Diccionario de medicamentos con sus variantes y emojis
    medicamentos_info = {
        "Metotrexato": {
            "variantes": ["metotrexato", "metotrexate", "mtx"],
            "emoji": "💉"
        },
        "Ácido Fólico": {
            "variantes": ["ácido fólico", "acido folico", "ac fólico", "ac folico", "acfol"],
            "emoji": "💊"
        },
        "Ibuprofeno": {
            "variantes": ["ibuprofeno", "ibuprofen"],
            "emoji": "💊"
        },
        "Naproxeno": {
            "variantes": ["naproxeno"],
            "emoji": "💊"
        },
        "Prednisona": {
            "variantes": ["prednisona", "prednisone", "corticoide"],
            "emoji": "💊"
        },
        "Adalimumab (Humira)": {
            "variantes": ["adalimumab", "humira"],
            "emoji": "💉"
        },
        "Tocilizumab": {
            "variantes": ["tocilizumab", "actemra"],
            "emoji": "💉"
        },
        "Etanercept": {
            "variantes": ["etanercept", "enbrel"],
            "emoji": "💉"
        }
    }
    
    for med_nombre, med_info in medicamentos_info.items():
        for variante in med_info["variantes"]:
            if variante in texto_lower:
                # Intentar extraer la dosis con regex
                patron_dosis = rf"{variante}[^\d]*(\d+(?:[.,]\d+)?)\s*mg"
                match = re.search(patron_dosis, texto_lower)
                dosis = match.group(1) + " mg" if match else ""
                
                # Detectar frecuencia en el contexto cercano
                frecuencia = ""
                idx = texto_lower.find(variante)
                contexto = texto_lower[idx:idx+100] if idx >= 0 else ""
                
                if "semanal" in contexto:
                    frecuencia = "semanal"
                elif "diario" in contexto or "cada día" in contexto or "/día" in contexto:
                    frecuencia = "diario"
                elif "quincenal" in contexto or "cada 2 semanas" in contexto:
                    frecuencia = "cada 2 semanas"
                elif "cada 8 horas" in contexto:
                    frecuencia = "cada 8 horas"
                elif "cada 12 horas" in contexto:
                    frecuencia = "cada 12 horas"
                elif any(dia in contexto for dia in ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]):
                    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                    for dia in dias:
                        if dia in contexto:
                            frecuencia = f"los {dia}s"
                            break
                
                # Formatear la medicación
                med_str = f"{med_info['emoji']} **{med_nombre}**"
                if dosis:
                    med_str += f" {dosis}"
                if frecuencia:
                    med_str += f" ({frecuencia})"
                
                if med_str not in medicaciones:
                    medicaciones.append(med_str)
                break  # No buscar más variantes si ya encontramos una
    
    return medicaciones if medicaciones else None


def responder_duda_paciente(pregunta, historial_paciente, nombre_paciente):
    """
    Genera una respuesta a la pregunta del paciente.
    
    Args:
        pregunta: Texto de la pregunta del paciente
        historial_paciente: Lista de registros de visitas del paciente
        nombre_paciente: Nombre del paciente para personalizar respuestas
        
    Returns:
        str: Respuesta formateada en Markdown
    """
    p = pregunta.lower()
    
    # =========================================================================
    # 1. GUARDRAILS - Detectar situaciones de riesgo
    # =========================================================================
    
    # Greetings
    if p in ["hello", "hi", "thanks", "thank you", "hey", "good morning", "good afternoon", "hola", "buenas", "gracias", "qué tal", "buenos días", "buenas tardes"]:
        return f"Hello {nombre_paciente}! I'm your unit's virtual assistant. I'm here to help with any questions about your treatment or medication."

    # Urgency: refer immediately
    palabras_urgencia = ["severe pain", "strong pain", "blood", "high fever", "swollen", "swelling", "can't breathe", "emergency", "chest pain", "dolor fuerte", "sangre", "fiebre alta", "hinchado", "ahogo", "urgencia", "pecho"]
    if any(x in p for x in palabras_urgencia):
        return "⚠️ **POSSIBLE URGENT SYMPTOM**\n\nAs a virtual assistant I cannot assess medical emergencies. Please go to the hospital or contact your rheumatologist immediately."

    # =========================================================================
    # 2. DOSIS OLVIDADAS - Respuestas específicas por medicamento
    # =========================================================================
    
    palabras_olvido = [
        "forgot", "missed", "forgotten", "lost", "didn't take", "skipped",
        "olvidé", "olvide", "olvidado", "perdí", "perdi", "perdido",
        "no me pinché", "no me pinche", "no tomé", "no tome",
        "salté", "salte", "saltado", "me la salté", "se me pasó",
        "yesterday", "what do i do", "qué hago", "que hago", "me olvide"
    ]
    es_dosis_olvidada = any(x in p for x in palabras_olvido)
    
    if es_dosis_olvidada:
        return ("If you miss a dose, you can usually take it within 24 to 48 hours of your "
                "scheduled time. If more than two days have passed, it is best to skip the "
                "missed dose and take the next one at your regular scheduled time. Do not take "
                "a double dose to make up for the missed one. If you have doubts, please contact "
                "your rheumatologist.")

    # =========================================================================
    # 3. ALCOHOL INTERACTION
    # =========================================================================

    palabras_alcohol = ["alcohol", "drink", "beer", "wine", "cerveza", "vino", "beber"]
    if any(x in p for x in palabras_alcohol):
        return ("Methotrexate is processed by the liver, and alcohol can increase the risk "
                "of liver strain or damage. It is generally recommended to avoid alcohol or "
                "strictly limit consumption while on this medication. Please discuss safe "
                "limits directly with your doctor.")

    # =========================================================================
    # 4. WEATHER / OUT OF SCOPE (checked early to avoid false positives)
    # =========================================================================

    palabras_weather = ["weather", "forecast", "rain", "temperature", "sunny",
                        "tiempo que hace", "lluvia", "clima", "pronóstico"]
    if any(x in p for x in palabras_weather):
        return ("I am a virtual assistant specialized in your medical follow-up for JIA, "
                "so I cannot check the weather forecast. However, remember that changes in "
                "weather can sometimes influence joint stiffness, so stay warm and active!")

    # =========================================================================
    # 5. CURRENT MEDICATION - Extract from history
    # =========================================================================

    palabras_medicacion = [
        "medication", "medicine", "treatment", "what am i taking",
        "my medication", "my medicine", "my dose",
        "medicación", "medicacion", "medicamento", "tratamiento",
        "qué tomo", "que tomo", "qué llevo", "que llevo",
        "dosis", "pauta", "pastilla"
    ]
    es_pregunta_medicacion = any(x in p for x in palabras_medicacion)
    
    if es_pregunta_medicacion:
        ultimo_plan = None
        
        # Buscar el plan de tratamiento en la última visita
        if historial_paciente and len(historial_paciente) > 0:
            ultimo = historial_paciente[-1]
            if isinstance(ultimo, dict):
                plan_directo = ultimo.get("plan_tratamiento", "")
                if not plan_directo:
                    # Intentar extraer del curso clínico
                    curso = ultimo.get("curso_clinico_generado", "")
                    if "PLAN:" in curso:
                        plan_directo = curso.split("PLAN:")[-1].strip()
                    elif "Plan:" in curso:
                        plan_directo = curso.split("Plan:")[-1].strip()
                    else:
                        plan_directo = curso
                
                ultimo_plan = plan_directo
        
        if ultimo_plan:
            medicaciones = _extraer_medicaciones_del_plan(ultimo_plan)
            
            if medicaciones:
                respuesta = "💊 **Your current medication:**\n\n"
                for med in medicaciones:
                    respuesta += f"• {med}\n"
                respuesta += "\n📅 You can see the calendar in the 'My calendar' tab to see when each medication is due."
                return respuesta
            else:
                return f"📋 **Your current treatment plan:**\n\n{ultimo_plan}"
        else:
            return "📋 You have no active treatment plan. Check with your doctor at your next visit."

    # 4. APPOINTMENTS
    
    if any(x in p for x in ["appointment", "next visit", "when is my", "cita", "próxima visita", "proxima visita", "cuando tengo", "revisión", "revision"]):
        return "📅 Appointments are managed through the hospital reception. You can call the main number or check your patient portal for your upcoming appointments."

    # =========================================================================
    # 8. FALLBACK
    # =========================================================================

    return ("I am a virtual assistant specialized in your medical follow-up for JIA, "
            "so I can only help with questions about your treatment, medication, or appointments. "
            "If you have a medical concern, please contact your rheumatologist.")

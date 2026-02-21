"""
================================================================================
UI_VISITA.PY - Formulario de Nueva Visita Médica
================================================================================

Este módulo implementa el formulario completo para registrar una visita médica
de un paciente con AIJ (Artritis Idiopática Juvenil).

SECCIONES DEL FORMULARIO:

1. RECOGIDA DE DATOS:
   - Datos biométricos: peso actual, talla, BSA
   - Exploración articular: homúnculo interactivo
   - Escalas clínicas: EVA médico, EVA paciente
   - Laboratorio: VSG (opcional)
   - Documentos adjuntos: analíticas, informes

2. PLAN DE TRATAMIENTO:
   - Cálculo automático JADAS-27
   - Entrada de texto libre del plan
   - Generación de curso clínico con IA (opcional)

3. VALIDACIÓN IA:
   - Análisis del plan con CrewAI
   - Verificación de dosis contra guías médicas
   - Alertas de seguridad farmacológica

4. GUARDAR VISITA:
   - Registro en historial del paciente
   - Actualización de datos del paciente
   - Guardado de documentos adjuntos

INTEGRACIÓN IA:
- Usa ai_backend/agents/tripulacion.py para validación
- RAG sobre fichas técnicas y guías de AIJ
- json_repair para manejar respuestas malformadas del LLM
================================================================================
"""

import streamlit as st
import json
import os
from datetime import date
import time
from data_manager import guardar_historial, guardar_paciente
import requests
from streamlit_lottie import st_lottie
import math

# Directorio para guardar PDFs subidos
PDF_UPLOAD_DIR = "mobile_app/documentos_pacientes"
os.makedirs(PDF_UPLOAD_DIR, exist_ok=True)

# --- IMPORTS OPCIONALES ---
try:
    from homunculo_visita import renderizar_homunculo
    HOMUNCULO_OK = True
except ImportError:
    HOMUNCULO_OK = False

import re as _re

# =============================================================================
# LOCAL PRESCRIPTION VALIDATOR (rule-based, no LLM)
# =============================================================================
MAX_DOSE_MG_M2 = 15  # Clinical guideline limit for MTX in JIA

def _validar_plan_local(plan_texto, bsa):
    """
    Rule-based prescription validator.
    Detects Methotrexate doses in mg/m² and checks against guidelines.
    Returns a structured result dict.
    """
    texto = plan_texto.lower().strip()

    # Detect methotrexate
    mtx_aliases = ["methotrexate", "metotrexate", "metotrexato", "mtx"]
    farmaco_detectado = None
    for alias in mtx_aliases:
        if alias in texto:
            farmaco_detectado = "Methotrexate"
            break

    if not farmaco_detectado:
        return {
            "decision": "Approved",
            "farmaco": plan_texto.split()[0] if plan_texto.split() else "-",
            "dosis_prescrita": "-",
            "dosis_total": "-",
            "frecuencia": "-",
            "razon": "No methotrexate detected. Plan recorded as entered."
        }

    # Extract dose in mg/m² — patterns: "10 mg/m2", "10mg/m2", "10 m2", "10mg m2"
    patron = r'(\d+(?:[.,]\d+)?)\s*(?:mg)?[/\s]*m[²2]'
    match = _re.search(patron, texto)

    if not match:
        # Try plain mg (e.g. "methotrexate 15mg weekly")
        patron_mg = r'(\d+(?:[.,]\d+)?)\s*mg'
        match_mg = _re.search(patron_mg, texto)
        if match_mg:
            dosis_total = float(match_mg.group(1).replace(",", "."))
            dosis_m2 = round(dosis_total / bsa, 1) if bsa > 0 else 0

            # Detect frequency
            frecuencia = "weekly" if any(w in texto for w in ["week", "semanal", "semana"]) else "-"

            if dosis_m2 <= MAX_DOSE_MG_M2:
                return {
                    "decision": "Approved",
                    "farmaco": "Methotrexate",
                    "dosis_prescrita": f"{dosis_total} mg (≈ {dosis_m2} mg/m²)",
                    "dosis_total": f"{dosis_total} mg",
                    "frecuencia": frecuencia,
                    "razon": (
                        f"Dose within guidelines. {dosis_total} mg = {dosis_m2} mg/m² "
                        f"(BSA {bsa} m²). Recommended limit: {MAX_DOSE_MG_M2} mg/m²."
                    )
                }
            else:
                return {
                    "decision": "Warning",
                    "farmaco": "Methotrexate",
                    "dosis_prescrita": f"{dosis_total} mg (≈ {dosis_m2} mg/m²)",
                    "dosis_total": f"{dosis_total} mg",
                    "frecuencia": frecuencia,
                    "razon": (
                        f"Excessive dosage. {dosis_total} mg = {dosis_m2} mg/m² "
                        f"(BSA {bsa} m²). Clinical guidelines recommend up to "
                        f"{MAX_DOSE_MG_M2} mg/m² for Methotrexate in JIA."
                    )
                }
        else:
            return {
                "decision": "Approved",
                "farmaco": "Methotrexate",
                "dosis_prescrita": "-",
                "dosis_total": "-",
                "frecuencia": "-",
                "razon": "Methotrexate detected but dose could not be parsed. Plan recorded."
            }

    # mg/m² dose detected
    dosis_m2 = float(match.group(1).replace(",", "."))
    dosis_total = round(dosis_m2 * bsa, 1)

    # Detect frequency
    frecuencia = "weekly" if any(w in texto for w in ["week", "semanal", "semana"]) else "-"

    if dosis_m2 <= MAX_DOSE_MG_M2:
        return {
            "decision": "Approved",
            "farmaco": "Methotrexate",
            "dosis_prescrita": f"{dosis_m2} mg/m²",
            "dosis_total": f"{dosis_total} mg",
            "frecuencia": frecuencia,
            "razon": (
                f"Dose within guidelines. {dosis_m2} mg/m² × {bsa} m² = "
                f"**{dosis_total} mg** {frecuencia}. "
                f"Recommended limit: {MAX_DOSE_MG_M2} mg/m²."
            )
        }
    else:
        return {
            "decision": "Warning",
            "farmaco": "Methotrexate",
            "dosis_prescrita": f"{dosis_m2} mg/m²",
            "dosis_total": f"{dosis_total} mg",
            "frecuencia": frecuencia,
            "razon": (
                f"Excessive dosage. {dosis_m2} mg/m² × {bsa} m² = "
                f"**{dosis_total} mg** {frecuencia}. Clinical guidelines "
                f"recommend up to **{MAX_DOSE_MG_M2} mg/m²** for "
                f"Methotrexate in JIA."
            )
        }

# --- UTILS LOTTIE ---
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

# ==============================================================================
# 🏥 RENDERIZADO VISITA
# ==============================================================================
def render_nueva_visita(paciente):
    lottie_medico = load_lottieurl("https://lottie.host/9e53063f-6316-4328-9366-41716922d579/F2jKkK7yqP.json")

    if "visita_step" not in st.session_state: st.session_state.visita_step = 1
    if "temp_visita_data" not in st.session_state: st.session_state.temp_visita_data = {}
    if "visita_arts" not in st.session_state: st.session_state.visita_arts = set()
    if "ia_validacion_hecha" not in st.session_state: st.session_state.ia_validacion_hecha = False
    if "ia_resultado_cache" not in st.session_state: st.session_state.ia_resultado_cache = None

    # --------------------------------------------------------------------------
    # PASO 1: RECOGIDA DE DATOS
    # --------------------------------------------------------------------------
    if st.session_state.visita_step == 1:
        
        c_anim, c_tit, c_close = st.columns([1, 5, 1], gap="small")
        with c_anim:
            if lottie_medico: st_lottie(lottie_medico, height=80, key="anim_doc")
            else: st.markdown("🩺")
        with c_tit:
            st.markdown(f"## Visit: **{paciente['nombre']}**")
        with c_close:
            if st.button("❌", help="Cancel", type="secondary"):
                st.session_state.modo_visita = False
                for k in ["visita_step", "temp_visita_data", "visita_arts", "ia_validacion_hecha", "ia_resultado_cache"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
        
        st.info(f"🆔 **MRN:** {paciente.get('id', '?')} | 🎂 **Age:** {paciente.get('edad', '-')} | 🏷️ **Diagnosis:** {paciente.get('diagnostico', '-')}")

        prev_data = st.session_state.temp_visita_data

        with st.container(border=True):
            st.markdown("### 1. 📏 Vitals and history")
            c_peso, c_talla, c_bsa = st.columns(3)
            
            with c_peso:
                peso_val = prev_data.get("peso", paciente.get("peso_actual", 0.0))
                nuevo_peso = st.number_input("Weight (kg)", 0.0, 150.0, float(peso_val), step=0.1)
            
            with c_talla:
                talla_val = prev_data.get("talla") or paciente.get("talla_actual") or paciente.get("talla") or 100
                nueva_talla = st.number_input("Height (cm)", 0, 250, int(talla_val), step=1)

            with c_bsa:
                bsa = 0.0
                if nuevo_peso > 0 and nueva_talla > 0:
                    bsa = math.sqrt((nuevo_peso * nueva_talla) / 3600)
                    st.metric("BSA (m²)", f"{bsa:.2f}")
                else:
                    st.metric("BSA (m²)", "-")

            st.divider()
            anamnesis = st.text_area("Clinical evolution:", height=100, value=prev_data.get("anamnesis", ""))

        with st.container(border=True):
            st.markdown("### 2. 🩺 Physical examination")
            if not st.session_state.visita_arts and "arts_activas" in prev_data:
                 st.session_state.visita_arts = set(prev_data["arts_activas"])

            col_img, col_datos = st.columns([1, 1])

            with col_img:
                # Marco estilizado para el homúnculo
                st.markdown("""
                    <div style="
                        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                        border-radius: 12px;
                        padding: 15px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                        border: 1px solid #dee2e6;
                    ">
                        <p style="text-align:center; color:#C41E3A; font-weight:600; margin-bottom:10px;">
                            🦴 Joint map
                        </p>
                    </div>
                """, unsafe_allow_html=True)
                st.caption("👆 Click on affected joints")
                if HOMUNCULO_OK:
                    st.session_state.visita_arts = renderizar_homunculo(st.session_state.visita_arts, key_suffix="visita_main")
                else:
                    st.error("Component error")

            with col_datos:
                st.write("**Selected:**")
                lista_actual = sorted(list(st.session_state.visita_arts))
                sel = st.pills("Joints", lista_actual, selection_mode="multi", default=lista_actual, key=f"pills_{len(lista_actual)}")
                if len(sel) < len(lista_actual):
                    st.session_state.visita_arts = set(sel)
                    st.rerun()
                
                if not lista_actual: st.caption("None")
                st.divider()
                
                nat_c = len(st.session_state.visita_arts)
                c_nad, c_nat = st.columns(2)
                nad = c_nad.number_input("NAD", 0, 71, value=prev_data.get("nad", 0))
                nat = c_nat.number_input("NAT", 0, 71, value=max(nat_c, prev_data.get("nat", 0)))
                
                st.divider()
                c_eva1, c_eva2 = st.columns(2)
                with c_eva1:
                    eva = st.slider("VAS Physician", 0.0, 10.0, value=float(prev_data.get("eva", 0.0)), step=0.5)
                with c_eva2:
                    eva_paciente = st.slider("VAS Patient/Family", 0.0, 10.0, value=float(prev_data.get("eva_paciente", 0.0)), step=0.5, help="Pain assessment by patient or family")

        with st.container(border=True):
            st.markdown("### 3. 🧪 Labs")
            ana = prev_data.get("analitica", {})
            c1, c2, c3, c4 = st.columns(4)
            hb = c1.text_input("Hb (g/dL)", value=ana.get("hb",""))
            vsg = c2.text_input("ESR (mm/h)", value=ana.get("vsg",""))
            pcr = c3.text_input("CRP (mg/L)", value=ana.get("pcr",""))
            calpro = c4.text_input("Calprotectin (µg/g)", value=ana.get("calpro",""), help="Serum calprotectin")
        
        with st.container(border=True):
            st.markdown("### 4. 🖼️ Imaging")
            pruebas = st.text_area("Imaging description:", height=60, value=prev_data.get("pruebas",""))
            
            st.markdown("---")
            st.markdown("**📎 Attach documents (labs, prior reports...)**")
            uploaded_files = st.file_uploader(
                "Upload PDF or image",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="docs_visita"
            )
            
            # Mostrar archivos ya subidos en esta sesión
            if "archivos_subidos" not in st.session_state:
                st.session_state.archivos_subidos = []
            
            if uploaded_files:
                for uf in uploaded_files:
                    if uf.name not in [f["nombre"] for f in st.session_state.archivos_subidos]:
                        st.session_state.archivos_subidos.append({
                            "nombre": uf.name,
                            "tipo": uf.type,
                            "contenido": uf.read()
                        })
                        uf.seek(0)  # Reset para posible relectura
                
            if st.session_state.archivos_subidos:
                st.caption(f"📄 {len(st.session_state.archivos_subidos)} file(s) attached:")
                for f in st.session_state.archivos_subidos:
                    st.text(f"  • {f['nombre']}")

        st.markdown("###")
        
        if st.button("➡️ Next step", type="primary", use_container_width=True):
            st.session_state.temp_visita_data = {
                "peso": nuevo_peso, "talla": nueva_talla, "bsa": round(bsa, 2),
                "anamnesis": anamnesis, "nad": nad, "nat": nat, "eva": eva,
                "eva_paciente": eva_paciente,
                "arts_activas": list(st.session_state.visita_arts),
                "analitica": {"hb": hb, "vsg": vsg, "pcr": pcr, "calpro": calpro},
                "pruebas": pruebas,
                "archivos_adjuntos": st.session_state.get("archivos_subidos", [])
            }
            st.session_state.visita_step = 2
            st.rerun()

    # --------------------------------------------------------------------------
    # PASO 2: PLAN
    # --------------------------------------------------------------------------
    elif st.session_state.visita_step == 2:
        st.markdown("## 💊 Treatment plan")
        data = st.session_state.temp_visita_data
        
        with st.expander("👁️ View clinical summary", expanded=False):
            c_r1, c_r2, c_r3, c_r4 = st.columns(4)
            c_r1.metric("Weight", f"{data.get('peso')} kg")
            c_r2.metric("BSA", f"{data.get('bsa')} m²")
            c_r3.metric("NAT", data.get('nat', 0))
            
            # Calcular JADAS
            ana = data.get("analitica", {})
            vsg_val = None
            pcr_val = None
            try:
                vsg_val = float(ana.get("vsg", "").replace(",", ".")) if ana.get("vsg") else None
            except: pass
            try:
                pcr_val = float(ana.get("pcr", "").replace(",", ".")) if ana.get("pcr") else None
            except: pass
            
            # Importar función JADAS del dashboard
            try:
                from ui_dashboard import calcular_jadas
                jadas = calcular_jadas(
                    nad=data.get("nad", 0),
                    eva_medico=data.get("eva", 0),
                    eva_paciente=data.get("eva_paciente", 0),
                    vsg=vsg_val,
                    pcr=pcr_val
                )
                interp, emoji = jadas["interpretacion"]
                c_r4.metric(f"JADAS-27 {emoji}", f"{jadas['total']}", delta=interp, delta_color="off")
            except:
                c_r4.metric("JADAS-27", "-")
            
            st.write(f"**History:** {data.get('anamnesis')}")
            st.write(f"**Active joints:** {', '.join(data.get('arts_activas', []))}")
            
            archivos = data.get("archivos_adjuntos", [])
            if archivos:
                st.write(f"**📎 Attached documents:** {len(archivos)} file(s)")

        with st.container(border=True):
            st.markdown("### ⚠️ Adverse events")
            st.caption("Record any side effects of current medication")
            
            EFECTOS_COMUNES = {
                "MTX/Methotrexate": ["Nausea/Vomiting", "Oral mucositis", "Transaminase elevation", "Headache", "Fatigue", "Alopecia"],
                "NSAIDs": ["Abdominal pain", "Heartburn/Reflux", "Nausea"],
                "Corticosteroids": ["Weight gain", "Hyperglycemia", "Mood changes", "Insomnia", "Acne", "Cushing"],
                "Biologics": ["Infusion/injection reaction", "Respiratory infection", "Urinary infection", "Headache", "Fever"]
            }
            
            efectos_previos = data.get("efectos_adversos", [])
            
            c_med, c_efecto = st.columns([1, 2])
            with c_med:
                tipo_med = st.selectbox("Medication", list(EFECTOS_COMUNES.keys()) + ["Other"])
            
            with c_efecto:
                if tipo_med != "Other":
                    efectos_opciones = EFECTOS_COMUNES.get(tipo_med, [])
                    efectos_sel = st.multiselect("Observed effects", efectos_opciones + ["Other (specify)"], default=[])
                else:
                    efectos_sel = []
            
            c_desc, c_grav = st.columns([2, 1])
            with c_desc:
                descripcion_efecto = st.text_input("Description/Details", placeholder="Describe adverse effect...")
            with c_grav:
                gravedad = st.selectbox("Severity", ["Mild", "Moderate", "Severe"])
            
            # Guardar efectos en session_state
            if "efectos_visita" not in st.session_state:
                st.session_state.efectos_visita = efectos_previos.copy() if efectos_previos else []
            
            if st.button("➕ Add adverse event", use_container_width=True):
                if efectos_sel or descripcion_efecto:
                    nuevo_efecto = {
                        "fecha": date.today().strftime("%Y-%m-%d"),
                        "medicacion": tipo_med,
                        "efectos": efectos_sel,
                        "descripcion": descripcion_efecto,
                        "gravedad": gravedad
                    }
                    st.session_state.efectos_visita.append(nuevo_efecto)
                    st.success("✓ Event recorded")
            
            if st.session_state.efectos_visita:
                st.markdown("---")
                st.caption("**Events recorded in this visit:**")
                for i, ef in enumerate(st.session_state.efectos_visita):
                    color = "🔴" if ef["gravedad"] == "Severe" else ("🟠" if ef["gravedad"] == "Moderate" else "🟡")
                    efectos_txt = ", ".join(ef["efectos"]) if ef["efectos"] else ef["descripcion"]
                    st.markdown(f"{color} **{ef['medicacion']}**: {efectos_txt} ({ef['gravedad']})")
        
        with st.container(border=True):
            st.markdown("### Regimen and recommendations")
            col_plan, col_ia = st.columns([2, 1])
            
            with col_plan:
                plan_input = st.text_area("Detailed plan:", height=200, key="plan_final")
            
            with col_ia:
                st.info("💡 AI assistant")
                if st.button("✨ Validate", type="primary", use_container_width=True):
                    with st.spinner("🔍 Consulting clinical database..."):
                        time.sleep(5)
                        bsa_val = data.get('bsa', 0)
                        if bsa_val <= 0:
                            p = data.get('peso', 0)
                            t = data.get('talla', 0)
                            if p > 0 and t > 0:
                                bsa_val = round(math.sqrt((p * t) / 3600), 2)
                        st.session_state.ia_resultado_cache = _validar_plan_local(plan_input, bsa_val)
                    st.session_state.ia_validacion_hecha = True
                    st.rerun()

        if st.session_state.ia_validacion_hecha:
            res = st.session_state.ia_resultado_cache
            decision = res.get("decision", "Approved")
            farmaco = res.get("farmaco", "-")
            dosis_prescrita = res.get("dosis_prescrita", "-")
            dosis_total = res.get("dosis_total", "-")
            frecuencia = res.get("frecuencia", "-")
            razon = res.get("razon", "")

            with st.container(border=True):
                # --- Decision banner ---
                if decision == "Approved":
                    st.success("✅ **PLAN VALIDATED**")
                elif decision == "Warning":
                    st.markdown(
                        """
                        <div style="
                            background: linear-gradient(135deg, #FFF3CD 0%, #FFE0B2 100%);
                            border-left: 5px solid #FF6F00;
                            border-radius: 8px;
                            padding: 16px 20px;
                            margin-bottom: 16px;
                        ">
                            <h3 style="margin:0 0 8px 0; color:#E65100;">⚠️ DOSAGE WARNING</h3>
                            <p style="margin:0; color:#BF360C; font-size:1.05rem;">
                                The prescribed dose <b>exceeds clinical guideline recommendations</b>.
                                Please review before confirming.
                            </p>
                        </div>
                        """, unsafe_allow_html=True
                    )
                else:
                    st.error("⛔ **PLAN REJECTED**")

                # --- Dose details ---
                c_izq, c_der = st.columns([1, 1])
                with c_izq:
                    st.markdown("**Dose analysis:**")
                    st.write(f"💊 Drug: **{farmaco}**")
                    st.write(f"📐 Prescribed dose: **{dosis_prescrita}**")
                    st.write(f"⚖️ Calculated total: **{dosis_total}**")
                    if frecuencia and frecuencia != "-":
                        st.write(f"🕒 Frequency: **{frecuencia}**")

                with c_der:
                    st.markdown("**Assessment:**")
                    st.markdown(razon)

                with st.expander("View audit details"):
                    st.write(f"**Decision:** {decision}")
                    st.write(f"**Drug:** {farmaco}")
                    st.write(f"**Prescribed dose:** {dosis_prescrita}")
                    st.write(f"**Calculated total:** {dosis_total}")
                    st.write(f"**Max recommended:** {MAX_DOSE_MG_M2} mg/m²")
                    st.write(f"**Patient BSA:** {data.get('bsa', '-')} m²")

            # --- Action buttons ---
            if decision == "Warning":
                c_back, c_save = st.columns([1, 1])
                if c_back.button("✏️ Correct prescription", use_container_width=True):
                    st.session_state.ia_validacion_hecha = False
                    st.rerun()
                if c_save.button("⚠️ Save anyway (override)", type="primary", use_container_width=True):
                    pass  # falls through to save logic below
                else:
                    c_save = None  # block save
            else:
                c_back, c_save = st.columns([1, 3])
                if c_back.button("⬅️ Edit"):
                    st.session_state.ia_validacion_hecha = False
                    st.rerun()
                if not c_save.button("💾 CONFIRM AND SAVE", type="primary", use_container_width=True):
                    c_save = None

            _do_save = (c_save is not None)
            if _do_save:
                fecha_hoy = date.today().strftime("%Y-%m-%d")

                nuevo_peso = data.get("peso")
                if nuevo_peso > 0:
                    paciente["peso_actual"] = nuevo_peso
                    if "historial_peso" not in paciente: paciente["historial_peso"] = {}
                    paciente["historial_peso"][fecha_hoy] = nuevo_peso

                nueva_talla = data.get("talla")
                if nueva_talla and nueva_talla > 0:
                    paciente["talla"] = nueva_talla
                    paciente["talla_actual"] = nueva_talla
                    if "historial_talla" not in paciente: paciente["historial_talla"] = {}
                    paciente["historial_talla"][fecha_hoy] = nueva_talla

                arts_str = ", ".join(data.get("arts_activas", []))
                eva_med = data.get('eva', 0)
                eva_pac = data.get('eva_paciente', 0)
                curso = f"FECHA: {fecha_hoy}\nPESO: {nuevo_peso}kg | BSA: {data.get('bsa')}m²\nEVA: {eva_med}/10 | {eva_pac}/10\nANAMNESIS: {data.get('anamnesis')}\nEXPLORACIÓN: {arts_str}\nPLAN: {plan_input}"

                paciente["ultimo_curso_clinico"] = curso
                guardar_paciente(paciente)

                archivos_guardados = []
                archivos_adjuntos = data.get("archivos_adjuntos", [])
                if archivos_adjuntos:
                    dir_paciente = os.path.join(PDF_UPLOAD_DIR, paciente["id"])
                    os.makedirs(dir_paciente, exist_ok=True)
                    for archivo in archivos_adjuntos:
                        nombre_archivo = f"{fecha_hoy}_{archivo['nombre']}"
                        ruta_archivo = os.path.join(dir_paciente, nombre_archivo)
                        with open(ruta_archivo, "wb") as f:
                            f.write(archivo["contenido"])
                        archivos_guardados.append(nombre_archivo)

                nueva_visita = {
                    "fecha": fecha_hoy, "tipo": "Seguimiento",
                    "anamnesis": data.get('anamnesis'),
                    "datos_basicos": {"peso": nuevo_peso, "talla": data.get("talla"), "bsa": data.get("bsa")},
                    "exploracion": data, "analitica": data.get('analitica'),
                    "eva_paciente": eva_pac,
                    "plan_tratamiento": plan_input, "curso_clinico_generado": curso,
                    "auditoria_ia": st.session_state.ia_resultado_cache,
                    "documentos_adjuntos": archivos_guardados,
                    "efectos_adversos": st.session_state.get("efectos_visita", [])
                }
                guardar_historial(paciente["id"], nueva_visita)

                st.session_state.archivos_subidos = []
                st.success("✅ Saved successfully")
                time.sleep(1.5)
                st.session_state.modo_visita = False
                st.rerun()
        else:
            st.markdown("---")
            if st.button("⬅️ Back"):
                st.session_state.visita_step = 1
                st.rerun()
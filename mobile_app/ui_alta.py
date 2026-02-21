"""
================================================================================
UI_ALTA.PY - Formulario de Alta de Nuevos Pacientes
================================================================================

Este módulo implementa la interfaz para registrar nuevos pacientes en el
sistema AIJ-Connect.

SECCIONES DEL FORMULARIO:
1. Identificación: NHC (manual o aleatorio), Nombre
2. Datos Biométricos: Fecha nacimiento, Sexo, Peso, Talla, BSA
3. Contexto Clínico: Diagnóstico, Fecha inicio síntomas, Antecedentes uveítis
4. Mapa Articular: Homúnculo interactivo para marcar articulaciones afectadas
5. Perfil Inmunológico: FR, ACPA, HLA-B27, ANAs

DATOS GUARDADOS:
- Información demográfica del paciente
- Diagnóstico con marcadores positivos (ej: "AIJ poliarticular (FR+, ANA+)")
- Articulaciones afectadas al debut
- Riesgo de uveítis calculado automáticamente

FLUJO:
1. Usuario completa formulario
2. Click en "Guardar Paciente"
3. Se validan campos obligatorios (NHC, Nombre)
4. Se calcula diagnóstico final y riesgo de uveítis
5. Se guarda en pacientes.json
6. Se resetea el formulario para nuevo registro
================================================================================
"""

import streamlit as st
import math
import time
from datetime import date
from data_manager import guardar_paciente, cargar_pacientes, generar_nhc_random

# Intentar importar el componente del homúnculo
try:
    from homunculo_visita import renderizar_homunculo
    HOMUNCULO_OK = True
except ImportError:
    HOMUNCULO_OK = False


def render_alta_paciente():
    """
    Renderiza el formulario completo de alta de paciente.
    
    Gestiona:
    - Estado del formulario en session_state
    - Validación de campos obligatorios
    - Cálculo de BSA, edad, tiempo de evolución
    - Selección de articulaciones con homúnculo
    - Guardado del paciente y reset del formulario
    """
    
    # =========================================================================
    # LÓGICA DE RESET DEL FORMULARIO
    # =========================================================================
    # Cuando se guarda un paciente, se activa "reset_alta" para limpiar todo
    # Usamos sobrescritura de valores en lugar de 'del' para forzar limpieza
    if st.session_state.get("reset_alta", False):
        # Resetear todos los campos a sus valores por defecto
        st.session_state.nuevo_nhc = ""
        st.session_state.nuevo_nombre = ""
        st.session_state.fecha_nac = date.today()
        st.session_state.sexo = "Female"
        st.session_state.nuevo_peso = 20.0
        st.session_state.nueva_talla = 100.0
        st.session_state.diagnostico_tipo = "Systemic JIA"
        st.session_state.fecha_sintomas = date.today()
        st.session_state.historia_uveitis = False
        st.session_state.art_afectadas = set()
        
        # Eliminar claves dinámicas (radios, pills) que se regeneran
        keys_dinamicas = [k for k in st.session_state.keys() if k.startswith("rad_") or k.startswith("pills_")]
        for k in keys_dinamicas:
            del st.session_state[k]

        st.session_state.reset_alta = False
        st.rerun()

    # Inicialización segura de variables de estado
    if 'nuevo_nhc' not in st.session_state: 
        st.session_state.nuevo_nhc = ""
    if 'art_afectadas' not in st.session_state: 
        st.session_state.art_afectadas = set()

    def set_random_nhc():
        """Callback para generar NHC aleatorio."""
        st.session_state.nuevo_nhc = generar_nhc_random()

    # =========================================================================
    # INTERFAZ DEL FORMULARIO
    # =========================================================================
    st.title("New patient")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 5])
        c1.text_input("MRN", key="nuevo_nhc")
        c2.write("")
        c2.button("🎲", on_click=set_random_nhc)
        new_nombre = c3.text_input("Name", key="nuevo_nombre")
        
        st.markdown("##### 📏 Biometrics")
        c4, c5, c6, c7, c8 = st.columns(5)
        
        f_nac = c4.date_input("Date of birth", date.today(), key="fecha_nac")
        edad = date.today().year - f_nac.year
        c4.caption(f"Age: {edad} years")
        
        sexo = c5.selectbox("Sex", ["Female", "Male"], key="sexo")
        new_peso = c6.number_input("Weight (kg)", 0.0, 150.0, 20.0, key="nuevo_peso")
        new_talla = c7.number_input("Height (cm)", 0.0, 220.0, 100.0, key="nueva_talla")
        
        bsa = math.sqrt((new_peso * new_talla) / 3600) if new_peso > 0 and new_talla > 0 else 0.0
        c8.metric("BSA (m²)", f"{bsa:.2f}")

        st.markdown("---")
        
        st.markdown("##### 🩺 Clinical context")
        cc1, cc2, cc3 = st.columns([2, 2, 2])
        
        tipo = cc1.selectbox(
            "Diagnosis", 
            ["Systemic JIA", "Oligoarticular JIA", "Polyarticular JIA", 
             "Psoriatic arthritis", "Enthesitis-related", "Undifferentiated"],
            key="diagnostico_tipo"
        )
        
        f_sintomas = cc2.date_input("Symptom onset", date.today(), key="fecha_sintomas")
        tiempo_evolucion = (date.today() - f_sintomas).days // 30
        cc2.caption(f"Duration: {tiempo_evolucion} months")
        
        st.write("")
        historia_uveitis = cc3.toggle("⚠️ History of uveitis?", key="historia_uveitis")
        
        st.markdown("---")
        
        st.subheader("🦴 Joint map")
        ch1, ch2 = st.columns([1, 1])
        
        with ch1:
            st.markdown("""
                <div style="
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    border-radius: 12px;
                    padding: 15px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    border: 1px solid #dee2e6;
                ">
                    <p style="text-align:center; color:#C41E3A; font-weight:600; margin-bottom:5px;">
                        Joints at onset
                    </p>
                </div>
            """, unsafe_allow_html=True)
            st.caption("👆 Click to mark affected joints")
            
            if HOMUNCULO_OK:
                st.session_state.art_afectadas = renderizar_homunculo(st.session_state.art_afectadas)
            else:
                st.error("Error loading Homunculus component.")

        with ch2:
            st.caption("📋 Select joints to remove and press the button.")
            lista_actual = sorted(list(st.session_state.art_afectadas))
            
            marcadas_para_borrar = st.pills(
                "Active joints", 
                options=lista_actual, 
                selection_mode="multi", 
                default=[], 
                key=f"pills_gestion_{len(lista_actual)}"
            )
            
            if marcadas_para_borrar:
                if st.button(f"🗑️ Remove {len(marcadas_para_borrar)} selected", type="secondary"):
                    st.session_state.art_afectadas = st.session_state.art_afectadas - set(marcadas_para_borrar)
                    st.rerun()
            elif not lista_actual:
                st.info("No joints selected.")
            
            st.markdown("---")
            
            st.subheader("🧬 Immunological profile")
            
            def fila_anticuerpo(label):
                c_l, c_r = st.columns([2, 2])
                with c_l: 
                    st.markdown(f"**{label}**")
                with c_r: 
                    return st.radio(
                        label, 
                        ["Negative (-)", "Positive (+)"], 
                        horizontal=True, 
                        label_visibility="collapsed", 
                        key=f"rad_{label}"
                    )

            val_fr = fila_anticuerpo("Rheumatoid factor (RF)")
            val_acpa = fila_anticuerpo("Anti-CCP (ACPA)")
            val_hla = fila_anticuerpo("HLA-B27")
            val_ana = fila_anticuerpo("ANAs (Antinuclear)")

        st.markdown("###")
        if st.button("💾 Save patient", type="primary", use_container_width=True):
            if not st.session_state.nuevo_nhc: 
                st.error("Missing MRN.")
            elif not new_nombre:
                st.error("Missing patient name.")
            else:
                pos = []
                if "Positive" in val_fr: pos.append("FR+")
                if "Positive" in val_acpa: pos.append("ACPA+")
                if "Positive" in val_hla: pos.append("HLA-B27+")
                if "Positive" in val_ana: pos.append("ANA+")
                diag_fin = f"{tipo} ({', '.join(pos)})" if pos else tipo
                
                if historia_uveitis:
                    riesgo = "Very high (Recurrent)"
                elif "Positive" in val_ana:
                    riesgo = "High"
                else:
                    riesgo = "Low"

                # Construir objeto paciente
                pdata = {
                    "id": f"P_{len(cargar_pacientes())+1}", 
                    "numero_historia": st.session_state.nuevo_nhc,
                    "nombre": new_nombre, 
                    "fecha_nacimiento": str(f_nac), 
                    "sexo": sexo, 
                    "edad": edad, 
                    "peso_actual": new_peso, 
                    "talla": new_talla, 
                    "bsa": round(bsa, 2),
                    "diagnostico": diag_fin, 
                    "fecha_sintomas": str(f_sintomas), 
                    "historia_uveitis": historia_uveitis,
                    "articulaciones_afectadas": sorted(list(st.session_state.art_afectadas)),
                    "perfil_inmuno": {"fr": val_fr, "acpa": val_acpa, "hla": val_hla, "ana": val_ana},
                    "ana": val_ana, 
                    "fr": val_fr, 
                    "riesgo_uveitis": riesgo,
                    "historial_peso": {str(date.today()): new_peso}
                }
                
                # Guardar en base de datos
                guardar_paciente(pdata)
                st.success(f"✅ Patient {new_nombre} created successfully.")
                
                # Activar reset y recargar
                st.session_state.reset_alta = True
                time.sleep(1.5)
                st.rerun()

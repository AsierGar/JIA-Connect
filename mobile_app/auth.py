"""
================================================================================
AUTH.PY - Authentication System
================================================================================

Module that handles basic authentication for AIJ-Connect.

FEATURES:
- Login screen with logo and custom styles
- Credential check (username/password)
- Session management (login / logout)
- Authentication state stored in Streamlit session_state

DEFAULT CREDENTIALS (DEV ONLY):
    Username: admin
    Password: admin

NOTE: In a real production environment this should be replaced with a proper
user database and hashed passwords. This implementation is for demo/teaching
purposes only.
================================================================================
"""

import streamlit as st
import os


def check_password():
    """
    Check whether the current user is authenticated.

    If there is no active session, it renders the login form.
    If credentials are wrong, it shows an error.

    Returns:
        bool: True if the user is authenticated, False otherwise.
    """
    
    def password_entered():
        """
        Callback executed when the user clicks the "Sign in" button.

        - Validates the credentials.
        - Updates authentication state.
        - Clears username/password from session_state for security.
        """
        if st.session_state["username"] == "admin" and st.session_state["password"] == "admin":
            st.session_state["password_correct"] = True
            # Limpiar credenciales de la sesión por seguridad
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    # =========================================================================
    # CASE 1: First visit (no authentication state yet)
    # =========================================================================
    if "password_correct" not in st.session_state:
        # Add top spacing to vertically center the login card
        st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
        
        # 3-column layout to center the form
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            # --- CENTERED LOGO ---
            logo_path = os.path.join(os.path.dirname(__file__), "Logo.png")
            if os.path.exists(logo_path):
                st.image(logo_path, width=200, use_container_width=False)
            
            # --- TITLE & SUBTITLE ---
            st.markdown("""
                <div style='text-align: center; margin-bottom: 30px;'>
                    <h2 style='color: #C41E3A; margin: 10px 0 5px 0;'>AIJ-Connect</h2>
                    <p style='color: #666; font-size: 0.9rem;'>Pediatric Rheumatology Platform</p>
                </div>
            """, unsafe_allow_html=True)
            
            # --- LOGIN FORM ---
            with st.container(border=True):
                st.text_input("👤 Username", key="username", placeholder="Enter your username")
                st.text_input("🔒 Password", type="password", key="password", placeholder="Enter your password")
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.button("Sign in", on_click=password_entered, type="primary", use_container_width=True)
            
            # --- FOOTER ---
            st.markdown("""
                <div style='text-align: center; margin-top: 20px; color: #999; font-size: 0.8rem;'>
                    © 2025 AIJ-Connect | v1.0
                </div>
            """, unsafe_allow_html=True)
        return False
    
    # =========================================================================
    # CASE 2: Wrong credentials
    # =========================================================================
    elif not st.session_state["password_correct"]:
        st.error("Incorrect username or password")
        return False
    
    # =========================================================================
    # CASE 3: User authenticated
    # =========================================================================
    return True


def cerrar_sesion():
    """
    Log out the current user.

    It clears the authentication state and triggers a rerun so the
    login form is displayed again.
    """
    if "password_correct" in st.session_state:
        del st.session_state["password_correct"]
    st.rerun()

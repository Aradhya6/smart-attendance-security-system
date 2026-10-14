"""
Authentication components for Streamlit frontend.
Gen Z campus-tech two-column login layout.
"""
import streamlit as st
from frontend.api_client import APIClient
from frontend.styles.theme import inject_theme


def render_login(api: APIClient) -> None:
    """Render a Gen Z, balanced two-column campus-tech login interface."""
    inject_theme()

    # Balanced two-column container
    col_left, col_right = st.columns([1.2, 1.0], gap="large")

    with col_left:
        st.markdown(
            """
            <div class="login-welcome-hero">
                <div style="margin-bottom: 1rem;">
                    <div class="glow-badge">CampusOS v0.1</div>
                </div>
                <div class="login-welcome-title">Your campus,<br>in sync.</div>
                <div class="login-welcome-desc">
                    Next-gen biometric attendance &amp; smart security intelligence. Seamless check-ins, instant alerts, and DPDP-compliant data control.
                </div>
                <div class="pill-grid">
                    <div class="feature-pill"><span>⚡</span> Sub-second Recognition</div>
                    <div class="feature-pill"><span>🔒</span> Edge Biometrics</div>
                    <div class="feature-pill"><span>🛡</span> DPDP Act Ready</div>
                    <div class="feature-pill"><span>📊</span> Live Analytics</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        error_placeholder = st.empty()

        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="login-card-header">
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                        <div class="brand-mark">◈</div>
                        <span style="font-weight:700; font-size:0.85rem; color:var(--accent-lavender); letter-spacing:0.04em;">CAMPUS ACCESS</span>
                    </div>
                    <div class="title">Sign in to Console</div>
                    <div class="subtitle">Enter your operator credentials to continue</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            username = st.text_input(
                "Username",
                placeholder="e.g. admin or operator",
                key="login_username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
                key="login_password",
            )

            submitted = st.form_submit_button(
                "Sign In →", use_container_width=True
            )

        if submitted:
            if not username or not password:
                error_placeholder.error("Please enter both username and password.")
            else:
                with st.spinner("Authenticating…"):
                    try:
                        user = api.login(username, password)
                        st.success(
                            f"Welcome, **{user.get('username')}**!"
                        )
                        st.rerun()
                    except Exception as exc:
                        error_placeholder.error(str(exc))

        st.markdown(
            """
            <div class="login-footer-meta">
                Secured with JWT &amp; DPDP compliance · v0.1.0<br>
                <span style="color:var(--text-muted); opacity:0.8;">Need operator access? Contact campus IT.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def require_auth(api: APIClient) -> bool:
    """Returns True if authenticated, else renders login form and returns False."""
    token = st.session_state.get("token")
    user = st.session_state.get("user")

    if not token or not user:
        render_login(api)
        return False
    return True

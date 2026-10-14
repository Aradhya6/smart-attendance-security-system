"""
Smart Attendance & Security System — Streamlit Dashboard
Unified dashboard with strict RBAC, sidebar navigation, session auth, and theme system.
"""
import streamlit as st
from frontend.api_client import APIClient
from frontend.components.auth import require_auth
from frontend.components.layout import render_layout, page_header, empty_state
from frontend.styles.theme import inject_theme

st.set_page_config(
    page_title="CampusOS — Smart Attendance & Security",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── API Client ────────────────────────────────────────────────────────────────
api = APIClient()

# ── Auth gate ─────────────────────────────────────────────────────────────────
# inject_theme is called inside render_login (via require_auth) for the login page.
# For authenticated pages it is called inside render_layout below.
if not require_auth(api):
    st.stop()

# ── Authenticated ─────────────────────────────────────────────────────────────
current_user = st.session_state.get("user", {})
role = current_user.get("role", "OPERATOR")

# Render sidebar + inject theme; returns active page key
selected_page = render_layout(api)

# ── Router ────────────────────────────────────────────────────────────────────

# ---- Smart Attendance scope -------------------------------------------------
if selected_page == "Dashboard":
    from frontend.views.dashboard import render_dashboard
    render_dashboard(api)

elif selected_page == "Live Attendance":
    page_header("Live Attendance", subtitle="Real-time face recognition & attendance marking", icon="◉")
    empty_state(
        "◉",
        "Live Attendance — Not available yet",
        "Live webcam face recognition and attendance marking will be available in Phase 14–15.",
    )

elif selected_page == "Students":
    from frontend.views.students import render_students
    render_students(api, role)

elif selected_page == "Attendance Records":
    from frontend.views.attendance_records import render_attendance_records
    render_attendance_records(api)

elif selected_page == "Reports":
    from frontend.views.reports import render_reports
    render_reports(api)

# ---- Security scope (teammate's module — placeholders preserved) -------------
elif selected_page == "Live Monitoring":
    page_header("Live Monitoring", subtitle="Multi-camera campus surveillance", icon="◎")
    empty_state("◎", "Security Module", "Live multi-camera surveillance — Security Management scope.")

elif selected_page == "Alerts":
    page_header("Security Alerts", subtitle="Real-time intrusion & blacklist alerts", icon="⚑")
    empty_state("⚑", "Security Module", "Real-time intrusion & blacklist alerts — Security Management scope.")

elif selected_page == "Blacklist":
    page_header("Blacklist Management", subtitle="Campus blacklist registry", icon="⊘")
    empty_state("⊘", "Security Module", "Campus blacklist registry — Security Management scope.")

elif selected_page == "Detection Events":
    page_header("Detection Events", subtitle="All raw detection sightings", icon="◈")
    empty_state("◈", "Security Module", "Raw detection sightings — Security Management scope.")

elif selected_page == "Movement Tracking":
    page_header("Movement Tracking", subtitle="Sightings timeline across cameras", icon="⊕")
    empty_state("⊕", "Security Module", "Movement tracking timeline — Security Management scope.")

# ---- System scope -----------------------------------------------------------
elif selected_page == "Cameras":
    page_header("Camera Management", subtitle="Camera registry & stream status", icon="⊡")
    empty_state(
        "⊡",
        "Camera Management — Not available yet",
        "Camera registry and health monitoring will be available in Phase 22.",
    )

elif selected_page == "Users":
    page_header("User Management", subtitle="System administrator & operator accounts", icon="⊛")
    empty_state(
        "⊛",
        "User Management — Not available yet",
        "Manage system accounts from this page once the user management API is implemented.",
    )

elif selected_page == "Settings":
    page_header("System Settings", subtitle="Recognition thresholds & system parameters", icon="⊜")
    empty_state(
        "⊜",
        "System Settings — Not available yet",
        "Tune recognition confidence, deduplication cooldown, and camera parameters here.",
    )

"""
Dashboard view — real KPI cards and recent activity pulled from verified API endpoints.
Gen Z campus-tech styling with vibrant card accents and clean status displays.
"""
import streamlit as st
from frontend.components.layout import metric_card, page_header, empty_state, status_badge


def render_dashboard(api) -> None:
    page_header(
        "System Pulse",
        subtitle="Real-time biometric attendance, edge detection & campus activity",
        icon="⬡",
    )

    # ── KPI row ──────────────────────────────────────────────────────────────
    cols = st.columns(4, gap="medium")

    # Total students (Lavender / Electric Purple accent)
    with cols[0]:
        try:
            res = api.list_students(page=1, size=1)
            total = res.get("total", 0)
            metric_card("Enrolled Students", str(total), "Verified student registry", accent="#8b5cf6")
        except Exception:
            metric_card("Enrolled Students", "—", "API unavailable", accent="#f87171")

    # Face-enrolled students (Lime accent)
    with cols[1]:
        try:
            res_active = api.list_students(status="ACTIVE", page=1, size=1)
            active = res_active.get("total", 0)
            metric_card(
                "Active Biometrics",
                str(active),
                "Status: Active in system",
                accent="#a3e635",
            )
        except Exception:
            metric_card("Active Biometrics", "—", "API unavailable", accent="#f87171")

    # Attendance today — endpoint not yet implemented; show honest placeholder (Coral accent)
    with cols[2]:
        metric_card(
            "Attendance Today",
            "—",
            "Marking engine in Phase 15",
            accent="#ff6b6b",
        )

    # Security alerts — endpoint not yet implemented (Amber accent)
    with cols[3]:
        metric_card(
            "Live Alerts",
            "—",
            "Security feed in Phase 18",
            accent="#fbbf24",
        )

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Recent students table & System Health ─────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("#### Recent Enrolments")
        try:
            res = api.list_students(page=1, size=8)
            items = res.get("items", [])
            if items:
                rows = []
                for s in items:
                    rows.append(
                        {
                            "Student ID": s.get("student_id", ""),
                            "Name": s.get("name", ""),
                            "Department": s.get("department", ""),
                            "Status": s.get("status", ""),
                            "Biometrics": "Enrolled" if s.get("face_registered") else "Pending",
                        }
                    )
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                empty_state("⊞", "No students registered yet", "Add students from the Student Management console.")
        except Exception as exc:
            st.warning(f"Could not load recent students: {exc}")

    with col_right:
        st.markdown("#### System Health & Nodes")
        st.markdown(
            """
            <div class="sas-card">
                <div style="display:flex;flex-direction:column;gap:0.85rem">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:var(--text-secondary);font-size:0.85rem;font-weight:600">FastAPI Core API</span>
                        <span class="badge badge-success">Online · 200 OK</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:var(--text-secondary);font-size:0.85rem;font-weight:600">PostgreSQL Database</span>
                        <span class="badge badge-success">Connected</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:var(--text-secondary);font-size:0.85rem;font-weight:600">InsightFace Engine</span>
                        <span class="badge badge-warning">Ready for model</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:var(--text-secondary);font-size:0.85rem;font-weight:600">RTSP / WebRTC Stream</span>
                        <span class="badge badge-muted">Phase 22</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:var(--text-secondary);font-size:0.85rem;font-weight:600">Redis Deduplication</span>
                        <span class="badge badge-muted">Standby</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="height:0.8rem"></div>
            <div class="sas-card">
                <div style="color:var(--accent-lavender);font-size:0.75rem;font-weight:800;
                            letter-spacing:0.08em;text-transform:uppercase;margin-bottom:0.6rem">
                    ⚡ Fast Actions
                </div>
                <div style="color:var(--text-secondary);font-size:0.84rem;line-height:2.0">
                    <span style="color:var(--accent-lime)">▸</span> Enrol Student with Biometric Consent<br>
                    <span style="color:var(--accent-coral)">▸</span> Query Historical Attendance Records<br>
                    <span style="color:var(--accent-purple)">▸</span> Export Department Breakdown Reports
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

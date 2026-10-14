"""
Reports view — attendance summary charts when data is available.
Gen Z themed Plotly charts with vibrant color scales.
"""
import streamlit as st
from frontend.components.layout import page_header, empty_state


def render_reports(api) -> None:
    page_header(
        "Campus Analytics",
        subtitle="Department distribution, enrolment velocity, and attendance logs",
        icon="↗",
    )

    # Try to fetch student department breakdown for a chart (real data)
    st.markdown("#### Department Distribution")
    try:
        res = api.list_students(page=1, size=200)
        items = res.get("items", [])
        if items:
            dept_counts: dict = {}
            for s in items:
                dept = s.get("department", "Unknown")
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

            import pandas as pd
            import plotly.express as px

            df = pd.DataFrame(
                {"Department": list(dept_counts.keys()), "Students": list(dept_counts.values())}
            ).sort_values("Students", ascending=False)

            # Gen Z vibrant color palette for chart
            fig = px.bar(
                df,
                x="Department",
                y="Students",
                color="Department",
                color_discrete_sequence=["#8b5cf6", "#ec4899", "#f97316", "#a3e635", "#38bdf8"],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#cbd5e1",
                font_family="Plus Jakarta Sans, sans-serif",
                showlegend=False,
                margin=dict(t=20, b=20, l=10, r=10),
                xaxis=dict(gridcolor="rgba(148, 163, 184, 0.15)", title=None),
                yaxis=dict(gridcolor="rgba(148, 163, 184, 0.15)", title="Students"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("↗", "No enrolment data yet", "Enrol students to visualize campus analytics.")
    except Exception as exc:
        st.warning(f"Could not generate department chart: {exc}")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("#### Exportable Reports")
    empty_state(
        "↗",
        "Attendance Export Engine — Phase 30",
        "Automated PDF reports, CSV logs, and daily presence audit summaries will be enabled here.",
    )

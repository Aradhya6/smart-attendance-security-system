"""
Attendance Records view.
Shows historical records when the endpoint is available;
renders an honest empty state when the endpoint is not yet implemented.
"""
import streamlit as st
from frontend.components.layout import page_header, empty_state


def render_attendance_records(api) -> None:
    page_header(
        "Attendance Records",
        subtitle="Historical attendance log filtered by date, student or course",
        icon="☰",
    )

    # Filters row
    col1, col2, col3 = st.columns([2, 2, 1], gap="medium")
    with col1:
        student_q = st.text_input("Student", placeholder="Name or Student ID…")
    with col2:
        dept_q = st.text_input("Department", placeholder="Filter by department…")
    with col3:
        limit = st.selectbox("Rows", [25, 50, 100])

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Attempt to call the attendance endpoint if it exists
    endpoint_available = False
    try:
        # The attendance records endpoint is not implemented yet (Phase 15).
        # We try a generic call; if the API client doesn't have it we catch AttributeError.
        records_fn = getattr(api, "list_attendance_records", None)
        if records_fn is not None:
            res = records_fn(
                q=student_q or None,
                department=dept_q or None,
                size=int(limit),
            )
            items = res.get("items", [])
            total = res.get("total", 0)
            endpoint_available = True

            st.caption(f"{total} record{'s' if total != 1 else ''} found")
            if items:
                st.dataframe(items, use_container_width=True, hide_index=True)
            else:
                empty_state(
                    "☰",
                    "No records found",
                    "Attendance is marked automatically during Live Attendance sessions.",
                )
    except Exception as exc:
        st.warning(f"Could not load records: {exc}")
        endpoint_available = False

    if not endpoint_available:
        empty_state(
            "☰",
            "Attendance Records — Not available yet",
            "This feature will be live in Phase 15. Once the attendance engine is running, "
            "all marked records will appear here.",
        )

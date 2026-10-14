"""
Students view — Search/List, Register, Manage, Face Registration.
Preserves all existing API calls and RBAC checks.
"""
import streamlit as st
from frontend.components.layout import page_header, status_badge, empty_state


def render_students(api, role: str) -> None:
    page_header("Student Management", subtitle="Enrol, search and manage student records", icon="⊞")

    tab_search, tab_register, tab_manage, tab_face = st.tabs(
        ["Search & List", "Register Student", "Manage Student", "Face Registration"]
    )

    # ── Tab 1: Search & List ──────────────────────────────────────────────────
    with tab_search:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1], gap="medium")
            with col1:
                search_query = st.text_input(
                    "Search", placeholder="Name or Student ID…", label_visibility="collapsed"
                )
            with col2:
                dept_filter = st.text_input(
                    "Department", placeholder="Filter by department…", label_visibility="collapsed"
                )
            with col3:
                status_filter = st.selectbox(
                    "Status", ["All", "ACTIVE", "INACTIVE"], label_visibility="collapsed"
                )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        try:
            res = api.list_students(
                q=search_query or None,
                department=dept_filter or None,
                status=status_filter if status_filter != "All" else None,
                page=1,
                size=50,
            )
            items = res.get("items", [])
            total = res.get("total", 0)

            # Summary row
            col_info, col_badge = st.columns([6, 1])
            with col_info:
                st.caption(f"{total} student{'s' if total != 1 else ''} found")

            if items:
                rows = [
                    {
                        "Student ID": s["student_id"],
                        "Name": s["name"],
                        "Department": s["department"],
                        "Year": s["year"],
                        "Status": s["status"],
                        "Consent": "Yes" if s.get("consent_given_at") else "No",
                        "Face Enrolled": "Yes" if s.get("face_registered") else "No",
                        "Samples": s.get("sample_count", 0),
                    }
                    for s in items
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                empty_state("⊞", "No students found", "Try adjusting your search filters.")
        except Exception as exc:
            st.error(f"Failed to fetch students: {exc}")

    # ── Tab 2: Register ───────────────────────────────────────────────────────
    with tab_register:
        if role != "ADMIN":
            st.warning("Only ADMIN users can enrol students.")
        else:
            st.markdown("#### Enrol New Student")
            with st.form("new_student_form", clear_on_submit=True):
                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    stu_id = st.text_input("Student ID", placeholder="e.g. CSE-2024-001")
                    name = st.text_input("Full Name", placeholder="Student's full name")
                with c2:
                    dept = st.text_input("Department", placeholder="e.g. Computer Science")
                    year = st.number_input("Year of Study", min_value=1, max_value=8, value=1)

                st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
                consent = st.checkbox(
                    "Student has provided biometric consent (DPDP Act compliance)",
                    value=True,
                )
                consent_ver = st.text_input("Consent Document Version", value="v1.0")

                submitted = st.form_submit_button("Register Student", use_container_width=True)
                if submitted:
                    if not stu_id or not name or not dept:
                        st.error("Student ID, Name, and Department are required.")
                    else:
                        try:
                            created = api.create_student(
                                student_id=stu_id,
                                name=name,
                                department=dept,
                                year=int(year),
                                consent=consent,
                                consent_version=consent_ver,
                            )
                            st.success(
                                f"Student **{created['name']}** ({created['student_id']}) registered successfully."
                            )
                        except Exception as exc:
                            st.error(f"Registration failed: {exc}")

    # ── Tab 3: Manage ─────────────────────────────────────────────────────────
    with tab_manage:
        if role != "ADMIN":
            st.warning("Only ADMIN users can update or deactivate students.")
        else:
            st.markdown("#### Edit Existing Student")
            search_id = st.text_input(
                "Student UUID",
                placeholder="Paste UUID from the Search & List tab…",
                key="manage_uuid",
            )
            if search_id:
                try:
                    student = api.get_student(search_id)
                    st.markdown(
                        f"Editing: **{student['name']}** · {student['student_id']}",
                    )
                    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

                    col1, col2 = st.columns([2, 1], gap="large")
                    with col1:
                        new_name = st.text_input("Name", value=student["name"])
                        new_dept = st.text_input("Department", value=student["department"])
                        new_year = st.number_input(
                            "Year", min_value=1, max_value=8, value=student["year"]
                        )
                        new_status = st.selectbox(
                            "Status",
                            ["ACTIVE", "INACTIVE"],
                            index=0 if student["status"] == "ACTIVE" else 1,
                        )
                        if st.button("Save Changes", type="primary", key="save_student"):
                            try:
                                api.update_student(
                                    student["id"],
                                    {
                                        "name": new_name,
                                        "department": new_dept,
                                        "year": int(new_year),
                                        "status": new_status,
                                    },
                                )
                                st.success("Student updated successfully.")
                            except Exception as exc:
                                st.error(f"Update failed: {exc}")

                    with col2:
                        st.markdown(
                            """
                            <div class="sas-card" style="border-color:rgba(239,68,68,0.3)">
                                <div style="color:var(--error);font-weight:600;
                                            font-size:0.82rem;margin-bottom:0.75rem">
                                    Danger Zone
                                </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "Deactivate Student",
                            key="deactivate_student",
                            use_container_width=True,
                        ):
                            try:
                                api.deactivate_student(student["id"])
                                st.warning(
                                    f"Student {student['student_id']} has been deactivated."
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Deactivation failed: {exc}")
                        st.markdown("</div>", unsafe_allow_html=True)
                except Exception as exc:
                    st.error(f"Could not load student: {exc}")

    # ── Tab 4: Face Registration ──────────────────────────────────────────────
    with tab_face:
        st.markdown("#### Webcam Face Registration")
        if role != "ADMIN":
            st.warning("Only ADMIN users can register biometrics.")
        else:
            target_stu_id = st.text_input(
                "Student UUID",
                placeholder="Paste UUID to enrol face biometrics…",
                key="face_reg_stu_id",
            )
            if target_stu_id:
                try:
                    stu = api.get_student(target_stu_id)
                    st.markdown(
                        f"Enrolling biometrics for: **{stu['name']}** ({stu['student_id']})"
                    )

                    if not stu.get("consent_given_at"):
                        st.error(
                            "Cannot register biometrics — student has NOT provided biometric consent. "
                            "Update the student profile with consent first."
                        )
                    else:
                        st.success("Consent verified. Ready for webcam enrolment.")
                        target_samples = st.slider(
                            "Target Samples", min_value=5, max_value=50, value=10
                        )

                        face_sess = st.session_state.get("face_session", {})
                        same_student = face_sess.get("student_uuid") == target_stu_id

                        if not same_student:
                            if st.button("Start Camera Registration Session", key="start_face_sess"):
                                try:
                                    sess = api.create_face_session(
                                        target_stu_id, target_samples=target_samples
                                    )
                                    ticket = api.get_stream_ticket("0")
                                    st.session_state["face_session"] = {
                                        "session_id": sess["session_id"],
                                        "student_uuid": target_stu_id,
                                        "target_samples": target_samples,
                                        "current_samples": 0,
                                        "ticket": ticket,
                                        "prompt": "Look directly at camera",
                                    }
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Could not start session: {ex}")
                        else:
                            active_sess = st.session_state["face_session"]
                            col_preview, col_controls = st.columns([3, 2], gap="large")

                            with col_preview:
                                stream_url = (
                                    f"{api.base_url}/stream/0?ticket={active_sess['ticket']}"
                                )
                                st.markdown(
                                    f'<img src="{stream_url}" width="100%" '
                                    'style="border-radius:10px;border:2px solid var(--accent-teal)" />',
                                    unsafe_allow_html=True,
                                )

                            with col_controls:
                                st.markdown(
                                    f"""
                                    <div class="sas-card">
                                        <div class="label">Current Prompt</div>
                                        <div style="font-weight:600;color:var(--text-primary);
                                                    font-size:1rem;margin-bottom:1rem">
                                            {active_sess.get('prompt', 'Look at camera')}
                                        </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                progress = min(
                                    1.0,
                                    active_sess["current_samples"]
                                    / active_sess["target_samples"],
                                )
                                st.progress(progress)
                                st.caption(
                                    f"Captured: {active_sess['current_samples']} / "
                                    f"{active_sess['target_samples']}"
                                )
                                st.markdown("</div>", unsafe_allow_html=True)

                                st.markdown(
                                    "<div style='height:0.5rem'></div>", unsafe_allow_html=True
                                )
                                if st.button(
                                    "Capture Frame Sample",
                                    use_container_width=True,
                                    key="capture_sample",
                                ):
                                    try:
                                        cap_res = api.capture_face_sample(
                                            target_stu_id, active_sess["session_id"]
                                        )
                                        active_sess["current_samples"] = cap_res["current_samples"]
                                        active_sess["prompt"] = cap_res["pose_prompt"]
                                        if (
                                            active_sess["current_samples"]
                                            >= active_sess["target_samples"]
                                        ):
                                            st.balloons()
                                            st.success(
                                                "Target samples reached! Proceed to commit in the next phase."
                                            )
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Capture failed: {ex}")

                                if st.button(
                                    "Cancel & Release Camera",
                                    use_container_width=True,
                                    key="cancel_face_sess",
                                ):
                                    try:
                                        api.cancel_face_session(
                                            target_stu_id, active_sess["session_id"]
                                        )
                                    except Exception:
                                        pass
                                    del st.session_state["face_session"]
                                    st.rerun()
                except Exception as exc:
                    st.error(f"Error loading student: {exc}")

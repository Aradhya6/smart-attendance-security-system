"""
Smart Attendance & Security System - Streamlit Dashboard Shell
Unified dashboard with strict RBAC, multi-page sidebar navigation, and session auth.
"""
import streamlit as st
from frontend.api_client import APIClient
from frontend.components.auth import require_auth

# Configure Streamlit page
st.set_page_config(
    page_title="Smart Attendance & Security",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize API client
api = APIClient()

# Check authentication gate
if not require_auth(api):
    st.stop()

# User is authenticated
current_user = st.session_state.get("user", {})
role = current_user.get("role", "OPERATOR")
username = current_user.get("username", "User")

# Top Header / User Info in Sidebar
st.sidebar.markdown(f"### 👤 Logged in as: **{username}**")
st.sidebar.caption(f"Role: **{role}**")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    api.logout()
    st.rerun()

st.sidebar.markdown("---")

# Navigation Sidebar exactly per Playbook Section 8:
# LOGIN
# Dashboard                      (7 real KPIs + recent attendance + recent alerts + live tile)
# ATTENDANCE   Live Attendance | Students | Attendance Records | Reports
# SECURITY     Live Monitoring | Alerts | Blacklist | Detection Events | Movement Tracking
# SYSTEM       Cameras | Users | Settings

NAV_SECTIONS = [
    "📊 Dashboard",
    "--- ATTENDANCE ---",
    "📹 Live Attendance",
    "👥 Students",
    "📋 Attendance Records",
    "📈 Reports",
    "--- SECURITY ---",
    "🛡️ Live Monitoring",
    "⚠️ Alerts",
    "🚫 Blacklist",
    "🔍 Detection Events",
    "📍 Movement Tracking",
    "--- SYSTEM ---",
    "📷 Cameras",
    "👤 Users",
    "⚙️ Settings",
]

# Clean display list (selectable options)
selectable_options = [
    opt for opt in NAV_SECTIONS if not opt.startswith("---")
]

selected_page = st.sidebar.radio("Navigation", selectable_options)

# Router
if selected_page == "👥 Students":
    st.header("👥 Student Management")
    tabs = st.tabs(["Search & List", "Register New Student", "Edit / Manage", "📸 Register Face (Webcam)"])

    with tabs[0]:
        st.subheader("Student Directory")
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            search_query = st.text_input("Search by Name or Student ID", "")
        with col2:
            dept_filter = st.text_input("Filter Department", "")
        with col3:
            status_filter = st.selectbox("Status", ["", "ACTIVE", "INACTIVE"])

        try:
            res = api.list_students(
                q=search_query or None,
                department=dept_filter or None,
                status=status_filter or None,
                page=1,
                size=50,
            )
            items = res.get("items", [])
            total = res.get("total", 0)
            st.caption(f"Total students found: {total}")

            if items:
                table_data = [
                    {
                        "UUID": s["id"],
                        "Student ID": s["student_id"],
                        "Name": s["name"],
                        "Department": s["department"],
                        "Year": s["year"],
                        "Status": s["status"],
                        "Consent": "✅ Yes" if s.get("consent_given_at") else "❌ No",
                        "Face Enrolled": "✅ Yes" if s.get("face_registered") else "❌ No",
                        "Samples": s.get("sample_count", 0),
                    }
                    for s in items
                ]
                st.dataframe(table_data, use_container_width=True)
            else:
                st.info("No students found matching current criteria.")
        except Exception as e:
            st.error(f"Failed to fetch students: {e}")

    with tabs[1]:
        st.subheader("Enroll New Student")
        if role != "ADMIN":
            st.warning("⚠️ Only ADMIN users have permission to enroll students.")
        else:
            with st.form("new_student_form"):
                stu_id = st.text_input("Student ID (e.g. 001, CSE-2024-01)")
                name = st.text_input("Full Name")
                dept = st.text_input("Department (e.g. Computer Science)")
                year = st.number_input("Year of Study", min_value=1, max_value=8, value=1)
                consent = st.checkbox("Student has provided Biometric Consent (DPDP Act compliance)", value=True)
                consent_ver = st.text_input("Consent Document Version", value="v1.0")

                submitted = st.form_submit_button("Register Student", use_container_width=True)
                if submitted:
                    if not stu_id or not name or not dept:
                        st.error("Please fill in Student ID, Name, and Department.")
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
                            st.success(f"Student '{created['name']}' ({created['student_id']}) created successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    with tabs[2]:
        st.subheader("Manage Existing Student")
        if role != "ADMIN":
            st.warning("⚠️ Only ADMIN users have permission to update or deactivate students.")
        else:
            search_id = st.text_input("Enter Student UUID or search above to find UUID", "")
            if search_id:
                try:
                    student = api.get_student(search_id)
                    st.write(f"Editing: **{student['name']}** ({student['student_id']})")
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Update Name", value=student["name"])
                        new_dept = st.text_input("Update Department", value=student["department"])
                        new_year = st.number_input("Update Year", min_value=1, max_value=8, value=student["year"])
                        new_status = st.selectbox("Update Status", ["ACTIVE", "INACTIVE"], index=0 if student["status"] == "ACTIVE" else 1)
                        if st.button("Save Changes"):
                            api.update_student(student["id"], {
                                "name": new_name,
                                "department": new_dept,
                                "year": int(new_year),
                                "status": new_status,
                            })
                            st.success("Student updated successfully!")
                            st.rerun()
                    with col2:
                        st.markdown("#### Danger Zone")
                        if st.button("🛑 Deactivate Student (Soft Delete)", type="primary"):
                            api.deactivate_student(student["id"])
                            st.warning(f"Student {student['student_id']} deactivated.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Could not load student: {e}")

    with tabs[3]:
        st.subheader("Webcam Face Registration")
        if role != "ADMIN":
            st.warning("⚠️ Only ADMIN users have permission to register biometrics.")
        else:
            target_stu_id = st.text_input("Enter Student UUID to Enroll Face", key="face_reg_stu_id")
            if target_stu_id:
                try:
                    stu = api.get_student(target_stu_id)
                    st.write(f"Enrolling: **{stu['name']}** ({stu['student_id']})")
                    if not stu.get("consent_given_at"):
                        st.error("❌ Cannot register biometrics: Student has NOT provided biometric consent. Please update student profile with consent first.")
                    else:
                        st.success("✅ Consent verified. Ready for webcam enrollment.")
                        target_samples = st.slider("Target Samples", min_value=5, max_value=50, value=10)

                        if "face_session" not in st.session_state or st.session_state["face_session"].get("student_uuid") != target_stu_id:
                            if st.button("▶️ Start Camera Registration Session"):
                                try:
                                    sess = api.create_face_session(target_stu_id, target_samples=target_samples)
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
                            col_preview, col_controls = st.columns([3, 2])
                            with col_preview:
                                stream_url = f"{api.base_url}/stream/0?ticket={active_sess['ticket']}"
                                st.markdown(f'<img src="{stream_url}" width="100%" style="border-radius:8px; border:2px solid #4CAF50;" />', unsafe_allow_html=True)
                            with col_controls:
                                st.markdown(f"#### Prompt: **{active_sess.get('prompt', 'Look at camera')}**")
                                progress = min(1.0, active_sess["current_samples"] / active_sess["target_samples"])
                                st.progress(progress)
                                st.caption(f"Captured: {active_sess['current_samples']} / {active_sess['target_samples']}")

                                if st.button("📸 Capture Frame Sample", use_container_width=True):
                                    try:
                                        cap_res = api.capture_face_sample(target_stu_id, active_sess["session_id"])
                                        active_sess["current_samples"] = cap_res["current_samples"]
                                        active_sess["prompt"] = cap_res["pose_prompt"]
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Capture failed: {ex}")

                                if active_sess["current_samples"] >= active_sess["target_samples"]:
                                    st.success("🎉 Target samples reached! Click below to save embeddings.")
                                    if st.button("💾 Commit & Save Face Embeddings", use_container_width=True, type="primary"):
                                        try:
                                            commit_res = api.commit_face_registration(target_stu_id, active_sess["session_id"])
                                            stored = commit_res.get("stored_count", 0)
                                            rejected = commit_res.get("rejected_count", 0)
                                            st.success(f"✅ Face registered! {stored} embeddings stored, {rejected} rejected by consistency check.")
                                            del st.session_state["face_session"]
                                            st.rerun()
                                        except Exception as ex:
                                            st.error(f"Commit failed: {ex}")

                                if st.button("❌ Cancel & Release Camera", use_container_width=True):
                                    try:
                                        api.cancel_face_session(target_stu_id, active_sess["session_id"])
                                    except Exception:
                                        pass
                                    del st.session_state["face_session"]
                                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading student: {e}")

elif selected_page == "📊 Dashboard":
    st.header("📊 System Overview")
    try:
        summary = api.get("/dashboard/summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👥 Total Students", summary.get("total_students", 0))
        col2.metric("✅ Present Today", summary.get("present_today", 0))
        col3.metric(
            "📊 Attendance %",
            f"{summary.get('attendance_percent', 0):.1f}%",
        )
        col4.metric("❓ Unknown Today", summary.get("unknown_today", 0))

        col5, col6, col7 = st.columns(3)
        col5.metric("📷 Active Cameras", summary.get("active_cameras", 0))
        col6.metric("⚠️ Open Alerts", summary.get("active_alerts", 0))
        col7.metric("🚫 Blacklisted Today", summary.get("blacklisted_today", 0))

        st.caption(f"Data for: {summary.get('date', 'today')} | Students with faces: {summary.get('students_with_faces', 0)}")
        st.divider()

        st.subheader("Recent Attendance")
        try:
            recent = api.get("/attendance/recent", params={"limit": 15})
            if recent:
                import pandas as pd
                df = pd.DataFrame([{
                    "Student ID": r["student_id"],
                    "Name": r["full_name"],
                    "Date": r["attendance_date"],
                    "Time": r["marked_at"],
                    "Status": r["status"],
                    "Score": f"{r['similarity']:.2f}",
                    "Method": r["method"],
                } for r in recent])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No attendance records yet today.")
        except Exception as e:
            st.warning(f"Could not load recent attendance: {e}")
    except Exception as e:
        st.error(f"Dashboard unavailable: {e}")

elif selected_page == "📹 Live Attendance":
    st.header("📹 Live Attendance Recognition")
    if role not in ("ADMIN",):
        st.warning("ADMIN access required to start/stop camera workers.")
    else:
        # Fetch cameras
        try:
            workers = api.get("/recognition/workers")
        except Exception:
            workers = []

        # Get seeded camera
        try:
            cams_resp = api.get("/students", params={"size": 1})  # just to test auth
            # Fetch the seeded camera id from DB
            import requests, os
            r = requests.get(
                f"{api.base_url}/health",
                headers=api._get_headers(),
            )
            # Use known camera id from seed
            camera_id_str = st.text_input(
                "Camera UUID (from `python scripts/seed_camera.py`)",
                key="live_cam_id",
            )
        except Exception:
            camera_id_str = ""

        running_ids = {w["camera_id"] for w in workers if w["status"] == "RUNNING"}
        col_start, col_stop, col_status = st.columns(3)
        with col_start:
            if st.button("▶️ Start Camera Worker", disabled=not camera_id_str):
                try:
                    res = api.post(f"/recognition/workers/{camera_id_str}/start")
                    st.success(f"Worker started: {res.get('status')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not start: {e}")
        with col_stop:
            if st.button("⏹️ Stop Camera Worker", disabled=not camera_id_str):
                try:
                    res = api.post(f"/recognition/workers/{camera_id_str}/stop")
                    st.success(f"Worker stopped: {res.get('status')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not stop: {e}")
        with col_status:
            st.write("**Active Workers:**", len(running_ids))

        if workers:
            for w in workers:
                st.info(f"Camera {w['camera_id'][:8]}… | Status: {w['status']} | FPS: {w.get('fps', 0):.1f}")

        if camera_id_str and camera_id_str in running_ids:
            try:
                ticket = api.get_stream_ticket(camera_id_str)
                stream_url = f"{api.base_url}/stream/{camera_id_str}?ticket={ticket}"
                st.markdown(
                    f'<img src="{stream_url}" width="100%" style="border-radius:8px; border:2px solid #2196F3;" />',
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.warning(f"Stream unavailable: {e}")

elif selected_page == "📋 Attendance Records":
    st.header("📋 Attendance Records")
    from datetime import date, timedelta
    import pandas as pd

    col1, col2, col3 = st.columns(3)
    with col1:
        from_dt = st.date_input("From Date", value=date.today() - timedelta(days=7))
    with col2:
        to_dt = st.date_input("To Date", value=date.today())
    with col3:
        sid_filter = st.text_input("Student ID (optional)")

    try:
        params = {"from_date": str(from_dt), "to_date": str(to_dt), "size": 200}
        if sid_filter:
            params["student_id"] = sid_filter
        records = api.get("/attendance", params=params)
        if records:
            df = pd.DataFrame([{
                "Student ID": r["student_id"],
                "Name": r["full_name"],
                "Date": r["attendance_date"],
                "Time": str(r["marked_at"])[:19],
                "Status": r["status"],
                "Score": f"{r['similarity']:.3f}",
                "Method": r["method"],
            } for r in records])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(records)} record(s) shown")

            if role == "ADMIN":
                st.subheader("Manual Attendance Mark")
                with st.form("manual_att"):
                    m_sid = st.text_input("Student ID")
                    m_reason = st.text_input("Reason")
                    m_date = st.date_input("Date", value=date.today())
                    if st.form_submit_button("Mark Present"):
                        try:
                            res = api.post("/attendance/manual", json={
                                "student_id": m_sid,
                                "reason": m_reason,
                                "attendance_date": str(m_date),
                            })
                            if res.get("marked"):
                                st.success(f"Marked present for {m_sid} on {m_date}")
                            else:
                                st.warning(f"{m_sid} already marked for {m_date}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No records for this date range.")
    except Exception as e:
        st.error(f"Failed to load records: {e}")

elif selected_page == "📈 Reports":
    st.header("📈 Reports & Exports")
    st.info("Attendance reporting & CSV exports (Phase 30 scope).")
    st.markdown("Use **Attendance Records** tab to view and filter records.")

elif selected_page == "🛡️ Live Monitoring":
    st.header("🛡️ Campus Security Monitoring")
    st.info("Multi-camera live surveillance (Security Module — separate scope)")

elif selected_page == "⚠️ Alerts":
    st.header("⚠️ Security Alerts")
    st.info("Real-time intrusion & blacklist alerts (Security Module)")

elif selected_page == "🚫 Blacklist":
    st.header("🚫 Blacklist Management")
    st.info("Campus blacklist registry (Security Module)")

elif selected_page == "🔍 Detection Events":
    st.header("🔍 Detection Events")
    st.info("All raw detection sightings (Security Module)")

elif selected_page == "📍 Movement Tracking":
    st.header("📍 Movement Tracking")
    st.info("Sightings timeline (Security Module)")

elif selected_page == "📷 Cameras":
    st.header("📷 Camera Management")
    try:
        workers = api.get("/recognition/workers")
        if workers:
            for w in workers:
                st.metric(f"Camera {w['camera_id'][:8]}…", w["status"], f"FPS: {w.get('fps', 0):.1f}")
        else:
            st.info("No camera workers currently running.")
        st.caption("To start a camera: go to 📹 Live Attendance and use the camera controls.")
    except Exception as e:
        st.warning(f"Could not fetch worker status: {e}")

elif selected_page == "👤 Users":
    st.header("👤 User Management")
    st.info("System administrator & operator accounts")

elif selected_page == "⚙️ Settings":
    st.header("⚙️ System Settings")
    st.info("Recognition thresholds and system parameters")


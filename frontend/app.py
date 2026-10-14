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
    tabs = st.tabs([
        "Search & List",
        "Register New Student",
        "Edit / Manage",
        "📸 Register Face (Webcam)",
        "🖼️ Register Face (Photo)",
    ])

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

    with tabs[4]:
        st.subheader("🖼️ Register Face Using Photo")
        if role != "ADMIN":
            st.warning("⚠️ Only ADMIN users have permission to register biometrics.")
        else:
            photo_stu_id = st.text_input("Enter Student UUID to Enroll Face", key="photo_reg_stu_id")
            if photo_stu_id:
                try:
                    stu = api.get_student(photo_stu_id)
                    st.write(f"Enrolling: **{stu['name']}** ({stu['student_id']})")
                    if not stu.get("consent_given_at"):
                        st.error("❌ Cannot register biometrics: Student has NOT provided biometric consent. Please update student profile with consent first.")
                    elif stu.get("status") != "ACTIVE":
                        st.error(f"❌ Cannot register biometrics: Student status is '{stu.get('status')}'. Only ACTIVE students can register.")
                    else:
                        st.success("✅ Consent and status verified. Ready for photo upload.")
                        uploaded_file = st.file_uploader(
                            "Upload Face Photo (JPG, JPEG, or PNG, max 5 MB)",
                            type=["jpg", "jpeg", "png"],
                            key="photo_reg_uploader",
                        )
                        if uploaded_file is not None:
                            st.image(uploaded_file, caption="Photo Preview", width=300)
                            if st.button("Validate & Register Face", type="primary", use_container_width=True):
                                with st.spinner("Analyzing image, detecting face, and generating biometric embedding..."):
                                    try:
                                        file_bytes = uploaded_file.getvalue()
                                        res = api.upload_face_photo(
                                            student_uuid=photo_stu_id,
                                            file_bytes=file_bytes,
                                            filename=uploaded_file.name,
                                            content_type=uploaded_file.type or "image/jpeg",
                                        )
                                        stored = res.get("stored_count", 1)
                                        q_score = res.get("quality_score", 0.0)
                                        st.success(f"🎉 Face registered successfully! Stored {stored} embedding (quality score: {q_score:.2f}).")
                                        st.balloons()
                                    except Exception as ex:
                                        st.error(f"❌ Registration failed: {ex}")
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
        # Fetch registered cameras and running workers from backend
        try:
            cameras = api.list_cameras()
        except Exception as e:
            st.error(f"Failed to fetch registered cameras: {e}")
            cameras = []

        try:
            workers = api.list_camera_workers()
        except Exception:
            workers = []

        if not cameras:
            st.warning("No registered cameras found in database.")
        else:
            # Find default camera (Laptop Webcam)
            default_idx = 0
            for idx, c in enumerate(cameras):
                if "laptop" in c["name"].lower() or "webcam" in c["name"].lower():
                    default_idx = idx
                    break

            cam_options = [f"{c['name']} ({c['location']} — {c['source_type']})" for c in cameras]
            col_cam, col_sess = st.columns([3, 2])
            with col_cam:
                selected_cam_idx = st.selectbox(
                    "Select Camera Device",
                    range(len(cam_options)),
                    format_func=lambda i: cam_options[i],
                    index=default_idx,
                    key="live_cam_select",
                )
                selected_camera = cameras[selected_cam_idx]
                camera_id_str = selected_camera["id"]
            with col_sess:
                session_label = st.text_input(
                    "Active Attendance Session Label",
                    value=st.session_state.get("active_session_label", "DEFAULT"),
                    key="live_session_label",
                )
                st.session_state["active_session_label"] = session_label

            # Check if this camera is currently running
            matching_worker = next((w for w in workers if w["camera_id"] == camera_id_str), None)
            is_running = matching_worker is not None and matching_worker.get("status") == "RUNNING"
            worker_status = matching_worker.get("status") if matching_worker else "STOPPED"
            worker_fps = matching_worker.get("fps", 0.0) if matching_worker else 0.0

            # Action bar: Start / Stop / Connection status
            col_start, col_stop, col_stat = st.columns([2, 2, 3])
            with col_start:
                if st.button("▶️ Start Live Attendance", type="primary" if not is_running else "secondary", disabled=is_running, use_container_width=True):
                    try:
                        res = api.start_camera_worker(camera_id_str, session_label=session_label)
                        st.success(f"Camera worker started: {res.get('status')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not start: {e}")

            with col_stop:
                if st.button("⏹️ Stop Attendance", type="secondary" if not is_running else "primary", disabled=not is_running, use_container_width=True):
                    try:
                        res = api.stop_camera_worker(camera_id_str)
                        st.success(f"Camera worker stopped: {res.get('status')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not stop: {e}")

            with col_stat:
                if is_running:
                    st.success(f"🟢 **Status: RUNNING** | {worker_fps:.1f} FPS | Camera: {selected_camera['name']}")
                else:
                    st.info(f"⚪ **Status: {worker_status}** | Camera: {selected_camera['name']} (Device {selected_camera.get('source_url', '0')})")

            # Live View & Real-Time Attendance Stream
            from datetime import date
            today_str = str(date.today())

            if is_running:
                col_stream, col_panel = st.columns([3, 2])
                with col_stream:
                    st.subheader("Live Recognition Stream")
                    try:
                        ticket = api.get_stream_ticket(camera_id_str)
                        stream_url = f"{api.base_url}/stream/{camera_id_str}?ticket={ticket}"
                        st.markdown(
                            f'<img src="{stream_url}" width="100%" style="border-radius:8px; border:2px solid #4CAF50;" />',
                            unsafe_allow_html=True,
                        )
                        st.caption("🟢 Green: Confirmed Student | 🔴 Red: Unknown / Unconfirmed")
                    except Exception as e:
                        st.warning(f"Stream preview unavailable: {e}")

                with col_panel:
                    st.subheader("📋 Session Attendance")
                    try:
                        live_records = api.get("/attendance", params={
                            "session_label": session_label,
                            "from_date": today_str,
                            "to_date": today_str,
                            "size": 50,
                        })
                        if live_records:
                            st.write(f"**Marked Present:** {len(live_records)} student(s)")
                            df_live = [
                                {
                                    "ID": r["student_id"],
                                    "Name": r["full_name"],
                                    "Time": str(r["marked_at"])[11:19] if r.get("marked_at") else "",
                                    "Score": f"{r['similarity']:.2f}",
                                    "Status": r["status"],
                                }
                                for r in live_records
                            ]
                            st.dataframe(df_live, use_container_width=True, hide_index=True)
                        else:
                            st.info("No students recognized in this session yet. Look at the camera to be marked.")
                    except Exception as e:
                        st.error(f"Could not load live attendance records: {e}")

                    if st.button("🔄 Refresh Live Attendance", use_container_width=True):
                        st.rerun()

            else:
                # When stopped: show session summary & finalize view
                st.divider()
                st.subheader(f"📊 Attendance Summary for Session: '{session_label}'")
                col_m1, col_m2 = st.columns(2)
                try:
                    records_today = api.get("/attendance", params={
                        "session_label": session_label,
                        "from_date": today_str,
                        "to_date": today_str,
                        "size": 200,
                    })
                    all_students_res = api.list_students(status="ACTIVE", size=200)
                    active_students = all_students_res.get("items", [])
                    present_ids = {r["student_id"] for r in records_today}

                    col_m1.metric("Present / Late", len(records_today))
                    col_m2.metric("Total Active Students", len(active_students))

                    if records_today:
                        st.write("#### Students Present in Session")
                        df_summary = [
                            {
                                "Student ID": r["student_id"],
                                "Name": r["full_name"],
                                "Time": str(r["marked_at"])[11:19] if r.get("marked_at") else "",
                                "Status": r["status"],
                                "Similarity": f"{r['similarity']:.3f}",
                            }
                            for r in records_today
                        ]
                        st.dataframe(df_summary, use_container_width=True, hide_index=True)

                    unmarked = [s for s in active_students if s["student_id"] not in present_ids]
                    if unmarked:
                        with st.expander(f"Unmarked Students ({len(unmarked)} students not present)"):
                            df_absent = [
                                {"Student ID": s["student_id"], "Name": s["name"], "Department": s["department"], "Year": s["year"]}
                                for s in unmarked
                            ]
                            st.dataframe(df_absent, use_container_width=True, hide_index=True)
                except Exception as ex:
                    st.caption(f"Summary info: {ex}")

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


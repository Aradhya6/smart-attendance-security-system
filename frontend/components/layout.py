"""
Shared layout helpers: sidebar brand, navigation, topbar, page header,
metric cards, badges, and empty-state components.
"""
import streamlit as st
from frontend.styles.theme import inject_theme, theme_toggle


# ── Navigation configuration ─────────────────────────────────────────────────
NAV_SECTIONS = [
    # (section_label, [("Display Name", "icon", "key")])
    ("ATTENDANCE", [
        ("Dashboard",           "⬡",  "Dashboard"),
        ("Live Attendance",     "◉",  "Live Attendance"),
        ("Students",            "⊞",  "Students"),
        ("Attendance Records",  "☰",  "Attendance Records"),
        ("Reports",             "↗",  "Reports"),
    ]),
    ("SECURITY", [
        ("Live Monitoring",     "◎",  "Live Monitoring"),
        ("Alerts",              "⚑",  "Alerts"),
        ("Blacklist",           "⊘",  "Blacklist"),
        ("Detection Events",    "◈",  "Detection Events"),
        ("Movement Tracking",   "⊕",  "Movement Tracking"),
    ]),
    ("SYSTEM", [
        ("Cameras",             "⊡",  "Cameras"),
        ("Users",               "⊛",  "Users"),
        ("Settings",            "⊜",  "Settings"),
    ]),
]

# Flat selectable list for st.radio (keys only)
SELECTABLE_KEYS = [item[2] for _, items in NAV_SECTIONS for item in items]

# Icon lookup
NAV_ICONS = {item[2]: item[1] for _, items in NAV_SECTIONS for item in items}
NAV_LABELS = {item[2]: item[0] for _, items in NAV_SECTIONS for item in items}


def render_sidebar(username: str, role: str, api) -> str:
    """
    Render the sidebar: brand, navigation, user info, theme toggle, logout.
    Returns the currently selected page key.
    """
    with st.sidebar:
        # ── Brand ────────────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="sidebar-brand">
                <div style="display:flex; align-items:center; gap:0.65rem;">
                    <div class="brand-mark">◈</div>
                    <div>
                        <div class="brand-name">CampusOS</div>
                        <div class="brand-sub">Attendance &amp; Security</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Navigation Buttons ───────────────────────────────────────────────
        current = st.session_state.get("current_page", "Dashboard")

        for sec_label, items in NAV_SECTIONS:
            st.markdown(
                f'<div class="section-header">{sec_label}</div>',
                unsafe_allow_html=True,
            )
            for display, icon, key in items:
                is_active = current == key
                btn_label = f"▸ {icon}  {display}" if is_active else f"  {icon}  {display}"
                if st.button(
                    btn_label,
                    key=f"nav_{key}",
                    use_container_width=True,
                    help=display,
                ):
                    st.session_state["current_page"] = key
                    st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # ── User info ────────────────────────────────────────────────────────
        initials = "".join(w[0].upper() for w in username.split()[:2]) or "U"
        st.markdown(
            f"""
            <div class="user-chip">
                <div class="user-avatar">{initials}</div>
                <div style="flex:1; overflow:hidden;">
                    <div style="font-weight:700; color:var(--text-primary); font-size:0.84rem; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">{username}</div>
                    <div style="font-size:0.68rem; color:var(--accent-lavender); font-weight:600; text-transform:uppercase;">{role}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── Theme toggle ─────────────────────────────────────────────────────
        theme_toggle(sidebar=True)

        # ── Logout ───────────────────────────────────────────────────────────
        if st.button("Sign Out", key="logout_btn", use_container_width=True):
            api.logout()
            st.rerun()

    return st.session_state.get("current_page", "Dashboard")


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Render a styled page header bar with vibrant icon accent."""
    icon_html = f'<div class="page-icon">{icon}</div>' if icon else ""
    sub_html = (
        f'<div class="sub">{subtitle}</div>' if subtitle else ""
    )
    st.markdown(
        f"""
        <div class="page-header">
            {icon_html}
            <div>
                <h1>{title}</h1>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, sub: str = "", accent: str = "") -> None:
    """
    Render a metric card with accent left-border.
    accent: optional CSS colour override for the left border.
    """
    style = f"--accent: {accent};" if accent else ""
    st.markdown(
        f"""
        <div class="sas-metric" style="{style}">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            {"" if not sub else f'<div class="sub">{sub}</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    """Return an HTML badge string for a given status string."""
    mapping = {
        "ACTIVE":    ("success", "Active"),
        "INACTIVE":  ("muted",   "Inactive"),
        "ONLINE":    ("success", "Online"),
        "OFFLINE":   ("error",   "Offline"),
        "PENDING":   ("warning", "Pending"),
        "YES":       ("success", "Yes"),
        "NO":        ("error",   "No"),
        "OPEN":      ("error",   "Open"),
        "RESOLVED":  ("success", "Resolved"),
        "HIGH":      ("error",   "High"),
        "MEDIUM":    ("warning", "Medium"),
        "LOW":       ("info",    "Low"),
    }
    cls, label = mapping.get(status.upper(), ("muted", status))
    return f'<span class="badge badge-{cls}">{label}</span>'


def empty_state(icon: str, title: str, desc: str = "") -> None:
    """Render a centred empty-state placeholder."""
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="icon">{icon}</div>
            <div class="title">{title}</div>
            {"" if not desc else f'<div class="desc">{desc}</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_layout(api) -> str:
    """
    Top-level layout entry: inject theme, render sidebar, return selected page.
    Call this AFTER require_auth() passes.
    """
    inject_theme()
    current_user = st.session_state.get("user", {})
    username = current_user.get("username", "User")
    role = current_user.get("role", "OPERATOR")
    return render_sidebar(username, role, api)

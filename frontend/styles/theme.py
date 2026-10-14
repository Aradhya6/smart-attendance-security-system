"""
Theme system for Smart Attendance & Security System.
Gen Z, vibrant campus-tech interface tokens & styles with light/dark mode support.
"""
import streamlit as st


# ── Gen Z Campus-Tech Color Tokens ──────────────────────────────────────────
# Palette: Lavender, Electric Purple, Vibrant Coral, Lime Accent, Crisp Neutrals
DARK = {
    # Backgrounds: Deep violet-tinted darks
    "bg_page":        "#0c0a17",
    "bg_sidebar":     "#120e24",
    "bg_card":        "#17132e",
    "bg_card_hover":  "#201a3d",
    "bg_input":       "#1f1a3a",
    # Borders
    "border":         "#2d2452",
    "border_focus":   "#a855f7",
    # Gen Z Vibrant Accents
    "accent_primary": "#8b5cf6",   # Electric Violet / Purple
    "accent_purple":  "#a855f7",   # Bright Purple
    "accent_coral":   "#ff6b6b",   # Vibrant Coral
    "accent_lime":    "#a3e635",   # High-voltage Lime Accent
    "accent_lavender":"#c084fc",   # Soft Lavender
    "accent_hover":   "#7c3aed",   # Electric Violet Hover
    # Text
    "text_primary":   "#f8fafc",
    "text_secondary": "#cbd5e1",
    "text_muted":     "#94a3b8",
    # Status
    "success":        "#4ade80",   # Fresh Lime-green
    "warning":        "#fbbf24",   # Amber
    "error":          "#f87171",   # Coral-red
    "info":           "#60a5fa",   # Sky blue
    # Sidebar Active
    "nav_active_bg":  "rgba(139, 92, 246, 0.18)",
    "nav_active_fg":  "#c084fc",
    "nav_active_border": "#a855f7",
}

LIGHT = {
    # Backgrounds: Crisp lavender-tinted light canvas
    "bg_page":        "#f7f6fc",
    "bg_sidebar":     "#ffffff",
    "bg_card":        "#ffffff",
    "bg_card_hover":  "#faf9ff",
    "bg_input":       "#f1effb",
    # Borders
    "border":         "#e4e0f5",
    "border_focus":   "#7c3aed",
    # Accents
    "accent_primary": "#7c3aed",   # Electric Purple
    "accent_purple":  "#6d28d9",   # Deep Purple
    "accent_coral":   "#f97316",   # Bright Coral
    "accent_lime":    "#65a30d",   # Lime Accent
    "accent_lavender":"#8b5cf6",   # Lavender
    "accent_hover":   "#5b21b6",
    # Text
    "text_primary":   "#0f0e17",
    "text_secondary": "#332f4a",
    "text_muted":     "#6e6a86",
    # Status
    "success":        "#15803d",
    "warning":        "#d97706",
    "error":          "#dc2626",
    "info":           "#2563eb",
    # Sidebar Active
    "nav_active_bg":  "rgba(124, 58, 237, 0.10)",
    "nav_active_fg":  "#6d28d9",
    "nav_active_border": "#7c3aed",
}


def _tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


def inject_theme() -> None:
    """
    Inject global CSS into the Streamlit app.
    Reads st.session_state.dark_mode (default True).
    """
    dark = st.session_state.get("dark_mode", True)
    t = _tokens(dark)

    css = f"""
<style>
/* ── Google Fonts: Outfit (expressive Gen Z headings) & Plus Jakarta Sans (ultra-clean body) ── */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* ── Root Design Tokens ───────────────────────────── */
:root {{
    --bg-page:        {t['bg_page']};
    --bg-sidebar:     {t['bg_sidebar']};
    --bg-card:        {t['bg_card']};
    --bg-card-hover:  {t['bg_card_hover']};
    --bg-input:       {t['bg_input']};
    --border:         {t['border']};
    --border-focus:   {t['border_focus']};
    --accent:         {t['accent_primary']};
    --accent-purple:  {t['accent_purple']};
    --accent-coral:   {t['accent_coral']};
    --accent-lime:    {t['accent_lime']};
    --accent-lavender:{t['accent_lavender']};
    --accent-hover:   {t['accent_hover']};
    --text-primary:   {t['text_primary']};
    --text-secondary: {t['text_secondary']};
    --text-muted:     {t['text_muted']};
    --success:        {t['success']};
    --warning:        {t['warning']};
    --error:          {t['error']};
    --info:           {t['info']};
    --nav-active-bg:  {t['nav_active_bg']};
    --nav-active-fg:  {t['nav_active_fg']};
    --nav-active-bdr: {t['nav_active_border']};
    --radius-sm:      8px;
    --radius:         14px;
    --radius-lg:      20px;
    --radius-full:    9999px;
    --shadow-sm:      0 2px 8px rgba(0,0,0,0.08);
    --shadow-md:      0 8px 24px rgba(0,0,0,0.14);
    --shadow-lg:      0 16px 36px rgba(124,58,237,0.12);
    --transition:     180ms cubic-bezier(0.16, 1, 0.3, 1);
}}

/* ── Reset & Global Typography ─────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [data-testid="stAppViewContainer"] {{
    background-color: var(--bg-page) !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
    font-size: 14px;
    -webkit-font-smoothing: antialiased;
}}

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 1.2rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
}}

/* ── Main Canvas ──────────────────────────────────── */
[data-testid="stMain"] {{
    background-color: var(--bg-page) !important;
}}
.main .block-container {{
    padding: 1.8rem 2.2rem !important;
    max-width: 1360px !important;
}}

/* ── Expressive Headings (Outfit) ─────────────────── */
h1, h2, h3, h4, h5, h6 {{
    color: var(--text-primary) !important;
    font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em;
}}
h1 {{ font-size: 1.85rem !important; font-weight: 800 !important; }}
h2 {{ font-size: 1.45rem !important; }}
h3 {{ font-size: 1.15rem !important; }}

p, .stMarkdown p {{
    color: var(--text-secondary) !important;
    line-height: 1.6;
    font-weight: 400;
}}

/* ── Playful Geometric Accents & Glows ────────────── */
.glow-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: var(--radius-full);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background: rgba(139, 92, 246, 0.15);
    color: var(--accent-lavender);
    border: 1px solid rgba(139, 92, 246, 0.3);
}}
.glow-badge::before {{
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-lime);
    box-shadow: 0 0 8px var(--accent-lime);
}}

/* ── Cards: High-polish, rounded, crisp borders ───── */
.sas-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.35rem 1.5rem;
    transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
    box-shadow: var(--shadow-sm);
}}
.sas-card:hover {{
    transform: translateY(-2px);
    border-color: var(--border-focus);
    box-shadow: var(--shadow-md);
}}

/* ── Metric Cards ─────────────────────────────────── */
.sas-metric {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
    transition: transform var(--transition), box-shadow var(--transition);
}}
.sas-metric:hover {{
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}}
.sas-metric::before {{
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: var(--accent);
    border-radius: var(--radius) 0 0 var(--radius);
}}
.sas-metric .label {{
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}}
.sas-metric .value {{
    color: var(--text-primary);
    font-family: 'Outfit', sans-serif;
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.25rem;
}}
.sas-metric .sub {{
    color: var(--text-muted);
    font-size: 0.76rem;
    font-weight: 500;
}}

/* ── Compact Status Pills ─────────────────────────── */
.badge {{
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: var(--radius-full);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.badge-success {{ background: rgba(74, 222, 128, 0.16); color: var(--success); border: 1px solid rgba(74, 222, 128, 0.35); }}
.badge-warning {{ background: rgba(251, 191, 36, 0.16); color: var(--warning); border: 1px solid rgba(251, 191, 36, 0.35); }}
.badge-error   {{ background: rgba(248, 113, 113, 0.16); color: var(--error); border: 1px solid rgba(248, 113, 113, 0.35); }}
.badge-info    {{ background: rgba(96, 165, 250, 0.16); color: var(--info); border: 1px solid rgba(96, 165, 250, 0.35); }}
.badge-muted   {{ background: rgba(148, 163, 184, 0.14); color: var(--text-muted); border: 1px solid rgba(148, 163, 184, 0.25); }}

/* ── Modern Form Controls ─────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] textarea {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 0.85rem !important;
    transition: all var(--transition);
}}
[data-testid="stTextInput"] input:focus {{
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.22) !important;
    outline: none !important;
}}
[data-testid="stTextInput"] label {{
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.02em;
}}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}}
[data-testid="stSelectbox"] label {{
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
}}

/* Form Submit Buttons (High-contrast Gen Z Gradient) */
[data-testid="stFormSubmitButton"] button {{
    background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 50%, #f97316 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.03em !important;
    padding: 0.65rem 1.4rem !important;
    box-shadow: 0 4px 18px rgba(139, 92, 246, 0.38) !important;
    transition: transform var(--transition), box-shadow var(--transition), opacity var(--transition) !important;
    cursor: pointer !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    opacity: 0.94 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 22px rgba(139, 92, 246, 0.52) !important;
}}
[data-testid="stFormSubmitButton"] button:active {{
    transform: translateY(0) !important;
}}

/* Form Container (Clean Card Enclosure) */
[data-testid="stForm"] {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    padding: 1.8rem 2rem !important;
    box-shadow: var(--shadow-lg) !important;
}}

/* Secondary Buttons */
.stButton > button {{
    background-color: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.45rem 1rem !important;
    transition: all var(--transition) !important;
}}
.stButton > button:hover {{
    border-color: var(--accent-purple) !important;
    background-color: var(--bg-card-hover) !important;
    color: var(--accent-lavender) !important;
    transform: translateY(-1px) !important;
}}

/* Tabs styling */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: transparent !important;
    gap: 8px;
    border-bottom: 1px solid var(--border) !important;
    margin-bottom: 1.25rem !important;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
    background: transparent !important;
    color: var(--text-muted) !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1rem !important;
    border: none !important;
    transition: color var(--transition) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
    color: var(--text-primary) !important;
}}
[data-testid="stTabs"] [aria-selected="true"][data-baseweb="tab"] {{
    color: var(--accent-lavender) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: transparent !important;
}}

/* Dataframe */
[data-testid="stDataFrame"] {{
    border-radius: var(--radius) !important;
    overflow: hidden;
    border: 1px solid var(--border) !important;
}}

/* Alerts */
[data-testid="stAlert"] {{
    border-radius: var(--radius-sm) !important;
    border-width: 0 0 0 3px !important;
    font-size: 0.85rem !important;
    padding: 0.75rem 1rem !important;
}}

/* Dividers */
hr {{
    border-color: var(--border) !important;
    margin: 1.2rem 0 !important;
    opacity: 0.6;
}}

/* Hide default streamlit junk */
#MainMenu, footer, header {{ visibility: hidden; }}

/* ── Page Header Component ────────────────────────── */
.page-header {{
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}}
.page-icon {{
    width: 42px;
    height: 42px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-coral) 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
}}
.page-header h1 {{
    margin: 0 !important;
    padding: 0 !important;
    font-size: 1.6rem !important;
}}
.page-header .sub {{
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-top: 1px;
}}

/* ── Section Header ───────────────────────────────── */
.section-header {{
    color: var(--text-muted);
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 0.8rem 0.5rem 0.3rem;
}}

/* ── Empty State ──────────────────────────────────── */
.empty-state {{
    text-align: center;
    padding: 3rem 1.5rem;
    color: var(--text-muted);
    background: var(--bg-card);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
}}
.empty-state .icon {{
    font-size: 2.2rem;
    margin-bottom: 0.6rem;
    display: inline-block;
    padding: 10px;
    background: rgba(139, 92, 246, 0.1);
    border-radius: 50%;
    color: var(--accent-lavender);
}}
.empty-state .title {{
    font-family: 'Outfit', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.35rem;
}}
.empty-state .desc {{
    font-size: 0.82rem;
    max-width: 420px;
    margin: 0 auto;
}}

/* ── Sidebar Brand & User Chip ────────────────────── */
.sidebar-brand {{
    padding: 0.4rem 0.4rem 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.4rem;
}}
.brand-mark {{
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-coral) 100%);
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: 'Outfit', sans-serif;
    font-weight: 900;
    font-size: 0.95rem;
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
}}
.brand-name {{
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: -0.01em;
    line-height: 1.15;
}}
.brand-sub {{
    font-size: 0.66rem;
    color: var(--text-muted);
    font-weight: 500;
}}

.user-chip {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.45rem 0.75rem;
}}
.user-avatar {{
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, var(--accent-purple) 0%, var(--accent-coral) 100%);
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: 'Outfit', sans-serif;
    font-size: 0.75rem;
    font-weight: 800;
}}

/* ── Two-Column Login Campus-Tech Styling ─────────── */
.login-welcome-hero {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    padding: 1.5rem 1.5rem 1.5rem 0.5rem;
}}
.login-welcome-title {{
    font-family: 'Outfit', sans-serif;
    font-size: 2.75rem;
    font-weight: 900;
    line-height: 1.08;
    letter-spacing: -0.035em;
    margin-bottom: 0.85rem;
    background: linear-gradient(135deg, var(--text-primary) 30%, var(--accent-lavender) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.login-welcome-desc {{
    font-size: 0.96rem;
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 1.5rem;
    max-width: 440px;
}}
.pill-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
}}
.feature-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-full);
    padding: 5px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
}}
.feature-pill span {{
    font-size: 0.85rem;
}}
.login-card-container {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2rem 2.2rem;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}}
.login-card-header {{
    margin-bottom: 1.4rem;
}}
.login-card-header .title {{
    font-family: 'Outfit', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 0.2rem;
}}
.login-card-header .subtitle {{
    font-size: 0.82rem;
    color: var(--text-muted);
}}
.login-footer-meta {{
    margin-top: 1.4rem;
    font-size: 0.72rem;
    color: var(--text-muted);
    text-align: center;
    line-height: 1.5;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def theme_toggle(sidebar: bool = True) -> None:
    """Render a compact Light/Dark toggle. Persists in session_state.dark_mode."""
    dark = st.session_state.get("dark_mode", True)
    label = "☀  Switch to Light" if dark else "🌙  Switch to Dark"
    if sidebar:
        if st.sidebar.button(label, key="theme_toggle_btn", use_container_width=True):
            st.session_state["dark_mode"] = not dark
            st.rerun()
    else:
        if st.button(label, key="theme_toggle_btn"):
            st.session_state["dark_mode"] = not dark
            st.rerun()

"""
Smoke import test - verifies all new frontend modules import cleanly.
Run with: python -m pytest frontend/tests/test_smoke_imports.py -v
"""


def test_theme_module_imports():
    from frontend.styles.theme import inject_theme, theme_toggle, DARK, LIGHT
    assert len(DARK) >= 10
    assert len(LIGHT) >= 10
    assert "bg_page" in DARK
    assert "accent_primary" in DARK


def test_auth_module_imports():
    from frontend.components.auth import require_auth, render_login
    assert callable(require_auth)
    assert callable(render_login)


def test_layout_module_imports():
    from frontend.components.layout import (
        render_layout, page_header, metric_card,
        status_badge, empty_state, NAV_SECTIONS, SELECTABLE_KEYS,
    )
    assert callable(page_header)
    assert callable(metric_card)
    assert callable(status_badge)
    assert callable(empty_state)
    assert len(NAV_SECTIONS) == 3
    assert len(SELECTABLE_KEYS) == 13


def test_status_badge_variants():
    from frontend.components.layout import status_badge
    for s in ["ACTIVE", "INACTIVE", "ONLINE", "OFFLINE", "PENDING"]:
        html = status_badge(s)
        assert "badge" in html
        assert s.lower() in html.lower() or "class" in html


def test_dashboard_view_imports():
    from frontend.views.dashboard import render_dashboard
    assert callable(render_dashboard)


def test_students_view_imports():
    from frontend.views.students import render_students
    assert callable(render_students)


def test_attendance_records_view_imports():
    from frontend.views.attendance_records import render_attendance_records
    assert callable(render_attendance_records)


def test_reports_view_imports():
    from frontend.views.reports import render_reports
    assert callable(render_reports)

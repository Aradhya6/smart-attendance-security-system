import logging
from typing import List, Dict, Any, Optional
from ..db.session import (
    get_alerts,
    acknowledge_alert,
    resolve_alert,
    get_blacklist,
    add_blacklist_entry,
    deactivate_blacklist_entry,
    get_recent_detection_events,
    get_security_summary,
    get_db
)

logger = logging.getLogger("security_service")

class SecurityService:
    @staticmethod
    def get_all_alerts(status: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        return get_alerts(status=status, severity=severity)

    @staticmethod
    def acknowledge(alert_id: str) -> Optional[Dict[str, Any]]:
        return acknowledge_alert(alert_id)

    @staticmethod
    def resolve(alert_id: str, note: str) -> Optional[Dict[str, Any]]:
        return resolve_alert(alert_id, note)

    @staticmethod
    def get_blacklist_entries(status: Optional[str] = None) -> List[Dict[str, Any]]:
        return get_blacklist(status=status)

    @staticmethod
    def add_to_blacklist(full_name: str, reason: str, severity: str = "CRITICAL", notes: Optional[str] = None) -> Dict[str, Any]:
        return add_blacklist_entry(full_name=full_name, reason=reason, severity=severity, notes=notes)

    @staticmethod
    def deactivate_blacklist(entry_id: str) -> bool:
        return deactivate_blacklist_entry(entry_id)

    @staticmethod
    def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
        return get_recent_detection_events(limit)

    @staticmethod
    def get_person_tracking_history(person_query: str) -> List[Dict[str, Any]]:
        """
        Retrieves sighting history for a person across cameras with first seen and last seen.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT camera_id, camera_location, event_type, person_name, 
                   min(occurred_at) as first_seen, max(occurred_at) as last_seen, count(*) as sighting_count
            FROM detection_events
            WHERE person_name LIKE ?
            GROUP BY camera_id, event_type, person_name
            ORDER BY last_seen DESC
            """, (f"%{person_query}%",))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_summary() -> Dict[str, Any]:
        return get_security_summary()

    # --- Attendance Module Hook ---
    @staticmethod
    def on_student_observed(person_id: str, person_name: str, camera_id: str, timestamp: str):
        """
        ATTENDANCE HOOK: Teammates can connect their attendance marking here.
        Does not affect any security operations.
        """
        logger.debug(f"[Attendance Hook] Observed student {person_name} ({person_id}) at {camera_id}")

security_service = SecurityService()

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from ...services.security_service import security_service

router = APIRouter(prefix="/alerts", tags=["Security Alerts"])

class AlertResolvePayload(BaseModel):
    resolution_note: str

@router.get("")
def get_alerts(status: Optional[str] = None, severity: Optional[str] = None):
    return security_service.get_all_alerts(status=status, severity=severity)

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    try:
        updated = security_service.acknowledge(alert_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Alert not found")
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: str, payload: AlertResolvePayload):
    try:
        updated = security_service.resolve(alert_id, payload.resolution_note)
        if not updated:
            raise HTTPException(status_code=404, detail="Alert not found")
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

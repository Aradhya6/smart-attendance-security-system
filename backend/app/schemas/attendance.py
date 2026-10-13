"""Attendance Pydantic schemas."""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class AttendanceRecordSchema(BaseModel):
    id: str
    student_uuid: str
    student_id: str
    full_name: str
    attendance_date: date
    session_label: str
    marked_at: datetime
    status: str
    similarity: float
    method: str
    camera_id: str


class ManualAttendanceRequest(BaseModel):
    student_id: str
    reason: str
    attendance_date: Optional[date] = None
    session_label: Optional[str] = None

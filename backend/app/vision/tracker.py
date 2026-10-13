"""
Simple IoU-based face tracker (Phase 14).

Tracks faces across frames by bounding-box IoU association.
A track becomes 'confirmed' after CONFIRM_FRAMES consecutive frames
with the same identity decision.  Confirmed tracks trigger attendance.

No biometric data is stored in tracks.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.app.vision.recognizer import FaceResult

# IoU threshold for associating a detection to an existing track
IOU_MIN = 0.3
# Seconds before a track with no updates is dropped
TRACK_TIMEOUT_SECONDS = 1.5


@dataclass
class Track:
    """Internal state for a single tracked face."""

    track_id: str
    bbox: List[int]
    last_seen: float = field(default_factory=time.monotonic)
    last_kind: Optional[str] = None
    last_student_uuid = None
    consecutive_count: int = 0
    confirmed: bool = False

    def update(self, result: FaceResult, confirm_frames: int) -> None:
        """Update track with a new recognition result."""
        self.bbox = result.bbox
        self.last_seen = time.monotonic()

        same_identity = (
            result.kind == self.last_kind
            and (
                (result.kind == "UNKNOWN") or
                (result._student_uuid is not None and result._student_uuid == self.last_student_uuid)
            )
        )

        if same_identity:
            self.consecutive_count += 1
        else:
            self.consecutive_count = 1
            self.confirmed = False

        self.last_kind = result.kind
        self.last_student_uuid = result._student_uuid

        if self.consecutive_count >= confirm_frames:
            self.confirmed = True


def _iou(a: List[int], b: List[int]) -> float:
    """Compute IoU of two bboxes [x1,y1,x2,y2]."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter)


class SimpleTracker:
    """
    Lightweight single-frame IoU tracker.

    Matches detections to existing tracks by IoU, creates new tracks for
    unmatched detections, drops stale tracks.
    """

    def __init__(self, confirm_frames: int = 3) -> None:
        self.confirm_frames = confirm_frames
        self._tracks: Dict[str, Track] = {}
        self._next_id: int = 0

    def update(self, results: List[FaceResult]) -> List[tuple]:
        """
        Update tracker with new recognition results.

        Parameters
        ----------
        results : list[FaceResult]
            Detections from the current frame.

        Returns
        -------
        list[(track_id, FaceResult, confirmed)]
            One entry per detection.
        """
        now = time.monotonic()
        # Drop stale tracks
        stale = [tid for tid, t in self._tracks.items() if now - t.last_seen > TRACK_TIMEOUT_SECONDS]
        for tid in stale:
            del self._tracks[tid]

        output = []
        matched_track_ids = set()

        for result in results:
            # Find best matching track
            best_tid = None
            best_iou = IOU_MIN

            for tid, track in self._tracks.items():
                if tid in matched_track_ids:
                    continue
                iou = _iou(result.bbox, track.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

            if best_tid is not None:
                matched_track_ids.add(best_tid)
                self._tracks[best_tid].update(result, self.confirm_frames)
                output.append((best_tid, result, self._tracks[best_tid].confirmed))
            else:
                # New track
                tid = f"T{self._next_id:04d}"
                self._next_id += 1
                track = Track(track_id=tid, bbox=result.bbox)
                track.update(result, self.confirm_frames)
                self._tracks[tid] = track
                output.append((tid, result, track.confirmed))

        return output

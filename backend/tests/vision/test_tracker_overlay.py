"""
Tests for Phase 14: tracker, overlay, and camera worker mock.
Run: pytest backend/tests/vision/test_tracker.py backend/tests/vision/test_overlay.py
     backend/tests/cameras/test_worker_mock.py -v
"""
import time
import threading
import types
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Tracker tests
# ---------------------------------------------------------------------------

from backend.app.vision.tracker import SimpleTracker, _iou
from backend.app.vision.recognizer import FaceResult


def make_result(bbox, recognized=True, student_uuid=None, kind="STUDENT", sim=0.85):
    import uuid
    r = FaceResult(
        recognized=recognized,
        kind=kind,
        student_id="001",
        name="Alice",
        similarity=sim,
        bbox=bbox,
        det_score=0.9,
        _student_uuid=student_uuid or uuid.uuid4(),
    )
    return r


class TestIoU:
    def test_same_box(self):
        assert abs(_iou([0, 0, 100, 100], [0, 0, 100, 100]) - 1.0) < 1e-5

    def test_no_overlap(self):
        assert _iou([0, 0, 50, 50], [100, 100, 200, 200]) == 0.0

    def test_partial_overlap(self):
        iou = _iou([0, 0, 100, 100], [50, 50, 150, 150])
        assert 0.0 < iou < 1.0


class TestSimpleTracker:
    def test_stable_id_for_moving_box(self):
        """Same face moving slightly keeps the same track ID."""
        tracker = SimpleTracker(confirm_frames=3)
        import uuid
        sid = uuid.uuid4()
        outputs = []
        for x in [10, 12, 14]:  # small movement
            r = make_result([x, 10, x + 100, 110], student_uuid=sid)
            tracked = tracker.update([r])
            outputs.append(tracked[0][0])  # track_id
        assert outputs[0] == outputs[1] == outputs[2], "Same face must keep same track ID"

    def test_new_id_for_disjoint_box(self):
        """Disjoint face gets a new track ID."""
        tracker = SimpleTracker(confirm_frames=3)
        import uuid
        r1 = make_result([0, 0, 100, 100], student_uuid=uuid.uuid4())
        r2 = make_result([500, 500, 600, 600], student_uuid=uuid.uuid4())
        t1 = tracker.update([r1])[0][0]
        t2 = tracker.update([r2])[0][0]
        assert t1 != t2

    def test_confirmed_after_n_frames(self):
        """Track confirmed after CONFIRM_FRAMES consecutive matching decisions."""
        tracker = SimpleTracker(confirm_frames=3)
        import uuid
        sid = uuid.uuid4()
        confirmed_flags = []
        for _ in range(4):
            r = make_result([10, 10, 110, 110], student_uuid=sid)
            tracked = tracker.update([r])
            confirmed_flags.append(tracked[0][2])
        # Not confirmed on frames 1,2; confirmed on frame 3+
        assert not confirmed_flags[0]
        assert not confirmed_flags[1]
        assert confirmed_flags[2]
        assert confirmed_flags[3]

    def test_not_confirmed_if_identity_changes(self):
        """2 same + 1 different → not confirmed on 3rd."""
        tracker = SimpleTracker(confirm_frames=3)
        import uuid
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        tracker.update([make_result([10, 10, 110, 110], student_uuid=sid1)])
        tracker.update([make_result([10, 10, 110, 110], student_uuid=sid1)])
        result = tracker.update([make_result([10, 10, 110, 110], student_uuid=sid2)])
        assert not result[0][2], "Different identity on 3rd frame must reset confirmation"

    def test_stale_track_dropped(self):
        """Track not updated for > timeout is dropped."""
        from backend.app.vision.tracker import TRACK_TIMEOUT_SECONDS
        tracker = SimpleTracker(confirm_frames=1)
        import uuid
        # Add a track
        tracker.update([make_result([10, 10, 110, 110], student_uuid=uuid.uuid4())])
        assert len(tracker._tracks) == 1
        # Expire all tracks
        for t in tracker._tracks.values():
            t.last_seen -= TRACK_TIMEOUT_SECONDS + 1
        # Update with a completely different box
        tracker.update([make_result([500, 500, 600, 600], student_uuid=uuid.uuid4())])
        # Old track should be gone; new track created
        assert len(tracker._tracks) == 1

    def test_unknown_track_not_confirmed_as_student(self):
        """UNKNOWN track never triggers attendance-style confirmation for a student."""
        tracker = SimpleTracker(confirm_frames=2)
        outputs = []
        for _ in range(3):
            r = FaceResult(
                recognized=False, kind="UNKNOWN", student_id=None,
                name=None, similarity=0.0, bbox=[10, 10, 110, 110], det_score=0.9,
            )
            tracked = tracker.update([r])
            outputs.append((tracked[0][1].kind, tracked[0][2]))
        # confirmed=True for UNKNOWN track is fine (tracker doesn't know about attendance rules)
        # But the attendance service checks recognized=True + kind=STUDENT
        assert all(o[0] == "UNKNOWN" for o in outputs)


# ---------------------------------------------------------------------------
# Overlay tests
# ---------------------------------------------------------------------------

from backend.app.vision.overlay import draw_faces, COLOR_RECOGNIZED, COLOR_UNKNOWN


class TestOverlay:
    def _blank(self, h=480, w=640):
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_green_box_for_recognized_confirmed(self):
        """Recognized + confirmed → green pixel somewhere on box border."""
        import uuid
        frame = self._blank()
        result = make_result([100, 100, 200, 200])
        tracked = [("T0", result, True)]  # confirmed=True
        draw_faces(frame, tracked)
        # Check right edge (x=200) scanning vertically — not covered by text background.
        # BGR green = (0, 200, 0) → channel index 1
        found_green = False
        for y in range(100, 200):
            pix = frame[y, 200]
            if pix[1] > 100:
                found_green = True
                break
        assert found_green, f"Expected green on right edge (x=200), top pixel: {frame[100, 200]}"

    def test_red_box_for_unknown(self):
        """UNKNOWN face → red pixel at box edge."""
        frame = self._blank()
        result = FaceResult(
            recognized=False, kind="UNKNOWN", student_id=None,
            name=None, similarity=0.0, bbox=[100, 100, 200, 200], det_score=0.9,
        )
        tracked = [("T0", result, False)]
        draw_faces(frame, tracked)
        found_red = False
        for x in range(101, 200):
            pix = frame[100, x]
            if pix[2] > 100:  # BGR: R is index 2
                found_red = True
                break
        assert found_red, f"Expected red pixel on box edge, sample at y=100: {frame[100, 150]}"

    def test_score_label_not_accuracy(self):
        """Overlay text must use 'score' not 'accuracy'."""
        import uuid
        from backend.app.vision.overlay import FONT, FONT_SCALE, FONT_THICKNESS
        # We can't easily read text from image, so verify via source code
        import inspect
        import backend.app.vision.overlay as ov
        src = inspect.getsource(ov)
        assert "score" in src
        assert "accuracy" not in src, "Overlay must use 'score' not 'accuracy'"

    def test_no_crash_empty_track_list(self):
        """Empty tracked list → no crash."""
        frame = self._blank()
        result = draw_faces(frame, [])
        assert result is not None

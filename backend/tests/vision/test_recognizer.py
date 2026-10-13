"""Phase 13: Pure recognizer decision-function tests."""
import uuid
import pytest
from backend.app.vision.recognizer import (
    IdentityCandidate, FaceResult, aggregate_candidates, decide
)


def make_cand(sim, student_uuid=None, blid=None):
    return IdentityCandidate(
        student_id=student_uuid or uuid.uuid4(),
        blacklist_entry_id=blid,
        similarity=sim,
    )


class TestDecide:
    def test_above_threshold_recognized(self):
        sid = uuid.uuid4()
        cands = [make_cand(0.75, student_uuid=sid)]
        ok, kind, best = decide(cands, threshold=0.50)
        assert ok and kind == "STUDENT"

    def test_below_threshold_unknown(self):
        cands = [make_cand(0.30)]
        ok, kind, best = decide(cands, threshold=0.50)
        assert not ok and kind == "UNKNOWN"

    def test_empty_candidates_unknown(self):
        ok, kind, best = decide([], threshold=0.50)
        assert not ok and kind == "UNKNOWN" and best is None

    def test_ambiguous_gap_unknown(self):
        s1 = uuid.uuid4()
        s2 = uuid.uuid4()
        cands = [make_cand(0.80, student_uuid=s1), make_cand(0.77, student_uuid=s2)]
        ok, kind, best = decide(cands, threshold=0.50, margin=0.05)
        assert not ok and kind == "UNKNOWN"

    def test_clear_gap_recognized(self):
        s1 = uuid.uuid4()
        s2 = uuid.uuid4()
        cands = [make_cand(0.90, student_uuid=s1), make_cand(0.70, student_uuid=s2)]
        ok, kind, best = decide(cands, threshold=0.50, margin=0.05)
        assert ok and best.student_id == s1


class TestAggregateCandidates:
    def test_max_per_identity(self):
        sid = uuid.uuid4()
        raw = [(sid, None, 0.6), (sid, None, 0.9), (sid, None, 0.7)]
        cands = aggregate_candidates(raw)
        assert len(cands) == 1
        assert abs(cands[0].similarity - 0.9) < 1e-6

    def test_sorted_descending(self):
        s1, s2 = uuid.uuid4(), uuid.uuid4()
        raw = [(s1, None, 0.7), (s2, None, 0.9)]
        cands = aggregate_candidates(raw)
        assert cands[0].similarity >= cands[1].similarity

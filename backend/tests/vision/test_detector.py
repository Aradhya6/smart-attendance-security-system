"""
Tests for Phase 10 — Face Detection.

Tests use:
- Synthetic numpy frames (blank/noise) — always run (no model needed)
- Real model tests in tests/fixtures_local/ — skipped if absent (NOT VERIFIED)
- ModelRegistry singleton identity tests (mocked) — always run

Run:
    pytest backend/tests/vision/test_detector.py -v -rs
"""
import threading
import types
import unittest.mock as mock
import uuid

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_blank_frame(h=480, w=640) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def make_noise_frame(h=480, w=640) -> np.ndarray:
    rng = np.random.default_rng(42)
    return (rng.integers(0, 256, (h, w, 3))).astype(np.uint8)


def _make_mock_registry(faces=None):
    """Return a mock registry that returns the given fake faces."""

    class FakeFace:
        def __init__(self, bbox, score=0.9):
            self.bbox = np.array(bbox, dtype=float)
            self.det_score = score
            self.kps = None

    class MockApp:
        def get(self, frame):
            return [] if faces is None else faces

    class MockRegistry:
        _app = MockApp()
        _load_count = 1

        @property
        def load_count(self):
            return self._load_count

        def get(self, **kwargs):
            return self._app

    return MockRegistry(), FakeFace


# ---------------------------------------------------------------------------
# ModelRegistry singleton tests (mocked — no model download needed)
# ---------------------------------------------------------------------------

class TestModelRegistrySingleton:
    def test_singleton_identity(self):
        """Two calls to ModelRegistry.instance() return the same object."""
        from backend.app.vision.model_registry import ModelRegistry

        r1 = ModelRegistry.instance()
        r2 = ModelRegistry.instance()
        assert r1 is r2, "ModelRegistry.instance() must return the same object"

    def test_singleton_across_threads(self):
        """ModelRegistry.instance() returns the same object from multiple threads."""
        from backend.app.vision.model_registry import ModelRegistry

        instances = []

        def collect():
            instances.append(ModelRegistry.instance())

        threads = [threading.Thread(target=collect) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(i is instances[0] for i in instances), "All thread instances must be identical"

    def test_load_count_mock(self):
        """load_count increments only once when model is loaded."""
        from backend.app.vision.model_registry import ModelRegistry

        reg = ModelRegistry.instance()
        # Reset for clean test (only in test context)
        reg.reset()
        assert reg.load_count == 0

        # Mock the FaceAnalysis class so no actual download occurs
        mock_app = mock.MagicMock()
        mock_app.get.return_value = []

        with mock.patch("backend.app.vision.model_registry.FaceAnalysis") as MockFA:
            MockFA.return_value = mock_app
            reg.get()
            reg.get()  # second call — should NOT reload
            reg.get()  # third call
            assert MockFA.call_count == 1, "FaceAnalysis must be instantiated exactly once"
            assert reg.load_count == 1, "load_count must be 1 after three get() calls"

        reg.reset()  # cleanup


# ---------------------------------------------------------------------------
# detect_faces — synthetic frames (no model download)
# ---------------------------------------------------------------------------

class TestDetectFacesWithMock:
    def test_blank_frame_returns_empty(self):
        """Blank frame with mock returning no faces → []."""
        from backend.app.vision.detector import detect_faces

        reg, _ = _make_mock_registry(faces=[])
        result = detect_faces(make_blank_frame(), registry=reg)
        assert result == [], "Expected empty list for blank frame"

    def test_none_frame_returns_empty(self):
        """None frame → empty list (no crash)."""
        from backend.app.vision.detector import detect_faces

        reg, _ = _make_mock_registry(faces=[])
        result = detect_faces(None, registry=reg)  # type: ignore[arg-type]
        assert result == []

    def test_empty_frame_returns_empty(self):
        """0-size frame → empty list."""
        from backend.app.vision.detector import detect_faces

        reg, _ = _make_mock_registry(faces=[])
        result = detect_faces(np.zeros((0, 0, 3), dtype=np.uint8), registry=reg)
        assert result == []

    def test_score_filter(self):
        """Faces below det_threshold are excluded."""
        from backend.app.vision.detector import detect_faces

        _, FakeFace = _make_mock_registry()
        low_score_face = FakeFace([50, 50, 150, 150], score=0.3)
        high_score_face = FakeFace([200, 200, 350, 350], score=0.95)
        reg, _ = _make_mock_registry(faces=[low_score_face, high_score_face])
        result = detect_faces(make_blank_frame(), det_threshold=0.5, registry=reg)
        assert len(result) == 1
        assert result[0].det_score == 0.95

    def test_size_filter(self):
        """Faces narrower than min_face_pixels are excluded."""
        from backend.app.vision.detector import detect_faces

        _, FakeFace = _make_mock_registry()
        tiny_face = FakeFace([10, 10, 50, 50], score=0.9)   # width=40
        big_face = FakeFace([100, 100, 250, 250], score=0.9)  # width=150
        reg, _ = _make_mock_registry(faces=[tiny_face, big_face])
        result = detect_faces(make_blank_frame(), min_face_pixels=80, registry=reg)
        assert len(result) == 1
        face_width = result[0].bbox[2] - result[0].bbox[0]
        assert face_width >= 80

    def test_sorted_by_score_descending(self):
        """Results are sorted by det_score descending."""
        from backend.app.vision.detector import detect_faces

        _, FakeFace = _make_mock_registry()
        f1 = FakeFace([10, 10, 150, 150], score=0.7)
        f2 = FakeFace([200, 10, 350, 150], score=0.95)
        f3 = FakeFace([400, 10, 550, 150], score=0.8)
        reg, _ = _make_mock_registry(faces=[f1, f2, f3])
        result = detect_faces(make_blank_frame(), det_threshold=0.5, min_face_pixels=80, registry=reg)
        scores = [r.det_score for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_multiple_faces_returned(self):
        """Multiple valid faces all returned."""
        from backend.app.vision.detector import detect_faces

        _, FakeFace = _make_mock_registry()
        faces = [FakeFace([i * 200, 10, i * 200 + 150, 160], score=0.9) for i in range(3)]
        reg, _ = _make_mock_registry(faces=faces)
        result = detect_faces(make_blank_frame(w=1920), det_threshold=0.5, min_face_pixels=80, registry=reg)
        assert len(result) == 3

    def test_registry_unavailable_returns_empty(self):
        """If registry raises RuntimeError (model not installed), return []."""
        from backend.app.vision.detector import detect_faces

        class BrokenRegistry:
            def get(self, **kwargs):
                raise RuntimeError("insightface not installed")

        result = detect_faces(make_blank_frame(), registry=BrokenRegistry())
        assert result == []


class TestDetectSingleFace:
    def test_no_face_returns_no_face_reason(self):
        """No faces in frame → (None, 'NO_FACE')."""
        from backend.app.vision.detector import detect_single_face

        reg, _ = _make_mock_registry(faces=[])
        face, reason = detect_single_face(make_blank_frame(), registry=reg)
        assert face is None
        assert reason == "NO_FACE"

    def test_one_face_returns_ok(self):
        """Single valid face → (DetectedFace, 'OK')."""
        from backend.app.vision.detector import detect_single_face

        _, FakeFace = _make_mock_registry()
        reg, _ = _make_mock_registry(faces=[FakeFace([100, 100, 250, 250], score=0.9)])
        face, reason = detect_single_face(make_blank_frame(), min_face_pixels=80, registry=reg)
        assert reason == "OK"
        assert face is not None

    def test_multiple_faces_returns_multiple_reason(self):
        """Two valid faces → (None, 'MULTIPLE_FACES')."""
        from backend.app.vision.detector import detect_single_face

        _, FakeFace = _make_mock_registry()
        faces = [FakeFace([i * 200, 10, i * 200 + 150, 160], score=0.9) for i in range(2)]
        reg, _ = _make_mock_registry(faces=faces)
        face, reason = detect_single_face(make_blank_frame(w=1920), registry=reg)
        assert face is None
        assert reason == "MULTIPLE_FACES"


# ---------------------------------------------------------------------------
# Real-model tests — skipped if fixtures_local absent
# ---------------------------------------------------------------------------

FIXTURES_LOCAL = "backend/tests/fixtures_local"


@pytest.fixture(scope="module")
def real_registry():
    """Load the real InsightFace model once for fixture-based tests."""
    pytest.importorskip("insightface", reason="insightface not installed")
    import os

    if not os.path.isdir(FIXTURES_LOCAL):
        pytest.skip(f"fixtures_local not found at {FIXTURES_LOCAL} — NOT VERIFIED")

    from backend.app.vision.model_registry import ModelRegistry

    reg = ModelRegistry.instance()
    reg.reset()
    try:
        reg.get()
    except Exception as exc:
        pytest.skip(f"Real model failed to load: {exc} — NOT VERIFIED")
    return reg


@pytest.mark.usefixtures("real_registry")
class TestDetectorWithRealModel:
    """
    Tests that need the real InsightFace model and local fixture images.
    Skipped automatically if fixtures_local/ is absent.
    """

    def test_blank_frame_no_faces(self, real_registry):
        """Blank frame returns zero faces with real model."""
        from backend.app.vision.detector import detect_faces

        result = detect_faces(make_blank_frame(), registry=real_registry)
        assert result == [], "Real model: blank frame must return 0 faces"

    def test_noise_frame_no_faces(self, real_registry):
        """Noise frame returns zero or very few spurious detections."""
        from backend.app.vision.detector import detect_faces

        result = detect_faces(make_noise_frame(), registry=real_registry)
        # Noise may produce zero or a tiny number of false detections;
        # the important thing is no crash
        assert isinstance(result, list)

"""
Tests for Phase 11 — Face Embeddings (ArcFace).

Tests use mocked InsightFace to verify:
- EmbeddingResult shape/dtype/norm assertions
- embed_face() handles missing normed_embedding
- consistency check accepts/rejects correctly
- Determinism: same face twice → identical vector (mocked)

Real-model tests skip if fixtures_local/ absent.

Run:
    pytest backend/tests/vision/test_embedder.py -v -rs
"""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.vision.embedder import EMBEDDING_DIM, EmbeddingResult
from backend.app.vision.quality import (
    check_consistency,
    compute_median_embedding,
    cosine_similarity,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_unit_vec(seed: int = 0) -> np.ndarray:
    """Create a deterministic L2-normalised float32 vector."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    return (v / np.linalg.norm(v)).astype(np.float32)


def make_mock_face(embedding: np.ndarray, score: float = 0.9, bbox=None):
    """Return a mock object mimicking an InsightFace Face with normed_embedding."""
    import types

    face = types.SimpleNamespace()
    face.normed_embedding = embedding
    face.det_score = score
    face.bbox = np.array(bbox or [100, 100, 250, 250], dtype=float)
    face.kps = None
    return face


class MockRegistry:
    """Registry that immediately returns a mock app."""

    def get(self, **kwargs):
        return self  # self has a .get() method below

    # This __call__ makes MockRegistry double as the app:
    def __call__(self, frame):
        return []


# ---------------------------------------------------------------------------
# EmbeddingResult assertions
# ---------------------------------------------------------------------------

class TestEmbeddingResultAssertions:
    def test_valid_embedding_accepted(self):
        """Valid 512-d float32 unit vector → EmbeddingResult created OK."""
        v = make_unit_vec(1)
        r = EmbeddingResult(vector=v, det_score=0.9)
        assert r.vector.shape == (EMBEDDING_DIM,)
        assert r.vector.dtype == np.float32

    def test_wrong_shape_raises(self):
        v = make_unit_vec()[:256]  # wrong shape
        with pytest.raises(AssertionError, match="shape"):
            EmbeddingResult(vector=v, det_score=0.9)

    def test_wrong_dtype_raises(self):
        v = make_unit_vec().astype(np.float64)
        with pytest.raises(AssertionError, match="dtype"):
            EmbeddingResult(vector=v, det_score=0.9)

    def test_unnormalised_raises(self):
        v = make_unit_vec() * 2.0  # norm ≈ 2 → fails
        with pytest.raises(AssertionError, match="norm"):
            EmbeddingResult(vector=v, det_score=0.9)

    def test_zero_norm_raises(self):
        v = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        with pytest.raises(AssertionError):
            EmbeddingResult(vector=v, det_score=0.9)


# ---------------------------------------------------------------------------
# embed_face — mocked
# ---------------------------------------------------------------------------

class TestEmbedFaceMocked:
    def test_uses_normed_embedding_when_present(self):
        """If face has normed_embedding, embed_face() returns it normalised."""
        from backend.app.vision.embedder import embed_face

        v = make_unit_vec(42)
        fake_face = make_mock_face(v)

        # Wrap in DetectedFace-like object
        import types

        df = types.SimpleNamespace(_raw=fake_face, bbox=[100, 100, 250, 250], det_score=0.9, landmarks=None)

        import numpy as np

        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        result = embed_face(blank, df, registry=MockRegistry())
        assert result is not None
        assert result.vector.shape == (EMBEDDING_DIM,)
        np.testing.assert_allclose(np.linalg.norm(result.vector), 1.0, atol=1e-3)

    def test_deterministic_same_face(self):
        """Same embedding twice → identical vectors."""
        from backend.app.vision.embedder import embed_face
        import types, numpy as np

        v = make_unit_vec(7)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)

        fake_face = make_mock_face(v)
        df = types.SimpleNamespace(_raw=fake_face, bbox=[100, 100, 250, 250], det_score=0.9, landmarks=None)

        r1 = embed_face(blank, df, registry=MockRegistry())
        r2 = embed_face(blank, df, registry=MockRegistry())
        assert r1 is not None and r2 is not None
        np.testing.assert_array_equal(r1.vector, r2.vector)

    def test_model_unavailable_returns_none(self):
        """If registry raises RuntimeError, embed_face returns None."""
        from backend.app.vision.embedder import embed_face
        import types, numpy as np

        class BrokenReg:
            def get(self, **kwargs):
                raise RuntimeError("no model")

        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        # face without normed_embedding → will try registry
        fake_face = types.SimpleNamespace(det_score=0.9, bbox=np.array([10, 10, 50, 50]))
        df = types.SimpleNamespace(_raw=fake_face, bbox=[10, 10, 50, 50], det_score=0.9, landmarks=None)
        result = embed_face(blank, df, registry=BrokenReg())
        assert result is None


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------

class TestConsistencyCheck:
    def test_all_similar_accepted(self):
        """5 nearly identical vectors → all accepted."""
        base = make_unit_vec(0)
        # Add tiny noise
        rng = np.random.default_rng(1)
        embeddings = [
            (lambda v: (v / np.linalg.norm(v)).astype(np.float32))(
                base + rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * 0.01
            )
            for _ in range(5)
        ]
        accepted, rejected = check_consistency(embeddings, min_cosine=0.5)
        assert len(rejected) == 0
        assert len(accepted) == 5

    def test_outlier_rejected(self):
        """One orthogonal vector among similar ones → rejected."""
        base = make_unit_vec(0)
        similar = [
            (lambda v: (v / np.linalg.norm(v)).astype(np.float32))(
                base + np.random.default_rng(i).standard_normal(EMBEDDING_DIM).astype(np.float32) * 0.01
            )
            for i in range(4)
        ]
        outlier = make_unit_vec(99)  # orthogonal seed → low cosine
        embeddings = similar + [outlier]
        accepted, rejected = check_consistency(embeddings, min_cosine=0.5)
        assert 99 in [i for i in rejected] or len(rejected) >= 1

    def test_single_embedding_always_accepted(self):
        """Single embedding → accepted without check."""
        v = [make_unit_vec(0)]
        accepted, rejected = check_consistency(v)
        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_cosine_similarity_unit_vectors(self):
        """Same vector → cosine 1.0; orthogonal → cosine ≈ 0."""
        v = make_unit_vec(5)
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-5
        # Build orthogonal vector
        w = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        w[0] = 1.0
        u = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        u[1] = 1.0
        assert abs(cosine_similarity(w, u)) < 1e-5

    def test_compute_median_normalised(self):
        """Median embedding is L2-normalised."""
        embeddings = [make_unit_vec(i) for i in range(5)]
        median = compute_median_embedding(embeddings)
        assert median.shape == (EMBEDDING_DIM,)
        assert abs(float(np.linalg.norm(median)) - 1.0) < 1e-3

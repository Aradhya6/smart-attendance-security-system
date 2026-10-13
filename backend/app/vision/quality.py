"""
Embedding quality / consistency checks (Phase 11).

Used at face registration time to reject samples that are outliers relative
to the group of collected embeddings for the same person.

The consistency check computes the cosine similarity of each sample to the
median embedding and rejects samples below CONSISTENCY_MIN_COSINE (default 0.5).

No embeddings are ever logged.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Minimum cosine similarity a sample must have to the median embedding.
# A sample further away than this is likely from a different person or a
# severely mis-aligned capture.  This is a starting value; tune with evidence.
CONSISTENCY_MIN_COSINE: float = 0.5


def compute_median_embedding(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Compute and L2-normalise the element-wise median of a list of embeddings.

    The median is more robust to outliers than the mean.

    Parameters
    ----------
    embeddings : list[np.ndarray]
        List of shape-(512,) float32 L2-normalised embeddings.

    Returns
    -------
    np.ndarray
        Shape-(512,) float32 L2-normalised median embedding.
    """
    stack = np.stack(embeddings, axis=0)   # (N, 512)
    median = np.median(stack, axis=0).astype(np.float32)
    norm = float(np.linalg.norm(median))
    if norm < 1e-8:
        return median
    return (median / norm).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two L2-normalised vectors (dot product)."""
    return float(np.dot(a.astype(np.float64), b.astype(np.float64)))


def check_consistency(
    embeddings: List[np.ndarray],
    min_cosine: float = CONSISTENCY_MIN_COSINE,
) -> Tuple[List[np.ndarray], List[int]]:
    """
    Filter out embeddings that are inconsistent with the group.

    Parameters
    ----------
    embeddings : list[np.ndarray]
        All embedding vectors for a single person's registration session.
    min_cosine : float
        Minimum cosine similarity to the median embedding required to pass.

    Returns
    -------
    (accepted, rejected_indices)
        accepted  : list of embeddings that passed the consistency check.
        rejected  : list of integer indices of embeddings that failed.
    """
    if len(embeddings) < 2:
        return embeddings, []

    median_emb = compute_median_embedding(embeddings)
    accepted: List[np.ndarray] = []
    rejected: List[int] = []

    for i, emb in enumerate(embeddings):
        sim = cosine_similarity(emb, median_emb)
        if sim >= min_cosine:
            accepted.append(emb)
        else:
            logger.debug(
                "Embedding %d rejected by consistency check (cosine=%.4f < %.4f)",
                i,
                sim,
                min_cosine,
            )
            rejected.append(i)

    logger.info(
        "Consistency check: %d accepted, %d rejected (min_cosine=%.2f)",
        len(accepted),
        len(rejected),
        min_cosine,
    )
    return accepted, rejected

"""
Face Recognizer (Phase 13).

Wraps the pgvector nearest-neighbour search and converts raw search results
into per-identity similarity scores using the best embedding match per identity.

Kept separate from the pipeline so it can be unit-tested without a camera.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class IdentityCandidate:
    """Aggregated similarity result for a single identity."""

    student_id: Optional[uuid.UUID]
    blacklist_entry_id: Optional[uuid.UUID]
    similarity: float  # max cosine similarity across all embeddings for this identity

    @property
    def kind(self) -> str:
        if self.blacklist_entry_id is not None:
            return "BLACKLISTED"
        return "STUDENT"


@dataclass
class FaceResult:
    """
    Decision result for a single detected face.

    recognized : bool   — True when similarity >= threshold and not ambiguous.
    kind        : str   — 'STUDENT' | 'BLACKLISTED' | 'UNKNOWN'
    student_id  : str | None — business student_id (e.g. '001'), not UUID
    name        : str | None
    similarity  : float — cosine similarity of best match (or 0.0 for UNKNOWN)
    bbox        : list[int] — [x1, y1, x2, y2]
    det_score   : float — detector confidence
    _student_uuid : uuid.UUID | None  — internal; not exposed via API
    """

    recognized: bool
    kind: str
    student_id: Optional[str]
    name: Optional[str]
    similarity: float
    bbox: List[int]
    det_score: float
    _student_uuid: Optional[uuid.UUID] = field(default=None, repr=False)


def aggregate_candidates(
    raw_results: List[Tuple[Optional[uuid.UUID], Optional[uuid.UUID], float]]
) -> List[IdentityCandidate]:
    """
    Aggregate per-embedding search results into per-identity max-similarity scores.

    Parameters
    ----------
    raw_results : list of (student_id, blacklist_entry_id, similarity)
        From face_repo.nearest().

    Returns
    -------
    list[IdentityCandidate]
        Sorted by similarity descending.  May be empty.
    """
    scores: dict[tuple, float] = {}
    for sid, blid, sim in raw_results:
        key = (sid, blid)
        scores[key] = max(scores.get(key, -1.0), sim)

    candidates = [
        IdentityCandidate(student_id=k[0], blacklist_entry_id=k[1], similarity=v)
        for k, v in scores.items()
    ]
    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates


def decide(
    candidates: List[IdentityCandidate],
    threshold: float,
    margin: float = 0.05,
) -> Tuple[bool, str, Optional[IdentityCandidate]]:
    """
    Pure decision function: convert candidates + threshold → recognition decision.

    Parameters
    ----------
    candidates : list[IdentityCandidate]
        Sorted by similarity descending.
    threshold : float
        Minimum cosine similarity to accept an identity.
    margin : float
        Minimum gap between top-1 and top-2 *different* identities.
        If gap < margin, decision is UNKNOWN (ambiguous).

    Returns
    -------
    (recognized, kind, best_candidate)
        recognized : bool
        kind       : 'STUDENT' | 'BLACKLISTED' | 'UNKNOWN'
        best       : IdentityCandidate or None
    """
    if not candidates:
        return False, "UNKNOWN", None

    best = candidates[0]
    if best.similarity < threshold:
        return False, "UNKNOWN", None

    # Ambiguity check: is the gap to a different identity too small?
    for c in candidates[1:]:
        if c.student_id != best.student_id or c.blacklist_entry_id != best.blacklist_entry_id:
            gap = best.similarity - c.similarity
            if gap < margin:
                logger.debug(
                    "decide: ambiguous (gap=%.4f < margin=%.4f) → UNKNOWN",
                    gap,
                    margin,
                )
                return False, "UNKNOWN", None
            break  # Only check the first different identity

    return True, best.kind, best

import json
import numpy as np
import cv2
from typing import List, Dict, Any, Optional
from ..core.config import settings
from ..db.session import get_registered_persons, get_blacklist

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

class FaceRecognizer:
    def __init__(self, threshold: float = settings.FACE_MATCH_THRESHOLD):
        self.threshold = threshold

    def extract_embedding(self, face_chip: np.ndarray) -> List[float]:
        """
        Extracts a normalized 512-d visual feature embedding from a cropped face.
        Uses 16 spatial blocks x 32-bin intensity histograms (512 dimensions) with L2 normalization.
        Fast, lightweight, runs natively on CPU with zero heavy dependencies.
        """
        if face_chip is None or face_chip.size == 0:
            return [0.0] * 512

        gray = cv2.cvtColor(face_chip, cv2.COLOR_BGR2GRAY) if len(face_chip.shape) == 3 else face_chip
        resized = cv2.resize(gray, (64, 64))

        blocks = []
        for r in range(4):
            for c in range(4):
                block = resized[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
                hist = cv2.calcHist([block], [0], None, [32], [0, 256]).flatten()
                blocks.append(hist)

        embedding = np.concatenate(blocks)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.tolist()

    def identify(self, face_chip: np.ndarray) -> Dict[str, Any]:
        """
        Matches detected face against:
        1. Blacklist entries (High priority)
        2. Registered persons / Students
        3. Returns UNKNOWN if no match above threshold.
        """
        embedding = np.array(self.extract_embedding(face_chip))

        best_similarity = -1.0
        match_kind = "UNKNOWN"
        match_id = None
        match_name = "Unknown Person"

        # 1. Check Blacklist
        active_blacklist = get_blacklist(status="ACTIVE")
        for blk in active_blacklist:
            emb_json = blk.get("embedding_json")
            if emb_json:
                try:
                    ref_emb = np.array(json.loads(emb_json))
                    sim = cosine_similarity(embedding, ref_emb)
                    if sim > best_similarity:
                        best_similarity = sim
                        if sim >= self.threshold:
                            match_kind = "BLACKLISTED"
                            match_id = blk["id"]
                            match_name = blk["full_name"]
                except Exception:
                    pass

        # 2. Check Registered Known Persons (if not blacklisted)
        if match_kind != "BLACKLISTED":
            active_students = get_registered_persons(status="ACTIVE")
            for std in active_students:
                emb_json = std.get("embedding_json")
                if emb_json:
                    try:
                        ref_emb = np.array(json.loads(emb_json))
                        sim = cosine_similarity(embedding, ref_emb)
                        if sim > best_similarity and sim >= self.threshold:
                            best_similarity = sim
                            match_kind = "STUDENT"
                            match_id = std["person_id"]
                            match_name = std["name"]
                    except Exception:
                        pass

        similarity_score = max(0.0, best_similarity if best_similarity > 0 else 0.25)
        
        return {
            "kind": match_kind,
            "person_id": match_id,
            "person_name": match_name,
            "similarity": round(similarity_score, 3),
            "is_suspicious": (match_kind in ("UNKNOWN", "BLACKLISTED")),
            "embedding": embedding.tolist()
        }

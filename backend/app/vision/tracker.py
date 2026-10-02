import time
import math
from typing import List, Dict, Tuple, Optional, Any

class Track:
    def __init__(self, track_id: str, bbox: Tuple[int, int, int, int], kind: str, person_name: str, similarity: float):
        self.track_id = track_id
        self.bbox = bbox
        self.kind = kind
        self.person_name = person_name
        self.similarity = similarity
        self.first_seen = time.time()
        self.last_seen = self.first_seen
        self.consecutive_frames = 1

    @property
    def centroid(self) -> Tuple[float, float]:
        x, y, w, h = self.bbox
        return (x + w / 2.0, y + h / 2.0)

class SimpleTracker:
    def __init__(self, max_distance: float = 100.0, max_disappeared_seconds: float = 2.0):
        self.next_track_id = 1
        self.tracks: Dict[str, Track] = {}
        self.max_distance = max_distance
        self.max_disappeared_seconds = max_disappeared_seconds

    def update(self, detections: List[Dict[str, Any]]) -> List[Track]:
        now = time.time()

        if not detections:
            self._prune(now)
            return list(self.tracks.values())

        det_centroids = [
            (d["bbox"][0] + d["bbox"][2] / 2.0, d["bbox"][1] + d["bbox"][3] / 2.0)
            for d in detections
        ]

        matched_tracks = set()
        matched_dets = set()

        for t_id, track in self.tracks.items():
            t_cent = track.centroid
            best_dist = float("inf")
            best_idx = -1

            for idx, d_cent in enumerate(det_centroids):
                if idx in matched_dets:
                    continue
                dist = math.hypot(t_cent[0] - d_cent[0], t_cent[1] - d_cent[1])
                if dist < best_dist and dist <= self.max_distance:
                    best_dist = dist
                    best_idx = idx

            if best_idx != -1:
                matched_dets.add(best_idx)
                matched_tracks.add(t_id)
                d = detections[best_idx]
                track.bbox = d["bbox"]
                track.kind = d["kind"]
                track.person_name = d["person_name"]
                track.similarity = d["similarity"]
                track.last_seen = now
                track.consecutive_frames += 1

        for idx, d in enumerate(detections):
            if idx not in matched_dets:
                t_id = f"trk-{self.next_track_id}"
                self.next_track_id += 1
                self.tracks[t_id] = Track(
                    track_id=t_id,
                    bbox=d["bbox"],
                    kind=d["kind"],
                    person_name=d["person_name"],
                    similarity=d["similarity"]
                )

        self._prune(now)
        return list(self.tracks.values())

    def _prune(self, now: float):
        dead = [t_id for t_id, t in self.tracks.items() if (now - t.last_seen) > self.max_disappeared_seconds]
        for t_id in dead:
            del self.tracks[t_id]

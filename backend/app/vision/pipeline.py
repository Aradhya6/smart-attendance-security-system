import cv2
import time
from datetime import datetime
import numpy as np
from typing import Tuple, List, Dict, Any
from .detector import FaceDetector
from .recognizer import FaceRecognizer
from .tracker import SimpleTracker
from ..core.config import settings
from ..db.session import log_detection_event, upsert_security_alert

# Colors (BGR)
COLOR_GREEN = (0, 200, 0)      # Known Student
COLOR_RED = (0, 0, 255)        # Unknown Person
COLOR_CRITICAL = (0, 0, 180)   # Blacklisted Subject

class VisionPipeline:
    def __init__(self):
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.tracker = SimpleTracker()
        self.last_alert_time: Dict[str, float] = {}

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str = settings.DEFAULT_CAMERA_ID,
        camera_location: str = settings.DEFAULT_CAMERA_LOCATION
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Processes a single video/camera frame:
        1. Detects faces
        2. Classifies: Known (Student), Unknown, or Blacklisted
        3. Updates track IDs
        4. Logs detection event to SQLite
        5. Triggers security alerts for Unknown and Blacklisted (with cooldown)
        6. Draws visual bounding boxes & telemetry
        """
        if frame is None or frame.size == 0:
            return frame, []

        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # 1. Detect faces
        bboxes = self.detector.detect_faces(frame)

        # 2. Identify each face
        detections: List[Dict[str, Any]] = []
        for bbox in bboxes:
            chip = self.detector.extract_face_chip(frame, bbox)
            ident = self.recognizer.identify(chip)
            detections.append({
                "bbox": bbox,
                "kind": ident["kind"],
                "person_id": ident.get("person_id"),
                "person_name": ident["person_name"],
                "similarity": ident["similarity"],
                "is_suspicious": ident["is_suspicious"]
            })

        # 3. Simple tracking
        tracks = self.tracker.update(detections)
        events_generated: List[Dict[str, Any]] = []
        now_ts = time.time()

        # 4. Process each track
        for t in tracks:
            x, y, bw, bh = t.bbox
            kind = t.kind
            name = t.person_name

            # Log to DB detection_events
            log_detection_event(
                camera_id=camera_id,
                camera_location=camera_location,
                event_type=kind,
                person_name=name,
                similarity=t.similarity
            )

            # Security Alert Generation
            if kind in ("UNKNOWN", "BLACKLISTED"):
                alert_type = "BLACKLISTED_PERSON" if kind == "BLACKLISTED" else "UNKNOWN_PERSON"
                severity = "CRITICAL" if kind == "BLACKLISTED" else "MEDIUM"
                dedup_key = f"{alert_type}:{camera_id}:{name}"

                # Throttle alert creation (at most once every 10 seconds per person/camera)
                last_time = self.last_alert_time.get(dedup_key, 0.0)
                if (now_ts - last_time) >= 10.0:
                    self.last_alert_time[dedup_key] = now_ts
                    alert = upsert_security_alert(
                        alert_type=alert_type,
                        severity=severity,
                        camera_id=camera_id,
                        camera_location=camera_location,
                        person_name=name,
                        dedup_key=dedup_key,
                        window_seconds=settings.ALERT_DEDUP_WINDOW_SECONDS
                    )
                    events_generated.append(alert)

            # 5. Visual Annotations
            if kind == "STUDENT":
                color = COLOR_GREEN
                label = f"{name} (KNOWN)"
                thickness = 2
            elif kind == "BLACKLISTED":
                color = COLOR_CRITICAL
                label = f"BLACKLISTED: {name}"
                thickness = 3
            else:
                color = COLOR_RED
                label = "UNKNOWN PERSON"
                thickness = 2

            # Draw box & label
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), color, thickness)
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (x, max(0, y - label_size[1] - 8)), (x + label_size[0] + 6, y), color, -1)
            cv2.putText(annotated, label, (x + 3, max(12, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # 6. Top Telemetry Header
        header = f"CAM: {camera_id} | {camera_location} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        cv2.rectangle(annotated, (0, 0), (w, 28), (20, 20, 20), -1)
        cv2.putText(annotated, header, (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

        return annotated, events_generated

vision_pipeline = VisionPipeline()

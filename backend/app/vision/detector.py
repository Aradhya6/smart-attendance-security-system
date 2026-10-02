import cv2
import numpy as np
from typing import List, Tuple

class FaceDetector:
    def __init__(self, min_size: Tuple[int, int] = (50, 50)):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(cascade_path)
        self.min_size = min_size

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects faces in a BGR frame.
        Returns a list of bounding boxes as (x, y, w, h).
        """
        if frame is None or frame.size == 0:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=self.min_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        return [tuple(f) for f in faces]

    def extract_face_chip(self, frame: np.ndarray, bbox: Tuple[int, int, int, int], target_size: Tuple[int, int] = (112, 112)) -> np.ndarray:
        """Crops and resizes face region for recognition."""
        x, y, w, h = bbox
        h_frame, w_frame = frame.shape[:2]
        
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w_frame, x + w)
        y2 = min(h_frame, y + h)

        chip = frame[y1:y2, x1:x2]
        if chip.size == 0:
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

        return cv2.resize(chip, target_size)

"""
Frame overlay: draw bounding boxes with name/ID/score (Phase 14).

Colour coding:
  green (0, 200, 0) = recognized student
  red   (0, 0, 220) = UNKNOWN or unconfirmed (OpenCV uses BGR)
  orange (0, 140, 255) = BLACKLISTED

Text format (playbook):
  <Name>
  ID: <student_id>   score: <0.87>

IMPORTANT: Display shows similarity 'score', not a percentage.
"""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

# BGR colours
COLOR_RECOGNIZED = (0, 200, 0)      # green
COLOR_UNKNOWN = (0, 0, 220)         # red
COLOR_BLACKLISTED = (0, 140, 255)   # orange

BOX_THICKNESS = 2
FONT = cv2.FONT_HERSHEY_DUPLEX
FONT_SCALE = 0.55
FONT_THICKNESS = 1


def draw_faces(
    frame: np.ndarray,
    tracked: List[Tuple],  # list of (track_id, FaceResult, confirmed)
    confirmed_only_green: bool = True,
) -> np.ndarray:
    """
    Draw bounding boxes and labels on *frame* (in-place).

    Parameters
    ----------
    frame : np.ndarray
        BGR image.  Modified in place.
    tracked : list
        From SimpleTracker.update(): list of (track_id, FaceResult, confirmed).
    confirmed_only_green : bool
        If True, only confirmed STUDENT results get a green box.

    Returns
    -------
    np.ndarray
        The same frame with annotations added.
    """
    for track_id, result, confirmed in tracked:
        x1, y1, x2, y2 = [int(v) for v in result.bbox]

        # --- Choose colour ---
        if result.kind == "BLACKLISTED":
            colour = COLOR_BLACKLISTED
        elif result.recognized and (not confirmed_only_green or confirmed):
            colour = COLOR_RECOGNIZED
        else:
            colour = COLOR_UNKNOWN

        # --- Bounding box ---
        cv2.rectangle(frame, (x1, y1), (x2, y2), colour, BOX_THICKNESS)

        # --- Build label lines ---
        if result.recognized and result.name:
            lines = [
                result.name,
                f"ID: {result.student_id}  score: {result.similarity:.2f}",
            ]
        elif result.kind == "BLACKLISTED":
            lines = ["BLACKLISTED", f"score: {result.similarity:.2f}"]
        else:
            lines = ["UNKNOWN"]

        # --- Draw text with background ---
        _draw_text_lines(frame, lines, (x1, y1), colour)

    return frame


def _draw_text_lines(
    frame: np.ndarray,
    lines: List[str],
    top_left: Tuple[int, int],
    colour: Tuple[int, int, int],
) -> None:
    """Draw lines of text above the bounding box with a dark background."""
    x, y = top_left
    line_height = 20
    padding = 2

    for i, line in enumerate(reversed(lines)):
        text_y = y - padding - i * line_height
        if text_y < line_height:
            # Below the box instead
            text_y = y + (len(lines) - i) * line_height + BOX_THICKNESS

        (tw, th), _ = cv2.getTextSize(line, FONT, FONT_SCALE, FONT_THICKNESS)
        bg_x1 = max(0, x)
        bg_y1 = max(0, text_y - th - padding)
        bg_x2 = min(frame.shape[1], x + tw + padding * 2)
        bg_y2 = min(frame.shape[0], text_y + padding)

        # Dark background rectangle
        cv2.rectangle(frame, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
        cv2.putText(
            frame,
            line,
            (x + padding, text_y),
            FONT,
            FONT_SCALE,
            colour,
            FONT_THICKNESS,
            lineType=cv2.LINE_AA,
        )

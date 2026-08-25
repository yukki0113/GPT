from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


COLOR_NAMES = ("red", "orange", "yellow", "green", "blue")


def classify_eval_cell(cell: np.ndarray) -> Optional[str]:
    """Classify the fill color of an Eval cell.

    White/gray cells return None. The classifier intentionally uses the
    saturated background pixels rather than OCR/text pixels, so it remains
    useful even when a digit itself is misread.
    """
    if cell.size == 0:
        return None

    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    # Colored rank cells have a saturated fill over most of the cell. Text,
    # antialiasing and JPEG edges are intentionally excluded by this mask.
    mask = (s >= 55) & (v >= 70)
    colored_fraction = float(mask.mean())
    if colored_fraction < 0.18:
        return None

    hues = h[mask].astype(np.float32)
    if hues.size == 0:
        return None
    hue = float(np.median(hues))

    # OpenCV hue range is 0..179.
    if hue < 8 or hue >= 170:
        return "red"
    if hue < 20:
        return "orange"
    if hue < 38:
        return "yellow"
    if hue < 90:
        return "green"
    if hue < 140:
        return "blue"
    return None

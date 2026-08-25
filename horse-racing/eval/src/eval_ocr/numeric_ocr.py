from __future__ import annotations

from collections import Counter
import re
from typing import Optional

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


def preprocess_numeric_cell(cell: np.ndarray, scale: int = 10) -> np.ndarray:
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if float(binary.mean()) < 127.0:
        binary = 255 - binary
    return cv2.copyMakeBorder(binary, 12, 12, 20, 20, cv2.BORDER_CONSTANT, value=255)


def _stack_cells(cells: list[np.ndarray]) -> tuple[np.ndarray, list[tuple[int, int]]]:
    prepared = [preprocess_numeric_cell(c) for c in cells]
    if not prepared:
        return np.full((1, 1), 255, dtype=np.uint8), []
    gap = 28
    width = max(p.shape[1] for p in prepared)
    height = sum(p.shape[0] for p in prepared) + gap * (len(prepared) - 1)
    canvas = np.full((height, width), 255, dtype=np.uint8)
    ranges: list[tuple[int, int]] = []
    y = 0
    for p in prepared:
        x = (width - p.shape[1]) // 2
        canvas[y:y + p.shape[0], x:x + p.shape[1]] = p
        ranges.append((y, y + p.shape[0]))
        y += p.shape[0] + gap
    return canvas, ranges


def _digit_components(binary: np.ndarray) -> list[tuple[int, int, int, int]]:
    foreground = (binary < 128).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
    blobs: list[tuple[int, int, int, int]] = []
    h_img, w_img = binary.shape
    min_area = max(30, int(h_img * w_img * 0.002))
    for idx in range(1, count):
        x, y, w, h, area = stats[idx]
        if area < min_area or h < h_img * 0.18:
            continue
        blobs.append((int(x), int(y), int(w), int(h)))
    blobs.sort(key=lambda b: b[0])
    return blobs


def _parse_value(text: str) -> Optional[int]:
    token = re.sub(r"\D", "", text or "")
    if not token:
        return None
    try:
        value = int(token)
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None


def _ocr_by_digit_components(binary: np.ndarray) -> Optional[int]:
    blobs = _digit_components(binary)
    if not (1 <= len(blobs) <= 3):
        return None
    chars: list[str] = []
    for x, y, w, h in blobs:
        pad = 10
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(binary.shape[1], x + w + pad), min(binary.shape[0], y + h + pad)
        char_img = binary[y1:y2, x1:x2]
        token = ""
        for extra_scale in (1.0, 2.0):
            test_img = char_img if extra_scale == 1.0 else cv2.resize(
                char_img, None, fx=extra_scale, fy=extra_scale, interpolation=cv2.INTER_CUBIC
            )
            for psm in (10, 8, 13):
                candidate = pytesseract.image_to_string(
                    test_img,
                    config=f"--psm {psm} -l eng -c tessedit_char_whitelist=0123456789",
                ).strip()
                candidate = re.sub(r"\D", "", candidate)
                if len(candidate) == 1:
                    token = candidate
                    break
            if token:
                break
        if len(token) != 1:
            return None
        chars.append(token)
    try:
        value = int("".join(chars))
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None


def _ocr_single_cell_candidates(binary: np.ndarray) -> list[int]:
    candidates: list[int] = []
    for psm in (7, 8, 10, 13):
        text = pytesseract.image_to_string(
            binary,
            config=f"--psm {psm} -l eng -c tessedit_char_whitelist=0123456789",
        )
        value = _parse_value(text)
        if value is not None:
            candidates.append(value)
    return candidates


def _cell_has_colored_fill(cell: np.ndarray) -> bool:
    """Return True when the Eval cell contains a substantial colored fill.

    master_eval highlights ranked cells with red/blue/yellow backgrounds.  A
    recurrent failure mode is stacked OCR dropping the leading digit from such
    white-on-color values (75->7, 52->2, 50->0, 62->2, 55->5).  Detecting the
    source color lets us selectively re-read those suspicious one-digit tokens
    without re-OCRing every ordinary white cell.
    """
    if cell.size == 0:
        return False
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    # Ignore very dark grid/text pixels. Colored fills occupy a broad portion
    # of the cell and retain materially higher saturation than white/gray cells.
    colored = (saturation >= 55) & (value >= 70)
    return float(colored.mean()) >= 0.18


def _needs_ambiguity_check(value: Optional[int], colored_fill: bool = False) -> bool:
    if value is None or not (0 <= value <= 100):
        return True
    token = str(value)
    if len(token) >= 2 and (token.startswith("1") or token.startswith("7")):
        return True
    # Generalize the production repair: colored cells returning only one digit
    # are suspicious regardless of which leading digit may have disappeared.
    return colored_fill and len(token) == 1


def _choose_value(batch_value: Optional[int], binary: np.ndarray, *, colored_fill: bool = False) -> Optional[int]:
    blobs = _digit_components(binary)
    token_len = len(str(batch_value)) if batch_value is not None else 0

    # Digit-count repair catches cleanly separated dropped digits (e.g. 37->3).
    if batch_value is None or not (0 <= batch_value <= 100) or (
        1 <= len(blobs) <= 3 and len(blobs) > token_len
    ):
        repaired = _ocr_by_digit_components(binary)
        if repaired is not None:
            batch_value = repaired

    if not _needs_ambiguity_check(batch_value, colored_fill=colored_fill):
        return batch_value

    candidates: list[int] = []
    if batch_value is not None and 0 <= batch_value <= 100:
        candidates.append(batch_value)

    component_value = _ocr_by_digit_components(binary)
    if component_value is not None:
        candidates.append(component_value)

    candidates.extend(_ocr_single_cell_candidates(binary))
    if not candidates:
        return batch_value

    # On a colored cell that initially collapsed to one digit, prefer a
    # repeatedly observed multi-digit candidate.  This specifically addresses
    # leading-digit loss while retaining the one-digit value when the re-read
    # evidence is weak or contradictory.
    if colored_fill and batch_value is not None and batch_value < 10:
        multi = [v for v in candidates if v >= 10]
        if multi:
            multi_counts = Counter(multi)
            best_multi, best_multi_count = multi_counts.most_common(1)[0]
            if best_multi_count >= 2:
                return best_multi

    counts = Counter(candidates)
    best_value, best_count = counts.most_common(1)[0]

    if batch_value is not None and 0 <= batch_value <= 100:
        batch_count = counts[batch_value]
        if best_value != batch_value and best_count >= 2 and best_count > batch_count:
            return best_value
        return batch_value

    return best_value


def ocr_numeric_cells(cells: list[np.ndarray]) -> list[Optional[int]]:
    if not cells:
        return []
    canvas, ranges = _stack_cells(cells)
    data = pytesseract.image_to_data(
        canvas,
        config="--psm 6 -l eng -c tessedit_char_whitelist=0123456789",
        output_type=Output.DICT,
    )
    raw = [""] * len(cells)
    for text, top, height in zip(data["text"], data["top"], data["height"]):
        token = re.sub(r"\D", "", (text or ""))
        if not token:
            continue
        cy = float(top) + float(height) / 2.0
        for idx, (y1, y2) in enumerate(ranges):
            if y1 <= cy <= y2:
                raw[idx] += token
                break

    values: list[Optional[int]] = []
    for cell, token in zip(cells, raw):
        batch_value = _parse_value(token)
        binary = preprocess_numeric_cell(cell)
        values.append(
            _choose_value(
                batch_value,
                binary,
                colored_fill=_cell_has_colored_fill(cell),
            )
        )
    return values

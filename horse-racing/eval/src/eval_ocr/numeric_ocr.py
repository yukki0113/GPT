from __future__ import annotations

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
            test_img = char_img if extra_scale == 1.0 else cv2.resize(char_img, None, fx=extra_scale, fy=extra_scale, interpolation=cv2.INTER_CUBIC)
            for psm in (10, 8, 13):
                candidate = pytesseract.image_to_string(test_img, config=f"--psm {psm} -l eng -c tessedit_char_whitelist=0123456789").strip()
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
        return int("".join(chars))
    except ValueError:
        return None


def ocr_numeric_cells(cells: list[np.ndarray]) -> list[Optional[int]]:
    if not cells:
        return []
    canvas, ranges = _stack_cells(cells)
    data = pytesseract.image_to_data(canvas, config="--psm 6 -l eng -c tessedit_char_whitelist=0123456789", output_type=Output.DICT)
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
        try:
            value: Optional[int] = int(token) if token else None
        except ValueError:
            value = None
        binary = preprocess_numeric_cell(cell)
        blobs = _digit_components(binary)
        token_len = len(str(value)) if value is not None else 0
        needs_repair = value is None or not (0 <= value <= 100)
        if 1 <= len(blobs) <= 3 and len(blobs) > token_len:
            needs_repair = True
        if needs_repair:
            repaired = _ocr_by_digit_components(binary)
            if repaired is not None:
                value = repaired
        values.append(value)
    return values

from __future__ import annotations

import difflib
import re
import unicodedata

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

JRA_VENUES = ["札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉"]


def _clean_name(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace(" ", "").replace("\n", "").replace("\t", "")
    text = text.strip("|｜「」『』[]()（）・.,。、:：;")
    return text


def preprocess_name_cell(cell: np.ndarray, scale: int = 5) -> np.ndarray:
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(binary, 10, 10, 15, 15, cv2.BORDER_CONSTANT, value=255)


def _stack_cells(cells: list[np.ndarray]) -> tuple[np.ndarray, list[tuple[int, int]]]:
    prepared = [preprocess_name_cell(c) for c in cells]
    if not prepared:
        return np.full((1, 1), 255, dtype=np.uint8), []
    gap = 28
    width = max(p.shape[1] for p in prepared)
    height = sum(p.shape[0] for p in prepared) + gap * (len(prepared) - 1)
    canvas = np.full((height, width), 255, dtype=np.uint8)
    ranges: list[tuple[int, int]] = []
    y = 0
    for p in prepared:
        canvas[y:y + p.shape[0], 0:p.shape[1]] = p
        ranges.append((y, y + p.shape[0]))
        y += p.shape[0] + gap
    return canvas, ranges


def ocr_name_cells(cells: list[np.ndarray]) -> list[str]:
    """OCR horse names as-is; no master-data correction is performed."""
    if not cells:
        return []
    canvas, ranges = _stack_cells(cells)
    data = pytesseract.image_to_data(canvas, config="--psm 6 -l jpn", output_type=Output.DICT)
    raw = [""] * len(cells)
    for text, top, height in zip(data["text"], data["top"], data["height"]):
        token = _clean_name(text)
        if not token:
            continue
        cy = float(top) + float(height) / 2.0
        for idx, (y1, y2) in enumerate(ranges):
            if y1 <= cy <= y2:
                raw[idx] += token
                break
    return [_clean_name(x) for x in raw]


def ocr_header_text(header: np.ndarray) -> str:
    gray = cv2.cvtColor(header, cv2.COLOR_BGR2GRAY)
    if float(np.median(gray)) < 128:
        gray = 255 - gray
    gray = cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = cv2.copyMakeBorder(binary, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    text = pytesseract.image_to_string(binary, config="--psm 7 -l jpn+eng")
    return _clean_name(text)


def resolve_venue(header_text: str) -> str:
    normalized = unicodedata.normalize("NFKC", header_text or "")
    for venue in JRA_VENUES:
        if venue in normalized:
            return venue
    match = re.search(r"(.{1,4}?)[0-9]+R", normalized)
    prefix = match.group(1) if match else normalized[:3]
    if not prefix:
        return "UNKNOWN"
    scored = [(difflib.SequenceMatcher(None, prefix, v).ratio(), v) for v in JRA_VENUES]
    score, venue = max(scored)
    return venue if score >= 0.45 else "UNKNOWN"

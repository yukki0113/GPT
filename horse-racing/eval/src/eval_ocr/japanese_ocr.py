from __future__ import annotations

import difflib
import re
import unicodedata

import cv2
import numpy as np
import pytesseract

JRA_VENUES = ["札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉"]


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace(" ", "").replace("\n", "").replace("\t", "")
    text = text.strip("|｜「」『』[]()（）・.,。、:：;")
    return text


def ocr_header_text(header: np.ndarray) -> str:
    """OCR a venue/race header. Horse-name OCR is intentionally not provided."""
    gray = cv2.cvtColor(header, cv2.COLOR_BGR2GRAY)
    if float(np.median(gray)) < 128:
        gray = 255 - gray
    gray = cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = cv2.copyMakeBorder(binary, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    text = pytesseract.image_to_string(binary, config="--psm 7 -l jpn+eng")
    return _clean_text(text)


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

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
    """Return True when the Eval cell contains a substantial colored fill."""
    if cell.size == 0:
        return False
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    colored = (saturation >= 55) & (value >= 70)
    return float(colored.mean()) >= 0.18


def _ambiguity_reasons(value: Optional[int], colored_fill: bool = False) -> list[str]:
    reasons: list[str] = []
    if value is None or not (0 <= value <= 100):
        reasons.append("missing_or_out_of_range")
        return reasons

    token = str(value)
    if len(token) >= 2 and token.startswith(("1", "7")):
        reasons.append("existing_leading_digit_ambiguity")
    # 2026-09-05 production regression: stacked OCR repeatedly confused a
    # leading 2 with 9 (24->94, 21->91, 23->93, 29->99). A 9x token is not
    # rewritten mechanically; it is only forced through independent re-reads.
    if len(token) == 2 and token.startswith("9"):
        reasons.append("leading_2_or_9_ambiguity")
    if colored_fill and len(token) == 1:
        reasons.append("colored_single_digit")
    return reasons


def _needs_ambiguity_check(value: Optional[int], colored_fill: bool = False) -> bool:
    return bool(_ambiguity_reasons(value, colored_fill=colored_fill))


def _choose_value_with_audit(
    batch_value: Optional[int],
    binary: np.ndarray,
    *,
    colored_fill: bool = False,
) -> tuple[Optional[int], dict]:
    initial_value = batch_value
    blobs = _digit_components(binary)
    token_len = len(str(batch_value)) if batch_value is not None else 0
    candidate_values: list[int] = []
    resolution_method = "stacked_batch"
    requires_review = False

    if batch_value is not None and 0 <= batch_value <= 100:
        candidate_values.append(batch_value)

    # Digit-count repair catches cleanly separated dropped digits (e.g. 37->3).
    if batch_value is None or not (0 <= batch_value <= 100) or (
        1 <= len(blobs) <= 3 and len(blobs) > token_len
    ):
        repaired = _ocr_by_digit_components(binary)
        if repaired is not None:
            candidate_values.append(repaired)
            batch_value = repaired
            resolution_method = "digit_component_repair"

    reasons = _ambiguity_reasons(batch_value, colored_fill=colored_fill)
    if not reasons:
        return batch_value, {
            "initial_ocr_value": initial_value,
            "final_ocr_value": batch_value,
            "colored_fill": colored_fill,
            "recheck_triggered": False,
            "recheck_reason": [],
            "candidate_values": candidate_values,
            "resolution_method": resolution_method,
            "requires_review": False,
        }

    if batch_value is not None and 0 <= batch_value <= 100 and batch_value not in candidate_values:
        candidate_values.append(batch_value)

    component_value = _ocr_by_digit_components(binary)
    if component_value is not None:
        candidate_values.append(component_value)

    single_candidates = _ocr_single_cell_candidates(binary)
    candidate_values.extend(single_candidates)

    if not candidate_values:
        requires_review = True
        final_value = batch_value
        resolution_method = "recheck_no_candidate"
    else:
        # On a colored cell that initially collapsed to one digit, prefer a
        # repeatedly observed multi-digit candidate. This specifically repairs
        # dropped leading digits while retaining a true one-digit value when
        # multi-digit evidence is weak.
        final_value = batch_value
        if colored_fill and batch_value is not None and batch_value < 10:
            multi = [v for v in candidate_values if v >= 10]
            if multi:
                multi_counts = Counter(multi)
                best_multi, best_multi_count = multi_counts.most_common(1)[0]
                if best_multi_count >= 2:
                    final_value = best_multi
                    resolution_method = "colored_multidigit_vote"

        if resolution_method != "colored_multidigit_vote":
            counts = Counter(candidate_values)
            best_value, best_count = counts.most_common(1)[0]
            batch_count = counts[batch_value] if batch_value is not None else 0

            if batch_value is None or not (0 <= batch_value <= 100):
                if best_count >= 2 or len(counts) == 1:
                    final_value = best_value
                    resolution_method = "recheck_recovered"
                else:
                    final_value = best_value
                    requires_review = True
                    resolution_method = "recheck_weak_consensus"
            elif best_value != batch_value and best_count >= 2 and best_count > batch_count:
                final_value = best_value
                resolution_method = "multi_ocr_vote"
            elif best_value == batch_value and best_count >= 2:
                final_value = batch_value
                resolution_method = "recheck_confirmed"
            else:
                final_value = batch_value
                requires_review = True
                resolution_method = "manual_review_required"

    return final_value, {
        "initial_ocr_value": initial_value,
        "final_ocr_value": final_value,
        "colored_fill": colored_fill,
        "recheck_triggered": True,
        "recheck_reason": reasons,
        "candidate_values": candidate_values,
        "resolution_method": resolution_method,
        "requires_review": requires_review,
    }


def recheck_numeric_cell(
    cell: np.ndarray,
    current_value: Optional[int],
    *,
    reason: str,
) -> tuple[Optional[int], dict]:
    """Conservatively re-read a value selected by independent color checks.

    This second-stage path is intentionally separate from the initial ambiguity
    rules. It is called only after the image-side rank colors contradict the
    numeric result. For an already multi-digit value, one-digit alternatives
    are ignored so a per-cell leading-digit drop cannot overwrite a sound batch
    read (for example 56 -> 6). An alternative needs repeated independent OCR
    support before it replaces the current value; otherwise manual review is
    required and the validator remains a fail-closed gate.
    """
    binary = preprocess_numeric_cell(cell)
    candidates: list[int] = []
    if current_value is not None and 0 <= current_value <= 100:
        candidates.append(current_value)

    component_value = _ocr_by_digit_components(binary)
    if component_value is not None:
        candidates.append(component_value)
    candidates.extend(_ocr_single_cell_candidates(binary))

    usable = list(candidates)
    if current_value is not None and current_value >= 10:
        width = len(str(current_value))
        same_width = [v for v in candidates if len(str(v)) == width]
        if same_width:
            usable = same_width

    final_value = current_value
    requires_review = False
    method = "color_conflict_recheck_no_candidate"
    if usable:
        counts = Counter(usable)
        best_value, best_count = counts.most_common(1)[0]
        current_count = counts[current_value] if current_value is not None else 0
        if current_value is None:
            if best_count >= 2 or len(counts) == 1:
                final_value = best_value
                method = "color_conflict_recovered"
            else:
                final_value = best_value
                requires_review = True
                method = "color_conflict_weak_consensus"
        elif best_value != current_value and best_count >= 2 and best_count > current_count:
            final_value = best_value
            method = "color_conflict_multi_ocr_vote"
        elif best_value == current_value and best_count >= 2:
            method = "color_conflict_recheck_confirmed"
        else:
            requires_review = True
            method = "color_conflict_manual_review_required"
    else:
        requires_review = True

    return final_value, {
        "final_ocr_value": final_value,
        "recheck_triggered": True,
        "recheck_reason": [reason],
        "candidate_values": candidates,
        "resolution_method": method,
        "requires_review": requires_review,
    }


def _choose_value(batch_value: Optional[int], binary: np.ndarray, *, colored_fill: bool = False) -> Optional[int]:
    value, _ = _choose_value_with_audit(batch_value, binary, colored_fill=colored_fill)
    return value


def ocr_numeric_cells_with_audit(cells: list[np.ndarray]) -> tuple[list[Optional[int]], list[dict]]:
    if not cells:
        return [], []
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
    audits: list[dict] = []
    for cell, token in zip(cells, raw):
        batch_value = _parse_value(token)
        binary = preprocess_numeric_cell(cell)
        value, audit = _choose_value_with_audit(
            batch_value,
            binary,
            colored_fill=_cell_has_colored_fill(cell),
        )
        values.append(value)
        audits.append(audit)
    return values, audits


def ocr_numeric_cells(cells: list[np.ndarray]) -> list[Optional[int]]:
    values, _ = ocr_numeric_cells_with_audit(cells)
    return values

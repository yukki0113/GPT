from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .color_detector import COLOR_RANK_INDEX, classify_eval_cell
from .japanese_ocr import ocr_header_text, resolve_venue
from .layout_detector import detect_column_lines, detect_layout, detect_row_lines
from .models import HorseRecord, PanelBox
from .numeric_ocr import ocr_numeric_cells_with_audit, recheck_numeric_cell
from .validator import validate


def _crop_inner(panel: np.ndarray, y1: int, y2: int, x1: int, x2: int) -> np.ndarray:
    yy1 = min(y2 - 1, y1 + 2)
    yy2 = max(yy1 + 1, y2 - 2)
    xx1 = min(x2 - 1, x1 + 2)
    xx2 = max(xx1 + 1, x2 - 2)
    return panel[yy1:yy2, xx1:xx2]


def _color_conflict_reasons(
    evals: list[int | None],
    colors: list[str | None],
    *,
    include_higher_rank_side: bool = False,
) -> dict[int, list[str]]:
    """Select cells for second-stage OCR using only image-side color rules.

    Pass 1 rechecks the unexpectedly high lower-rank side. If a contradiction
    remains, pass 2 also rechecks the higher-rank side. This avoids needlessly
    replacing a sound multi-digit batch read when per-cell OCR happens to drop
    its leading digit, while still repairing cases where the higher-rank value
    itself was read too low.
    """
    reasons: dict[int, list[str]] = defaultdict(list)
    colored = [i for i, (value, color) in enumerate(zip(evals, colors)) if value is not None and color]
    uncolored = [i for i, (value, color) in enumerate(zip(evals, colors)) if value is not None and not color]

    by_color: dict[str, list[int]] = defaultdict(list)
    for i in colored:
        by_color[str(colors[i])].append(i)
    for color, indexes in by_color.items():
        values = {int(evals[i]) for i in indexes if evals[i] is not None}
        if len(indexes) > 1 and len(values) > 1:
            for i in indexes:
                reasons[i].append(f"same_color_eval_conflict:{color}")

    if colored and uncolored:
        min_colored = min(int(evals[i]) for i in colored if evals[i] is not None)
        for i in uncolored:
            if int(evals[i]) > min_colored:
                reasons[i].append("uncolored_above_colored_boundary")

    for left in colored:
        left_color = str(colors[left])
        left_rank = COLOR_RANK_INDEX.get(left_color)
        if left_rank is None:
            continue
        for right in colored:
            right_color = str(colors[right])
            right_rank = COLOR_RANK_INDEX.get(right_color)
            if right_rank is None or left_rank >= right_rank:
                continue
            if int(evals[left]) < int(evals[right]):
                if include_higher_rank_side:
                    reasons[left].append(
                        f"higher_rank_color_below_lower:{left_color}>{right_color}"
                    )
                reasons[right].append(
                    f"lower_rank_color_above_higher:{right_color}<{left_color}"
                )

    return {i: list(dict.fromkeys(items)) for i, items in reasons.items()}


def _merge_recheck_audit(base: dict, update: dict, reasons: list[str]) -> dict:
    merged = dict(base)
    merged["recheck_triggered"] = True
    merged["recheck_reason"] = list(dict.fromkeys(
        list(base.get("recheck_reason") or []) + reasons + list(update.get("recheck_reason") or [])
    ))
    merged["candidate_values"] = list(base.get("candidate_values") or []) + list(update.get("candidate_values") or [])
    history = list(base.get("resolution_history") or [])
    previous_method = base.get("resolution_method")
    if previous_method:
        history.append(previous_method)
    if update.get("resolution_method"):
        history.append(update["resolution_method"])
        merged["resolution_method"] = update["resolution_method"]
    merged["resolution_history"] = list(dict.fromkeys(history))
    merged["final_ocr_value"] = update.get("final_ocr_value", base.get("final_ocr_value"))
    merged["requires_review"] = bool(base.get("requires_review")) or bool(update.get("requires_review"))
    return merged


def _extract_panel_rows(panel_image: np.ndarray) -> tuple[list[int | None], list[str | None], list[int], list[dict]]:
    """Extract Eval values/colors while using horse-name cells only for row existence."""
    row_lines = detect_row_lines(panel_image)
    if len(row_lines) < 3:
        return [], [], row_lines, []

    col_lines = detect_column_lines(panel_image, row_lines)
    intervals = list(zip(row_lines[:-1], row_lines[1:]))[:18]
    eval_cells: list[np.ndarray] = []
    occupied: list[bool] = []

    for y1, y2 in intervals:
        name_cell = _crop_inner(panel_image, y1, y2, col_lines[1], col_lines[2])
        eval_cell = _crop_inner(panel_image, y1, y2, col_lines[2], col_lines[3])
        eval_cells.append(eval_cell)

        if name_cell.size:
            name_gray = cv2.cvtColor(name_cell, cv2.COLOR_BGR2GRAY)
            has_ink = float(name_gray.std()) > 8.0 or int((name_gray < 210).sum()) >= 8
        else:
            has_ink = False
        occupied.append(has_ink)

    last_occupied = 0
    for idx, flag in enumerate(occupied, start=1):
        if flag:
            last_occupied = idx
    if last_occupied == 0:
        return [], [], row_lines, []

    eval_cells = eval_cells[:last_occupied]
    evals, audits = ocr_numeric_cells_with_audit(eval_cells)
    colors = [classify_eval_cell(cell) for cell in eval_cells]

    # Pass 1: unexpectedly high lower-rank/uncolored cells and same-color
    # inconsistencies. Pass 2: if a rank contradiction remains, allow the
    # higher-rank side to be re-read as well. A cell at the same value is not
    # OCRed twice.
    rechecked_at_value: set[tuple[int, int | None]] = set()
    for pass_index in range(2):
        conflicts = _color_conflict_reasons(
            evals,
            colors,
            include_higher_rank_side=pass_index > 0,
        )
        if not conflicts:
            break
        for idx, reasons in conflicts.items():
            marker = (idx, evals[idx])
            if marker in rechecked_at_value:
                continue
            rechecked_at_value.add(marker)
            new_value, recheck_audit = recheck_numeric_cell(
                eval_cells[idx],
                evals[idx],
                reason=";".join(reasons),
            )
            audits[idx] = _merge_recheck_audit(audits[idx], recheck_audit, reasons)
            if new_value != evals[idx]:
                evals[idx] = new_value

    return evals, colors, row_lines, audits


def run_pipeline(
    image_path: str | Path,
    date: str = "",
    expected_venues: Optional[int] = None,
    debug_dir: str | Path | None = None,
) -> tuple[list[HorseRecord], dict, list[PanelBox]]:
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    detection = detect_layout(image)
    panels = detection.panels

    for venue_idx in sorted({p.venue_index for p in panels}):
        anchor = next(p for p in panels if p.venue_index == venue_idx and p.race_no == 1)
        header = image[anchor.y:anchor.y + 20, anchor.x:anchor.x + anchor.width]
        header_text = ocr_header_text(header)
        venue = resolve_venue(header_text)
        for p in panels:
            if p.venue_index == venue_idx:
                p.venue = venue
                p.header_ocr = header_text if p.race_no == 1 else None

    debug_path = Path(debug_dir) if debug_dir else None
    if debug_path:
        debug_path.mkdir(parents=True, exist_ok=True)

    records: list[HorseRecord] = []
    color_observations: list[dict] = []
    ocr_cell_audits: list[dict] = []
    panel_debug: list[dict] = []
    for p in sorted(panels, key=lambda x: (x.venue_index, x.race_no)):
        panel_img = image[p.y:p.y + p.height, p.x:p.x + p.width]
        evals, colors, row_lines, audits = _extract_panel_rows(panel_img)
        count = max(len(evals), len(colors))
        panel_audits: list[dict] = []
        for i in range(count):
            value = evals[i] if i < len(evals) else None
            color = colors[i] if i < len(colors) else None
            horse_no = i + 1
            records.append(HorseRecord(date=date, venue=p.venue or "UNKNOWN", race_no=p.race_no, horse_no=horse_no, eval=value))
            color_observations.append({"venue": p.venue or "UNKNOWN", "race_no": p.race_no, "horse_no": horse_no, "color": color, "eval": value})

            cell_audit = dict(audits[i]) if i < len(audits) else {
                "initial_ocr_value": None,
                "final_ocr_value": value,
                "colored_fill": bool(color),
                "recheck_triggered": False,
                "recheck_reason": [],
                "candidate_values": [],
                "resolution_method": "audit_missing",
                "requires_review": True,
            }
            cell_audit.update({"venue": p.venue or "UNKNOWN", "race_no": p.race_no, "horse_no": horse_no, "color": color})
            ocr_cell_audits.append(cell_audit)
            panel_audits.append(cell_audit)

        panel_debug.append({
            "venue": p.venue,
            "race_no": p.race_no,
            "rows": count,
            "row_lines": row_lines,
            "colored_rows": [
                {"horse_no": i + 1, "color": colors[i], "eval": evals[i] if i < len(evals) else None}
                for i in range(len(colors)) if colors[i]
            ],
            "ocr_audit": panel_audits,
            "box": p.to_dict(),
        })
        if debug_path:
            cv2.imwrite(str(debug_path / f"v{p.venue_index + 1}_{p.race_no:02d}R.png"), panel_img)

    report = validate(
        records,
        panels,
        detection.warnings,
        expected_venues=expected_venues,
        color_observations=color_observations,
        ocr_cell_audits=ocr_cell_audits,
    )
    report["panels"] = panel_debug
    report["ocr_cell_audits"] = ocr_cell_audits
    report["source_image"] = str(image_path)
    report["date"] = date
    if not date:
        report["warnings"].append("Date was not supplied; CSV date column is blank.")
    return records, report, panels

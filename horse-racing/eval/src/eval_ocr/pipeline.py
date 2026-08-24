from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .japanese_ocr import ocr_header_text, ocr_name_cells, resolve_venue
from .layout_detector import detect_column_lines, detect_layout, detect_row_lines
from .models import HorseRecord, PanelBox
from .numeric_ocr import ocr_numeric_cells
from .validator import validate


def _crop_inner(panel: np.ndarray, y1: int, y2: int, x1: int, x2: int) -> np.ndarray:
    yy1 = min(y2 - 1, y1 + 2)
    yy2 = max(yy1 + 1, y2 - 2)
    xx1 = min(x2 - 1, x1 + 2)
    xx2 = max(xx1 + 1, x2 - 2)
    return panel[yy1:yy2, xx1:xx2]


def _extract_panel_rows(panel_image: np.ndarray) -> tuple[list[str], list[int | None], list[int]]:
    row_lines = detect_row_lines(panel_image)
    if len(row_lines) < 3:
        return [], [], row_lines
    col_lines = detect_column_lines(panel_image, row_lines)
    intervals = list(zip(row_lines[:-1], row_lines[1:]))[:18]
    name_cells: list[np.ndarray] = []
    eval_cells: list[np.ndarray] = []
    occupied: list[bool] = []
    for y1, y2 in intervals:
        name_cell = _crop_inner(panel_image, y1, y2, col_lines[1], col_lines[2])
        eval_cell = _crop_inner(panel_image, y1, y2, col_lines[2], col_lines[3])
        name_cells.append(name_cell)
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
        return [], [], row_lines

    names = ocr_name_cells(name_cells[:last_occupied])
    evals = ocr_numeric_cells(eval_cells[:last_occupied])
    return names, evals, row_lines


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
    panel_debug: list[dict] = []
    for p in sorted(panels, key=lambda x: (x.venue_index, x.race_no)):
        panel_img = image[p.y:p.y + p.height, p.x:p.x + p.width]
        names, evals, row_lines = _extract_panel_rows(panel_img)
        count = max(len(names), len(evals))
        for i in range(count):
            records.append(HorseRecord(date=date,venue=p.venue or "UNKNOWN",race_no=p.race_no,horse_no=i + 1,horse_name_ocr=names[i] if i < len(names) else "",eval=evals[i] if i < len(evals) else None))
        panel_debug.append({"venue": p.venue,"race_no": p.race_no,"rows": count,"row_lines": row_lines,"box": p.to_dict()})
        if debug_path:
            cv2.imwrite(str(debug_path / f"v{p.venue_index + 1}_{p.race_no:02d}R.png"), panel_img)

    report = validate(records, panels, detection.warnings, expected_venues=expected_venues)
    report["panels"] = panel_debug
    report["source_image"] = str(image_path)
    report["date"] = date
    if not date:
        report["warnings"].append("Date was not supplied; CSV date column is blank.")
    return records, report, panels

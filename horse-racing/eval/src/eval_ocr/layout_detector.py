from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

from .models import PanelBox


@dataclass
class LayoutDetection:
    panels: list[PanelBox]
    header_rows: list[list[tuple[int, int, int, int]]]
    warnings: list[str]

    @property
    def venue_count(self) -> int:
        return len(self.header_rows) // 2


def _cluster_by_y(boxes: list[tuple[int, int, int, int]], tolerance: int = 4) -> list[list[tuple[int, int, int, int]]]:
    rows: list[list[tuple[int, int, int, int]]] = []
    for box in sorted(boxes, key=lambda b: (b[1], b[0])):
        if not rows:
            rows.append([box])
            continue
        row_y = int(round(sum(b[1] for b in rows[-1]) / len(rows[-1])))
        if abs(box[1] - row_y) <= tolerance:
            rows[-1].append(box)
        else:
            rows.append([box])
    for row in rows:
        row.sort(key=lambda b: b[0])
    return rows


def _find_header_bars(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark = (gray < 45).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    h_img, w_img = gray.shape
    min_w = max(80, int(w_img * 0.075))
    max_w = int(w_img * 0.20)
    min_h = max(7, int(h_img * 0.0035))
    max_h = max(35, int(h_img * 0.025))
    candidates: list[tuple[int, int, int, int]] = []
    for idx in range(1, count):
        x, y, w, h, area = stats[idx]
        fill = area / max(1, w * h)
        if not (min_w <= w <= max_w and min_h <= h <= max_h):
            continue
        if fill < 0.45:
            continue
        if x < int(w_img * 0.08):
            continue
        candidates.append((int(x), int(y), int(w), int(h)))
    if not candidates:
        return []
    widths = np.array([b[2] for b in candidates], dtype=float)
    median_w = float(np.median(widths))
    return [b for b in candidates if abs(b[2] - median_w) <= max(8, median_w * 0.12)]


def detect_layout(image: np.ndarray) -> LayoutDetection:
    warnings: list[str] = []
    bars = _find_header_bars(image)
    if not bars:
        raise RuntimeError("Race header bars were not detected.")
    rows = _cluster_by_y(bars, tolerance=4)
    six_rows = [r for r in rows if len(r) == 6]
    if len(six_rows) != len(rows):
        warnings.append(f"Ignored {len(rows) - len(six_rows)} non-six-panel header row(s).")
    rows = six_rows
    if len(rows) < 2 or len(rows) % 2 != 0:
        raise RuntimeError(f"Expected an even number of six-panel rows, detected {len(rows)}.")
    venue_count = len(rows) // 2
    if venue_count not in (2, 3):
        warnings.append(f"Detected {venue_count} venue block(s); current PoC was tuned for 2 or 3 venues.")
    panels: list[PanelBox] = []
    image_h = image.shape[0]
    intra_spans = []
    for venue_idx in range(venue_count):
        upper = rows[venue_idx * 2]
        lower = rows[venue_idx * 2 + 1]
        intra_spans.append(int(round(np.median([b[1] for b in lower]) - np.median([b[1] for b in upper]))))
    panel_height = int(np.median(intra_spans)) if intra_spans else 310
    panel_height = max(250, min(330, panel_height))
    for venue_idx in range(venue_count):
        for row_in_venue in range(2):
            header_row = rows[venue_idx * 2 + row_in_venue]
            for col_idx, (x, y, w, h) in enumerate(header_row):
                race_no = col_idx + 1 + (6 if row_in_venue == 1 else 0)
                height = min(panel_height, image_h - y)
                panels.append(PanelBox(venue_index=venue_idx,row_in_venue=row_in_venue,col_index=col_idx,race_no=race_no,x=x,y=y,width=w,height=height))
    return LayoutDetection(panels=panels, header_rows=rows, warnings=warnings)


def _consolidate_positions(values: Iterable[int], max_gap: int = 1) -> list[int]:
    groups: list[list[int]] = []
    for v in sorted(set(int(x) for x in values)):
        if not groups or v > groups[-1][-1] + max_gap:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [int(round(sum(g) / len(g))) for g in groups]


def detect_row_lines(panel_image: np.ndarray, header_bar_height: int = 15) -> list[int]:
    gray = cv2.cvtColor(panel_image, cv2.COLOR_BGR2GRAY)
    dark_counts = (gray < 185).sum(axis=1)
    width = gray.shape[1]
    raw = [i for i, count in enumerate(dark_counts) if count >= width * 0.78]
    lines = _consolidate_positions(raw, max_gap=1)
    start_candidates = [y for y in lines if y >= header_bar_height + 10]
    if not start_candidates:
        return []
    start = start_candidates[0]
    data_lines = [y for y in lines if y >= start]
    filtered = [data_lines[0]]
    for y in data_lines[1:]:
        gap = y - filtered[-1]
        if gap < 7:
            continue
        if gap > 30:
            break
        filtered.append(y)
        if len(filtered) >= 20:
            break
    return filtered


def detect_column_lines(panel_image: np.ndarray, row_lines: list[int]) -> list[int]:
    w = panel_image.shape[1]
    if len(row_lines) >= 2:
        y1 = row_lines[0]
        y2 = min(panel_image.shape[0], row_lines[-1] + 1)
        body = cv2.cvtColor(panel_image[y1:y2], cv2.COLOR_BGR2GRAY)
        counts = (body < 185).sum(axis=0)
        threshold = max(10, body.shape[0] * 0.65)
        positions = _consolidate_positions([i for i, c in enumerate(counts) if c >= threshold], max_gap=1)
        targets = [0.0, 0.125, 0.755, 1.0]
        found: list[int] = []
        for target in targets:
            tx = target * (w - 1)
            nearby = [x for x in positions if abs(x - tx) <= max(5, w * 0.06)]
            found.append(min(nearby, key=lambda x: abs(x - tx)) if nearby else int(round(tx)))
        if found == sorted(found) and len(set(found)) == 4:
            return found
    return [0, int(round(w * 0.125)), int(round(w * 0.755)), w - 1]

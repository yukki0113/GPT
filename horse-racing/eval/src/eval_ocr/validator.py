from __future__ import annotations

from collections import Counter, defaultdict

from .color_detector import COLOR_RANK_INDEX, COLOR_RANK_ORDER
from .models import HorseRecord, PanelBox


def _validate_colors(color_observations: list[dict]) -> dict:
    """Validate ranked-cell colors against numeric Eval values.

    The color order is an image-side invariant taken from the master_eval
    legend: red(1st) -> blue(2nd) -> orange(3rd) -> green(4th) -> yellow(5th).
    It is deliberately *not* inferred from OCR values. OCR values are the
    subject being validated and must never determine the validation baseline.
    """
    by_race: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for obs in color_observations:
        by_race[(str(obs["venue"]), int(obs["race_no"]))].append(obs)

    active_colors = [
        color for color in COLOR_RANK_ORDER
        if any(str(o.get("color")) == color for o in color_observations if o.get("color"))
    ]

    top_set_violations: list[dict] = []
    order_violations: list[dict] = []
    tie_color_groups: list[dict] = []
    inconsistent_same_color_groups: list[dict] = []

    for (venue, race_no), rows in sorted(by_race.items()):
        colored = [r for r in rows if r.get("color") and r.get("eval") is not None]
        uncolored = [r for r in rows if not r.get("color") and r.get("eval") is not None]
        if not colored:
            continue

        # Same-color duplicates are expected only when the same rank is tied.
        # Different numeric values attached to the same rank color are a direct
        # contradiction and therefore independent evidence of OCR/color error.
        by_color: dict[str, list[dict]] = defaultdict(list)
        for row in colored:
            by_color[str(row["color"])].append(row)
        for color, same_color_rows in sorted(by_color.items()):
            if len(same_color_rows) <= 1:
                continue
            values = sorted({int(r["eval"]) for r in same_color_rows})
            payload = {
                "venue": venue,
                "race_no": race_no,
                "color": color,
                "eval_values": values,
                "horse_nos": sorted(int(r["horse_no"]) for r in same_color_rows),
            }
            if len(values) == 1:
                tie_color_groups.append(payload)
            else:
                inconsistent_same_color_groups.append(payload)

        # Colored cells are the ranked top set. An uncolored Eval may tie the
        # lowest colored boundary, but may not be strictly greater than it.
        if uncolored:
            min_colored = min(int(r["eval"]) for r in colored)
            max_uncolored = max(int(r["eval"]) for r in uncolored)
            if max_uncolored > min_colored:
                top_set_violations.append(
                    {
                        "venue": venue,
                        "race_no": race_no,
                        "min_colored_eval": min_colored,
                        "max_uncolored_eval": max_uncolored,
                        "colored": [
                            {
                                "horse_no": int(r["horse_no"]),
                                "color": str(r["color"]),
                                "eval": int(r["eval"]),
                            }
                            for r in colored
                        ],
                        "uncolored_above_boundary": [
                            {
                                "horse_no": int(r["horse_no"]),
                                "eval": int(r["eval"]),
                            }
                            for r in uncolored
                            if int(r["eval"]) > min_colored
                        ],
                    }
                )

        # Directly compare the fixed image-side rank colors. Ties are legal;
        # only a strictly lower-ranked color beating a higher-ranked color is
        # an error. Compare all pairs so one bad OCR value cannot redefine the
        # global color order and hide itself.
        for left in colored:
            left_color = str(left["color"])
            left_rank = COLOR_RANK_INDEX.get(left_color)
            if left_rank is None:
                continue
            for right in colored:
                right_color = str(right["color"])
                right_rank = COLOR_RANK_INDEX.get(right_color)
                if right_rank is None or left_rank >= right_rank:
                    continue
                if int(left["eval"]) < int(right["eval"]):
                    order_violations.append(
                        {
                            "venue": venue,
                            "race_no": race_no,
                            "higher_rank_color": left_color,
                            "higher_rank": left_rank + 1,
                            "higher_horse_no": int(left["horse_no"]),
                            "higher_eval": int(left["eval"]),
                            "lower_rank_color": right_color,
                            "lower_rank": right_rank + 1,
                            "lower_horse_no": int(right["horse_no"]),
                            "lower_eval": int(right["eval"]),
                        }
                    )

    return {
        "colored_cells": sum(1 for o in color_observations if o.get("color")),
        "active_colors": active_colors,
        "color_order_source": "master_eval_image_legend_fixed",
        "fixed_color_order": list(COLOR_RANK_ORDER),
        # Compatibility aliases retained for existing audit readers. The value
        # is now fixed, never OCR-inferred.
        "inferred_color_order": list(COLOR_RANK_ORDER),
        "median_numeric_rank_by_color": {},
        "top_set_violations": top_set_violations,
        "order_violations": order_violations,
        "tie_color_groups": tie_color_groups,
        "inconsistent_same_color_groups": inconsistent_same_color_groups,
    }


def validate(
    records: list[HorseRecord],
    panels: list[PanelBox],
    layout_warnings: list[str],
    expected_venues: int | None = None,
    color_observations: list[dict] | None = None,
    ocr_cell_audits: list[dict] | None = None,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = list(layout_warnings)

    venues = sorted({p.venue or "UNKNOWN" for p in panels})
    detected_venue_count = len({p.venue_index for p in panels})
    race_count = len(panels)

    if expected_venues is not None and detected_venue_count != expected_venues:
        errors.append(f"Expected {expected_venues} venue(s), detected {detected_venue_count}.")
    if race_count != detected_venue_count * 12:
        errors.append(f"Expected {detected_venue_count * 12} race panels, detected {race_count}.")

    by_venue: dict[int, list[int]] = defaultdict(list)
    for p in panels:
        by_venue[p.venue_index].append(p.race_no)
    for venue_idx, race_nos in sorted(by_venue.items()):
        if sorted(race_nos) != list(range(1, 13)):
            errors.append(f"Venue block {venue_idx + 1}: race numbers are not exactly 1..12: {sorted(race_nos)}")

    keys = [(r.date, r.venue, r.race_no, r.horse_no) for r in records]
    duplicate_keys = [k for k, c in Counter(keys).items() if c > 1]
    if duplicate_keys:
        errors.append(f"Duplicate date/venue/race_no/horse_no keys: {len(duplicate_keys)}")

    missing_eval = [r for r in records if r.eval is None]
    out_of_range = [r for r in records if r.eval is not None and not (0 <= r.eval <= 100)]
    if missing_eval:
        warnings.append(f"Missing Eval OCR: {len(missing_eval)} row(s).")
    if out_of_range:
        errors.append(f"Eval outside 0..100: {len(out_of_range)} row(s).")

    if any((p.venue or "UNKNOWN") == "UNKNOWN" for p in panels):
        errors.append("At least one venue header could not be resolved.")

    by_race: dict[tuple[str, int], list[int]] = defaultdict(list)
    for r in records:
        by_race[(r.venue, r.race_no)].append(r.horse_no)
    for key, numbers in by_race.items():
        expected = list(range(1, max(numbers) + 1)) if numbers else []
        if sorted(numbers) != expected:
            errors.append(f"Horse-number gap in {key[0]} {key[1]}R: {sorted(numbers)}")

    color_validation = _validate_colors(color_observations or [])
    if color_validation["top_set_violations"]:
        errors.append(
            f"Colored Eval top-set violation: {len(color_validation['top_set_violations'])} race(s)."
        )
    if color_validation["order_violations"]:
        errors.append(
            f"Colored Eval color-order violation: {len(color_validation['order_violations'])} pair(s)."
        )
    if color_validation["inconsistent_same_color_groups"]:
        errors.append(
            "Repeated rank color mapped to different Eval values: "
            f"{len(color_validation['inconsistent_same_color_groups'])} group(s)."
        )

    audits = list(ocr_cell_audits or [])
    manual_review = [audit for audit in audits if audit.get("requires_review")]
    if manual_review:
        errors.append(f"Eval OCR manual review required: {len(manual_review)} cell(s).")

    return {
        "status": "ok" if not errors else "error",
        "summary": {
            "detected_venues": detected_venue_count,
            "resolved_venue_names": venues,
            "race_panels": race_count,
            "horse_rows": len(records),
            "missing_eval": len(missing_eval),
            "eval_out_of_range": len(out_of_range),
            "duplicate_keys": len(duplicate_keys),
            "colored_cells": color_validation["colored_cells"],
            "color_top_set_violations": len(color_validation["top_set_violations"]),
            "color_order_violations": len(color_validation["order_violations"]),
            "color_tie_groups": len(color_validation["tie_color_groups"]),
            "color_same_color_inconsistencies": len(color_validation["inconsistent_same_color_groups"]),
            "ocr_rechecked_cells": sum(1 for audit in audits if audit.get("recheck_triggered")),
            "ocr_manual_review_required": len(manual_review),
        },
        "color_validation": color_validation,
        "ocr_manual_review": manual_review,
        "errors": errors,
        "warnings": warnings,
    }

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from .models import HorseRecord, PanelBox


def _validate_colors(color_observations: list[dict]) -> dict:
    by_race: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for obs in color_observations:
        by_race[(str(obs["venue"]), int(obs["race_no"]))].append(obs)

    active_colors = sorted({str(o["color"]) for o in color_observations if o.get("color")})
    rank_samples: dict[str, list[float]] = defaultdict(list)

    for rows in by_race.values():
        numeric = [int(r["eval"]) for r in rows if r.get("eval") is not None]
        for row in rows:
            color = row.get("color")
            value = row.get("eval")
            if not color or value is None:
                continue
            # Rank 1 + number of strictly greater values; ties share the rank.
            rank = 1 + sum(1 for v in numeric if v > int(value))
            rank_samples[str(color)].append(float(rank))

    inferred_order = sorted(
        active_colors,
        key=lambda color: (
            median(rank_samples[color]) if rank_samples[color] else 999.0,
            color,
        ),
    )
    order_index = {color: idx for idx, color in enumerate(inferred_order)}

    top_set_violations: list[dict] = []
    order_violations: list[dict] = []
    tie_color_groups: list[dict] = []
    inconsistent_same_color_groups: list[dict] = []

    for (venue, race_no), rows in sorted(by_race.items()):
        colored = [r for r in rows if r.get("color") and r.get("eval") is not None]
        uncolored = [r for r in rows if not r.get("color") and r.get("eval") is not None]
        if not colored:
            continue

        # Same-color duplicates are expected when multiple horses share the
        # same Eval/rank. Record them as normal tie information. Only treat a
        # repeated color as inconsistent when it is attached to different
        # numeric Eval values inside the same race.
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

        # Colored cells represent the top-N horses. Therefore an uncolored Eval
        # must never be strictly greater than the lowest colored Eval. Ties are
        # allowed because a boundary tie can legitimately be partly colored.
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
                    }
                )

        ordered = sorted(
            colored,
            key=lambda r: order_index.get(str(r["color"]), 999),
        )
        for left, right in zip(ordered, ordered[1:]):
            if str(left["color"]) == str(right["color"]):
                continue
            if int(left["eval"]) < int(right["eval"]):
                order_violations.append(
                    {
                        "venue": venue,
                        "race_no": race_no,
                        "higher_color": str(left["color"]),
                        "higher_eval": int(left["eval"]),
                        "lower_color": str(right["color"]),
                        "lower_eval": int(right["eval"]),
                    }
                )

    return {
        "colored_cells": sum(1 for o in color_observations if o.get("color")),
        "active_colors": active_colors,
        "inferred_color_order": inferred_order,
        "median_numeric_rank_by_color": {
            color: median(rank_samples[color]) if rank_samples[color] else None
            for color in inferred_order
        },
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
        },
        "color_validation": color_validation,
        "errors": errors,
        "warnings": warnings,
    }

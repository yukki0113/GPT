from __future__ import annotations

from collections import Counter, defaultdict

from .models import HorseRecord, PanelBox


def validate(records: list[HorseRecord], panels: list[PanelBox], layout_warnings: list[str], expected_venues: int | None = None) -> dict:
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
    missing_name = [r for r in records if not r.horse_name_ocr]
    if missing_eval:
        warnings.append(f"Missing Eval OCR: {len(missing_eval)} row(s).")
    if out_of_range:
        errors.append(f"Eval outside 0..100: {len(out_of_range)} row(s).")
    if missing_name:
        warnings.append(f"Missing horse-name OCR: {len(missing_name)} row(s).")

    if any((p.venue or "UNKNOWN") == "UNKNOWN" for p in panels):
        errors.append("At least one venue header could not be resolved.")

    by_race: dict[tuple[str, int], list[int]] = defaultdict(list)
    for r in records:
        by_race[(r.venue, r.race_no)].append(r.horse_no)
    for key, numbers in by_race.items():
        expected = list(range(1, max(numbers) + 1)) if numbers else []
        if sorted(numbers) != expected:
            errors.append(f"Horse-number gap in {key[0]} {key[1]}R: {sorted(numbers)}")

    return {
        "status": "ok" if not errors else "error",
        "summary": {
            "detected_venues": detected_venue_count,
            "resolved_venue_names": venues,
            "race_panels": race_count,
            "horse_rows": len(records),
            "missing_eval": len(missing_eval),
            "missing_horse_name": len(missing_name),
            "eval_out_of_range": len(out_of_range),
            "duplicate_keys": len(duplicate_keys),
        },
        "errors": errors,
        "warnings": warnings,
    }

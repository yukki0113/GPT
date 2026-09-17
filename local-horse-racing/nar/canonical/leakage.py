from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass


def parse_record(value: str | None) -> tuple[int, int, int, int] | None:
    text = (value or "").strip()
    parts = text.split("-")
    if len(parts) != 4:
        return None
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _expected_delta(finish_position: int | None) -> tuple[int, int, int, int] | None:
    if finish_position is None:
        return None
    if finish_position == 1:
        return (1, 0, 0, 0)
    if finish_position == 2:
        return (0, 1, 0, 0)
    if finish_position == 3:
        return (0, 0, 1, 0)
    if finish_position >= 4:
        return (0, 0, 0, 1)
    return None


@dataclass
class ValidationMetric:
    field: str
    evidence_pairs: int = 0
    matched_pairs: int = 0
    mismatched_pairs: int = 0
    skipped_pairs: int = 0

    @property
    def match_rate(self) -> float | None:
        denom = self.matched_pairs + self.mismatched_pairs
        return None if denom == 0 else self.matched_pairs / denom

    def to_dict(self) -> dict:
        result = asdict(self)
        result["match_rate"] = self.match_rate
        return result


def _sort_key(row: dict) -> tuple[str, int]:
    return str(row.get("race_date") or ""), int(row.get("race_no") or 0)


def _result_by_runner(result_rows: list[dict]) -> dict[str, dict]:
    return {str(row["runner_id"]): row for row in result_rows}


def _validate_record_group(
    history_rows: list[dict], result_lookup: dict[str, dict], *, field: str, group_fields: tuple[str, ...],
) -> ValidationMetric:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in history_rows:
        groups[tuple(row.get(name) for name in group_fields)].append(row)
    metric = ValidationMetric(field)
    for rows in groups.values():
        rows.sort(key=_sort_key)
        for previous, current in zip(rows, rows[1:]):
            prev_record = parse_record(previous.get(field))
            curr_record = parse_record(current.get(field))
            result = result_lookup.get(str(previous["runner_id"]))
            expected = _expected_delta(None if result is None else result.get("finish_position"))
            if prev_record is None or curr_record is None or expected is None:
                metric.skipped_pairs += 1
                continue
            delta = tuple(cur - prev for prev, cur in zip(prev_record, curr_record))
            metric.evidence_pairs += 1
            if delta == expected:
                metric.matched_pairs += 1
            else:
                metric.mismatched_pairs += 1
    return metric


def _validate_directional_record(
    history_rows: list[dict], result_lookup: dict[str, dict], *, field: str, required_direction: str,
) -> ValidationMetric:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in history_rows:
        groups[str(row.get("horse_key"))].append(row)
    metric = ValidationMetric(field)
    for rows in groups.values():
        rows.sort(key=_sort_key)
        for previous, current in zip(rows, rows[1:]):
            prev_record = parse_record(previous.get(field))
            curr_record = parse_record(current.get(field))
            result = result_lookup.get(str(previous["runner_id"]))
            finish = None if result is None else result.get("finish_position")
            expected_result = _expected_delta(finish)
            if prev_record is None or curr_record is None or expected_result is None:
                metric.skipped_pairs += 1
                continue
            is_target = (
                str(previous.get("surface") or "").strip() == "ダート"
                and str(previous.get("direction") or "").strip() == required_direction
            )
            expected = expected_result if is_target else (0, 0, 0, 0)
            delta = tuple(cur - prev for prev, cur in zip(prev_record, curr_record))
            metric.evidence_pairs += 1
            if delta == expected:
                metric.matched_pairs += 1
            else:
                metric.mismatched_pairs += 1
    return metric


def _validate_best_time(
    history_rows: list[dict], result_lookup: dict[str, dict], *, field: str, good_only: bool,
) -> ValidationMetric:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in history_rows:
        groups[(row.get("horse_key"), row.get("venue"), row.get("distance_m"))].append(row)
    metric = ValidationMetric(field)
    for rows in groups.values():
        rows.sort(key=_sort_key)
        for previous, current in zip(rows, rows[1:]):
            previous_best = previous.get(field)
            current_best = current.get(field)
            result = result_lookup.get(str(previous["runner_id"]))
            result_time = None if result is None else result.get("finish_time_seconds")
            finish = None if result is None else result.get("finish_position")
            if previous_best is None or current_best is None or result_time is None or finish is None:
                metric.skipped_pairs += 1
                continue
            if good_only and str(previous.get("track_condition") or "").strip() != "良":
                expected = previous_best
            else:
                expected = min(float(previous_best), float(result_time))
            metric.evidence_pairs += 1
            if abs(float(current_best) - expected) < 1e-9:
                metric.matched_pairs += 1
            else:
                metric.mismatched_pairs += 1
    return metric


def validate_history_asof(history_rows: list[dict], result_rows: list[dict]) -> dict:
    """Validate snapshot fields without promoting them automatically.

    The report is evidence only. FIELD_CATALOG keeps these fields PENDING until a broad-period
    audit is reviewed and explicitly promoted.
    """
    results = _result_by_runner(result_rows)
    metrics = [
        _validate_record_group(history_rows, results, field="overall_record_raw", group_fields=("horse_key",)),
        _validate_record_group(history_rows, results, field="jockey_record_raw", group_fields=("horse_key", "jockey_name")),
        _validate_record_group(history_rows, results, field="venue_record_raw", group_fields=("horse_key", "venue")),
        _validate_record_group(
            history_rows, results, field="venue_distance_record_raw", group_fields=("horse_key", "venue", "distance_m")
        ),
        _validate_directional_record(history_rows, results, field="dirt_left_record_raw", required_direction="左"),
        _validate_directional_record(history_rows, results, field="dirt_right_record_raw", required_direction="右"),
        _validate_best_time(history_rows, results, field="best_time_seconds", good_only=False),
        _validate_best_time(history_rows, results, field="best_time_good_seconds", good_only=True),
    ]
    return {
        "status": "evidence_only",
        "promotion": "manual_after_broad_period_review",
        "fields": {metric.field: metric.to_dict() for metric in metrics},
    }

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    name: str
    relative_path: str
    schema: dict[str, str]
    canonical_key: tuple[str, ...]
    partition_by: tuple[str, ...] = ("race_year",)
    non_null_columns: tuple[str, ...] = ()


BASE_RACE = {
    "race_id": "string",
    "race_date": "date32",
    "race_year": "int16",
    "venue": "string",
    "race_no": "int16",
}

BASE_RUNNER = {
    **BASE_RACE,
    "runner_id": "string",
    "horse_key": "string",
    "horse_no": "int16",
}

PRE_RACE_SCHEMA = {
    **BASE_RACE,
    "post_time": "string",
    "race_type_name": "string",
    "race_name": "string",
    **{f"prize_name_{i:02d}": "string" for i in range(1, 16)},
    "surface": "string",
    "direction": "string",
    "distance_m": "int32",
    "weather": "string",
    "track_condition": "string",
    "field_size": "int16",
    "conditions": "string",
    **{f"prize_yen_{i}": "int64" for i in range(1, 6)},
    "source_yyyymm": "string",
}

PRE_RUNNER_SCHEMA = {
    **BASE_RUNNER,
    "gate": "int16",
    "cap_color": "string",
    "horse_name": "string",
    "sex": "string",
    "age": "int16",
    "coat_color": "string",
    "birth_date": "date32",
    "sire_name": "string",
    "dam_name": "string",
    "damsire_name": "string",
    "jockey_name": "string",
    "jockey_affiliation": "string",
    "assigned_weight_raw": "string",
    "assigned_weight": "float64",
    "allowance_mark": "string",
    "trainer_name": "string",
    "trainer_affiliation": "string",
    "owner_name": "string",
    "breeder_name": "string",
    "body_weight_raw": "string",
    "body_weight_kg": "int32",
    "body_weight_change_raw": "string",
    "body_weight_change_kg": "int32",
    "source_yyyymm": "string",
}

PRE_RUNNER_HISTORY_SCHEMA = {
    **BASE_RUNNER,
    "distance_m": "int32",
    "surface": "string",
    "direction": "string",
    "track_condition": "string",
    "jockey_name": "string",
    "jockey_record_raw": "string",
    "overall_record_raw": "string",
    "dirt_left_record_raw": "string",
    "dirt_right_record_raw": "string",
    "venue_record_raw": "string",
    "venue_distance_record_raw": "string",
    "best_time_raw": "string",
    "best_time_seconds": "float64",
    "best_time_good_raw": "string",
    "best_time_good_seconds": "float64",
    "leakage_status": "string",
    "source_yyyymm": "string",
}

POST_RACE_RESULT_SCHEMA = {
    **BASE_RACE,
    "final_4f_raw": "string",
    "final_3f_raw": "string",
    **{f"furlong_time_{i:02d}": "string" for i in range(1, 16)},
    **{f"corner_name_{i:02d}": "string" for i in range(1, 9)},
    **{f"corner_order_{i:02d}": "string" for i in range(1, 9)},
    "source_yyyymm": "string",
}

POST_RUNNER_RESULT_SCHEMA = {
    **BASE_RUNNER,
    "finish_position_raw": "string",
    "finish_position": "int16",
    "finish_time_raw": "string",
    "finish_time_seconds": "float64",
    "margin": "string",
    "final_3f_raw": "string",
    "final_3f_seconds": "float64",
    "popularity": "int16",
    "source_yyyymm": "string",
}

POST_PAYOUT_SCHEMA = {
    **BASE_RACE,
    "payback_row_no": "int16",
    "bet_type": "string",
    "selection1": "string",
    "selection2": "string",
    "selection3": "string",
    "payout_yen": "int64",
    "popularity": "int16",
    "source_yyyymm": "string",
}

RACE_STATUS_SCHEMA = {
    **BASE_RACE,
    "status": "string",
    "is_model_target": "bool",
    "is_return_target": "bool",
    "reason": "string",
    "runner_count": "int16",
    "finish_count": "int16",
    "payback_row_count": "int16",
    "source_yyyymm": "string",
}

TABLE_SPECS = {
    "pre_race": TableSpec(
        "pre_race", "pre/race", PRE_RACE_SCHEMA, ("race_id",),
        non_null_columns=("race_id", "race_date", "race_year", "venue", "race_no"),
    ),
    "pre_runner": TableSpec(
        "pre_runner", "pre/runner", PRE_RUNNER_SCHEMA, ("runner_id",),
        non_null_columns=("race_id", "runner_id", "horse_key", "race_date", "venue", "race_no", "horse_no"),
    ),
    "pre_runner_history_snapshot": TableSpec(
        "pre_runner_history_snapshot", "pre/runner_history_snapshot", PRE_RUNNER_HISTORY_SCHEMA, ("runner_id",),
        non_null_columns=("race_id", "runner_id", "horse_key", "race_date", "venue", "race_no", "horse_no", "leakage_status"),
    ),
    "post_race_result": TableSpec(
        "post_race_result", "post/race_result", POST_RACE_RESULT_SCHEMA, ("race_id",),
        non_null_columns=("race_id", "race_date", "venue", "race_no"),
    ),
    "post_runner_result": TableSpec(
        "post_runner_result", "post/runner_result", POST_RUNNER_RESULT_SCHEMA, ("runner_id",),
        non_null_columns=("race_id", "runner_id", "horse_key", "race_date", "venue", "race_no", "horse_no"),
    ),
    "post_payout": TableSpec(
        "post_payout", "post/payout", POST_PAYOUT_SCHEMA,
        ("race_id", "payback_row_no", "bet_type", "selection1", "selection2", "selection3"),
        non_null_columns=("race_id", "race_date", "venue", "race_no", "payback_row_no", "bet_type"),
    ),
    "control_race_status": TableSpec(
        "control_race_status", "control/race_status", RACE_STATUS_SCHEMA, ("race_id",),
        non_null_columns=("race_id", "race_date", "venue", "race_no", "status"),
    ),
}


def table_spec(name: str) -> TableSpec:
    return TABLE_SPECS[name]

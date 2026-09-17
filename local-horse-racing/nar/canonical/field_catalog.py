from __future__ import annotations

from dataclasses import asdict, dataclass

from nar.schema import HORSELIST_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS

PRE_SAFE = "PRE_SAFE"
PRE_ASOF_PENDING = "PRE_ASOF_PENDING"
POST_ONLY = "POST_ONLY"

ENTRY = "ENTRY"
RACE_DAY = "RACE_DAY"
WEIGH_IN = "WEIGH_IN"
POST = "POST"

ALLOW = "ALLOW"
PENDING = "PENDING"
BLOCK = "BLOCK"


@dataclass(frozen=True)
class FieldPolicy:
    source_table: str
    source_field: str
    canonical_table: str
    canonical_field: str
    availability_class: str
    available_stage: str
    feature_policy: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RACE_PRE_ENTRY_MAP = {
    "競馬場": "venue",
    "競走年月日": "race_date",
    "レース番号": "race_no",
    "発走時刻": "post_time",
    "競走種類名称": "race_type_name",
    "レース名": "race_name",
    **{f"副賞名{i}": f"prize_name_{i:02d}" for i in range(1, 16)},
    "芝ダート区分": "surface",
    "回り": "direction",
    "距離": "distance_m",
    "頭数": "field_size",
    "条件": "conditions",
    **{f"{i}着賞金(円)": f"prize_yen_{i}" for i in range(1, 6)},
}

RACE_PRE_DAY_MAP = {
    "天候": "weather",
    "馬場": "track_condition",
}

RACE_POST_MAP = {
    "上がり4F": "final_4f_raw",
    "上がり3F": "final_3f_raw",
    **{f"ハロンタイム{i}": f"furlong_time_{i:02d}" for i in range(1, 16)},
    **{f"コーナー名称{i}": f"corner_name_{i:02d}" for i in range(1, 9)},
    **{f"コーナー通過順{i}": f"corner_order_{i:02d}" for i in range(1, 9)},
}

RUNNER_PRE_ENTRY_MAP = {
    "競馬場": "venue",
    "競走年月日": "race_date",
    "レース番号": "race_no",
    "枠番": "gate",
    "帽色": "cap_color",
    "馬番": "horse_no",
    "馬名": "horse_name",
    "性": "sex",
    "齢": "age",
    "毛色": "coat_color",
    "生年月日": "birth_date",
    "父馬名": "sire_name",
    "母馬名": "dam_name",
    "母父馬名": "damsire_name",
    "騎手名": "jockey_name",
    "騎手所属": "jockey_affiliation",
    "負担重量": "assigned_weight_raw",
    "調教師": "trainer_name",
    "調教師所属": "trainer_affiliation",
    "馬主氏名": "owner_name",
    "生産牧場名": "breeder_name",
}

RUNNER_PRE_WEIGH_MAP = {
    "馬体重": "body_weight_raw",
    "馬体重増減": "body_weight_change_raw",
}

RUNNER_HISTORY_MAP = {
    "騎手成績": "jockey_record_raw",
    "全成績": "overall_record_raw",
    "ダート左成績": "dirt_left_record_raw",
    "ダート右成績": "dirt_right_record_raw",
    "当競馬場成績": "venue_record_raw",
    "うち当距離成績": "venue_distance_record_raw",
    "最高タイム": "best_time_raw",
    "最高タイム良馬場": "best_time_good_raw",
}

RUNNER_POST_MAP = {
    "着順": "finish_position_raw",
    "タイム": "finish_time_raw",
    "着差": "margin",
    "上がり3F": "final_3f_raw",
    "人気": "popularity",
}


def _make_catalog() -> tuple[FieldPolicy, ...]:
    rows: list[FieldPolicy] = []

    for raw, canonical in RACE_PRE_ENTRY_MAP.items():
        rows.append(FieldPolicy("racelist", raw, "pre_race", canonical, PRE_SAFE, ENTRY, ALLOW))
    for raw, canonical in RACE_PRE_DAY_MAP.items():
        rows.append(FieldPolicy(
            "racelist", raw, "pre_race", canonical, PRE_SAFE, RACE_DAY, ALLOW,
            "Historical monthly files do not encode the exact observation timestamp; use only for race-day/pre-bet policies.",
        ))
    for raw, canonical in RACE_POST_MAP.items():
        rows.append(FieldPolicy("racelist", raw, "post_race_result", canonical, POST_ONLY, POST, BLOCK))

    for raw, canonical in RUNNER_PRE_ENTRY_MAP.items():
        rows.append(FieldPolicy("horselist", raw, "pre_runner", canonical, PRE_SAFE, ENTRY, ALLOW))
    for raw, canonical in RUNNER_PRE_WEIGH_MAP.items():
        rows.append(FieldPolicy(
            "horselist", raw, "pre_runner", canonical, PRE_SAFE, WEIGH_IN, ALLOW,
            "Available only after official body-weight publication; exclude from entry-stage models.",
        ))
    for raw, canonical in RUNNER_HISTORY_MAP.items():
        rows.append(FieldPolicy(
            "horselist", raw, "pre_runner_history_snapshot", canonical,
            PRE_ASOF_PENDING, ENTRY, PENDING,
            "Candidate pre-race snapshot. Block from model features until longitudinal as-of validation passes.",
        ))
    for raw, canonical in RUNNER_POST_MAP.items():
        notes = ""
        if raw == "人気":
            notes = "Observed unstable/placeholder values before result finalization; treat as post-market metadata and block from pre-race features."
        rows.append(FieldPolicy("horselist", raw, "post_runner_result", canonical, POST_ONLY, POST, BLOCK, notes))

    for raw in PAYBACK_COLUMNS:
        rows.append(FieldPolicy(
            "payback", raw, "post_payout", raw, POST_ONLY, POST, BLOCK,
            "Evaluation-only return data; never expose to feature generation.",
        ))

    _assert_complete(rows)
    return tuple(rows)


def _assert_complete(rows: list[FieldPolicy]) -> None:
    actual = {
        "racelist": {row.source_field for row in rows if row.source_table == "racelist"},
        "horselist": {row.source_field for row in rows if row.source_table == "horselist"},
        "payback": {row.source_field for row in rows if row.source_table == "payback"},
    }
    expected = {
        "racelist": set(RACELIST_COLUMNS),
        "horselist": set(HORSELIST_COLUMNS),
        "payback": set(PAYBACK_COLUMNS),
    }
    for table in expected:
        missing = expected[table] - actual[table]
        extra = actual[table] - expected[table]
        if missing or extra:
            raise RuntimeError(f"field catalog mismatch for {table}: missing={sorted(missing)!r} extra={sorted(extra)!r}")


FIELD_CATALOG = _make_catalog()


def catalog_rows() -> list[dict]:
    return [row.to_dict() for row in FIELD_CATALOG]


def feature_allowed(source_table: str, source_field: str, stage: str) -> bool:
    match = next((row for row in FIELD_CATALOG if row.source_table == source_table and row.source_field == source_field), None)
    if match is None or match.feature_policy != ALLOW:
        return False
    order = {ENTRY: 0, RACE_DAY: 1, WEIGH_IN: 2, POST: 3}
    return order[match.available_stage] <= order[stage]

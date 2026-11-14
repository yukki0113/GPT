"""Fail-closed, read-only JRDB Analysis v1.4 QuerySpec -> SELECT compiler.

The Parquet engine is always tools/data-storage; this file owns only JRDB semantics.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from data_storage.common import sql_literal

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "niche_query"
ALLOWED = json.loads((CONFIG_ROOT / "allowed_fields_v1.json").read_text(encoding="utf-8"))
METRIC_RULES = json.loads((CONFIG_ROOT / "aggregations_v1.json").read_text(encoding="utf-8"))
FIELDS = ALLOWED["fields"]
SUPPORTED_METRICS = METRIC_RULES["supported_metrics"]
DEFAULT_METRICS = list(SUPPORTED_METRICS)
TEXT_NORMALIZED = {"horse_name", "jockey_name", "sire_name", "broodmare_sire_name"}


class SpecError(ValueError):
    pass


def _object(value: Any, *, allowed: set[str], required: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise SpecError(f"Invalid object fields (expected {sorted(allowed)}, required {sorted(required)})")
    return value


def _date(value: str, key: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise SpecError(f"{key} must be YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise SpecError(f"Invalid {key}") from exc
    return value


def _typed_value(field: str, value: Any) -> str:
    kind = FIELDS[field]
    if kind == "integer":
        if type(value) is not int or not -(10 ** 8) <= value <= 10 ** 8:
            raise SpecError(f"{field}: expected bounded integer")
        return str(value)
    if not isinstance(value, str) or not value or len(value) > 180 or any(ord(c) < 32 for c in value):
        raise SpecError(f"{field}: expected non-empty safe text <= 180 chars")
    return sql_literal(value)


def _column(field: str) -> str:
    if field not in FIELDS:
        raise SpecError(f"Unknown field: {field}")
    if field == "track_condition":
        return "CASE WHEN TRIM(COALESCE(CAST(track_condition_code AS VARCHAR),'')) IN ('1','10','11','12') THEN '良' " \
               "WHEN TRIM(COALESCE(CAST(track_condition_code AS VARCHAR),'')) IN ('2','20','21','22') THEN '稍重' " \
               "WHEN TRIM(COALESCE(CAST(track_condition_code AS VARCHAR),'')) IN ('3','30','31','32') THEN '重' " \
               "WHEN TRIM(COALESCE(CAST(track_condition_code AS VARCHAR),'')) IN ('4','40','41','42') THEN '不良' ELSE '不明' END"
    # Field identifiers are from a literal allowlist (never user-controlled SQL).
    col = '"' + field + '"'
    if field in TEXT_NORMALIZED:
        return f"TRIM(REPLACE(COALESCE({col}, ''), '　', ''))"
    if field == "race_condition_code":
        return f"UPPER(TRIM(COALESCE({col}, '')))"
    return col


def _validate_filter(f: Any) -> dict:
    f = _object(f, allowed={"field", "op", "value"}, required={"field", "op", "value"})
    field, op, value = f["field"], f["op"], f["value"]
    if not isinstance(field, str) or field not in FIELDS or op not in ALLOWED["filter_ops"]:
        raise SpecError("Unknown filter field/operator")
    if op in ("in", "between"):
        if not isinstance(value, list) or len(value) < (2 if op == "between" else 1) or len(value) > (2 if op == "between" else 30):
            raise SpecError(f"Invalid {op} list")
        [_typed_value(field, v) for v in value]
        if op == "between" and value[0] > value[1]:
            raise SpecError("between bounds reversed")
    else:
        _typed_value(field, value)
    return f


def _validate_grouping(g: Any) -> dict:
    g = _object(g, allowed={"field", "kind", "bands", "other_bucket"}, required={"field"})
    field = g["field"]
    if field not in FIELDS:
        raise SpecError("Unknown grouping field")
    kind = g.get("kind", "field")
    if kind == "field":
        if "bands" in g or "other_bucket" in g:
            raise SpecError("bands options not allowed for field grouping")
        return g
    if kind != "bands" or FIELDS[field] != "integer":
        raise SpecError("bands only allowed for integer fields")
    if g.get("other_bucket", "excluded_with_count") not in ("excluded_with_count", "included"):
        raise SpecError("Invalid other_bucket")
    bands = g.get("bands")
    if not isinstance(bands, list) or not 1 <= len(bands) <= ALLOWED["max_bands"]:
        raise SpecError("Invalid number of bands")
    limits = []
    labels = set()
    for band in bands:
        _object(band, allowed={"label", "min", "max"}, required={"label", "min", "max"})
        label, lo, hi = band["label"], band["min"], band["max"]
        if not isinstance(label, str) or not 1 <= len(label) <= 60 or label in labels or label == "__OUT_OF_BAND__":
            raise SpecError("Invalid/duplicate band label")
        labels.add(label)
        if type(lo) is not int or (hi is not None and type(hi) is not int) or (hi is not None and hi < lo):
            raise SpecError("Invalid band bounds")
        limits.append((lo, hi))
    for i, (a, b) in enumerate(limits):
        for c, d in limits[i + 1:]:
            if (b is None or c <= b) and (d is None or a <= d):
                raise SpecError("Overlapping bands")
    return g


def validate_spec(spec: dict) -> dict:
    _object(spec, allowed={"dataset", "as_of_generation", "date_from", "date_to", "filters", "groupings", "metrics", "detail", "detail_limit"},
            required={"dataset", "as_of_generation", "date_from", "date_to", "filters", "groupings"})
    if spec["dataset"] != "jrdb.analysis.current" or spec["as_of_generation"] != "CURRENT_AT_REQUEST":
        raise SpecError("Unsupported dataset or generation policy")
    start, end = _date(spec["date_from"], "date_from"), _date(spec["date_to"], "date_to")
    if start > end:
        raise SpecError("date_from after date_to")
    filters, groups = spec["filters"], spec["groupings"]
    if not isinstance(filters, list) or len(filters) > ALLOWED["max_filters"]:
        raise SpecError("Invalid filters")
    if not isinstance(groups, list) or len(groups) > ALLOWED["max_groupings"]:
        raise SpecError("Invalid groupings")
    [_validate_filter(f) for f in filters]
    [_validate_grouping(g) for g in groups]
    metrics = spec.get("metrics", DEFAULT_METRICS)
    if not isinstance(metrics, list) or any(not isinstance(m, str) for m in metrics) or len(set(metrics)) != len(metrics) or not set(metrics) <= set(SUPPORTED_METRICS):
        raise SpecError("Invalid metrics")
    if type(spec.get("detail", False)) is not bool:
        raise SpecError("detail must be boolean")
    n = spec.get("detail_limit", 500)
    if type(n) is not int or not 1 <= n <= 1000:
        raise SpecError("detail_limit must be 1..1000")
    return spec


def _filter_sql(f: dict) -> str:
    field, op, value = f["field"], f["op"], f["value"]
    col = _column(field)
    if op in ("eq", "ne", "gte", "lte"):
        operator = {"eq":"=", "ne":"<>", "gte":">=", "lte":"<="}[op]
        return f"({col} {operator} {_typed_value(field,value)})"
    if op == "in":
        return f"({col} IN ({', '.join(_typed_value(field,v) for v in value)}))"
    return f"({col} BETWEEN {_typed_value(field,value[0])} AND {_typed_value(field,value[1])})"


def _group_sql(g: dict) -> str:
    col = _column(g["field"])
    if g.get("kind", "field") == "field":
        return f"COALESCE(CAST(({col}) AS VARCHAR), '不明')"
    arms = []
    for b in g["bands"]:
        upper = f" AND {col} <= {b['max']}" if b["max"] is not None else ""
        arms.append(f"WHEN {col} >= {b['min']}{upper} THEN {sql_literal(b['label'])}")
    default = "__OUT_OF_BAND__" if g.get("other_bucket", "excluded_with_count") == "excluded_with_count" else "その他"
    return "CASE " + " ".join(arms) + f" ELSE {sql_literal(default)} END"


def build_sql(spec: dict) -> dict[str, str]:
    validate_spec(spec)
    predicates = [f'"race_date" BETWEEN {sql_literal(spec["date_from"])} AND {sql_literal(spec["date_to"])}']
    predicates.extend(_filter_sql(f) for f in spec["filters"])
    where = " AND ".join(predicates)
    groups = spec["groupings"]
    select_groups = ", ".join(f"{_group_sql(g)} AS g{i}" for i,g in enumerate(groups))
    group_cte = f"SELECT *, {select_groups} FROM data WHERE {where}" if groups else f"SELECT * FROM data WHERE {where}"
    cte = f"WITH filtered AS ({group_cte})"
    started = "(TRIM(COALESCE(CAST(abnormal_code AS VARCHAR),'')) NOT IN ('1','01','2','02'))"
    n = f"COUNT(*) FILTER (WHERE {started})"
    win = f"COUNT(*) FILTER (WHERE {started} AND finish=1)"
    second = f"COUNT(*) FILTER (WHERE {started} AND finish=2)"
    third = f"COUNT(*) FILTER (WHERE {started} AND finish=3)"
    expressions = {
       "win":win, "second":second, "third":third,
       "other":f"COUNT(*) FILTER (WHERE {started} AND (finish NOT IN (1,2,3) OR finish IS NULL))",
       "win_rate":f"ROUND(100.0*({win})/NULLIF({n},0),2)",
       "top2_rate":f"ROUND(100.0*({win}+{second})/NULLIF({n},0),2)",
       "top3_rate":f"ROUND(100.0*({win}+{second}+{third})/NULLIF({n},0),2)",
       "win_roi":f"ROUND(SUM(CASE WHEN {started} THEN COALESCE(win_payout,0) ELSE 0 END)*1.0/NULLIF({n},0),2)",
       "place_roi":f"ROUND(SUM(CASE WHEN {started} THEN COALESCE(place_payout,0) ELSE 0 END)*1.0/NULLIF({n},0),2)",
    }
    cols = ["COUNT(*) AS entries", f"{n} AS starts", f"COUNT(*) FILTER (WHERE NOT {started}) AS cancelled",
            "COUNT(DISTINCT horse_id) AS horses"]
    cols += [f"{expressions[m]} AS {m}" for m in spec.get("metrics", DEFAULT_METRICS)]
    if groups:
        gn = [f"g{i}" for i in range(len(groups))]
        conditions = [f"g{i} <> '__OUT_OF_BAND__'" for i,g in enumerate(groups) if g.get("kind") == "bands" and g.get("other_bucket", "excluded_with_count") == "excluded_with_count"]
        group_filter = " WHERE " + " AND ".join(conditions) if conditions else ""
        summary = cte + " SELECT " + ", ".join(gn + cols) + " FROM filtered" + group_filter + " GROUP BY " + ", ".join(gn) + " ORDER BY " + ", ".join(gn)
    else:
        summary = cte + " SELECT '全体' AS segment, " + ", ".join(cols) + " FROM filtered"
    excluded = " OR ".join(f"g{i}='__OUT_OF_BAND__'" for i,g in enumerate(groups) if g.get("kind") == "bands" and g.get("other_bucket", "excluded_with_count") == "excluded_with_count") or "FALSE"
    audit = cte + f""" SELECT COUNT(*) AS matching_entries, {n} AS starts, COUNT(*) FILTER (WHERE NOT {started}) AS cancelled,
        COUNT(*) FILTER (WHERE {excluded}) AS excluded_band_entries,
        COUNT(*) FILTER (WHERE {started} AND finish IS NULL) AS missing_finish_started,
        COUNT(*) FILTER (WHERE {started} AND finish=1 AND win_payout IS NULL) AS missing_win_payout_winner,
        COUNT(*) FILTER (WHERE {started} AND finish IN (1,2,3) AND place_payout IS NULL) AS missing_place_payout_top3,
        COUNT(*) FILTER (WHERE TRIM(COALESCE(CAST(abnormal_code AS VARCHAR),'')) NOT IN ('','0','00','1','01','2','02','3','03','4','04','5','05','6','06')) AS unknown_abnormal_code,
        COALESCE(SUM(CASE WHEN {started} THEN COALESCE(win_payout,0) ELSE 0 END),0) AS win_payout_total,
        COALESCE(SUM(CASE WHEN {started} THEN COALESCE(place_payout,0) ELSE 0 END),0) AS place_payout_total FROM filtered"""
    # No user-selected column reaches this detail query other than validated filters.
    detail = (cte + f" SELECT race_date, race_key, race_no, horse_no, horse_id, horse_name, age, sire_name, jockey_name, track_type, distance, race_condition_code, grade_code, track_condition_code, final_win_popularity, final_win_odds, finish, abnormal_code, win_payout, place_payout"
              + (", " + ", ".join(f"g{i}" for i in range(len(groups))) if groups else "")
              + " FROM filtered ORDER BY race_date, race_key, horse_no LIMIT " + str(spec.get("detail_limit",500)))
    return {"summary":summary,"audit":audit,"detail":detail}
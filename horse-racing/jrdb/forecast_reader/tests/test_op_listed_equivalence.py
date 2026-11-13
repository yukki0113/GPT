"""Regression checks for strict OP/Listed class equivalence in sampling."""
import importlib.util
from datetime import date
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "src" / "sampling.py"
spec = importlib.util.spec_from_file_location("forecast_sampling_class_equivalence", MODULE)
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)

RULES = {
    "schema_version": "forecast-sampling-rules.v1",
    "exact_threshold": 10,
    "target_races": 10,
    "supplement_per_year": 0,
    "stages": [
        {"name": "S1", "days": 21, "relax_fields": []},
        {"name": "S2", "days": 21, "relax_fields": ["weight_rule"]},
        {"name": "S3", "days": 21, "relax_fields": ["weight_rule", "eligibility"]},
        {"name": "S4", "days": 42, "relax_fields": ["weight_rule", "eligibility"]},
    ],
}

def race(key, year, klass="OP:6", weight="1", venue="08", name="アンドロメダステークス"):
    return {
        "race_key": key,
        "date": f"{year}-11-14",
        "name": name,
        "venue": venue,
        "surface": "1",
        "distance": 2000,
        "race_class": klass,
        "eligibility": "13:100",
        "course": "1:1",
        "weight_rule": weight,
    }

def test_op_and_listed_are_equivalent_without_overwriting_raw_identity():
    target = race("08265310", 2026)
    records = [race("r2016", 2016, "OP:5"), race("r2019", 2019, "OP:6"),
               race("r2020", 2020, "OP:L")]
    result = sampling.select(target, records, RULES)
    assert result["exact_count"] == 3
    assert result["exact_race_keys"] == ["r2016", "r2019", "r2020"]
    audited = {r["race_key"]: r for r in result["candidates"]}
    assert audited["r2016"]["class_identity"] == "OP:5"
    assert audited["r2016"]["class_equivalence_applied"] is True
    assert audited["r2019"]["class_equivalence_applied"] is False
    assert audited["r2020"]["class_equivalence_applied"] is True

def test_op_listed_equivalence_does_not_relax_weight_or_venue():
    target = race("08265310", 2026)
    records = [race("different-weight", 2025, "OP:5", weight="4"),
               race("different-venue", 2024, "OP:5", venue="09")]
    result = sampling.select(target, records, RULES)
    assert result["exact_count"] == 0
    assert result["selected_stage"] == "S2"
    assert result["supplement_race_keys"] == ["different-weight"]
    assert "different-venue" not in result["supplement_race_keys"]

def test_graded_races_not_merged_with_op():
    target = race("08265310", 2026)
    records = [race("g3", 2025, "OP:3"), race("three-win", 2024, "16:5")]
    result = sampling.select(target, records, RULES)
    assert result["total_selected"] == 0
    assert all("race_class" in r["condition_mismatches"] for r in result["candidates"])

def test_unknown_classes_remain_ineligible():
    target = race("08265310", 2026)
    records = [race("missing", 2025, "UNKNOWN_CLASS")]
    result = sampling.select(target, records, RULES)
    assert result["total_selected"] == 0

def test_non_open_classes_still_require_identity():
    target = race("08265310", 2026, "16:5")
    records = [race("opp", 2025, "OP:5"), race("listed", 2024, "OP:6")]
    result = sampling.select(target, records, RULES)
    assert result["total_selected"] == 0

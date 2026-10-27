"""Fail-closed contract tests for RaceNote pseudo-batch controller."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "racenote_v055_batch_controller.py"
spec = importlib.util.spec_from_file_location("batch_controller", SOURCE)
bc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bc
spec.loader.exec_module(bc)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bc.canonical(value))


def fixture_day(base, ident, target_date, grades, *, pred_only=False):
    folder = base / ident
    write(folder / "selection.json", {
        "selection_id": ident, "n": 1, "dates": [target_date]
    })
    root = folder / target_date.replace("-", "")
    write(root / "operation_handoff.json", {
        "status": "READY_FOR_V055_AUTHORING", "selection_id": ident,
        "target_date": target_date, "logic_version": bc.LOGIC,
        "contract_revision": bc.CONTRACT, "session_id": f"V055-{ident}",
        "race_count": len(grades), "result_opened": False,
        "target_market_opened": False, "market_blind": True,
        "authoring_bundle_status": "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
    })
    root = root / "v055"
    pred = [{
        "selection_id": ident, "target_date": target_date,
        "session_id": f"V055-{ident}", "venue": "東京", "race_no": i,
        "decision_core": {"marks": [i, 20, 21, 22, 23]},
    } for i in range(1, len(grades) + 1)]
    conf = [{"venue": "東京", "race_no": i, "honmei": i, "confidence": g}
            for i, g in enumerate(grades, 1)]
    write(root / "frozen/records.json", pred)
    write(root / "frozen/authoring_quality_report.json", {"status": "PASS"})
    psha = bc.digest((root / "frozen/records.json").read_bytes())
    qsha = bc.digest((root / "frozen/authoring_quality_report.json").read_bytes())
    write(root / "frozen/day_handoff.json", {
        "status": bc.PRED, "validator_status": "PASS", "confidence_pending": True,
        "selection_id": ident, "target_date": target_date,
        "session_id": f"V055-{ident}", "contract_revision": bc.CONTRACT,
        "record_count": len(grades), "records_sha256": psha,
        "authoring_quality_report_sha256": qsha,
        "result_opened": False, "target_market_opened": False, "market_blind": True,
    })
    if pred_only:
        return root
    write(root / "confidence_frozen/records.json", conf)
    csha = bc.digest((root / "confidence_frozen/records.json").read_bytes())
    write(root / "confidence_frozen/day_handoff.json", {
        "status": bc.CONF, "confidence_frozen": True,
        "prediction_freeze_status": bc.PRED,
        "confidence_meaning": "HONMEI_WIN_CONFIDENCE",
        "selection_id": ident, "target_date": target_date,
        "session_id": f"V055-{ident}", "contract_revision": bc.CONTRACT,
        "record_count": len(grades), "prediction_records_sha256": psha,
        "confidence_records_sha256": csha,
        "result_opened": False, "target_market_opened": False, "market_blind": True,
    })
    from collections import Counter
    write(root / "turn2_summary.json", {
        "status": bc.DONE, "selection_id": ident,
        "target_date": target_date, "session_id": f"V055-{ident}",
        "record_count": len(grades), "authoring_quality": "PASS",
        "prediction_status": bc.PRED, "confidence_status": bc.CONF,
        "prediction_origin": "LLM_RACE_BY_RACE",
        "automated_prediction": False, "automated_scoring": False,
        "confidence_counts": dict(Counter(grades)),
        "prediction_records_sha256": psha, "confidence_records_sha256": csha,
        "result_opened": False, "target_market_opened": False,
    })
    return root


def batch(base, *, mode="confidence_count", target_count=3,
          days=None, cap=None, name="V055-BATCH-TEST"):
    return bc.init(base, name, "BTDAY-0136", mode, target_count, "A", days, cap)


def test_confidence_target_whole_btday_and_immutable_seal(tmp_path):
    batch(tmp_path)
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "PICK"
    fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A", "B", "A"])
    first = bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)
    assert first["progress"]["confidence_counts"]["A"] == 2
    assert first["progress"]["next_selection_id"] == "BTDAY-0137"
    assert first["next_action"] == "PICK"
    # Resume does not recount already completed days.
    again = bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)
    assert again["progress"]["completed_btday_count"] == 1
    fixture_day(tmp_path, "BTDAY-0137", "2025-01-02", ["B", "A", "A"])
    ready = bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)
    assert ready["status"] == "READY_TO_SEAL"
    assert ready["progress"]["confidence_counts"]["A"] == 4
    sealed = bc.seal(tmp_path, "V055-BATCH-TEST")
    assert sealed["status"] == bc.SEALED
    assert sealed["cohort_count"] == 4
    assert sealed["selection_count"] == 2
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "COMPLETE"
    with pytest.raises(ValueError, match="already exists|Another"):
        batch(tmp_path)
    with pytest.raises(FileExistsError, match="Immutable"):
        bc.seal(tmp_path, "V055-BATCH-TEST")


def test_two_day_limit_and_only_A_cohort(tmp_path):
    batch(tmp_path, mode="btday_count", days=2)
    fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["B", "C", "Z"])
    fixture_day(tmp_path, "BTDAY-0137", "2025-01-02", ["A", "B"])
    assert bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)["next_action"] == "SEAL"
    seal = bc.seal(tmp_path, "V055-BATCH-TEST")
    assert seal["selection_count"] == 2 and seal["cohort_count"] == 1


def test_either_safety_limit(tmp_path):
    batch(tmp_path, mode="either", target_count=99, cap=2)
    fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["B"])
    fixture_day(tmp_path, "BTDAY-0137", "2025-01-02", ["A"])
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "SEAL"
    assert bc.seal(tmp_path, "V055-BATCH-TEST")["cohort_count"] == 1


def test_pending_phases_and_clean_blind_guard(tmp_path):
    batch(tmp_path, mode="btday_count", days=1)
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "PICK"
    folder = tmp_path / "BTDAY-0136"
    write(folder / "selection.json", {
        "selection_id": "BTDAY-0136", "n": 1, "dates": ["2025-01-01"]
    })
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "T1"
    root = fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A"], pred_only=True)
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "T2_CONFIDENCE"
    write(root / "confidence_frozen/day_handoff.json", {"status": bc.CONF})
    assert bc.inspect(tmp_path, "V055-BATCH-TEST")["next_action"] == "T2_VERIFY"
    write(root / "turn2_summary.json", {"status": bc.DONE, "result_opened": True})
    with pytest.raises(ValueError, match="Clean-blind"):
        bc.inspect(tmp_path, "V055-BATCH-TEST")


def test_tamper_blocks_sync_and_sealed_verify(tmp_path):
    batch(tmp_path, mode="btday_count", days=1)
    root = fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A"])
    target = root / "confidence_frozen/records.json"
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA"):
        bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)
    assert bc.load(tmp_path / "batches/V055-BATCH-TEST/batch_manifest.json")["completed_sessions"] == []


def test_frozen_honmei_mismatch_and_auto_prediction_fail_closed(tmp_path):
    batch(tmp_path, mode="btday_count", days=1)
    root = fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A"])
    rows = bc.load(root / "confidence_frozen/records.json")
    rows[0]["honmei"] = 17
    write(root / "confidence_frozen/records.json", rows)
    digest = bc.digest((root / "confidence_frozen/records.json").read_bytes())
    handoff = bc.load(root / "confidence_frozen/day_handoff.json")
    handoff["confidence_records_sha256"] = digest
    write(root / "confidence_frozen/day_handoff.json", handoff)
    summary = bc.load(root / "turn2_summary.json")
    summary["confidence_records_sha256"] = digest
    write(root / "turn2_summary.json", summary)
    with pytest.raises(ValueError, match="honmei mismatch"):
        bc.inspect(tmp_path, "V055-BATCH-TEST")
    rows[0]["honmei"] = 1
    write(root / "confidence_frozen/records.json", rows)
    digest = bc.digest((root / "confidence_frozen/records.json").read_bytes())
    handoff["confidence_records_sha256"] = digest
    summary["confidence_records_sha256"] = digest
    summary["automated_prediction"] = True
    write(root / "confidence_frozen/day_handoff.json", handoff)
    write(root / "turn2_summary.json", summary)
    with pytest.raises(ValueError, match="TURN2"):
        bc.inspect(tmp_path, "V055-BATCH-TEST")


def test_previously_observed_session_mutation_fails(tmp_path):
    batch(tmp_path, mode="btday_count", days=2)
    fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A"])
    bc.inspect(tmp_path, "V055-BATCH-TEST", persist=True)
    root = tmp_path / "BTDAY-0136/20250101/v055"
    summary = bc.load(root / "turn2_summary.json")
    summary["confidence_counts"] = {"B": 1}
    write(root / "turn2_summary.json", summary)
    with pytest.raises(ValueError, match="summary disagrees"):
        bc.inspect(tmp_path, "V055-BATCH-TEST")


def test_wrong_arguments_rejected_before_state_created(tmp_path):
    with pytest.raises(ValueError, match="Invalid BTDAY target"):
        batch(tmp_path, mode="btday_count", days=0)
    with pytest.raises(ValueError, match="Invalid confidence target"):
        batch(tmp_path, target_count=-1)
    with pytest.raises(ValueError, match="Invalid safety day limit"):
        batch(tmp_path, mode="either", target_count=5, cap=None)
    assert not (tmp_path / "batches").exists()


def test_sealed_cohort_tamper_detected(tmp_path):
    batch(tmp_path, mode="btday_count", days=1)
    fixture_day(tmp_path, "BTDAY-0136", "2025-01-01", ["A", "Z"])
    bc.seal(tmp_path, "V055-BATCH-TEST")
    cohort = tmp_path / "batches/V055-BATCH-TEST/confidence_A_cohort.json"
    cohort.write_bytes(cohort.read_bytes() + b" ")
    with pytest.raises(ValueError, match="cohort seal invalid"):
        bc.inspect(tmp_path, "V055-BATCH-TEST")

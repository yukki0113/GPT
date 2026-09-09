from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_jrdb_edge_forward_ledger as ledger  # noqa: E402


def _occurrence(
    *,
    edge_id: str = "EDGE-A",
    horse_no: int = 1,
    place_payout: int = 160,
    race_date: str = "2026-09-05",
    race_key: str = "01262501",
    evaluation_mode: str = "TRUE_FORWARD",
) -> dict:
    return {
        "runner_identity": f"{race_key}:{horse_no:02d}",
        "race_date": race_date,
        "horse_id": f"2310000{horse_no}",
        "edge_id": edge_id,
        "display_text": edge_id,
        "family": "COURSE",
        "polarity": "POSITIVE",
        "status": "ACTIVE",
        "review_due": False,
        "registry_version": "phase1-full",
        "strength_score": 0.8,
        "confidence_band": "HIGH",
        "evaluator_version": "0.3.0",
        "evaluation_mode": evaluation_mode,
        "eligibility": "ELIGIBLE",
        "evidence": {
            "family": "COURSE",
            "place_rate": 0.30,
            "place_roi": 0.80,
            "baseline_place_rate": 0.20,
        },
        "outcome": {
            "race_key": race_key,
            "horse_no": horse_no,
            "horse_id": f"2310000{horse_no}",
            "race_date": race_date,
            "finish": 1 if horse_no == 1 else 5,
            "abnormal_code": "0",
            "win_payout": 350 if horse_no == 1 else 0,
            "place_payout": place_payout,
        },
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_import_and_cumulative_summary(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    _write(audit, [_occurrence(), _occurrence(edge_id="EDGE-B", horse_no=2, place_payout=0)])
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        imported = ledger.import_daily_audit(connection, audit)
        report = ledger.summarize(connection)
    finally:
        connection.close()
    assert imported["status"] == "IMPORTED"
    assert imported["evaluation_mode"] == "TRUE_FORWARD"
    assert report["evaluation_mode"] == "TRUE_FORWARD"
    assert report["date_range"] == {"from": "2026-09-05", "to": "2026-09-05", "days": 1, "zero_match_days": 0}
    assert report["available_evaluation_modes"]["TRUE_FORWARD"] == {"days": 1, "occurrences": 2}
    assert report["overall"]["eligible"] == 2
    assert report["overall"]["win_rate"] == pytest.approx(0.5)
    assert report["overall"]["place_rate"] == pytest.approx(0.5)
    assert report["overall"]["win_roi"] == pytest.approx(1.75)
    assert report["overall"]["place_roi"] == pytest.approx(0.8)
    assert report["overall"]["place_rate_vs_historical"] == pytest.approx(0.2)
    assert report["by_edge_registry"]["EDGE-A|phase1-full"]["eligible"] == 1


def test_reconstructed_backfill_is_segregated_from_default_summary(tmp_path: Path) -> None:
    true_audit = tmp_path / "true.jsonl"
    backfill_audit = tmp_path / "backfill.jsonl"
    _write(true_audit, [_occurrence(place_payout=160)])
    _write(backfill_audit, [_occurrence(
        race_date="2026-09-06",
        race_key="01262601",
        place_payout=0,
        evaluation_mode="RECONSTRUCTED_BACKFILL",
    )])
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        ledger.import_daily_audit(connection, true_audit)
        ledger.import_daily_audit(connection, backfill_audit)
        primary = ledger.summarize(connection)
        backfill = ledger.summarize(connection, evaluation_mode="RECONSTRUCTED_BACKFILL")
        all_modes = ledger.summarize(connection, evaluation_mode="ALL")
    finally:
        connection.close()
    assert primary["date_range"]["days"] == 1
    assert primary["overall"]["eligible"] == 1
    assert primary["overall"]["place_hits"] == 1
    assert backfill["date_range"]["days"] == 1
    assert backfill["overall"]["eligible"] == 1
    assert backfill["overall"]["place_hits"] == 0
    assert all_modes["date_range"]["days"] == 2
    assert all_modes["overall"]["eligible"] == 2
    assert all_modes["available_evaluation_modes"]["TRUE_FORWARD"]["days"] == 1
    assert all_modes["available_evaluation_modes"]["RECONSTRUCTED_BACKFILL"]["days"] == 1


def test_missing_mode_in_legacy_audit_is_normalized(tmp_path: Path) -> None:
    audit = tmp_path / "legacy.jsonl"
    row = _occurrence()
    row.pop("evaluation_mode")
    _write(audit, [row])
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        imported = ledger.import_daily_audit(connection, audit)
        legacy = ledger.summarize(connection, evaluation_mode="LEGACY_UNSPECIFIED")
        primary = ledger.summarize(connection)
    finally:
        connection.close()
    assert imported["evaluation_mode"] == "LEGACY_UNSPECIFIED"
    assert legacy["overall"]["eligible"] == 1
    assert primary["overall"]["eligible"] == 0


def test_semantically_identical_reimport_is_noop(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    row = _occurrence()
    _write(first, [row])
    second.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2).replace("\n", "") + "\n", encoding="utf-8")
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        assert ledger.import_daily_audit(connection, first)["status"] == "IMPORTED"
        assert ledger.import_daily_audit(connection, second)["status"] == "NOOP"
    finally:
        connection.close()


def test_conflicting_same_day_fails_closed(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write(first, [_occurrence(place_payout=160)])
    _write(second, [_occurrence(place_payout=170)])
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        ledger.import_daily_audit(connection, first)
        with pytest.raises(ledger.LedgerError, match="immutable forward day conflict"):
            ledger.import_daily_audit(connection, second)
    finally:
        connection.close()


def test_duplicate_occurrence_in_one_audit_is_rejected(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    row = _occurrence()
    _write(audit, [row, row])
    with pytest.raises(ledger.LedgerError, match="duplicate forward occurrence"):
        ledger.load_daily_audit(audit)


def test_empty_day_requires_explicit_date_and_mode_and_is_recorded(tmp_path: Path) -> None:
    audit = tmp_path / "empty.jsonl"
    audit.write_text("", encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="requires explicit race_date"):
        ledger.load_daily_audit(audit)
    with pytest.raises(ledger.LedgerError, match="requires explicit evaluation_mode"):
        ledger.load_daily_audit(audit, race_date="2026-09-12")
    connection = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        imported = ledger.import_daily_audit(
            connection,
            audit,
            race_date="2026-09-12",
            evaluation_mode="TRUE_FORWARD",
        )
        report = ledger.summarize(connection)
    finally:
        connection.close()
    assert imported["occurrences"] == 0
    assert imported["evaluation_mode"] == "TRUE_FORWARD"
    assert report["date_range"]["zero_match_days"] == 1


def test_runner_outcome_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    row = _occurrence()
    row["outcome"]["horse_no"] = 9
    _write(audit, [row])
    with pytest.raises(ledger.LedgerError, match="runner/outcome identity mismatch"):
        ledger.load_daily_audit(audit)

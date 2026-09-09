from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import evaluate_jrdb_edge_forward as forward_eval  # noqa: E402


def _put(row: bytearray, start: int, width: int, value: str, encoding: str = "ascii") -> None:
    raw = value.encode(encoding)
    row[start - 1:start - 1 + width] = raw.ljust(width, b" ")[:width]


def _sed_row(*, race_key: str, horse_no: int, horse_id: str, date_raw: str,
             finish: int | None, abnormal: str = "0", win_payout: int = 0,
             place_payout: int = 0) -> bytes:
    row = bytearray(b" " * 374)
    _put(row, 1, 8, race_key)
    _put(row, 9, 2, f"{horse_no:02d}")
    _put(row, 11, 8, horse_id)
    _put(row, 19, 8, date_raw)
    if finish is not None:
        _put(row, 141, 2, f"{finish:02d}")
    _put(row, 143, 1, abnormal)
    if win_payout:
        _put(row, 342, 7, str(win_payout))
    if place_payout:
        _put(row, 349, 7, str(place_payout))
    return bytes(row)


def _write_sed(path: Path, rows: list[bytes], yymmdd: str = "260905") -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"SED{yymmdd}.txt", b"\r\n".join(rows) + b"\r\n")


def _match_row(race_key: str, horse_no: int, horse_id: str, edge_id: str,
               polarity: str, family: str, *, review_due: bool = False) -> dict:
    return {
        "key": {
            "race_key": race_key,
            "horse_no": horse_no,
            "horse_id": horse_id,
            "race_date": "2026-09-05",
        },
        "edge_matches": [{
            "edge_id": edge_id,
            "display_text": edge_id,
            "registry_version": "phase1-full",
            "strength_score": 0.8,
            "confidence_band": "HIGH",
            "polarity": polarity,
            "status": "ACTIVE",
            "evidence": {
                "family": family,
                "review_due": review_due,
                "place_rate": 0.30,
                "place_roi": 0.80,
                "baseline_place_rate": 0.20,
            },
        }],
    }


def test_forward_settlement_keeps_sed_postrace_only_and_uses_mart_label_semantics(tmp_path: Path) -> None:
    sed = tmp_path / "SED260905.zip"
    _write_sed(sed, [
        _sed_row(race_key="01262501", horse_no=1, horse_id="23100001", date_raw="20260905",
                 finish=1, win_payout=350, place_payout=160),
        _sed_row(race_key="01262501", horse_no=2, horse_id="23100002", date_raw="20260905",
                 finish=5),
    ])
    matches = [
        _match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE"),
        _match_row("01262501", 2, "23100002", "EDGE-B", "NEGATIVE", "TRANSITION", review_due=True),
    ]
    outcomes = forward_eval.load_sed_outcomes(sed)
    report, occurrences = forward_eval.evaluate(matches, outcomes)
    assert len(occurrences) == 2
    assert occurrences[0]["evaluator_version"] == "0.3.0"
    assert occurrences[0]["evaluation_mode"] == "TRUE_FORWARD"
    assert occurrences[0]["registry_version"] == "phase1-full"
    assert occurrences[0]["strength_score"] == pytest.approx(0.8)
    assert occurrences[0]["confidence_band"] == "HIGH"
    assert report["evaluation_mode"] == "TRUE_FORWARD"
    assert report["overall"]["eligible"] == 2
    assert report["overall"]["win_rate"] == pytest.approx(0.5)
    assert report["overall"]["place_rate"] == pytest.approx(0.5)
    assert report["overall"]["win_roi"] == pytest.approx(1.75)
    assert report["overall"]["place_roi"] == pytest.approx(0.8)
    assert report["by_polarity"]["POSITIVE"]["place_hits"] == 1
    assert report["by_polarity"]["NEGATIVE"]["place_hits"] == 0
    assert report["by_review_due"]["True"]["review_due_occurrences"] == 1


def test_reconstructed_backfill_is_explicitly_stamped(tmp_path: Path) -> None:
    sed = tmp_path / "SED260905.zip"
    _write_sed(sed, [
        _sed_row(race_key="01262501", horse_no=1, horse_id="23100001", date_raw="20260905",
                 finish=1, win_payout=350, place_payout=160),
    ])
    matches = [_match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE")]
    report, occurrences = forward_eval.evaluate(
        matches,
        forward_eval.load_sed_outcomes(sed),
        evaluation_mode="RECONSTRUCTED_BACKFILL",
    )
    assert report["evaluation_mode"] == "RECONSTRUCTED_BACKFILL"
    assert occurrences[0]["evaluation_mode"] == "RECONSTRUCTED_BACKFILL"


def test_invalid_evaluation_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported evaluation_mode"):
        forward_eval.normalize_evaluation_mode("backtest")


def test_abnormal_result_is_not_eligible(tmp_path: Path) -> None:
    sed = tmp_path / "SED260905.zip"
    _write_sed(sed, [
        _sed_row(race_key="01262501", horse_no=1, horse_id="23100001", date_raw="20260905",
                 finish=1, abnormal="1", win_payout=350, place_payout=160),
    ])
    matches = [_match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE")]
    report, _ = forward_eval.evaluate(matches, forward_eval.load_sed_outcomes(sed))
    assert report["overall"]["eligible"] == 0
    assert report["overall"]["abnormal"] == 1


def test_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    sed = tmp_path / "SED260905.zip"
    _write_sed(sed, [
        _sed_row(race_key="01262501", horse_no=1, horse_id="99999999", date_raw="20260905", finish=3),
    ])
    matches = [_match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE")]
    with pytest.raises(ValueError, match="horse_id mismatch"):
        forward_eval.evaluate(matches, forward_eval.load_sed_outcomes(sed))


def test_missing_sed_runner_fails_closed() -> None:
    matches = [_match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE")]
    with pytest.raises(ValueError, match="SED is missing"):
        forward_eval.evaluate(matches, {})


def test_load_match_rows_rejects_duplicate_runner_identity(tmp_path: Path) -> None:
    path = tmp_path / "matches.jsonl"
    row = _match_row("01262501", 1, "23100001", "EDGE-A", "POSITIVE", "COURSE")
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate matcher runner identity"):
        forward_eval.load_match_rows(path)

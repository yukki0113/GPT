from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import build_jrdb_edge_forward_ledger as ledger  # noqa: E402
import evaluate_jrdb_edge_forward as forward_eval  # noqa: E402


def _occurrence(
    *,
    date: str = "2026-09-05",
    runner: str = "01262501:01",
    edge: str = "EDGE-A",
    family: str = "COURSE",
    polarity: str = "POSITIVE",
    finish: int | None = 1,
    win: int = 350,
    place: int = 160,
    eligibility: str = "ELIGIBLE",
    review: bool = False,
) -> dict:
    return {
        "runner_identity": runner,
        "race_date": date,
        "horse_id": "23100001",
        "edge_id": edge,
        "family": family,
        "polarity": polarity,
        "status": "ACTIVE",
        "review_due": review,
        "eligibility": eligibility,
        "evidence": {
            "family": family,
            "review_due": review,
            "place_rate": 0.30,
            "place_roi": 0.80,
            "baseline_place_rate": 0.20,
        },
        "outcome": {
            "finish": finish,
            "abnormal_code": "0",
            "win_payout": win,
            "place_payout": place,
        },
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_import_two_days_and_cumulative_summary_matches_forward_semantics(tmp_path: Path) -> None:
    first = _occurrence()
    second = _occurrence(
        date="2026-09-06",
        runner="01262601:02",
        edge="EDGE-B",
        family="TRANSITION",
        polarity="NEGATIVE",
        finish=5,
        win=0,
        place=0,
        review=True,
    )
    d1 = tmp_path / "d1.jsonl"
    d2 = tmp_path / "d2.jsonl"
    _write(d1, [first])
    _write(d2, [second])

    result = ledger.run(ledger_path=tmp_path / "ledger.sqlite", audit_jsonl=[d1, d2])
    summary = result["summary"]

    assert summary["date_range"] == {"from": "2026-09-05", "to": "2026-09-06"}
    assert summary["overall"] == forward_eval.summarize_occurrences([first, second])
    assert summary["overall"]["eligible"] == 2
    assert summary["overall"]["win_roi"] == pytest.approx(1.75)
    assert summary["overall"]["place_roi"] == pytest.approx(0.8)
    assert summary["by_edge"]["EDGE-A"]["place_hits"] == 1
    assert summary["by_review_due"]["True"]["review_due_occurrences"] == 1


def test_reimport_same_source_is_idempotent(tmp_path: Path) -> None:
    audit = tmp_path / "d1.jsonl"
    _write(audit, [_occurrence()])
    database = tmp_path / "ledger.sqlite"

    first = ledger.run(ledger_path=database, audit_jsonl=[audit])
    second = ledger.run(ledger_path=database, audit_jsonl=[audit])

    assert first["imports"][0]["inserted"] == 1
    assert second["imports"][0]["already_imported"] is True
    assert second["summary"]["overall"]["matches"] == 1


def test_same_occurrence_from_other_source_can_repeat_only_if_exact(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, [_occurrence()])
    _write(b, [_occurrence()])

    result = ledger.run(ledger_path=tmp_path / "ledger.sqlite", audit_jsonl=[a, b])

    assert result["imports"][1]["existing"] == 1
    assert result["summary"]["overall"]["matches"] == 1


def test_conflicting_immutable_occurrence_fails_closed_and_rolls_back_source(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write(a, [_occurrence()])
    _write(b, [_occurrence(place=999)])
    database = tmp_path / "ledger.sqlite"
    ledger.run(ledger_path=database, audit_jsonl=[a])

    with pytest.raises(ValueError, match="conflicting immutable"):
        ledger.run(ledger_path=database, audit_jsonl=[b])

    with ledger.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM forward_occurrence").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM forward_source_import").fetchone()[0] == 1


def test_duplicate_occurrence_inside_audit_is_rejected(tmp_path: Path) -> None:
    audit = tmp_path / "dup.jsonl"
    row = _occurrence()
    _write(audit, [row, row])

    with pytest.raises(ValueError, match="duplicate occurrence_key"):
        ledger.run(ledger_path=tmp_path / "ledger.sqlite", audit_jsonl=[audit])


def test_eligible_occurrence_requires_finish(tmp_path: Path) -> None:
    audit = tmp_path / "bad.jsonl"
    _write(audit, [_occurrence(finish=None)])

    with pytest.raises(ValueError, match="requires outcome.finish"):
        ledger.run(ledger_path=tmp_path / "ledger.sqlite", audit_jsonl=[audit])

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0_queue as queue  # noqa: E402


def _row(
    *,
    order: int,
    role: str,
    status: str,
    race_key: str,
    race_date: str,
    surface_code: str,
) -> dict:
    """Build one queue row with the identity fields required by the helper."""
    return {
        "manifest_id": "Gen0-G000-abc",
        "generation_id": "Gen0-G000",
        "sample_order": order,
        "sample_role": role,
        "queue_status": status,
        "race_key": race_key,
        "race_date": race_date,
        "surface_code": surface_code,
    }


def _rows() -> list[dict]:
    """Build a compact queue with primary and reserve rows."""
    return [
        _row(
            order=1,
            role="PRIMARY",
            status="READY",
            race_key="01251101",
            race_date="2025-06-01",
            surface_code="1",
        ),
        _row(
            order=2,
            role="PRIMARY",
            status="READY",
            race_key="01251102",
            race_date="2025-06-02",
            surface_code="2",
        ),
        _row(
            order=51,
            role="RESERVE",
            status="RESERVE",
            race_key="02251101",
            race_date="2025-06-03",
            surface_code="1",
        ),
        _row(
            order=52,
            role="RESERVE",
            status="RESERVE",
            race_key="02251102",
            race_date="2025-06-04",
            surface_code="2",
        ),
    ]


def test_next_ready_rows_uses_sample_order() -> None:
    """Operational chunks consume READY races in immutable sample order."""
    rows = list(reversed(_rows()))
    selected = queue.next_ready_rows(rows, "Gen0-G000", limit=1)
    assert [row["race_key"] for row in selected] == ["01251101"]


def test_normal_forward_transitions_are_allowed() -> None:
    """Queue can move only forward through the forecast lifecycle."""
    row = _rows()[0]
    row = queue.transition_row(row, "SOURCE_READY")
    row = queue.transition_row(row, "IN_PROGRESS")
    row = queue.transition_row(row, "FROZEN")
    row = queue.transition_row(row, "RESULT_JOINED")
    row = queue.transition_row(row, "EVALUATED")
    assert row["queue_status"] == "EVALUATED"


def test_queue_rewind_is_rejected() -> None:
    """Frozen or evaluated rows cannot be moved back to READY."""
    with pytest.raises(queue.QueueStateError, match="invalid queue transition"):
        queue.validate_transition("FROZEN", "READY")


def test_technical_replacement_preserves_surface() -> None:
    """A skipped turf primary promotes the earliest eligible turf reserve."""
    skipped, promoted = queue.technical_replacement(
        _rows(),
        failed_race_key="01251101",
        skip_reason="historical RaceNote source missing",
    )
    assert skipped["queue_status"] == "SKIPPED_TECH"
    assert skipped["skip_reason"] == "historical RaceNote source missing"
    assert promoted["queue_status"] == "READY"
    assert promoted["replacement_for"] == "01251101"
    assert promoted["sample_order"] == 51
    assert promoted["surface_code"] == "1"


def test_replacement_respects_date_cap() -> None:
    """A reserve on an already full date is skipped for the next valid reserve."""
    rows = _rows()
    rows.extend(
        [
            _row(
                order=3,
                role="PRIMARY",
                status="READY",
                race_key="03251101",
                race_date="2025-06-03",
                surface_code="2",
            ),
            _row(
                order=4,
                role="PRIMARY",
                status="READY",
                race_key="03251102",
                race_date="2025-06-03",
                surface_code="1",
            ),
            _row(
                order=5,
                role="PRIMARY",
                status="READY",
                race_key="03251103",
                race_date="2025-06-03",
                surface_code="2",
            ),
            _row(
                order=53,
                role="RESERVE",
                status="RESERVE",
                race_key="04251101",
                race_date="2025-06-05",
                surface_code="1",
            ),
        ]
    )
    _skipped, promoted = queue.technical_replacement(
        rows,
        failed_race_key="01251101",
        skip_reason="reader validation failed",
    )
    assert promoted["sample_order"] == 53
    assert promoted["race_date"] == "2025-06-05"


def test_replacement_after_forecast_start_is_rejected() -> None:
    """Prediction difficulty or later outcome can never trigger replacement."""
    rows = _rows()
    rows[0]["queue_status"] = "IN_PROGRESS"
    with pytest.raises(queue.QueueStateError, match="before forecast starts"):
        queue.technical_replacement(
            rows,
            failed_race_key="01251101",
            skip_reason="difficult race",
        )

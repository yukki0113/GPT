"""Focused tests for the Newspaper EdgeDB ``特注メモ`` adapter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import jrdb_newspaper_edge_adapter as adapter  # noqa: E402


def _row(matches):
    """Build one exact-identity EdgeDB row."""
    return {
        "key": {
            "race_key": "01262501",
            "race_horse_key": "0126250104",
            "horse_id": "24102603",
            "horse_no": 4,
            "race_date": "2026-09-05",
        },
        "edge_matches": matches,
    }


def test_legacy_active_match_is_served_without_inventing_future_fields() -> None:
    """Current matcher output stays usable but absent v0.2 fields stay absent."""
    raw = {
        "edge_id": "EDGE-LEGACY",
        "display_text": "＋ 東京芝1600mで好走傾向",
        "polarity": "MIXED",
        "status": "ACTIVE",
        "strength_score": 50.0,
        "evidence": {
            "performance_signal": "POSITIVE",
            "value_signal": "NEGATIVE",
        },
    }

    normalized = adapter.normalize_row(_row([raw]), line_no=1)
    memo = normalized["special_memos"][0]

    assert memo["registry_status"] == "ACTIVE"
    assert memo["performance_signal"] == "POSITIVE"
    assert memo["performance_evidence_level"] is None
    assert memo["presentation_role"] is None
    assert memo["serving_reason"] == "LEGACY_ACTIVE_PERFORMANCE_SIGNAL"
    assert memo["memo_text"] == "＋ 東京芝1600mで好走傾向"


def test_future_confirmed_primary_adds_sign_only_when_needed() -> None:
    """The future explicit contract is CONFIRMED/PRIMARY compatible."""
    raw = {
        "edge_id": "EDGE-FUTURE",
        "display_text": "東京芝1600mで好走傾向",
        "polarity": "POSITIVE",
        "registry_status": "ACTIVE",
        "performance_signal": "POSITIVE",
        "performance_evidence_level": "CONFIRMED",
        "value_evidence_level": "NONE",
        "presentation_role": "PRIMARY",
    }

    normalized = adapter.normalize_row(_row([raw]), line_no=1)
    memo = normalized["special_memos"][0]

    assert memo["serving_reason"] == "ACTIVE_CONFIRMED"
    assert memo["memo_text"] == "＋ 東京芝1600mで好走傾向"


def test_initial_serving_filters_suggestive_neutral_secondary_and_inactive() -> None:
    """Only ACTIVE confirmed performance evidence is served in the first UI."""
    matches = [
        {
            "edge_id": "SUGGESTIVE",
            "display_text": "参考傾向",
            "registry_status": "ACTIVE",
            "performance_signal": "POSITIVE",
            "performance_evidence_level": "SUGGESTIVE",
            "presentation_role": "PRIMARY",
        },
        {
            "edge_id": "NEUTRAL",
            "display_text": "中立材料",
            "registry_status": "ACTIVE",
            "performance_signal": "NEUTRAL",
            "performance_evidence_level": "CONFIRMED",
            "presentation_role": "PRIMARY",
        },
        {
            "edge_id": "SECONDARY",
            "display_text": "副材料",
            "registry_status": "ACTIVE",
            "performance_signal": "NEGATIVE",
            "performance_evidence_level": "CONFIRMED",
            "presentation_role": "SECONDARY",
        },
        {
            "edge_id": "WATCH",
            "display_text": "監視材料",
            "registry_status": "WATCH",
            "performance_signal": "POSITIVE",
            "performance_evidence_level": "CONFIRMED",
            "presentation_role": "PRIMARY",
        },
    ]

    normalized = adapter.normalize_row(_row(matches), line_no=1)

    assert normalized["special_memos"] == []
    reasons = [item["serving_reason"] for item in normalized["edge_matches"]]
    assert reasons == [
        "PERFORMANCE_NOT_CONFIRMED",
        "PERFORMANCE_NEUTRAL_OR_MISSING",
        "SECONDARY_HIDDEN",
        "REGISTRY_NOT_ACTIVE",
    ]


def test_conflict_role_preserves_positive_and_negative_memos() -> None:
    """CONFLICT retains both sides instead of collapsing them in Newspaper."""
    positive = {
        "edge_id": "POS",
        "display_text": "好走傾向",
        "registry_status": "ACTIVE",
        "performance_signal": "POSITIVE",
        "performance_evidence_level": "CONFIRMED",
        "presentation_role": "CONFLICT",
    }
    negative = {
        "edge_id": "NEG",
        "display_text": "苦戦傾向",
        "registry_status": "ACTIVE",
        "performance_signal": "NEGATIVE",
        "performance_evidence_level": "CONFIRMED",
        "presentation_role": "CONFLICT",
    }

    normalized = adapter.normalize_row(_row([positive, negative]), line_no=1)

    assert [memo["memo_text"] for memo in normalized["special_memos"]] == [
        "＋ 好走傾向",
        "－ 苦戦傾向",
    ]


def test_loader_rejects_duplicate_exact_join_key(tmp_path: Path) -> None:
    """Duplicate horse rows fail closed before Newspaper merge."""
    path = tmp_path / "edge_matches.jsonl"
    rows = [_row([]), _row([])]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(adapter.NewspaperEdgeAdapterError, match="duplicate join key"):
        adapter.load_special_memo_index(path)

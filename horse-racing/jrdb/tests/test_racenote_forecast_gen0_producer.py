from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0_producer as producer  # noqa: E402
from test_racenote_gen0_2_input_firewall import _bundle  # noqa: E402
from test_racenote_forecast_gen0 import _forecast  # noqa: E402


def _decision() -> dict:
    value = _forecast()
    value["race_key"] = "201812020601"
    value["artifact_ref"] = "warehouse/2018-12-02/中山/01.json"
    value["horses"] = [value["horses"][0]]
    value["horses"][0]["horse_no"] = 1
    value["horses"][0]["horse_name"] = "A"
    value["horses"][0]["gpt_rank"] = 1
    value["horses"][0]["mark"] = "◎"
    value["final_prediction"]["axis_horse_no"] = 1
    return value


def test_producer_uses_only_independent_view_and_validates_candidate() -> None:
    request = producer.build_prediction_request(_bundle())
    assert request["independent_view"]["policy"]["current_jrdb_consensus_visible"] is False
    candidate = producer.materialize_gpt_decision(
        request, _decision(), created_at="2026-09-23T00:00:00+09:00"
    )
    assert candidate["producer"]["forbidden_evidence_status"] == "PASS"
    assert candidate["source"]["semantic_sha256"] == request["source_semantic_sha256"]


def test_producer_fails_closed_for_missing_runner() -> None:
    request = producer.build_prediction_request(_bundle())
    decision = _decision()
    decision["horses"] = []
    with pytest.raises(producer.ProducerError, match="exactly"):
        producer.materialize_gpt_decision(request, decision, created_at="2026-09-23T00:00:00+09:00")


def test_producer_rejects_identity_substitution() -> None:
    request = producer.build_prediction_request(_bundle())
    decision = _decision()
    decision["venue"] = "東京"
    with pytest.raises(producer.ProducerError, match="identity mismatch"):
        producer.materialize_gpt_decision(request, decision, created_at="2026-09-23T00:00:00+09:00")

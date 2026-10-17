from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from racenote_v055_authoring_bundle import build
from racenote_v055_single_day import digest


def test_authoring_bundle_is_lossless_and_non_predictive(tmp_path):
    root = ROOT / "daily" / "20261018" / "v055_day" / "v055"
    out = tmp_path / "authoring_bundle"

    manifest = build(root, out)

    assert manifest["status"] == "READY_FOR_LLM_RACE_BY_RACE_REVIEW"
    assert manifest["race_count"] == 36
    assert manifest["prediction_policy"] == "LLM_RACE_BY_RACE_ONLY"
    assert manifest["automated_scoring"] is False
    assert manifest["automated_ranking"] is False
    assert manifest["automated_marks"] is False
    assert manifest["confidence_generation"] is False
    assert {x["venue"] for x in manifest["files"]} == {"京都", "新潟", "東京"}

    seen = set()
    for item in manifest["files"]:
        payload = json.loads((out / item["file"]).read_text(encoding="utf-8"))
        assert payload["reader_semantics"] == "FULL_SEALED_LEAN_READER_NO_OMISSION"
        assert payload["automated_scoring"] is False
        assert payload["automated_ranking"] is False
        assert payload["automated_marks"] is False
        policy = payload["reader_facing_prose_policy"]
        assert policy["audience"] == "ORDINARY_RACING_READER"
        assert policy["translate_internal_evidence"] is True
        assert "IDM" in policy["forbidden_terms"]
        assert policy["day_wide_fill_in_template"] is False
        for race in payload["races"]:
            key = (race["venue"], race["race_no"])
            assert key not in seen
            seen.add(key)
            source = root / "reader" / race["reader_filename"]
            raw = source.read_bytes()
            assert race["reader_sha256"] == digest(raw)
            assert race["reader"] == json.loads(raw)

    assert len(seen) == 36

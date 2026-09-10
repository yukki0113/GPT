import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_repeat_settlement as repeat  # noqa: E402


def test_block_label_and_date_validation():
    assert repeat.block_label(["20260705", "20260711", "20260712"]) == "20260705_11_12"
    assert repeat.normalize_dates(["2026-07-05", "20260711", "20260712"]) == (
        "20260705",
        "20260711",
        "20260712",
    )
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260705", "20260711"])
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260705", "20260705", "20260712"])
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260712", "20260711", "20260705"])


def test_run_delegates_to_base_and_renames_block_outputs(tmp_path, monkeypatch):
    request = {
        "request_id": "repeat-test",
        "dates": ["20260705", "20260711", "20260712"],
        "freeze": {},
        "results": {},
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    output_root = tmp_path / "out"

    def fake_base_run(request_path_arg, freeze_root, raw_root, output_root_arg, *, run_id, head_sha):
        assert request_path_arg == request_path
        assert repeat.base.EXPECTED_DATES == ("20260705", "20260711", "20260712")
        assert repeat.base.FREEZE_MANIFEST == (
            "RaceNote_v1_1_Polarity_Gated_20260705_11_12_PRE_HJC_FREEZE.json"
        )
        cache = output_root_arg / "result_cache"
        runs = output_root_arg / "settlement_runs"
        cache.mkdir(parents=True)
        runs.mkdir(parents=True)
        payout = cache / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_HJC_Payouts.csv"
        finish = cache / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SED_Finish.csv"
        payout.write_text("x\n", encoding="utf-8")
        finish.write_text("y\n", encoding="utf-8")
        manifest = {
            "result_cache": {
                "hjc_payouts": {"file": payout.name, "sha256": "payout-sha"},
                "sed_finish": {"file": finish.name, "sha256": "finish-sha"},
            }
        }
        repeat.base.dump_json(
            runs / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SETTLEMENT_MANIFEST.json",
            manifest,
        )
        return {"status": "success", "run_id": run_id, "head_sha": head_sha}

    monkeypatch.setattr(repeat.base, "run", fake_base_run)
    result = repeat.run(
        request_path,
        tmp_path / "freeze",
        tmp_path / "raw",
        output_root,
        run_id="123",
        head_sha="abc",
    )

    label = "20260705_11_12"
    payout = output_root / "result_cache" / f"RaceNote_v1_1_Polarity_Gated_{label}_HJC_Payouts.csv"
    finish = output_root / "result_cache" / f"RaceNote_v1_1_Polarity_Gated_{label}_SED_Finish.csv"
    manifest_path = output_root / "settlement_runs" / f"RaceNote_v1_1_Polarity_Gated_{label}_SETTLEMENT_MANIFEST.json"
    assert payout.is_file() and finish.is_file() and manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dates"] == ["20260705", "20260711", "20260712"]
    assert manifest["result_cache"]["hjc_payouts"]["file"] == payout.name
    assert manifest["result_cache"]["sed_finish"]["file"] == finish.name
    assert result["settlement_manifest_file"] == manifest_path.name

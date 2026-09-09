from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_jrdb_edge_forward_freeze as freeze  # noqa: E402
import run_jrdb_edge_forward_settlement as settlement  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_true_forward_guard_accepts_only_before_earliest_post() -> None:
    earliest = datetime(2026, 9, 12, 10, 5, tzinfo=freeze.JST)
    freeze._assert_pre_race(
        frozen_at_utc=datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc),
        earliest_post_jst=earliest,
    )
    with pytest.raises(freeze.FreezeError, match="not before the earliest scheduled post"):
        freeze._assert_pre_race(
            frozen_at_utc=datetime(2026, 9, 12, 1, 5, tzinfo=timezone.utc),
            earliest_post_jst=earliest,
        )


def test_post_time_parser_is_strict() -> None:
    parsed = freeze._parse_post_datetime("2026-09-12", "1005")
    assert parsed.isoformat() == "2026-09-12T10:05:00+09:00"
    with pytest.raises(freeze.FreezeError, match="invalid BAC post_time_raw"):
        freeze._parse_post_datetime("2026-09-12", "9:5")


def _freeze_assets(tmp_path: Path, *, mode: str = "TRUE_FORWARD") -> tuple[Path, Path, Path]:
    matches = tmp_path / "edge_matches.jsonl"
    matches.write_text('{"key":{"race_key":"01262601","horse_no":1},"edge_matches":[]}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "PASS",
                "evaluation_mode": mode,
                "race_date": "2026-09-12",
                "frozen_at_utc": "2026-09-12T00:00:00+00:00",
                "earliest_post_time_jst": "2026-09-12T10:05:00+09:00",
                "pre_race_guard": "PASS",
                "files": {
                    "edge_matches.jsonl": {
                        "size_bytes": matches.stat().st_size,
                        "sha256": _sha(matches),
                    }
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sed = tmp_path / "SED260912.zip"
    sed.write_bytes(b"fake-sed")
    return matches, manifest, sed


def test_settlement_rejects_non_true_forward_freeze(tmp_path: Path) -> None:
    _, manifest, _ = _freeze_assets(tmp_path, mode="RECONSTRUCTED_BACKFILL")
    with pytest.raises(settlement.SettlementError, match="not TRUE_FORWARD"):
        settlement._load_freeze_manifest(manifest, _sha(manifest))


def test_settlement_rejects_modified_matches_before_evaluation(tmp_path: Path) -> None:
    matches, manifest, sed = _freeze_assets(tmp_path)
    matches.write_text(matches.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(settlement.SettlementError, match="Frozen matches"):
        settlement.run(
            matches_jsonl=matches,
            freeze_manifest=manifest,
            sed_path=sed,
            ledger_path=tmp_path / "ledger.sqlite",
            output_dir=tmp_path / "out",
        )


def test_settlement_forces_true_forward_and_builds_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matches, manifest, sed = _freeze_assets(tmp_path)
    ledger_path = tmp_path / "ledger.sqlite"

    def fake_eval_run(**kwargs):
        assert kwargs["evaluation_mode"] == "TRUE_FORWARD"
        Path(kwargs["output_json"]).write_text("{}\n", encoding="utf-8")
        Path(kwargs["audit_jsonl"]).write_text("", encoding="utf-8")
        return {
            "overall": {"matches": 0, "eligible": 0},
            "runner_audit": {"matcher_rows": 1, "sed_joined_rows": 1, "abnormal_rows": 0},
        }

    def fake_ledger_run(**kwargs):
        assert kwargs["evaluation_mode"] == "TRUE_FORWARD"
        assert kwargs["summary_evaluation_mode"] == "TRUE_FORWARD"
        Path(kwargs["ledger_path"]).write_bytes(b"ledger")
        Path(kwargs["output_json"]).write_text("{}\n", encoding="utf-8")
        return {"import": {"status": "IMPORTED", "race_date": "2026-09-12", "evaluation_mode": "TRUE_FORWARD"}}

    monkeypatch.setattr(settlement.forward_eval, "run", fake_eval_run)
    monkeypatch.setattr(settlement.forward_ledger, "run", fake_ledger_run)

    result = settlement.run(
        matches_jsonl=matches,
        freeze_manifest=manifest,
        sed_path=sed,
        ledger_path=ledger_path,
        output_dir=tmp_path / "out",
        expected_freeze_manifest_sha256=_sha(manifest),
        expected_matches_sha256=_sha(matches),
        expected_sed_sha256=_sha(sed),
    )
    assert result["status"] == "success"
    assert result["evaluation_mode"] == "TRUE_FORWARD"
    assert result["race_date"] == "2026-09-12"
    assert result["ledger_sha256"] == hashlib.sha256(b"ledger").hexdigest()
    assert result["manifest"]["status"] == "PASS"

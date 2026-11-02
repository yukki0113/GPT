from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_v03_operational_replay as target  # noqa: E402


def _edge(
    edge_id: str,
    template: str,
    signal: str,
    *,
    hierarchy: str | None = None,
    reversal: bool = False,
) -> dict:
    return {
        "edge_id": edge_id,
        "status": "ACTIVE",
        "display_text": edge_id,
        "polarity": "+" if signal == "POSITIVE" else "-",
        "performance_signal": signal,
        "value_signal": "NEUTRAL",
        "redundancy_group_id": f"G-{template}",
        "conditions": {
            "template_id": template,
            "anchor": {"venue_code": "06"},
            "modifiers": {},
        },
        "v03_shadow": {
            "mode": "SHADOW_ONLY",
            "reader_facing": True,
            "shadow_class": "INCREMENTAL_PERFORMANCE" if hierarchy else "ORTHOGONAL",
            "hierarchy": hierarchy,
            "performance_signal": signal,
            "value_signal": "NEUTRAL",
            "is_reversal_vs_v02": reversal,
        },
    }


def _old_match(edge_id: str, template: str, signal: str) -> dict:
    return {
        "edge_id": edge_id,
        "evidence": {
            "template_id": template,
            "performance_signal": signal,
            "value_signal": "NEUTRAL",
        },
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_replay_uses_same_facts_shadow_direction_and_absorption(tmp_path: Path) -> None:
    facts = tmp_path / "facts.jsonl"
    old = tmp_path / "old.jsonl"
    catalog = tmp_path / "catalog.jsonl"
    out_matches = tmp_path / "matches.jsonl"
    out_summary = tmp_path / "summary.json"
    _write(
        facts,
        [
            {
                "race_key": "R1",
                "race_horse_key": "R1H1",
                "horse_no": 1,
                "race_date": "2026-09-12",
                "venue_code": "06",
            },
            {
                "race_key": "R1",
                "race_horse_key": "R1H2",
                "horse_no": 2,
                "race_date": "2026-09-12",
                "venue_code": "06",
            },
        ],
    )
    _write(
        old,
        [
            {
                "key": {
                    "race_key": "R1",
                    "race_horse_key": "R1H1",
                    "horse_no": 1,
                    "race_date": "2026-09-12",
                },
                "edge_matches": [
                    _old_match("context", "COURSE_FRAME_V1", "POSITIVE"),
                    _old_match("child", "COURSE_EXACT_FRAME_V2", "POSITIVE"),
                ],
            },
            {
                "key": {
                    "race_key": "R1",
                    "race_horse_key": "R1H2",
                    "horse_no": 2,
                    "race_date": "2026-09-12",
                },
                "edge_matches": [],
            },
        ],
    )
    _write(
        catalog,
        [
            _edge(
                "child",
                "COURSE_EXACT_FRAME_V2",
                "NEGATIVE",
                hierarchy="COURSE_EXACT_WITHIN_ZONE",
                reversal=True,
            ),
        ],
    )
    result = target.run(
        days=[("20260912", facts, old)],
        shadow_catalog=catalog,
        output_matches=out_matches,
        output_summary=out_summary,
    )
    assert result["v02"]["performance_matches"] == 2
    assert result["v03"]["performance_matches"] == 2
    assert result["v03"]["incremental_reversal_matches"] == 2
    assert result["context_absorption"]["template_counts"] == {"COURSE_FRAME_V1": 1}
    assert result["production_serving_changed"] is False
    replay_row = json.loads(out_matches.read_text(encoding="utf-8").splitlines()[0])
    presentation = replay_row["edge_matches"][0]["v03_shadow"]["presentation"]
    assert presentation["contract"] == "V03_SHADOW_PRESENTATION"
    assert presentation["performance_signal"] == "NEGATIVE"


def test_shadow_display_text_overrides_legacy_polarity() -> None:
    assert target._shadow_display_text({"display_text": "－ legacy"}, "POSITIVE") == "＋ legacy"
    assert target._shadow_display_text({"display_text": "＋ legacy"}, "NEGATIVE") == "－ legacy"


def test_key_mismatch_fails_closed() -> None:
    facts = [{"race_key": "R1", "race_horse_key": "R1H1", "horse_no": 1}]
    matches = [
        {
            "key": {"race_key": "R1", "race_horse_key": "OTHER", "horse_no": 1},
            "edge_matches": [],
        }
    ]
    try:
        target._day_rows(facts, matches, [])
    except target.ReplayAuditError as exc:
        assert "key mismatch" in str(exc)
    else:
        raise AssertionError("expected ReplayAuditError")

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_v02_operational_hits as target  # noqa: E402


def _match(
    edge_id: str,
    *,
    signal: str,
    template: str,
    group: str,
    conditions: dict,
    role: str = "PRIMARY",
) -> dict:
    return {
        "edge_id": edge_id,
        "performance_evidence_level": "CONFIRMED",
        "value_evidence_level": "NONE",
        "redundancy_group_id": group,
        "presentation": {
            "performance": {"role": role, "conflict": False},
            "value": {"role": "NONE", "conflict": False},
        },
        "evidence": {
            "family": "TEST",
            "template_id": template,
            "performance_signal": signal,
            "value_signal": "UNASSESSED",
            "conditions": {
                "anchor": conditions,
                "modifiers": {},
            },
        },
    }


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_operational_audit_counts_density_conflict_and_nesting(tmp_path: Path) -> None:
    path = tmp_path / "matches.jsonl"
    rows = [
        {
            "key": {
                "race_date": "2026-09-19",
                "race_key": "0926c101",
                "race_horse_key": "0926c10101",
                "horse_no": 1,
            },
            "edge_matches": [
                _match(
                    "parent",
                    signal="POSITIVE",
                    template="PARENT",
                    group="g1",
                    conditions={"sire_name": "A", "distance_m": 2000},
                ),
                _match(
                    "child",
                    signal="POSITIVE",
                    template="CHILD",
                    group="g2",
                    conditions={
                        "sire_name": "A",
                        "distance_m": 2000,
                        "venue_code": "09",
                    },
                ),
                _match(
                    "negative",
                    signal="NEGATIVE",
                    template="NEG",
                    group="g3",
                    conditions={"jockey_code": "00123", "venue_code": "09"},
                ),
                _match(
                    "duplicate-secondary",
                    signal="POSITIVE",
                    template="PARENT_ALT",
                    group="g1",
                    conditions={"sire_name": "A", "distance_m": 2000},
                    role="SECONDARY",
                ),
                _match(
                    "extra",
                    signal="POSITIVE",
                    template="EXTRA",
                    group="g4",
                    conditions={"frame_no": 8},
                ),
            ],
        },
        {
            "key": {
                "race_date": "2026-09-19",
                "race_key": "0926c101",
                "race_horse_key": "0926c10102",
                "horse_no": 2,
            },
            "edge_matches": [],
        },
    ]
    _write(path, rows)

    result = target.audit([path])
    assert result["runners"] == 2
    assert result["performance_pm"]["matches"] == 5
    assert result["performance_pm"]["mixed_direction_runners"] == 1
    assert result["performance_pm"]["runners_with_5plus"] == 1
    assert result["existing_redundancy"]["within_group_extra_matches"] == 1
    assert result["existing_redundancy"]["runners_with_multiple_groups"] == 1
    assert result["condition_nesting"]["runners_with_parent_child_relation"] == 1
    assert result["condition_nesting"]["parent_child_pairs"] >= 1
    assert result["condition_nesting"]["same_signal_pairs"] >= 1
    assert result["high_hit_examples"][0]["positive"] == 4
    assert result["high_hit_examples"][0]["negative"] == 1


def test_markdown_explicitly_avoids_net_scoring(tmp_path: Path) -> None:
    path = tmp_path / "matches.jsonl"
    _write(
        path,
        [
            {
                "key": {
                    "race_date": "2026-09-19",
                    "race_key": "0926c101",
                    "race_horse_key": "0926c10101",
                    "horse_no": 1,
                },
                "edge_matches": [
                    _match(
                        "edge",
                        signal="POSITIVE",
                        template="ONE",
                        group="g1",
                        conditions={"frame_no": 1},
                    )
                ],
            }
        ],
    )
    report = target.markdown(target.audit([path]))
    assert "最終scoreを作らない" in report
    assert "Childの追加効果はまだ判定しない" in report

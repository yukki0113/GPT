from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

import run_jrdb_edge_v03_forward_shadow_freeze as target  # noqa: E402


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),
        encoding="utf-8",
    )


def test_write_shadow_matches_uses_v03_shadow_direction(tmp_path: Path) -> None:
    facts=tmp_path/"facts.jsonl"
    catalog=tmp_path/"shadow.jsonl"
    output=tmp_path/"matches.jsonl"
    _write(facts,[{
        "race_key":"R1","race_horse_key":"R1H1","horse_id":"H1",
        "horse_no":1,"race_date":"2026-09-26","venue_code":"06",
    }])
    _write(catalog,[{
        "edge_id":"E1",
        "status":"ACTIVE",
        "display_text":"edge",
        "polarity":"+",
        "performance_signal":"POSITIVE",
        "value_signal":"NEUTRAL",
        "conditions":{
            "template_id":"COURSE_EXACT_FRAME_V2",
            "anchor":{"venue_code":"06"},
            "modifiers":{},
        },
        "v03_shadow":{
            "mode":"SHADOW_ONLY",
            "reader_facing":True,
            "shadow_class":"INCREMENTAL_PERFORMANCE",
            "hierarchy":"COURSE_EXACT_WITHIN_ZONE",
            "performance_signal":"NEGATIVE",
            "value_signal":"NEUTRAL",
            "is_reversal_vs_v02":True,
        },
    }])
    result=target._write_shadow_matches(
        facts_jsonl=facts,
        shadow_catalog_jsonl=catalog,
        output_jsonl=output,
    )
    assert result=={
        "runner_rows":1,
        "matched_runners":1,
        "matches":1,
        "incremental_reversal_matches":1,
        "presentation_overrides":1,
    }
    row=json.loads(output.read_text(encoding="utf-8").strip())
    match=row["edge_matches"][0]
    assert match["evidence"]["performance_signal"]=="NEGATIVE"
    assert match["v03_shadow"]["is_reversal_vs_v02"] is True
    assert match["v03_shadow"]["presentation"]["contract"]=="V03_SHADOW_PRESENTATION"
    assert match["v03_shadow"]["presentation"]["performance_signal"]=="NEGATIVE"


def test_expected_scheduled_races_fails_closed_on_partial_snapshot() -> None:
    manifest={"provenance":{"scheduled_races":1}}
    try:
        target._assert_expected_scheduled_races(manifest,24)
    except target.ShadowFreezeError as exc:
        assert "expected=24 actual=1" in str(exc)
    else:
        raise AssertionError("expected ShadowFreezeError")
    assert target._assert_expected_scheduled_races(
        {"provenance":{"scheduled_races":24}},24
    )==24
    assert target._assert_expected_scheduled_races(
        {"provenance":{"scheduled_races":24}},None
    )==24
    try:
        target._assert_expected_scheduled_races(
            {"provenance":{"scheduled_races":24}},0
        )
    except target.ShadowFreezeError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("expected ShadowFreezeError")


def test_shadow_catalog_sha_is_exact(tmp_path: Path) -> None:
    path=tmp_path/"x"
    path.write_bytes(b"abc")
    assert target._sha256(path)==(
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )

#!/usr/bin/env python3
"""Freeze v0.2 STANDARD and v0.3 SHADOW_ONLY Edge outputs on the same pre-race facts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import audit_jrdb_edge_v03_operational_replay as stage_d
import run_jrdb_edge_forward_freeze as v02_freeze

VERSION = "0.1.0-stage-e"
EVALUATION_MODE = "TRUE_FORWARD_SHADOW"


class ShadowFreezeError(RuntimeError):
    pass


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            value=json.loads(raw)
            if not isinstance(value,dict):
                raise ShadowFreezeError(f"object required: {path}")
            rows.append(value)
    return rows


def _write_shadow_matches(
    *,
    facts_jsonl: Path,
    shadow_catalog_jsonl: Path,
    output_jsonl: Path,
) -> dict[str, int]:
    registry=stage_d._load_shadow_catalog(shadow_catalog_jsonl)
    facts=_load_jsonl(facts_jsonl)
    rows=[]
    matches=0
    matched_runners=0
    reversal_matches=0
    presentation_overrides=0
    for runner in facts:
        found=stage_d._match_shadow(registry,runner)
        matches+=len(found)
        matched_runners+=bool(found)
        for match in found:
            shadow=match.get("v03_shadow") or {}
            if shadow.get("is_reversal_vs_v02"):
                reversal_matches+=1
            presentation=shadow.get("presentation") or {}
            if presentation.get("display_text") and presentation.get("display_text")!=match.get("display_text"):
                presentation_overrides+=1
        key={
            field:runner.get(field)
            for field in stage_d.v02.base.IDENTITY_FIELDS
            if field in runner
        }
        rows.append({"key":key,"edge_matches":found})
    with output_jsonl.open("w",encoding="utf-8",newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    return {
        "runner_rows":len(facts),
        "matched_runners":matched_runners,
        "matches":matches,
        "incremental_reversal_matches":reversal_matches,
        "presentation_overrides":presentation_overrides,
    }


def run(
    *,
    paci_path: str | Path,
    v02_catalog_jsonl: str | Path,
    v03_shadow_catalog_jsonl: str | Path,
    output_dir: str | Path,
    analysis_db: str | Path | None = None,
    analysis_root: str | Path | None = None,
    expected_race_date: str | None = None,
    expected_paci_sha256: str | None = None,
    expected_v02_sha256: str | None = None,
    expected_v03_sha256: str | None = None,
    expected_analysis_generation_id: str | None = None,
    expected_analysis_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    v03=Path(v03_shadow_catalog_jsonl)
    if not v03.is_file():
        raise ShadowFreezeError(f"v0.3 shadow catalog missing: {v03}")
    v03_sha=_sha256(v03)
    if expected_v03_sha256 and v03_sha!=expected_v03_sha256.lower():
        raise ShadowFreezeError(
            f"v0.3 shadow catalog SHA mismatch expected={expected_v03_sha256.lower()} actual={v03_sha}"
        )

    base=v02_freeze.run(
        paci_path=paci_path,
        serving_catalog_jsonl=v02_catalog_jsonl,
        output_dir=output,
        analysis_db=analysis_db,
        analysis_root=analysis_root,
        expected_race_date=expected_race_date,
        expected_paci_sha256=expected_paci_sha256,
        expected_publication_sha256=expected_v02_sha256,
        expected_analysis_generation_id=expected_analysis_generation_id,
        expected_analysis_manifest_sha256=expected_analysis_manifest_sha256,
    )

    facts=output/"current_facts.jsonl"
    shadow_matches=output/"edge_matches_v0_3_shadow.jsonl"
    shadow_summary=_write_shadow_matches(
        facts_jsonl=facts,
        shadow_catalog_jsonl=v03,
        output_jsonl=shadow_matches,
    )
    inputs=output/"inputs"
    inputs.mkdir(exist_ok=True)
    target=inputs/"edge_serving_catalog_v0_3_shadow.jsonl"
    target.write_bytes(v03.read_bytes())

    provenance=json.loads((output/"provenance.json").read_text(encoding="utf-8"))
    provenance["evaluation_mode"]=EVALUATION_MODE
    provenance["v03_shadow"]={
        "mode":"SHADOW_ONLY",
        "catalog_file":"edge_serving_catalog_v0_3_shadow.jsonl",
        "catalog_sha256":v03_sha,
        "matcher_contract":"same Current Facts as v0.2; v03_shadow signals authoritative",
        "runner_rows":shadow_summary["runner_rows"],
        "matched_runners":shadow_summary["matched_runners"],
        "matches":shadow_summary["matches"],
        "incremental_reversal_matches":shadow_summary["incremental_reversal_matches"],
        "presentation_overrides":shadow_summary["presentation_overrides"],
        "presentation_contract":"V03_SHADOW_PRESENTATION",
        "result_data_used":False,
    }
    provenance["semantics"]=(
        "v0.2 STANDARD and v0.3 SHADOW_ONLY outputs frozen from the same pre-race Current Facts "
        "before earliest scheduled post; no SED/result input used"
    )
    (output/"provenance.json").write_text(
        json.dumps(provenance,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    manifest=v02_freeze._write_manifest(output,provenance)
    result={
        "status":"success",
        "driver_version":VERSION,
        "evaluation_mode":EVALUATION_MODE,
        "race_date":provenance["race_date"],
        "frozen_at_utc":provenance["frozen_at_utc"],
        "earliest_post_time_jst":provenance["earliest_post_time_jst"],
        "pre_race_guard":"PASS",
        "result_data_used":False,
        "v02":base["matcher"],
        "v03":shadow_summary,
        "v03_catalog_sha256":v03_sha,
        "manifest":manifest,
    }
    (output/"result_shadow.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--paci",required=True)
    parser.add_argument("--v02-catalog",required=True)
    parser.add_argument("--v03-shadow-catalog",required=True)
    history=parser.add_mutually_exclusive_group()
    history.add_argument("--analysis-db")
    history.add_argument("--analysis-root")
    parser.add_argument("--output-dir",required=True)
    parser.add_argument("--expected-race-date")
    parser.add_argument("--expected-paci-sha256")
    parser.add_argument("--expected-v02-sha256")
    parser.add_argument("--expected-v03-sha256")
    parser.add_argument("--expected-analysis-generation-id")
    parser.add_argument("--expected-analysis-manifest-sha256")
    args=parser.parse_args()
    result=run(
        paci_path=args.paci,
        v02_catalog_jsonl=args.v02_catalog,
        v03_shadow_catalog_jsonl=args.v03_shadow_catalog,
        output_dir=args.output_dir,
        analysis_db=args.analysis_db,
        analysis_root=args.analysis_root,
        expected_race_date=args.expected_race_date,
        expected_paci_sha256=args.expected_paci_sha256,
        expected_v02_sha256=args.expected_v02_sha256,
        expected_v03_sha256=args.expected_v03_sha256,
        expected_analysis_generation_id=args.expected_analysis_generation_id,
        expected_analysis_manifest_sha256=args.expected_analysis_manifest_sha256,
    )
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""BRDB D4 real-PACI full-field acceptance runner (research-only).

Runs exact committed synthetic gate tests, parses one fixed PACI race with the
canonical JRDB parser, joins every declared horse to PACI UKC, then runs the
pinned D3 -> D4 sidecar twice and requires byte-identical output.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from brdb_d4_paci_field import extract
from run_brdb_d4_sidecar import run as run_sidecar

ROOT = Path(__file__).resolve().parents[3]
PACI_NAME = "PACI261115.zip"
RACE_KEY = "05265412"
EXPECTED_FIELD_SIZE = 18


class AcceptanceError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise AcceptanceError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_synthetic_tests() -> dict[str, Any]:
    tests_dir = ROOT / "horse-racing/brdb/tests"
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(
        str(tests_dir), pattern="test_brdb_d4_paci_field.py"
    )
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    require(result.testsRun == 12, f"expected 12 PACI tests, got {result.testsRun}")
    require(result.wasSuccessful(), "synthetic PACI gate tests failed: " + stream.getvalue())
    return {"tests_run": result.testsRun, "status": "PASS", "log": stream.getvalue()}


def _forbidden_exact_keys(value: Any) -> list[str]:
    forbidden = {"score", "rank", "probability", "win_probability", "forecast"}
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                found.append(key)
            found.extend(_forbidden_exact_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_forbidden_exact_keys(child))
    return found


def execute(*, paci_root: Path, d3_root: Path, output_dir: Path) -> dict[str, Any]:
    tests = _run_synthetic_tests()
    paci = (paci_root / PACI_NAME).resolve(strict=True)
    full = (d3_root / "output/d3_full_condition_evidence.json").resolve(strict=True)
    temporal = (d3_root / "output/d3_temporal_diagnostic.json").resolve(strict=True)
    receipt = (d3_root / "output/d3_run_receipt.json").resolve(strict=True)

    context, source_receipt = extract(paci, RACE_KEY)
    require(context["race"]["field_size"] == EXPECTED_FIELD_SIZE, "unexpected BAC field size")
    require(len(context["entrants"]) == EXPECTED_FIELD_SIZE, "not all KYI declarations joined")
    require(source_receipt["ukc_joined_horses"] == EXPECTED_FIELD_SIZE,
            "UKC join did not cover the full declared field")
    require("track_condition_code" not in context["race"],
            "PACI adapter must not invent going code")

    with tempfile.TemporaryDirectory(prefix="brdb-d4-real-paci-") as tmp:
        tmp = Path(tmp)
        context_path = tmp / "context.json"
        context_path.write_text(
            json.dumps(context, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        sidecar_paths = [tmp / "sidecar1.json", tmp / "sidecar2.json"]
        run_results = [
            run_sidecar(full, temporal, receipt, context_path, path)
            for path in sidecar_paths
        ]
        require(run_results[0]["output_sha256"] == run_results[1]["output_sha256"],
                "D4 sidecar output is not byte deterministic")
        sidecar = json.loads(sidecar_paths[1].read_text(encoding="utf-8"))
        require(run_results[1]["horse_count"] == EXPECTED_FIELD_SIZE,
                "sidecar does not account for full field")
        require(sidecar.get("release_status") == "RESEARCH_SIDECAR_ONLY",
                "sidecar promoted beyond research")
        require(sidecar.get("prediction_safe") is False and
                sidecar.get("research_only") is True and
                sidecar.get("historical_asof_status") == "AS_OF_UNVERIFIED",
                "research/as-of guard drift")
        require(sidecar.get("no_forecast_or_score") is True,
                "non-scoring flag missing")
        require(sidecar.get("aggregate_coverage", {}).get("reviewed_horses")
                == EXPECTED_FIELD_SIZE, "not all horses reviewed")
        require(not _forbidden_exact_keys(sidecar),
                "forbidden forecast/score/rank key present")
        for horse in sidecar["horses"]:
            require(horse["availability"] == "AS_OF_UNVERIFIED",
                    "horse availability promoted")
            require(horse["factors"] == {"positive": [], "negative": [], "unknown": []},
                    "research sidecar generated factors")
            require(horse["summary"] is None and horse["confidence"] == "UNASSESSED",
                    "research sidecar generated interpretation")

        output_dir.mkdir(parents=True, exist_ok=True)
        final_context = output_dir / "d4_paci_research_context.json"
        final_source = output_dir / "d4_paci_source_receipt.json"
        final_sidecar = output_dir / "d4_paci_research_sidecar.json"
        shutil.copyfile(context_path, final_context)
        final_source.write_text(
            json.dumps(source_receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(sidecar_paths[1], final_sidecar)

        acceptance = {
            "status": "PASS",
            "research_only": True,
            "prediction_safe": False,
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "source_time_status": source_receipt["source_time_status"],
            "synthetic_paci_tests": tests["tests_run"],
            "source_archive": PACI_NAME,
            "source_archive_sha256": source_receipt["source_archive_sha256"],
            "race_key": RACE_KEY,
            "field_size": EXPECTED_FIELD_SIZE,
            "ukc_joined_horses": source_receipt["ukc_joined_horses"],
            "reviewed_horses": sidecar["aggregate_coverage"]["reviewed_horses"],
            "research_evidence_items": sidecar["aggregate_coverage"]["research_evidence_items"],
            "two_run_byte_identity": True,
            "context_sha256": sha256(final_context),
            "source_receipt_sha256": sha256(final_source),
            "sidecar_sha256": sha256(final_sidecar),
            "d3_provenance": sidecar["provenance"],
            "no_forecast_or_score": sidecar["no_forecast_or_score"],
        }
        (output_dir / "d4_paci_e2e_acceptance_receipt.json").write_text(
            json.dumps(acceptance, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "d4_paci_synthetic_test.log").write_text(
            tests["log"], encoding="utf-8"
        )
        return acceptance


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--paci-root", type=Path, required=True)
    p.add_argument("--d3-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    result = execute(
        paci_root=args.paci_root,
        d3_root=args.d3_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

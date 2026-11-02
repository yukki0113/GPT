#!/usr/bin/env python3
"""Settle an immutable TRUE_FORWARD Edge freeze against post-race SED and append its ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_jrdb_edge_forward_ledger as forward_ledger
import evaluate_jrdb_edge_forward as forward_eval

VERSION = "0.1.0"
EVALUATION_MODE = "TRUE_FORWARD"


class SettlementError(RuntimeError):
    """Raised when a frozen TRUE_FORWARD asset cannot be settled safely."""


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _verify_sha(path: str | Path, expected: str | None, label: str) -> str:
    actual = _sha256(path)
    if expected and actual != expected.lower():
        raise SettlementError(f"{label} SHA-256 mismatch: expected={expected.lower()} actual={actual}")
    return actual


def _load_freeze_manifest(path: Path, expected_sha256: str | None) -> tuple[dict[str, Any], str]:
    digest = _verify_sha(path, expected_sha256, "Freeze manifest")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettlementError("freeze manifest is invalid JSON") from exc
    if manifest.get("status") != "PASS":
        raise SettlementError(f"freeze manifest status is not PASS: {manifest.get('status')}")
    if manifest.get("evaluation_mode") != EVALUATION_MODE:
        raise SettlementError("freeze manifest is not TRUE_FORWARD")
    if manifest.get("pre_race_guard") != "PASS":
        raise SettlementError("freeze manifest pre_race_guard is not PASS")
    race_date = str(manifest.get("race_date") or "")
    if len(race_date) != 10 or race_date[4] != "-" or race_date[7] != "-":
        raise SettlementError(f"freeze manifest has invalid race_date: {race_date!r}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise SettlementError("freeze manifest files must be an object")
    match_meta = files.get("edge_matches.jsonl")
    if not isinstance(match_meta, dict) or not match_meta.get("sha256"):
        raise SettlementError("freeze manifest lacks edge_matches.jsonl SHA-256")
    return manifest, digest


def _write_manifest(output_dir: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rel = str(path.relative_to(output_dir))
        files[rel] = {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
    manifest = {
        "status": "PASS",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "race_date": provenance["race_date"],
        "settled_at_utc": provenance["settled_at_utc"],
        "provenance": provenance,
        "files": files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def run(
    *,
    matches_jsonl: str | Path,
    freeze_manifest: str | Path,
    sed_path: str | Path,
    ledger_path: str | Path,
    output_dir: str | Path,
    expected_freeze_manifest_sha256: str | None = None,
    expected_matches_sha256: str | None = None,
    expected_sed_sha256: str | None = None,
    expected_ledger_sha256: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    matches = Path(matches_jsonl)
    freeze = Path(freeze_manifest)
    sed = Path(sed_path)
    ledger = Path(ledger_path)
    for label, path in (("Matches", matches), ("Freeze manifest", freeze), ("SED", sed)):
        if not path.is_file():
            raise SettlementError(f"{label} input not found: {path}")
    if expected_ledger_sha256:
        if not ledger.is_file():
            raise SettlementError("expected prior ledger SHA supplied but ledger file is missing")
        _verify_sha(ledger, expected_ledger_sha256, "Prior ledger")

    freeze_data, freeze_sha = _load_freeze_manifest(freeze, expected_freeze_manifest_sha256)
    race_date = str(freeze_data["race_date"])
    manifest_match_sha = str(freeze_data["files"]["edge_matches.jsonl"]["sha256"]).lower()
    matches_sha = _verify_sha(matches, expected_matches_sha256 or manifest_match_sha, "Frozen matches")
    if matches_sha != manifest_match_sha:
        raise SettlementError(
            f"Frozen matches do not match freeze manifest: expected={manifest_match_sha} actual={matches_sha}"
        )
    sed_sha = _verify_sha(sed, expected_sed_sha256, "SED")

    forward_json = output / "forward_evaluation.json"
    audit_jsonl = output / "forward_audit.jsonl"
    evaluation = forward_eval.run(
        matches_jsonl=matches,
        sed_path=sed,
        output_json=forward_json,
        audit_jsonl=audit_jsonl,
        evaluation_mode=EVALUATION_MODE,
    )
    runner_audit = evaluation.get("runner_audit") or {}
    if runner_audit.get("matcher_rows") != runner_audit.get("sed_joined_rows"):
        raise SettlementError(
            f"SED exact-join incomplete: matcher={runner_audit.get('matcher_rows')} "
            f"joined={runner_audit.get('sed_joined_rows')}"
        )

    ledger_result = forward_ledger.run(
        ledger_path=ledger,
        audit_jsonl=audit_jsonl,
        race_date=race_date,
        evaluation_mode=EVALUATION_MODE,
        output_json=output / "ledger_result.json",
        summary_evaluation_mode=EVALUATION_MODE,
    )
    ledger_sha = _sha256(ledger)

    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    shutil.copy2(freeze, inputs / "freeze_manifest.json")
    shutil.copy2(matches, inputs / "edge_matches.jsonl")
    shutil.copy2(sed, inputs / sed.name)

    provenance = {
        "race_date": race_date,
        "evaluation_mode": EVALUATION_MODE,
        "settled_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze": {
            "manifest_sha256": freeze_sha,
            "matches_sha256": matches_sha,
            "frozen_at_utc": freeze_data.get("frozen_at_utc"),
            "earliest_post_time_jst": freeze_data.get("earliest_post_time_jst"),
            "pre_race_guard": freeze_data.get("pre_race_guard"),
        },
        "sed_sha256": sed_sha,
        "ledger_sha256": ledger_sha,
        "settlement_runner_audit": runner_audit,
        "ledger_import": ledger_result.get("import"),
        "semantics": "settlement consumes frozen matcher output; SED is post-race outcome only",
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = _write_manifest(output, provenance)
    return {
        "status": "success",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "race_date": race_date,
        "evaluation_overall": evaluation.get("overall"),
        "runner_audit": runner_audit,
        "ledger": ledger_result,
        "ledger_sha256": ledger_sha,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches-jsonl", required=True)
    parser.add_argument("--freeze-manifest", required=True)
    parser.add_argument("--sed", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-freeze-manifest-sha256")
    parser.add_argument("--expected-matches-sha256")
    parser.add_argument("--expected-sed-sha256")
    parser.add_argument("--expected-ledger-sha256")
    args = parser.parse_args()
    result = run(
        matches_jsonl=args.matches_jsonl,
        freeze_manifest=args.freeze_manifest,
        sed_path=args.sed,
        ledger_path=args.ledger,
        output_dir=args.output_dir,
        expected_freeze_manifest_sha256=args.expected_freeze_manifest_sha256,
        expected_matches_sha256=args.expected_matches_sha256,
        expected_sed_sha256=args.expected_sed_sha256,
        expected_ledger_sha256=args.expected_ledger_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

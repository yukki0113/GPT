#!/usr/bin/env python3
"""Select one accepted forward generation set and bind it to a target date."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from racenote_forward_errors import DataInvalid, OrchestrationMissing, run_cli
from racenote_forward_source_acceptance import (
    BINDING_SCHEMA,
    GENERATION_SCHEMA,
    HEX,
    _canonical_receipt,
    _date,
    _load,
)

GEN_DIR = Path("horse-racing/jrdb/forward-acceptance/generation-sets")


def _eligible(record: dict, target_date: str) -> bool:
    if record.get("schema_version") != GENERATION_SCHEMA or record.get("status") != "ACCEPTED":
        return False
    completion = record.get("completion_evidence")
    consistency = record.get("consumed_field_consistency")
    if (not isinstance(completion, dict) or completion.get("status") != "PASS"
            or not isinstance(consistency, dict) or consistency.get("status") != "PASS"
            or not HEX.fullmatch(str(consistency.get("report_sha256", "")))):
        return False
    cutoff = completion.get("required_completed_through")
    try:
        if _date(cutoff, "cutoff") >= _date(target_date, "target"):
            return False
        for label in ("analysis", "rrdb"):
            coverage = record.get(label, {}).get("coverage_through")
            if not (_date(cutoff, "cutoff") <= _date(coverage, label + " coverage")
                    < _date(target_date, "target")):
                return False
        if record.get("race_lap", {}).get("period_to") != cutoff:
            return False
        if _date(record.get("course_fit", {}).get("as_of"), "course_fit as_of") >= _date(target_date, "target"):
            return False
    except (ValueError, TypeError):
        return False
    return True


def select_generation_set(repo_root: Path, target_date: str) -> tuple[Path, dict, str]:
    base = (repo_root / GEN_DIR).resolve()
    if not base.is_dir():
        raise OrchestrationMissing("no forward generation-set directory")
    candidates = []
    for path in sorted(base.glob("*.json")):
        try:
            record = _load(path)
        except (OSError, ValueError) as exc:
            raise DataInvalid(f"malformed generation-set record: {path.name}") from exc
        if not _eligible(record, target_date):
            continue
        digest = _canonical_receipt(path, repo_root)
        cutoff = record["completion_evidence"]["required_completed_through"]
        candidates.append((cutoff, str(record.get("generation_set_id", "")), path, record, digest))
    if not candidates:
        raise OrchestrationMissing("no accepted forward generation set is eligible for target")
    latest_cutoff = max(item[0] for item in candidates)
    latest = [item for item in candidates if item[0] == latest_cutoff]
    ids = {item[1] for item in latest}
    if len(latest) != 1 or len(ids) != 1 or "" in ids:
        raise DataInvalid("ambiguous accepted generation set for latest completed-race cutoff")
    _, _, path, record, digest = latest[0]
    return path, record, digest


def build_binding(repo_root: Path, target_date: str, output: Path) -> dict:
    generation_path, generation, generation_sha = select_generation_set(repo_root, target_date)
    relative = generation_path.resolve().relative_to(repo_root.resolve()).as_posix()
    result = {
        "schema_version": BINDING_SCHEMA,
        "status": "BOUND",
        "target_date": target_date,
        "generation_set_id": generation["generation_set_id"],
        "generation_set_path": relative,
        "generation_set_sha256": generation_sha,
        "required_completed_through": generation["completion_evidence"]["required_completed_through"],
    }
    if output.exists():
        existing = _load(output)
        if existing != result:
            raise DataInvalid("existing target binding differs from selected generation set")
        return existing
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-date", required=True)
    ap.add_argument("--repo-root", type=Path, default=Path("."))
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    output = args.output or (
        args.repo_root / "horse-racing/jrdb/forward-acceptance/targets"
        / (args.target_date.replace("-", "") + ".json")
    )
    result = build_binding(args.repo_root, args.target_date, output)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main, "TARGET_BINDING"))

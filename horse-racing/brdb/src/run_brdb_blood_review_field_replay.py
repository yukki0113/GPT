#!/usr/bin/env python3
"""Replay one immutable RaceNote field against SHA-pinned BRDB CURRENT.

Only aggregate counts are written. The input bundle is never copied to output.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from brdb_blood_review import BloodReviewEngine
from brdb_current import DEFAULT_TRANSPORT_MANIFEST, resolve_brdb_current
from brdb_racenote_p2_adapter import adapt_racenote_bundle


def replay(bundle_path: Path, current_zip: Path, cache_root: Path, *,
           source_commit: str, input_ref: str) -> dict:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    race = bundle["race"]
    context = {
        "target_date": race["date"], "venue": race["venue"],
        "surface": race["surface"], "distance": race["distance_m"],
    }
    horse_ids = [horse["basic"]["horse_id"] for horse in bundle["horses"]]

    def pinned_fetcher(_manifest: Path, output_root: Path) -> Path:
        destination = output_root / "BloodReviewDB_CURRENT.zip"
        shutil.copyfile(current_zip, destination)
        return destination

    resolved = resolve_brdb_current(cache_root, transport_manifest=DEFAULT_TRANSPORT_MANIFEST,
                                    fetcher=pinned_fetcher)
    evidence = adapt_racenote_bundle(bundle, horse_ids, expected_context=context)
    engine = BloodReviewEngine(resolved.reader)
    batch = engine.reviews_for_horses(horse_ids, context, pedigree_contexts=evidence)
    if len(batch) != len(horse_ids):
        raise RuntimeError("field replay lost or duplicated a requested horse")
    for horse_id in horse_ids:
        if batch[horse_id] != engine.horse_review(
            horse_id, context, pedigree_context=evidence.get(horse_id)
        ):
            raise RuntimeError("batch/single review mismatch")
    if any(review["review"]["overall_score"] is not None or
           review["classification"]["regional_type"] is not None
           for review in batch.values()):
        raise RuntimeError("phase boundary violated")

    statuses = Counter(review["status"] for review in batch.values())
    coverage = Counter(review["coverage"]["pedigree_context"] for review in batch.values())
    missing = {status: count for status, count in statuses.items()
               if status in {"NO_HORSE_ID", "NO_PEDIGREE", "AS_OF_UNVERIFIED",
                             "UNSUPPORTED_CONTEXT"}}
    return {
        "contract_version": "brdb-review-v0.1",
        "target": {**context, "race_no": race.get("race_no")},
        "requested_horses": len(horse_ids),
        "produced_reviews": len(batch),
        "statuses": dict(sorted(statuses.items())),
        "p2_coverage": {key: coverage[key] for key in ("NONE", "PARTIAL", "FULL")},
        "identity_missing_by_reason": dict(sorted(missing.items())),
        "fail_closed_count": sum(count for status, count in statuses.items()
                                 if status != "AVAILABLE"),
        "batch_single_equal": True,
        "current_generation_id": resolved.reader.generation_id,
        "current_zip_sha256": resolved.provenance["transport"]["zip_sha256"],
        "source_commit": source_commit,
        "input_ref": input_ref,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race-bundle", required=True, type=Path)
    parser.add_argument("--current-zip", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--input-ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = replay(args.race_bundle, args.current_zip, args.cache_root,
                    source_commit=args.source_commit, input_ref=args.input_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

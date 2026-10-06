#!/usr/bin/env python3
"""Run real Horse History acceptance checks on an immutable Analysis artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import tarfile
import tempfile
from datetime import date
from pathlib import Path

import duckdb
import pyarrow

from jrdb_horse_history_query import query
from jrdb_analysis_parquet_current import resolve_current

EXPECTED_GENERATION = "analysis-v1_4-canonical-20260928-02"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-bundle", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--upstream-run-id", required=True, type=int)
    parser.add_argument("--upstream-artifact-name", required=True)
    parser.add_argument("--upstream-artifact-digest", required=True)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="horse-history-analysis-") as temp:
        root = Path(temp)
        with tarfile.open(args.analysis_bundle, "r:xz") as archive:
            archive.extractall(root, filter="data")
        shadow_path = root / "shadow_current.json"
        shadow = json.loads(shadow_path.read_text(encoding="utf-8"))
        if shadow.get("generation_id") != EXPECTED_GENERATION:
            raise SystemExit(f"unexpected upstream generation: {shadow.get('generation_id')!r}")
        if shadow.get("status") != "SHADOW_PASS":
            raise SystemExit("upstream candidate pointer is not SHADOW_PASS")
        current_pointer = {**shadow, "status": "CURRENT"}
        (root / "current.json").write_text(json.dumps(current_pointer, sort_keys=True) + "\n", encoding="utf-8")
        report = resolve_current(root)
        if report["generation_id"] != EXPECTED_GENERATION:
            raise SystemExit("canonical generation identity mismatch")
        manifest_path = Path(report["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        fact_count = len(manifest["fact_table"]["partitions"])
        files = [str(asset["path"]) for asset in report["assets"][:fact_count]]
        con = duckdb.connect()
        try:
            bounds = con.execute(
                "SELECT CAST(min(race_date) AS VARCHAR), CAST(max(race_date) AS VARCHAR) FROM read_parquet(?, union_by_name=true)",
                [files],
            ).fetchone()
            sample = con.execute(
                "SELECT CAST(horse_id AS VARCHAR), CAST(race_date AS VARCHAR) FROM read_parquet(?, union_by_name=true) WHERE horse_id IS NOT NULL ORDER BY race_date, race_key, horse_no LIMIT 1",
                [files],
            ).fetchone()
        finally:
            con.close()
        if not bounds or not bounds[0] or not bounds[1] or not sample:
            raise SystemExit("canonical fact partitions have no usable coverage/sample")
        min_date, max_date = str(bounds[0])[:10], str(bounds[1])[:10]
        horse_id, sample_date = str(sample[0]), str(sample[1])[:10]
        date.fromisoformat(min_date)
        date.fromisoformat(max_date)
        date.fromisoformat(sample_date)
        if not (min_date <= sample_date <= max_date):
            raise SystemExit("sample horse date falls outside canonical coverage")

        full = query(horse_id=horse_id, analysis_root=root, order="asc", limit=10)
        starts = full["starts"]
        if not starts or any(str(row.get("horse_id")) != horse_id for row in starts):
            raise SystemExit("exact horse_id filtering failed")
        dates = [str(row["race_date"])[:10] for row in starts]
        if dates != sorted(dates):
            raise SystemExit("chronological ordering failed")
        identities = [(row.get("race_key"), row.get("horse_no")) for row in starts]
        if any(None in identity for identity in identities) or len(identities) != len(set(identities)):
            raise SystemExit("race identity missing or duplicate race_key + horse_no")
        if full["source_provenance"].get("generation_id") != EXPECTED_GENERATION:
            raise SystemExit("Horse History provenance generation mismatch")

        bounded = query(
            horse_id=horse_id,
            analysis_root=root,
            from_date=sample_date,
            to_date=sample_date,
            order="asc",
            limit=1,
        )
        if not bounded["starts"] or len(bounded["starts"]) > 1:
            raise SystemExit("real date-bound/limit query returned no row or exceeded limit")
        if any(str(row["race_date"])[:10] != sample_date for row in bounded["starts"]):
            raise SystemExit("real query violated inclusive date bounds")
        if any(str(row.get("horse_id")) != horse_id for row in bounded["starts"]):
            raise SystemExit("bounded query returned another horse")

        result = {
            "status": "PASS",
            "implementation_base_commit": "6cf0ad5a27971be622dce84269aaffef80e81912",
            "analysis": {
                "generation_id": report["generation_id"],
                "manifest_sha256": sha256(manifest_path),
                "manifest_relative_path": f"generations/{EXPECTED_GENERATION}/manifest.json",
                "fact_table": manifest["fact_table"]["name"],
                "partition_count": fact_count,
                "row_count": report["rows"],
                "coverage_min_date": min_date,
                "coverage_max_date": max_date,
                "upstream_run_id": args.upstream_run_id,
                "upstream_artifact_name": args.upstream_artifact_name,
                "upstream_artifact_digest": args.upstream_artifact_digest,
            },
            "runtime": {
                "python": platform.python_version(),
                "duckdb": duckdb.__version__,
                "pyarrow": pyarrow.__version__,
            },
            "real_query": {
                "horse_id": horse_id,
                "sample_date": sample_date,
                "returned_rows": len(starts),
                "bounded_rows": len(bounded["starts"]),
                "bounded_date": sample_date,
                "limit": 1,
                "exact_horse_filter": True,
                "chronological_order": True,
                "unique_race_key_horse_no": True,
                "provenance_generation_id": full["source_provenance"]["generation_id"],
            },
            "focused_validation": "PASS",
        }
        (output / "horse-history-canonical-validation.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

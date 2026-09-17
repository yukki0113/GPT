#!/usr/bin/env python3
"""Create an immutable Fact Lite Parquet generation and advance its shadow/current pointer."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

TABLES = ("meta_pwa_fact_build", "dim_sire", "dim_bms", "dim_jockey", "dim_race", "fact_stats_entry")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish(source: Path, root: Path, generation_id: str, *, promote: bool = False,
            analysis_manifest: str | None = None) -> dict:
    source, root = source.resolve(), root.resolve()
    audit_path = source / "equivalence_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS":
        raise RuntimeError("Fact Lite logical audit did not pass")
    generation = root / "generations" / generation_id
    if generation.exists():
        raise FileExistsError(generation)
    generation.mkdir(parents=True)
    try:
        tables: dict[str, dict] = {}
        for table in TABLES:
            candidate = source / f"{table}.parquet"
            if not candidate.is_file():
                raise RuntimeError(f"missing table: {table}")
            target = generation / candidate.name
            shutil.copy2(candidate, target)
            tables[table] = {"path": candidate.name, "size_bytes": target.stat().st_size, "sha256": sha256(target),
                             "rows": int(audit["table_rows"].get(table, 1))}
        shutil.copy2(audit_path, generation / "equivalence_audit.json")
        manifest = {"artifact_type": "jrdb_fact_lite", "schema_version": "v0.3", "storage_format": "parquet",
                    "storage_version": "1", "generation_id": generation_id, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "analysis_manifest": analysis_manifest, "tables": tables, "validation_status": "PASS"}
        (generation / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pointer = {"status": "CURRENT" if promote else "SHADOW_PASS", "generation_id": generation_id,
                   "manifest": f"generations/{generation_id}/manifest.json"}
        pointer_path = root / ("parquet_current.json" if promote else "parquet_shadow_current.json")
        pending = pointer_path.with_suffix(".pending")
        pending.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.replace(pointer_path)
        return {"manifest": manifest, "pointer": pointer}
    except Exception:
        shutil.rmtree(generation, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--analysis-manifest")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    print(json.dumps(publish(args.source, args.output_root, args.generation_id, promote=args.promote,
                             analysis_manifest=args.analysis_manifest), ensure_ascii=False))


if __name__ == "__main__":
    main()

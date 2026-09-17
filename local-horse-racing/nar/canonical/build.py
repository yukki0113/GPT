from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import zipfile

from .field_catalog import catalog_rows
from .leakage import validate_history_asof
from .parser import CanonicalBatch
from .reconciliation import parse_monthly_race_zip_reconciled
from .schema import TABLE_SPECS
from .storage import materialize_parquet


def iter_monthly_race_zips(path: Path):
    """Yield (source_name, bytes) from an official monthly race ZIP or a year wrapper ZIP."""
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if any(name.endswith("_racelist.csv") for name in names):
            yield path.name, raw
            return
        monthly = [name for name in names if name.lower().endswith("_race.zip")]
        if not monthly or len(monthly) != len(names):
            raise ValueError(f"unsupported ZIP layout: {path}")
        for name in sorted(monthly):
            yield name, archive.read(name)


def _ensure_writer(writer_state: dict, output_dir: Path, table_name: str):
    state = writer_state.get(table_name)
    if state is None:
        spec = TABLE_SPECS[table_name]
        output_dir.mkdir(parents=True, exist_ok=True)
        handle = (output_dir / f"{table_name}.csv").open("w", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(handle, fieldnames=list(spec.schema), extrasaction="raise")
        writer.writeheader()
        state = (handle, writer)
        writer_state[table_name] = state
    return state


def _write_rows(writer_state: dict, output_dir: Path, table_name: str, rows: list[dict]) -> None:
    spec = TABLE_SPECS[table_name]
    handle, writer = _ensure_writer(writer_state, output_dir, table_name)
    for row in rows:
        writer.writerow({name: "" if row.get(name) is None else row.get(name) for name in spec.schema})


def build_staging(inputs: list[Path], output_dir: Path, *, validate_asof: bool = False) -> dict:
    writers: dict = {}
    month_count = 0
    row_counts = {name: 0 for name in TABLE_SPECS}
    reconciled_race_count = 0
    history_rows: list[dict] = []
    result_rows: list[dict] = []
    try:
        for table_name in TABLE_SPECS:
            _ensure_writer(writers, output_dir, table_name)
        for input_path in inputs:
            for source_name, content in iter_monthly_race_zips(input_path):
                batch: CanonicalBatch = parse_monthly_race_zip_reconciled(content, source_name)
                month_count += 1
                reconciled_race_count += sum(
                    1
                    for row in batch.tables["control_race_status"]
                    if str(row.get("reason") or "").startswith("racelist_missing_horselist_present")
                )
                for table_name, rows in batch.tables.items():
                    _write_rows(writers, output_dir, table_name, rows)
                    row_counts[table_name] += len(rows)
                if validate_asof:
                    history_rows.extend(batch.tables["pre_runner_history_snapshot"])
                    result_rows.extend(batch.tables["post_runner_result"])
    finally:
        for handle, _ in writers.values():
            handle.close()

    control = output_dir / "control"
    control.mkdir(parents=True, exist_ok=True)
    field_catalog_path = control / "field_catalog.json"
    field_catalog_path.write_text(json.dumps(catalog_rows(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    leakage_report = None
    if validate_asof:
        leakage_report = validate_history_asof(history_rows, result_rows)
        (control / "leakage_validation.json").write_text(
            json.dumps(leakage_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    summary = {
        "status": "success",
        "monthly_zip_count": month_count,
        "row_counts": row_counts,
        "historical_reconciliation": {
            "racelist_missing_horselist_present_races": reconciled_race_count,
        },
        "field_catalog": str(field_catalog_path),
        "leakage_validation": leakage_report,
    }
    (control / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build leakage-safe NAR canonical staging data")
    parser.add_argument("--input", action="append", required=True, help="official monthly race ZIP or year wrapper ZIP")
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--validate-asof", action="store_true")
    parser.add_argument("--parquet-dir")
    parser.add_argument("--audit-dir")
    args = parser.parse_args(argv)

    staging = Path(args.staging_dir)
    summary = build_staging([Path(item) for item in args.input], staging, validate_asof=args.validate_asof)
    if args.parquet_dir:
        audit_dir = Path(args.audit_dir) if args.audit_dir else Path(args.parquet_dir) / "_audit"
        summary["parquet"] = materialize_parquet(staging, Path(args.parquet_dir), audit_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

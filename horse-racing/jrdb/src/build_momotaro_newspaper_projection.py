#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the public Momotaro Newspaper projection from an audited Newspaper day.

The projection is intentionally allowlist-based:
- keep JRDB/base race and horse fields already present in the Newspaper bundle;
- keep only the shared external addons.keibailuka addon;
- remove private/individual addons such as Eval, RaceNote and my_index;
- clear Edge matches;
- optionally merge sparse three-member predictions from an exact-key CSV.

The output directory contains only manifest.json, audit.json, day-package.json
and races/*.json so unrelated files from the source release cannot leak.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

MEMBER_ALIASES = {
    "ryota": "ryota",
    "りょーた": "ryota",
    "oji": "oji",
    "おーじ": "oji",
    "kenshow": "kenshow",
    "けんしょー": "kenshow",
}

PREDICTION_REQUIRED_COLUMNS = {
    "date",
    "venue_code",
    "race_no",
    "horse_no",
    "horse_name",
    "member",
    "mark",
    "confidence",
    "review_horse",
    "comment",
}

SHARED_SOURCE_KEYS = {
    "jrdb_base",
    "jrdb_history",
    "keibailuka",
}


def sha_bytes(data: bytes) -> str:
    """Return lowercase SHA-256 for bytes."""
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    """Return lowercase SHA-256 for a file."""
    return sha_bytes(path.read_bytes())


def write_json(value: Any, path: Path, *, compact: bool = False) -> None:
    """Write UTF-8 JSON with deterministic trailing newline."""
    if compact:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    path.write_text(payload + "\n", encoding="utf-8")


def parse_bool(value: str, line_no: int) -> bool:
    """Parse a conservative CSV boolean value."""
    normalized = str(value or "").strip().lower()
    if normalized in {"", "0", "false", "no", "n", "-", "×"}:
        return False
    if normalized in {"1", "true", "yes", "y", "○"}:
        return True
    raise ValueError(
        f"invalid review_horse at CSV line {line_no}: {value!r}"
    )


def load_predictions(
    path: Path,
) -> tuple[
    dict[tuple[str, str, int, int, str], dict[str, Any]],
    str,
]:
    """Load sparse Momotaro predictions with exact horse/member identity."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = PREDICTION_REQUIRED_COLUMNS - fields
        if missing:
            raise ValueError(
                "Momotaro CSV missing required columns: "
                f"{sorted(missing)}"
            )
        rows = list(reader)

    if not rows:
        raise ValueError("Momotaro CSV has no data rows")

    index: dict[tuple[str, str, int, int, str], dict[str, Any]] = {}
    for line_no, row in enumerate(rows, start=2):
        date = str(row.get("date") or "").strip()
        venue_code = str(row.get("venue_code") or "").strip().zfill(2)
        horse_name = str(row.get("horse_name") or "").strip()
        member_raw = str(row.get("member") or "").strip()
        member = MEMBER_ALIASES.get(member_raw)
        mark = str(row.get("mark") or "").strip()
        confidence = str(row.get("confidence") or "").strip()
        tag = str(row.get("tag") or "").strip()
        comment = str(row.get("comment") or "").strip()

        try:
            race_no = int(str(row.get("race_no") or "").strip())
            horse_no = int(str(row.get("horse_no") or "").strip())
        except ValueError as exc:
            raise ValueError(
                f"invalid Momotaro numeric identity at CSV line {line_no}"
            ) from exc

        try:
            dt.date.fromisoformat(date)
        except ValueError as exc:
            raise ValueError(
                f"invalid Momotaro date at CSV line {line_no}: {date!r}"
            ) from exc

        if not re.fullmatch(r"\d{2}", venue_code):
            raise ValueError(
                f"invalid Momotaro venue_code at CSV line {line_no}: "
                f"{venue_code!r}"
            )
        if not 1 <= race_no <= 12 or horse_no < 1:
            raise ValueError(
                f"invalid Momotaro race/horse at CSV line {line_no}"
            )
        if not horse_name:
            raise ValueError(
                f"blank Momotaro horse_name at CSV line {line_no}"
            )
        if member is None:
            raise ValueError(
                f"invalid Momotaro member at CSV line {line_no}: "
                f"{member_raw!r}"
            )

        review_horse = parse_bool(
            str(row.get("review_horse") or ""),
            line_no,
        )
        if not mark and not confidence and not review_horse and not comment:
            raise ValueError(
                f"empty Momotaro prediction at CSV line {line_no}"
            )

        key = (date, venue_code, race_no, horse_no, member)
        if key in index:
            raise ValueError(f"duplicate Momotaro key: {key}")

        index[key] = {
            "date": date,
            "venue_code": venue_code,
            "race_no": race_no,
            "horse_no": horse_no,
            "horse_name": horse_name,
            "member": member,
            "mark": mark,
            "confidence": confidence,
            "tag": tag,
            "review_horse": review_horse,
            "comment": comment,
        }

    return index, sha_file(path)


def filtered_source_status(source_status: Any) -> dict[str, Any]:
    """Keep only source states approved for the Momotaro public surface."""
    if not isinstance(source_status, dict):
        return {}

    output: dict[str, Any] = {}
    for key in SHARED_SOURCE_KEYS:
        value = source_status.get(key)
        if isinstance(value, dict):
            output[key] = value
    return output


def project_horse(
    horse: dict[str, Any],
    *,
    race_date: str,
    venue_code: str,
    race_no: int,
    prediction_index: dict[
        tuple[str, str, int, int, str],
        dict[str, Any],
    ],
    seen_predictions: set[tuple[str, str, int, int, str]],
) -> dict[str, Any]:
    """Project one horse and optionally attach exact-key Momotaro predictions."""
    projected = json.loads(json.dumps(horse, ensure_ascii=False))

    original_addons = horse.get("addons")
    shared_addons: dict[str, Any] = {}
    if isinstance(original_addons, dict):
        iluka = original_addons.get("keibailuka")
        if iluka is not None:
            shared_addons["keibailuka"] = iluka

    horse_no = int(projected["key"]["horse_no"])
    horse_name = str(projected["basic"]["horse_name"])
    momotaro: dict[str, Any] = {}

    for member in ("ryota", "oji", "kenshow"):
        key = (
            race_date,
            venue_code,
            race_no,
            horse_no,
            member,
        )
        row = prediction_index.get(key)
        if row is None:
            continue
        if row["horse_name"] != horse_name:
            raise ValueError(
                f"Momotaro horse-name mismatch for {key}: "
                f"{row['horse_name']!r} != {horse_name!r}"
            )

        momotaro[member] = {
            "mark": row["mark"] or None,
            "confidence": row["confidence"] or None,
            "tag": row["tag"] or None,
            "review_horse": row["review_horse"],
            "comment": row["comment"] or None,
        }
        seen_predictions.add(key)

    if momotaro:
        shared_addons["momotaro"] = momotaro

    projected["addons"] = shared_addons
    projected["edge_matches"] = []
    return projected


def build_projection(
    day_dir: Path,
    output_dir: Path,
    *,
    momotaro_csv: Path | None = None,
) -> dict[str, Any]:
    """Build a fail-closed public Momotaro projection."""
    source_manifest_path = day_dir / "manifest.json"
    source_races_dir = day_dir / "races"
    if not source_manifest_path.is_file() or not source_races_dir.is_dir():
        raise ValueError("day-dir must contain manifest.json and races/")

    if day_dir.resolve() == output_dir.resolve():
        raise ValueError("output-dir must differ from day-dir")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "races").mkdir(parents=True)

    manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    if (
        manifest.get("schema_version") != "0.1"
        or manifest.get("manifest_kind")
        != "jrdb_pwa_newspaper_daily_manifest"
    ):
        raise ValueError("unexpected Newspaper daily manifest")

    prediction_index: dict[
        tuple[str, str, int, int, str],
        dict[str, Any],
    ] = {}
    prediction_sha: str | None = None
    if momotaro_csv is not None:
        prediction_index, prediction_sha = load_predictions(
            momotaro_csv
        )

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    seen_predictions: set[
        tuple[str, str, int, int, str]
    ] = set()
    output_entries: list[dict[str, Any]] = []
    race_outputs: list[dict[str, Any]] = []

    for source_entry in manifest.get("races") or []:
        relative = str(source_entry.get("path") or "")
        source_race_path = day_dir / relative
        if not source_race_path.is_file():
            raise ValueError(
                f"source Newspaper race file missing: {relative}"
            )

        bundle = json.loads(
            source_race_path.read_text(encoding="utf-8")
        )
        race = bundle.get("race") or {}
        race_date = str(race.get("date") or "")
        venue_code = str(race.get("venue_code") or "").zfill(2)
        race_no = int(race.get("race_no") or 0)

        projected_horses: list[dict[str, Any]] = []
        for horse in bundle.get("horses") or []:
            projected_horses.append(
                project_horse(
                    horse,
                    race_date=race_date,
                    venue_code=venue_code,
                    race_no=race_no,
                    prediction_index=prediction_index,
                    seen_predictions=seen_predictions,
                )
            )
        bundle["horses"] = projected_horses

        metadata = bundle.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            bundle["metadata"] = metadata
        metadata["source_status"] = filtered_source_status(
            metadata.get("source_status")
        )
        metadata["projection"] = {
            "kind": "momotaro_newspaper_public",
            "generated_at": now,
        }

        expected_for_race = 0
        if momotaro_csv is not None:
            for key in prediction_index:
                if (
                    key[0] == race_date
                    and key[1] == venue_code
                    and key[2] == race_no
                ):
                    expected_for_race += 1
            metadata["source_status"]["momotaro"] = {
                "state": "READY",
                "source_version": momotaro_csv.name,
                "generated_at": now,
                "message": (
                    f"targeted={expected_for_race} "
                    f"merged={expected_for_race}"
                ),
            }
        else:
            metadata["source_status"]["momotaro"] = {
                "state": "PENDING",
                "source_version": None,
                "generated_at": now,
                "message": "prediction source not supplied",
            }

        race_notes = bundle.get("race_notes")
        if isinstance(race_notes, dict):
            race_notes.pop("racenote_short_comment", None)

        target_path = output_dir / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(bundle, target_path)

        projected_entry = json.loads(
            json.dumps(source_entry, ensure_ascii=False)
        )
        projected_entry["sha256"] = sha_file(target_path)
        projected_entry["size_bytes"] = target_path.stat().st_size
        output_entries.append(projected_entry)
        race_outputs.append(bundle)

    if set(prediction_index) != seen_predictions:
        unused = sorted(set(prediction_index) - seen_predictions)
        raise ValueError(
            f"Momotaro rows not consumed: count={len(unused)} "
            f"sample={unused[:5]}"
        )

    manifest["generated_at"] = now
    manifest["source_status"] = filtered_source_status(
        manifest.get("source_status")
    )
    if momotaro_csv is not None:
        manifest["source_status"]["momotaro"] = {
            "state": "READY",
            "source_version": momotaro_csv.name,
            "generated_at": now,
            "message": (
                f"targeted={len(prediction_index)} "
                f"merged={len(seen_predictions)}"
            ),
        }
    else:
        manifest["source_status"]["momotaro"] = {
            "state": "PENDING",
            "source_version": None,
            "generated_at": now,
            "message": "prediction source not supplied",
        }
    manifest["projection"] = {
        "kind": "momotaro_newspaper_public",
        "generated_at": now,
        "shared_addons": ["keibailuka"],
        "private_addons_removed": True,
        "edge_matches_removed": True,
    }
    manifest["races"] = output_entries
    write_json(manifest, output_dir / "manifest.json")

    package = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_day_package",
        "manifest": manifest,
        "races": race_outputs,
    }
    write_json(
        package,
        output_dir / "day-package.json",
        compact=True,
    )

    audit = {
        "status": "PASS",
        "generated_at": now,
        "projection_kind": "momotaro_newspaper_public",
        "source_manifest_sha256": sha_file(source_manifest_path),
        "race_count": len(output_entries),
        "momotaro_predictions": {
            "source_file": None,
            "source_sha256": prediction_sha,
            "targeted": len(prediction_index),
            "merged": len(seen_predictions),
        },
        "privacy": {
            "allowed_addons": ["keibailuka", "momotaro"],
            "private_addons_removed": True,
            "edge_matches_removed": True,
            "source_audit_not_copied": True,
        },
    }
    if momotaro_csv is not None:
        audit["momotaro_predictions"]["source_file"] = (
            momotaro_csv.name
        )
    write_json(audit, output_dir / "audit.json")

    return {
        "status": "PASS",
        "output_dir": str(output_dir),
        "date": manifest.get("date"),
        "races": len(output_entries),
        "momotaro_rows": len(seen_predictions),
        "manifest_sha256": sha_file(output_dir / "manifest.json"),
        "day_package_sha256": sha_file(
            output_dir / "day-package.json"
        ),
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--momotaro-csv", type=Path)
    args = parser.parse_args()

    result = build_projection(
        args.day_dir,
        args.output_dir,
        momotaro_csv=args.momotaro_csv,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

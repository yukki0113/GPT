#!/usr/bin/env python3
"""BTDAY RaceLap input: fixed baseline OR reviewed/approved current snapshot.

No authenticated Drive API, folder listing or automatic promotion in Actions.
Each invocation resolves a reviewed immutable transport and seals a run receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "horse-racing/jrdb/config/racenote_btday_racelap_baseline_v1.json"
APPROVED_CURRENT = ROOT / "horse-racing/jrdb/config/racenote_btday_racelap_approved_current_v1.json"
APPROVED_TRANSPORT_ROOT = ROOT / "horse-racing/jrdb/config/public_drive"
MODES = {"baseline": BASELINE, "approved_current": APPROVED_CURRENT}
SCHEMA = "racenote-btday-racelap-source-v1"
RECEIPT_SCHEMA = "racenote-btday-racelap-input-receipt-v1"
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
GENERATION = re.compile(r"racelap-forward-canonical-[0-9]{8}-[0-9]{2}\Z")

sys.path.insert(0, str(ROOT))
from tools.gpt_io.public_drive.fetch import fetch, read_manifest  # noqa: E402


class RaceLapSourceError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve(mode: str, *, source_config: Path | None = None) -> dict:
    if mode not in MODES:
        raise RaceLapSourceError(f"unknown RaceLap input mode: {mode}")
    path = Path(source_config) if source_config is not None else MODES[mode]
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != SCHEMA or data.get("mode") != mode:
        raise RaceLapSourceError("RaceLap source contract mismatch")
    expected_status = "ACCEPTED_BASELINE" if mode == "baseline" else "APPROVED"
    if data.get("status") != expected_status:
        raise RaceLapSourceError("RaceLap source not accepted for selected mode")
    policy = ("fixed-reproduction" if mode == "baseline"
              else "reviewed-immutable-promotion")
    if data.get("selection_policy") != policy:
        raise RaceLapSourceError("RaceLap source selection policy mismatch")
    if mode == "approved_current" and not re.fullmatch(
        r"racelap-approved-current-[A-Za-z0-9_-]+", str(data.get("approval_id", ""))
    ):
        raise RaceLapSourceError("RaceLap CURRENT approval ID required")
    for key in ("parquet_sha256", "archive_sha256"):
        if not HEX64.fullmatch(str(data.get(key, ""))):
            raise RaceLapSourceError(f"RaceLap source {key} missing")
    if not GENERATION.fullmatch(str(data.get("generation_id", ""))):
        raise RaceLapSourceError("invalid RaceLap source generation")
    if not re.fullmatch(r"20\d{2}-\d\d-\d\d", str(data.get("period_to", ""))):
        raise RaceLapSourceError("invalid RaceLap source period_to")
    if type(data.get("race_count")) is not int or data["race_count"] <= 0:
        raise RaceLapSourceError("invalid RaceLap source race_count")
    transport_relative = str(data.get("transport_manifest", ""))
    transport_path = (ROOT / transport_relative).resolve()
    if not transport_path.is_relative_to(APPROVED_TRANSPORT_ROOT.resolve()) or transport_path.suffix != ".json":
        raise RaceLapSourceError("transport manifest outside approved public Drive directory")
    rows = read_manifest(transport_path)
    matched = [r for r in rows if r["artifact_id"] == data.get("artifact_id")]
    if len(matched) != 1:
        raise RaceLapSourceError("RaceLap approved artifact not found in reviewed manifest")
    row = matched[0]
    if row["sha256"] != data["archive_sha256"] or not row.get("expected_size"):
        raise RaceLapSourceError("RaceLap transport SHA/size not pinned in approval")
    # CURRENT must never fetch the mutable operational Drive object directly.
    if row["file_id"] == "1RdmS-8q0NsA8opCvNioaqVotk2wiEZz-" or row["expected_name"] == "RaceLap_CURRENT.zip":
        raise RaceLapSourceError("mutable Drive CURRENT is not an immutable approved source")
    return {"binding": data, "binding_sha256": _sha(raw),
            "manifest": transport_path, "manifest_sha256": _sha(transport_path.read_bytes()),
            "artifact": row}


def materialize(
    mode: str,
    output_root: Path,
    *,
    selection_id: str,
    target_date: str,
    source_config: Path | None = None,
    downloader: Callable | None = None,
) -> dict:
    """Fetch with canonical pinned helper; validate manifest+parquet; seal receipt."""
    source = resolve(mode, source_config=source_config)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    binding = source["binding"]
    row = source["artifact"]
    with tempfile.TemporaryDirectory(prefix="racelap-btday-", dir=root) as tmp:
        stage = Path(tmp)
        remote = fetch(source["manifest"], stage / "transport",
                       selected=row["artifact_id"], downloader=downloader)
        if len(remote["artifacts"]) != 1 or not remote["artifacts"][0].get("verified"):
            raise RaceLapSourceError("RaceLap transport receipt not verified")
        archive_path = stage / "transport" / row["destination"]
        archive_sha = _sha(archive_path.read_bytes())
        if archive_sha != binding["archive_sha256"]:
            raise RaceLapSourceError("RaceLap archive SHA changed")
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise RaceLapSourceError("RaceLap ZIP CRC mismatch")
            required = ("current/manifest.json", "current/race_lap.parquet",
                        "current/audit.json")
            names = archive.namelist()
            if len(names) != len(set(names)) or any(n not in names for n in required):
                raise RaceLapSourceError("RaceLap ZIP missing or duplicate member")
            manifest_bytes = archive.read(required[0])
            parquet = archive.read(required[1])
            audit_bytes = archive.read(required[2])
        manifest = json.loads(manifest_bytes)
        audit = json.loads(audit_bytes)
        parquet_sha = _sha(parquet)
        if (manifest.get("status") != "CURRENT"
            or manifest.get("validation_status") != "PASS"
            or manifest.get("generation_id") != binding["generation_id"]
            or manifest.get("period_to") != binding["period_to"]
            or manifest.get("race_count") != binding["race_count"]
            or manifest.get("parquet_sha256") != binding["parquet_sha256"]
            or manifest.get("parquet_size_bytes") != len(parquet)
            or audit.get("generation_id") != binding["generation_id"]
            or audit.get("validation_status") != "PASS"
            or audit.get("parquet_sha256") != binding["parquet_sha256"]
            or parquet_sha != binding["parquet_sha256"]):
            raise RaceLapSourceError("RaceLap approved generation/Parquet/coverage mismatch")
        for name in ("race_lap.parquet", "race_lap.audit.json",
                     "race_lap.manifest.json", "race_lap.input_receipt.json"):
            if (root / name).exists():
                raise RaceLapSourceError(f"RaceLap output exists; refusing overwrite: {name}")
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "mode": mode,
            "selection_id": selection_id,
            "target_date": target_date,
            "approval_id": binding.get("approval_id") if mode == "approved_current" else None,
            "selection_policy": binding["selection_policy"],
            "transport_manifest": binding["transport_manifest"],
            "transport_manifest_sha256": source["manifest_sha256"],
            "binding_sha256": source["binding_sha256"],
            "artifact_id": row["artifact_id"],
            "drive_file_id": row["file_id"],
            "archive_sha256": archive_sha,
            "archive_size_bytes": archive_path.stat().st_size,
            "generation_id": binding["generation_id"],
            "period_to": binding["period_to"],
            "race_count": binding["race_count"],
            "parquet_sha256": parquet_sha,
            "parquet_size_bytes": len(parquet),
            "source_manifest_sha256": _sha(manifest_bytes),
            "validation_status": "PASS",
        }
        # Stage every consumer output before exposing it.
        outputs = {
            "race_lap.parquet": parquet,
            "race_lap.audit.json": audit_bytes,
            "race_lap.manifest.json": manifest_bytes,
            "race_lap.input_receipt.json":
                (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        }
        for name, contents in outputs.items():
            (stage / name).write_bytes(contents)
        for name in outputs:
            (stage / name).replace(root / name)
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--selection-id", required=True)
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()
    receipt = materialize(args.mode, args.output_root,
                          selection_id=args.selection_id, target_date=args.target_date)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

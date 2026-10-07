#!/usr/bin/env python3
"""Complete the canonical 2026 PACI set after an unreliable folder transfer."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def recover(paci_root, sed_root, inventory_path, fetch=None):
    inventory = json.loads(Path(inventory_path).read_text())
    files = inventory["files"]
    expected = {p.name.replace("SED", "PACI") for p in Path(sed_root).rglob("SED26????.zip")}
    if not expected or expected - files.keys():
        raise ValueError(f"SED dates absent from canonical PACI inventory: {sorted(expected - files.keys())}")
    existing = {p.name for p in Path(paci_root).rglob("PACI26????.zip")}
    if existing - expected:
        raise ValueError(f"PACI dates absent from SED chronology: {sorted(existing - expected)}")
    bulk_count = len(existing)
    fetch = fetch or (lambda file_id, path: subprocess.run(
        ["gdown", "--id", file_id, "-O", str(path)], check=True))
    recovered = []
    for name in sorted(expected - existing):
        target = Path(paci_root) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        fetch(files[name], target)
        if not target.is_file() or not target.stat().st_size:
            raise ValueError(f"exact-ID download failed: {name}")
        recovered.append(name)
    final = {p.name for p in Path(paci_root).rglob("PACI26????.zip")}
    missing = sorted(expected - final)
    report = {"folder_inventory_count": len(files), "sed_date_count": len(expected),
              "bulk_downloaded_count": bulk_count, "exact_id_recovered_count": len(recovered),
              "exact_id_recovered_files": recovered, "final_paci_count": len(final),
              "remaining_missing_date_count": len(missing), "remaining_missing_files": missing,
              "file_ids": {name: files[name] for name in sorted(expected)}}
    report["input_set_sha256"] = hashlib.sha256(json.dumps(
        [(name, hashlib.sha256(next(Path(paci_root).rglob(name)).read_bytes()).hexdigest())
         for name in sorted(expected)], separators=(",", ":")).encode()).hexdigest()
    if missing or final != expected:
        raise ValueError(f"canonical PACI date mismatch: {report}")
    return report


def main():
    parser = argparse.ArgumentParser()
    for key in ("paci_root", "sed_root", "inventory", "output"):
        parser.add_argument("--" + key.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    result = recover(args.paci_root, args.sed_root, args.inventory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "file_ids"}, sort_keys=True))


if __name__ == "__main__":
    main()

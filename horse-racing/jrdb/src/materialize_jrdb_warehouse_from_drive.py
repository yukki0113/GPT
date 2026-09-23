#!/usr/bin/env python3
"""Materialize an accepted JRDB Warehouse generation from Drive staging folders.

This is a read-only consumer: it downloads immutable Parquet objects and
sidecars, never rebuilds or uploads Warehouse assets.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
from typing import Any

GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
FAMILIES = ("BAC","KYI","CHA","CYB","SED","SKB","ZED","ZKB","HJC","UKC")
RELATIONS = {
    "BAC": {"bac"}, "KYI": {"kyi"}, "CHA": {"cha"}, "CYB": {"cyb"},
    "SED": {"sed"}, "SKB": {"skb"}, "ZED": {"zed"}, "ZKB": {"zkb"},
    "UKC": {"ukc", "ukc_source_record_lineage"},
    "HJC": {"hjc_payout", "hjc_race"},
}

def download(file_id: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.unlink(missing_ok=True)
    subprocess.run(["gdown", file_id, "-O", str(tmp), "--quiet"], check=True)
    tmp.replace(out)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def folder_download(folder_id: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "gdown", "--folder", f"https://drive.google.com/drive/folders/{folder_id}",
        "-O", str(out), "--quiet",
    ], check=True)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest-id", required=True)
    p.add_argument("--audit-id", required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--asset-root", action="append", required=True,
                   help="FAMILY=Drive staging folder id")
    p.add_argument("--result-json", type=Path, required=True)
    a = p.parse_args()
    roots = {}
    for value in a.asset_root:
        family, sep, folder = value.partition("=")
        if not sep or family.upper() not in FAMILIES or not folder:
            raise SystemExit("asset-root must be FAMILY=DriveFolderId")
        roots[family.upper()] = folder
    if set(roots) != set(FAMILIES):
        raise SystemExit(f"asset-root must contain exactly {','.join(FAMILIES)}")

    a.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = a.output_root / "manifest.json"
    audit_path = a.output_root / "audit.json"
    download(a.manifest_id, manifest_path)
    download(a.audit_id, audit_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if manifest.get("generation_id") != GENERATION or manifest.get("status") != "PASS":
        raise SystemExit("accepted manifest gate failed")
    if audit.get("generation_id") != GENERATION or audit.get("status") != "PASS":
        raise SystemExit("accepted audit gate failed")
    assets = manifest.get("assets") or []
    expected = [x for x in assets if str(x.get("family","")).lower() in {r for rs in RELATIONS.values() for r in rs}]
    if len(expected) != 192:
        raise SystemExit(f"expected 192 Warehouse assets, got {len(expected)}")

    checks = {}
    for family, folder_id in roots.items():
        staging = a.output_root / "_staging" / family
        folder_download(folder_id, staging)
        marker = next(staging.rglob("completion_marker.json"), None)
        if marker:
            marker_data = json.loads(marker.read_text(encoding="utf-8"))
            marker_status = str(marker_data.get("status") or "").upper()
            if marker_status in {"FAIL", "FAILED", "ERROR"}:
                raise SystemExit(f"{family} completion marker is failed")
        family_expected = [x for x in expected if str(x["family"]).lower() in RELATIONS[family]]
        family_root = a.output_root / family
        family_root.mkdir(parents=True, exist_ok=True)
        rows = []
        for spec in sorted(family_expected, key=lambda x: (int(x["year"]), str(x["relative_path"]))):
            year = int(spec["year"])
            rel = Path(spec["relative_path"])
            source = next((x for x in staging.rglob(rel.name) if x.is_file()), None)
            if source is None:
                raise SystemExit(f"missing Drive asset {family}/{year}: {rel.name}")
            target = family_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            actual_sha = sha256(target)
            actual_size = target.stat().st_size
            if actual_sha != str(spec["sha256"]).lower() or actual_size != int(spec["size_bytes"]):
                raise SystemExit(f"asset verification failed {family}/{year}")
            rows.append({"year": year, "path": str(target), "sha256": actual_sha,
                         "size_bytes": actual_size, "row_count": spec.get("row_count")})
        checks[family] = {"status": "PASS", "asset_count": len(rows), "assets": rows}

    result = {"status": "PASS", "generation_id": GENERATION, "asset_count": sum(x["asset_count"] for x in checks.values()),
              "families": checks, "manifest": str(manifest_path), "audit": str(audit_path)}
    a.result_json.parent.mkdir(parents=True, exist_ok=True)
    a.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

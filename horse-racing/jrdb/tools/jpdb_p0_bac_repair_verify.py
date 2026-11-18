#!/usr/bin/env python3
"""Read-only verifier for the JPDB P0 BAC 2025 repaired source generation.

Run from repository root. Pass original, daily-source-artifact, repaired BAC,
2025 KYI and 2025 SED local ZIPs explicitly. Uses shared JRDB Raw parser.
This script makes no write to source ZIP, Drive, Warehouse or CURRENT.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jrdb_raw import Parser, iter_archive_records, read_fixed_records


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_sha(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    require(actual == expected, f"SHA256 mismatch {path}: {actual}")


def archive_files(path):
    with zipfile.ZipFile(path) as zf:
        require(zf.testzip() is None, f"ZIP integrity error: {path}")
        names = [n for n in zf.namelist() if not n.endswith("/")]
        require(len(names) == len(set(names)), f"duplicate members: {path}")
        return {name: zf.read(name) for name in names}


class ByteMember:
    """Provide bytes to canonical jrdb_raw.read_fixed_records, not a new parser."""
    def __init__(self, data):
        self.data = data

    def read(self, name):
        require(name == "BAC", "unexpected internal member")
        return self.data


def daily_race_keys(data):
    parser = Parser()
    records = read_fixed_records(ByteMember(data), "BAC", "BAC")
    require(bool(records), "empty or malformed daily BAC")
    keys = [parser.bac(rec)["race_key_raw"] for rec in records]
    require(len(keys) == len(set(keys)), "duplicate daily race keys")
    return set(keys)


def annual_race_keys(archive, family):
    parser = Parser()
    keys = []
    for _member, rec in iter_archive_records(archive, family):
        fields = (parser.bac(rec) if family == "BAC"
                  else parser.kyi(rec) if family == "KYI"
                  else parser.sed(rec))
        keys.append(fields["race_key_raw"])
    return set(keys), len(keys)


def run(args):
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sources = manifest["immutable_lineage"]
    check_sha(args.annual_bac, sources["canonical_original_bac"]["sha256"])
    check_sha(args.source_artifact, sources["source_reacquisition"]["sha256"])
    check_sha(args.repaired_bac, sources["verified_repaired_bac"]["sha256"])

    old = archive_files(args.annual_bac)
    repaired = archive_files(args.repaired_bac)
    artifact = archive_files(args.source_artifact)
    require(set(old) == set(repaired), "annual BAC member set changed")
    changed = sorted(name for name in old if old[name] != repaired[name])
    expected_changed = sorted(manifest["replacement_policy"]["replaced_members"])
    require(changed == expected_changed, f"unexpected changed members: {changed}")

    added = 0
    overwritten = 0
    for entry in sources["source_reacquisition"]["daily_archives"]:
        zip_name = entry["name"]
        nested_name = "BAC/" + zip_name
        require(nested_name in artifact, "daily source missing: " + nested_name)
        raw_zip = artifact[nested_name]
        require(hashlib.sha256(raw_zip).hexdigest() == entry["sha256"],
                "daily source SHA mismatch: " + zip_name)
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
            require(zf.testzip() is None, "nested ZIP corruption")
            member = zip_name[:-4] + ".txt"
            require(zf.namelist() == [member], "unexpected BAC source member")
            data = zf.read(member)
        require(repaired[member] == data, "repaired member differs: " + member)
        old_keys = daily_race_keys(old[member])
        new_keys = daily_race_keys(data)
        require(old_keys <= new_keys, "previous race keys disappeared")
        require(len(new_keys) == entry["race_count"], "expected daily count mismatch")
        added += len(new_keys - old_keys)
        overwritten += len(old_keys)

    base_keys, base_count = annual_race_keys(args.annual_bac, "BAC")
    fixed_keys, fixed_count = annual_race_keys(args.repaired_bac, "BAC")
    kyi_keys, kyi_count = annual_race_keys(args.kyi, "KYI")
    sed_keys, sed_count = annual_race_keys(args.sed, "SED")
    require(len(base_keys) == base_count, "original BAC duplicate race keys")
    require(len(fixed_keys) == fixed_count, "repaired BAC duplicate race keys")
    require(base_keys <= fixed_keys, "BAC keys dropped")
    require(fixed_keys == kyi_keys == sed_keys, "KYI/SED/BAC race keys differ")
    policy = manifest["replacement_policy"]
    require(added == len(fixed_keys-base_keys) == policy["new_races"],
            "added race count mismatch")
    require(overwritten == policy["existing_races_with_changed_raw_bytes"],
            "old race overlap count mismatch")
    require(len(fixed_keys) == policy["race_key_coverage_2025_with_kyi"],
            "expected annual coverage mismatch")
    return {
        "status": "PASS",
        "generation_id": manifest["generation_id"],
        "original_bac_races": base_count,
        "repaired_bac_races": fixed_count,
        "new_races": added,
        "updated_existing_races": overwritten,
        "unchanged_members": len(old) - len(changed),
        "kyi_rows": kyi_count,
        "sed_rows": sed_count,
        "pre_race_availability_proven": False,
        "accepted_warehouse_promoted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "annual-bac", "source-artifact",
                 "repaired-bac", "kyi", "sed"):
        parser.add_argument("--" + name, type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(run(options), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

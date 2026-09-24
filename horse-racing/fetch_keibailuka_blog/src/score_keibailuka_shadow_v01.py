#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
JRDB_SRC = REPOSITORY_ROOT / "horse-racing" / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from jrdb_raw import ReaderAudit, canonical_members, read_fixed_records
from jrdb_warehouse_normalize import RawProvenance, normalize_record
from analyze_keibailuka_historical import (
    VENUE_CODES,
    load_reason_definitions,
    normalize_name,
    tag_comment,
    to_int,
    write_csv,
)

RULE_ID = "KBI_SURFACE_BASEPOP_6_9_V01"
RULE_PATH = (
    REPOSITORY_ROOT
    / "horse-racing"
    / "fetch_keibailuka_blog"
    / "research"
    / "surface_basepop_6_9_shadow_v0_1.json"
)


def parse_kyi(paci_zip: Path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(paci_zip) as zipped:
        members = canonical_members(zipped, "KYI")
        if not members:
            raise RuntimeError(f"no canonical KYI members in {paci_zip.name}")
        for member in members:
            audit = ReaderAudit()
            records = read_fixed_records(zipped, member, "KYI", audit)
            if audit.record_length_errors:
                raise RuntimeError(
                    f"KYI fixed-record length errors {member}: "
                    f"{dict(audit.record_length_errors)}"
                )
            for ordinal, record in enumerate(records, start=1):
                rows.append(
                    normalize_record(
                        "KYI",
                        record,
                        RawProvenance(
                            source_archive_name=paci_zip.name,
                            source_member=member,
                            source_record_ordinal=ordinal,
                        ),
                    )
                )
    keys = [
        (str(row.get("race_key_raw") or ""), to_int(row.get("horse_no")))
        for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise RuntimeError("KYI canonical key duplicate detected")
    return rows


def read_keibailuka_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keibailuka-csv", required=True, type=Path)
    parser.add_argument("--paci", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    rule = json.loads(RULE_PATH.read_text(encoding="utf-8"))
    if rule.get("rule_id") != RULE_ID:
        raise RuntimeError("shadow rule contract mismatch")
    if rule.get("status") != "SHADOW_FORWARD_CANDIDATE":
        raise RuntimeError("shadow rule is not active candidate")

    reason_definitions = load_reason_definitions()
    if (
        reason_definitions.get("version")
        != rule["source_contract"]["keibailuka_reason_tag_version"]
    ):
        raise RuntimeError("reason tag version mismatch")

    rows = read_keibailuka_csv(args.keibailuka_csv)
    dates = sorted(
        {
            (row.get("日付") or "").strip()
            for row in rows
            if (row.get("日付") or "").strip()
        }
    )
    if len(dates) != 1:
        raise RuntimeError(f"keibailuka CSV must contain exactly one date: {dates}")
    target_date = dates[0]

    kyi_rows = parse_kyi(args.paci)
    kyi_by_join = {}
    for row in kyi_rows:
        venue_code = str(row.get("venue_code") or "").zfill(2)
        race_no = to_int(row.get("race_no"))
        horse_name = normalize_name(row.get("horse_name"))
        key = (venue_code, race_no, horse_name)
        kyi_by_join.setdefault(key, []).append(row)

    audited = []
    candidates = []
    unmatched = []
    ambiguous = []

    for source in rows:
        raw_horse = (source.get("馬名") or source.get("馬名_raw") or "").strip()
        venue = (source.get("会場") or "").strip()
        race_text = (source.get("R") or "").strip()
        comment = source.get("コメント") or ""
        if not raw_horse or raw_horse == "🤡":
            continue
        if venue not in VENUE_CODES:
            unmatched.append(
                {
                    "日付": target_date,
                    "会場": venue,
                    "R": race_text,
                    "馬名": raw_horse,
                    "reason": "unsupported_venue",
                }
            )
            continue
        match = re.fullmatch(r"(\d+)R", race_text)
        if not match:
            unmatched.append(
                {
                    "日付": target_date,
                    "会場": venue,
                    "R": race_text,
                    "馬名": raw_horse,
                    "reason": "invalid_race_no",
                }
            )
            continue

        join_key = (
            VENUE_CODES[venue],
            int(match.group(1)),
            normalize_name(raw_horse),
        )
        matches = kyi_by_join.get(join_key, [])
        if len(matches) == 0:
            unmatched.append(
                {
                    "日付": target_date,
                    "会場": venue,
                    "R": race_text,
                    "馬名": raw_horse,
                    "reason": "kyi_unmatched",
                }
            )
            continue
        if len(matches) > 1:
            ambiguous.append(
                {
                    "日付": target_date,
                    "会場": venue,
                    "R": race_text,
                    "馬名": raw_horse,
                    "candidate_count": len(matches),
                }
            )
            continue

        kyi = matches[0]
        tags = tag_comment(comment, reason_definitions)
        primary_reason = tags[0]
        base_win_rank = to_int(kyi.get("base_win_rank"))
        selected = (
            primary_reason == "surface"
            and base_win_rank is not None
            and 6 <= base_win_rank <= 9
        )
        item = {
            "rule_id": RULE_ID,
            "日付": target_date,
            "会場": venue,
            "R": race_text,
            "馬名": raw_horse,
            "primary_reason": primary_reason,
            "base_win_rank": base_win_rank,
            "base_win_odds": kyi.get("base_win_odds"),
            "idm": kyi.get("idm"),
            "total_index": kyi.get("total_index"),
            "selected": int(selected),
            "コメント": comment,
        }
        audited.append(item)
        if selected:
            candidates.append(item)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "shadow_candidates.csv", candidates)
    write_csv(args.output_dir / "shadow_audit_rows.csv", audited)
    write_csv(args.output_dir / "unmatched.csv", unmatched)
    write_csv(args.output_dir / "ambiguous.csv", ambiguous)

    result = {
        "artifact_type": "keibailuka_shadow_score",
        "rule_id": RULE_ID,
        "date": target_date,
        "status": "PASS" if not ambiguous else "FAIL",
        "input_rows": len(rows),
        "normal_rows": sum(
            1
            for row in rows
            if (row.get("馬名") or row.get("馬名_raw") or "").strip()
            and (row.get("馬名") or row.get("馬名_raw") or "").strip() != "🤡"
        ),
        "matched_rows": len(audited),
        "unmatched_rows": len(unmatched),
        "ambiguous_rows": len(ambiguous),
        "candidate_count": len(candidates),
        "decision_uses_result_data": False,
        "decision_fields": [
            "keibailuka primary_reason",
            "KYI base_win_rank",
        ],
    }
    (args.output_dir / "shadow_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if ambiguous:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

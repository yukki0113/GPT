#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
JRDB_SRC = REPOSITORY_ROOT / "horse-racing" / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from jrdb_raw import ReaderAudit, canonical_members, read_fixed_records
from jrdb_warehouse_normalize import RawProvenance, normalize_record
from analyze_keibailuka_historical import (
    VENUE_CODES,
    load_reason_definitions,
    metric,
    normalize_name,
    pct,
    tag_comment,
    to_float,
    to_int,
    write_csv,
)


def get(url: str, **kwargs):
    response = requests.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    return response


def download_drive(file_id: str, path: Path, expected_size: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    response = get(
        "https://drive.usercontent.google.com/download",
        params={"id": file_id, "export": "download", "confirm": "t"},
    )
    data = response.content
    if b"<html" in data[:200].lower():
        data = get(
            "https://drive.google.com/uc",
            params={"export": "download", "id": file_id},
        ).content
    path.write_bytes(data)
    if expected_size is not None and path.stat().st_size != int(expected_size):
        raise RuntimeError(
            f"size mismatch for {path.name}: expected={expected_size} actual={path.stat().st_size}"
        )


def fetch_sheet_rows(spreadsheet_id: str, sheet_name: str) -> list[dict[str, str]]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote(sheet_name)}"
    )
    text = get(url).content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def parse_family_zip(path: Path, family: str) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as zipped:
        members = canonical_members(zipped, family)
        if not members:
            raise RuntimeError(f"no canonical {family} members in {path.name}")
        for member in members:
            audit = ReaderAudit()
            records = read_fixed_records(zipped, member, family, audit)
            if audit.record_length_errors:
                raise RuntimeError(
                    f"{family} fixed-record length errors {path.name}/{member}: "
                    f"{dict(audit.record_length_errors)}"
                )
            for ordinal, record in enumerate(records, start=1):
                rows.append(
                    normalize_record(
                        family,
                        record,
                        RawProvenance(
                            source_archive_name=path.name,
                            source_member=member,
                            source_record_ordinal=ordinal,
                        ),
                    )
                )
    return rows


def competition_ranks(rows: list[dict], field: str) -> dict[tuple[str, int], int | None]:
    by_race = defaultdict(list)
    for row in rows:
        key = str(row.get("race_key_raw") or "")
        horse_no = to_int(row.get("horse_no"))
        value = to_float(row.get(field))
        if key and horse_no is not None:
            by_race[key].append((horse_no, value))
    result = {}
    for race_key, values in by_race.items():
        valid = sorted(
            [value for _, value in values if value is not None],
            reverse=True,
        )
        for horse_no, value in values:
            if value is None:
                result[(race_key, horse_no)] = None
            else:
                result[(race_key, horse_no)] = valid.index(value) + 1
    return result


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    request = json.load(open(args.request_json, encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = REPOSITORY_ROOT / request["source_manifest_path"]
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    reason_definitions = load_reason_definitions()
    if reason_definitions["version"] != request["reason_tag_version"]:
        raise RuntimeError("reason tag version mismatch")

    source_rows = fetch_sheet_rows(
        request["spreadsheet_id"],
        request.get("sheet_name", "イルカ明細"),
    )

    picks = []
    for source in source_rows:
        race_date = (source.get("日付") or "").strip()
        raw_horse = (source.get("馬名_raw") or "").strip()
        venue = (source.get("会場") or "").strip()
        if not race_date.startswith("2026-"):
            continue
        if not raw_horse or raw_horse == "🤡":
            continue
        match = re.fullmatch(r"(\d+)R", (source.get("R") or "").strip())
        if venue not in VENUE_CODES or not match:
            continue
        tags = tag_comment(source.get("コメント", ""), reason_definitions)
        picks.append(
            {
                "source_id": len(picks) + 1,
                "key": (source.get("key") or "").strip(),
                "race_date": race_date,
                "date_compact": race_date[2:].replace("-", ""),
                "venue": venue,
                "venue_code": VENUE_CODES[venue],
                "race_no": int(match.group(1)),
                "horse_name_raw": normalize_name(raw_horse),
                "comment": source.get("コメント", ""),
                "primary_reason": tags[0],
            }
        )

    needed_dates = sorted({pick["date_compact"] for pick in picks})
    missing_dates = [
        date for date in needed_dates if date not in source_manifest["dates"]
    ]
    if missing_dates:
        raise RuntimeError(f"source manifest missing dates: {missing_dates}")

    temporary_dir = Path(tempfile.mkdtemp(prefix="keibailuka_forward_2026_"))
    all_kyi = []
    all_sed = []
    source_audit = []

    for date in needed_dates:
        spec = source_manifest["dates"][date]
        paci_path = temporary_dir / spec["paci"]["file_name"]
        sed_path = temporary_dir / spec["sed"]["file_name"]
        download_drive(
            spec["paci"]["file_id"],
            paci_path,
            spec["paci"]["size_bytes"],
        )
        download_drive(
            spec["sed"]["file_id"],
            sed_path,
            spec["sed"]["size_bytes"],
        )
        kyi_rows = parse_family_zip(paci_path, "KYI")
        sed_rows = parse_family_zip(sed_path, "SED")
        all_kyi.extend(kyi_rows)
        all_sed.extend(sed_rows)
        source_audit.append(
            {
                "date_compact": date,
                "paci_file": spec["paci"]["file_name"],
                "paci_size": paci_path.stat().st_size,
                "kyi_rows": len(kyi_rows),
                "sed_file": spec["sed"]["file_name"],
                "sed_size": sed_path.stat().st_size,
                "sed_rows": len(sed_rows),
            }
        )

    kyi_key_count = len(
        {
            (str(row.get("race_key_raw") or ""), to_int(row.get("horse_no")))
            for row in all_kyi
        }
    )
    if kyi_key_count != len(all_kyi):
        raise RuntimeError(
            f"KYI canonical key duplicate: rows={len(all_kyi)} keys={kyi_key_count}"
        )
    sed_key_count = len(
        {
            (str(row.get("race_key_raw") or ""), to_int(row.get("horse_no")))
            for row in all_sed
        }
    )
    if sed_key_count != len(all_sed):
        raise RuntimeError(
            f"SED canonical key duplicate: rows={len(all_sed)} keys={sed_key_count}"
        )

    idm_ranks = competition_ranks(all_kyi, "idm")
    total_ranks = competition_ranks(all_kyi, "total_index")

    kyi_by_name = {}
    kyi_same_race = defaultdict(list)
    for row in all_kyi:
        race_date = "20" + str(row.get("year_yy") or "") + "-" + str(row.get("race_key_raw") or "")[2:4] + "-" + str(row.get("race_key_raw") or "")[4:6]
        venue_code = str(row.get("venue_code") or "").zfill(2)
        race_no = to_int(row.get("race_no"))
        horse_name = normalize_name(row.get("horse_name"))
        key = (race_date, venue_code, race_no, horse_name)
        kyi_by_name.setdefault(key, []).append(row)
        kyi_same_race[(race_date, venue_code, race_no)].append(row)

    sed_by_key = {}
    for row in all_sed:
        key = (str(row.get("race_key_raw") or ""), to_int(row.get("horse_no")))
        sed_by_key[key] = row

    matched = []
    unmatched = []
    ambiguous = []
    for pick in picks:
        key = (
            pick["race_date"],
            pick["venue_code"],
            pick["race_no"],
            pick["horse_name_raw"],
        )
        candidates = kyi_by_name.get(key, [])
        if len(candidates) == 0:
            unmatched.append(pick)
            continue
        if len(candidates) > 1:
            ambiguous.append({**pick, "candidate_count": len(candidates)})
            continue
        kyi = candidates[0]
        sed = sed_by_key.get(
            (str(kyi.get("race_key_raw") or ""), to_int(kyi.get("horse_no")))
        )
        if sed is None:
            unmatched.append({**pick, "reason": "KYI matched but SED missing"})
            continue
        abnormal = sed.get("abnormal_code")
        if abnormal not in (None, "", 0, "0"):
            continue
        race_key = str(kyi.get("race_key_raw") or "")
        horse_no = to_int(kyi.get("horse_no"))
        matched.append(
            {
                **pick,
                "race_key_raw": race_key,
                "horse_no": horse_no,
                "kyi_horse_name": kyi.get("horse_name"),
                "idm": kyi.get("idm"),
                "idm_rank": idm_ranks.get((race_key, horse_no)),
                "total_index": kyi.get("total_index"),
                "total_rank": total_ranks.get((race_key, horse_no)),
                "base_win_rank": kyi.get("base_win_rank"),
                "final_popularity": sed.get("final_popularity"),
                "final_win_odds": sed.get("final_win_odds"),
                "finish": sed.get("finish"),
                "win_payout": sed.get("win_payout"),
                "place_payout": sed.get("place_payout"),
                "abnormal_code": abnormal,
            }
        )

    for row in matched:
        row["final_popularity"] = to_int(row.get("final_popularity"))
        row["idm_rank"] = to_int(row.get("idm_rank"))
        row["total_rank"] = to_int(row.get("total_rank"))
        row["base_win_rank"] = to_int(row.get("base_win_rank"))

    conditions = {
        "surface_pop6_9_idm_top5": lambda row: (
            row["primary_reason"] == "surface"
            and row["final_popularity"] is not None
            and 6 <= row["final_popularity"] <= 9
            and row["idm_rank"] is not None
            and row["idm_rank"] <= 5
        ),
        "surface_pop6_9_any_core_top5": lambda row: (
            row["primary_reason"] == "surface"
            and row["final_popularity"] is not None
            and 6 <= row["final_popularity"] <= 9
            and any(
                value is not None and value <= 5
                for value in (
                    row["base_win_rank"],
                    row["idm_rank"],
                    row["total_rank"],
                )
            )
        ),
        "pace_flow_pop6_9": lambda row: (
            row["primary_reason"] == "pace_flow"
            and row["final_popularity"] is not None
            and 6 <= row["final_popularity"] <= 9
        ),
        "surface_pop6_9": lambda row: (
            row["primary_reason"] == "surface"
            and row["final_popularity"] is not None
            and 6 <= row["final_popularity"] <= 9
        ),
    }

    condition_rows = {}
    condition_metrics = {}
    for name, predicate in conditions.items():
        selected = [row for row in matched if predicate(row)]
        condition_rows[name] = selected
        condition_metrics[name] = metric(selected)

    # Monthly split is descriptive only; criteria are not altered by it.
    monthly = {}
    for name, rows in condition_rows.items():
        monthly[name] = {}
        for month in range(1, 10):
            label = f"2026-{month:02d}"
            selected = [
                row for row in rows if row["race_date"].startswith(label + "-")
            ]
            monthly[name][label] = metric(selected)

    payout_examples = []
    for row in matched:
        if to_int(row.get("finish")) == 1:
            odds = to_float(row.get("final_win_odds"))
            payout = to_float(row.get("win_payout"))
            if odds is not None and payout is not None:
                payout_examples.append(
                    {
                        "race_date": row["race_date"],
                        "key": row["key"],
                        "odds": odds,
                        "win_payout": payout,
                        "difference": round(payout - odds * 100, 6),
                    }
                )
            if len(payout_examples) >= 10:
                break
    payout_unit_ok = bool(payout_examples) and all(
        abs(row["difference"]) < 0.01 for row in payout_examples
    )

    summary = {
        "schema_version": "keibailuka-forward-2026-v0.1",
        "criteria_frozen_before_evaluation": True,
        "reason_tag_version": reason_definitions["version"],
        "source_manifest_version": source_manifest["version"],
        "source_date_count_used": len(needed_dates),
        "source_date_from": needed_dates[0] if needed_dates else None,
        "source_date_to": needed_dates[-1] if needed_dates else None,
        "source_audit": source_audit,
        "population": {
            "normal_picks_2026": len(picks),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "ambiguous": len(ambiguous),
            "match_rate_pct": pct(len(matched), len(picks)),
            "kyi_rows": len(all_kyi),
            "sed_rows": len(all_sed),
        },
        "payout_unit_100yen_confirmed": payout_unit_ok,
        "conditions": condition_metrics,
        "monthly": monthly,
    }

    write_json(output_dir / "summary.json", summary)
    write_csv(output_dir / "source_audit.csv", source_audit)
    write_csv(output_dir / "unmatched.csv", unmatched)
    write_csv(output_dir / "ambiguous.csv", ambiguous)
    for name, rows in condition_rows.items():
        write_csv(output_dir / f"{name}.csv", rows)

    labels = {
        "surface_pop6_9_idm_top5": "馬場・芝ダート × 6〜9人気 × IDM上位5",
        "surface_pop6_9_any_core_top5": "馬場・芝ダート × 6〜9人気 × JRDB coreいずれかTop5",
        "pace_flow_pop6_9": "展開・ペース × 6〜9人気",
        "surface_pop6_9": "馬場・芝ダート × 6〜9人気 baseline",
    }
    lines = [
        "# keibailuka 2026 Forward/OOT Validation v0.1",
        "",
        "- criteria frozen before 2026 evaluation: True",
        (
            f"- normal picks: {len(picks)} / matched: {len(matched)} / "
            f"unmatched: {len(unmatched)} / ambiguous: {len(ambiguous)} / "
            f"match rate: {summary['population']['match_rate_pct']:.2f}%"
        ),
        (
            f"- source dates: {len(needed_dates)} "
            f"({needed_dates[0] if needed_dates else '-'} to "
            f"{needed_dates[-1] if needed_dates else '-'})"
        ),
        f"- payout 100yen unit confirmed: {payout_unit_ok}",
    ]
    for name in (
        "surface_pop6_9_idm_top5",
        "surface_pop6_9_any_core_top5",
        "pace_flow_pop6_9",
        "surface_pop6_9",
    ):
        m = condition_metrics[name]
        lines.extend(
            [
                "",
                f"## {labels[name]}",
                (
                    f"N={m['N']} wins={m['wins']} places={m['places']} "
                    f"win%={m['win_rate_pct']} place%={m['place_rate_pct']} "
                    f"winROI={m['win_roi_pct']}% placeROI={m['place_roi_pct']}%"
                ),
            ]
        )

    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()

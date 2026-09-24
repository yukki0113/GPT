#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import math
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
    data = get(
        "https://drive.usercontent.google.com/download",
        params={"id": file_id, "export": "download", "confirm": "t"},
    ).content
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


def parse_family_zip(path: Path, family: str, source_date: str | None = None) -> list[dict]:
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
                row = normalize_record(
                    family,
                    record,
                    RawProvenance(
                        source_archive_name=path.name,
                        source_member=member,
                        source_record_ordinal=ordinal,
                    ),
                )
                if source_date:
                    row["_proxy_source_date"] = source_date
                rows.append(row)
    return rows


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if den == 0:
        return None
    return round(sum(x*y for x, y in zip(dx, dy)) / den, 6)


def proxy_band(rank: int | None, band: str) -> bool:
    if rank is None:
        return False
    if band == "6-9":
        return 6 <= rank <= 9
    if band == "5-10":
        return 5 <= rank <= 10
    if band == "4-11":
        return 4 <= rank <= 11
    raise ValueError(band)


def rank_audit(rows: list[dict]) -> dict:
    valid = [
        row for row in rows
        if to_int(row.get("base_win_rank")) is not None
        and to_int(row.get("final_popularity")) is not None
        and to_int(row.get("final_popularity")) != 99
    ]
    diffs = [
        abs(to_int(row["base_win_rank"]) - to_int(row["final_popularity"]))
        for row in valid
    ]
    xs = [float(to_int(row["base_win_rank"])) for row in valid]
    ys = [float(to_int(row["final_popularity"])) for row in valid]
    target = [row for row in valid if 6 <= to_int(row["final_popularity"]) <= 9]
    bands = {}
    for band in ("6-9", "5-10", "4-11"):
        selected = [
            row for row in valid if proxy_band(to_int(row["base_win_rank"]), band)
        ]
        true_positive = [
            row for row in selected if 6 <= to_int(row["final_popularity"]) <= 9
        ]
        bands[band] = {
            "selected_N": len(selected),
            "target_N": len(target),
            "true_positive_N": len(true_positive),
            "precision_pct": pct(len(true_positive), len(selected)),
            "recall_pct": pct(len(true_positive), len(target)),
        }
    return {
        "N": len(valid),
        "exact_rank_pct": pct(sum(diff == 0 for diff in diffs), len(valid)),
        "within_1_pct": pct(sum(diff <= 1 for diff in diffs), len(valid)),
        "within_2_pct": pct(sum(diff <= 2 for diff in diffs), len(valid)),
        "mean_abs_rank_diff": round(sum(diffs) / len(diffs), 4) if diffs else None,
        "rank_pearson": pearson(xs, ys),
        "bands": bands,
    }


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
    temp = Path(tempfile.mkdtemp(prefix="keibailuka_pop_proxy_"))

    reason_definitions = load_reason_definitions()
    if reason_definitions["version"] != request["reason_tag_version"]:
        raise RuntimeError("reason tag version mismatch")

    sheet_rows = fetch_sheet_rows(request["spreadsheet_id"], "イルカ明細")
    correction_rows = fetch_sheet_rows(request["spreadsheet_id"], "研究join補正")
    correction_map = {}
    for row in correction_rows:
        if row.get("status") == "accepted_for_research_join":
            key = (row.get("key") or "").strip()
            candidate = (row.get("SED候補") or "").strip()
            if key and candidate:
                correction_map[key] = normalize_name(candidate)

    kyi_rows: list[dict] = []
    sed_rows: list[dict] = []
    source_audit = []

    for year in (2024, 2025):
        kspec = request["historical"][str(year)]["kyi"]
        sspec = request["historical"][str(year)]["sed"]
        kp = temp / f"KYI_{year}.zip"
        sp = temp / f"SED_{year}.zip"
        download_drive(kspec["id"], kp, kspec["size"])
        download_drive(sspec["id"], sp, sspec["size"])
        ky = parse_family_zip(kp, "KYI")
        se = parse_family_zip(sp, "SED")
        if len(ky) != int(kspec["expected_rows"]):
            raise RuntimeError(f"KYI {year} row mismatch {len(ky)}")
        if len(se) != int(sspec["expected_rows"]):
            raise RuntimeError(f"SED {year} row mismatch {len(se)}")
        kyi_rows.extend(ky)
        sed_rows.extend(se)
        source_audit.append({
            "year": year, "source": "annual_raw",
            "kyi_rows": len(ky), "sed_rows": len(se),
        })

    manifest = json.loads(
        (REPOSITORY_ROOT / request["forward_manifest_path"]).read_text(encoding="utf-8")
    )
    for compact, spec in sorted(manifest["dates"].items()):
        race_date = f"20{compact[:2]}-{compact[2:4]}-{compact[4:6]}"
        kp = temp / spec["paci"]["file_name"]
        sp = temp / spec["sed"]["file_name"]
        download_drive(spec["paci"]["file_id"], kp, spec["paci"]["size_bytes"])
        download_drive(spec["sed"]["file_id"], sp, spec["sed"]["size_bytes"])
        ky = parse_family_zip(kp, "KYI", race_date)
        se = parse_family_zip(sp, "SED", race_date)
        if len(ky) != len(se):
            raise RuntimeError(
                f"2026 daily row mismatch {compact}: KYI={len(ky)} SED={len(se)}"
            )
        kyi_rows.extend(ky)
        sed_rows.extend(se)
        source_audit.append({
            "year": 2026, "source": compact,
            "kyi_rows": len(ky), "sed_rows": len(se),
        })

    kyi_by_key = {}
    for row in kyi_rows:
        key = (str(row.get("race_key_raw") or ""), to_int(row.get("horse_no")))
        if key in kyi_by_key:
            # 2024/25 annual and 2026 daily are disjoint by race year.
            raise RuntimeError(f"KYI duplicate canonical key {key}")
        kyi_by_key[key] = row

    runner_rows = []
    sed_by_pick_key = defaultdict(list)
    for sed in sed_rows:
        race_key = str(sed.get("race_key_raw") or "")
        horse_no = to_int(sed.get("horse_no"))
        kyi = kyi_by_key.get((race_key, horse_no))
        if kyi is None:
            continue
        race_date = sed.get("race_date") or sed.get("_proxy_source_date")
        if not race_date:
            race_date = kyi.get("_proxy_source_date")
        item = {
            "year": int(str(race_date)[:4]),
            "race_date": str(race_date),
            "venue_code": str(sed.get("venue_code") or "").zfill(2),
            "race_no": to_int(sed.get("race_no")),
            "horse_name": normalize_name(sed.get("horse_name")),
            "race_key_raw": race_key,
            "horse_no": horse_no,
            "base_win_rank": to_int(kyi.get("base_win_rank")),
            "base_win_odds": to_float(kyi.get("base_win_odds")),
            "final_popularity": to_int(sed.get("final_popularity")),
            "final_win_odds": to_float(sed.get("final_win_odds")),
            "finish": to_int(sed.get("finish")),
            "abnormal_code": sed.get("abnormal_code"),
            "win_payout": to_float(sed.get("win_payout")),
            "place_payout": to_float(sed.get("place_payout")),
        }
        runner_rows.append(item)
        sed_by_pick_key[
            (
                item["race_date"],
                item["venue_code"],
                item["race_no"],
                item["horse_name"],
            )
        ].append(item)

    picks = []
    unmatched = []
    ambiguous = []
    for source in sheet_rows:
        race_date = (source.get("日付") or "").strip()
        if not (
            race_date.startswith("2024-")
            or race_date.startswith("2025-")
            or race_date.startswith("2026-")
        ):
            continue
        horse = (source.get("馬名_raw") or "").strip()
        if not horse or horse == "🤡":
            continue
        venue = (source.get("会場") or "").strip()
        rm = re.fullmatch(r"(\d+)R", (source.get("R") or "").strip())
        if venue not in VENUE_CODES or not rm:
            continue
        source_key = (source.get("key") or "").strip()
        join_name = correction_map.get(source_key, normalize_name(horse))
        key = (race_date, VENUE_CODES[venue], int(rm.group(1)), join_name)
        candidates = sed_by_pick_key.get(key, [])
        if len(candidates) == 0:
            unmatched.append({"key": source_key, "race_date": race_date, "horse": horse})
            continue
        if len(candidates) > 1:
            ambiguous.append({"key": source_key, "candidate_count": len(candidates)})
            continue
        item = dict(candidates[0])
        if item.get("abnormal_code") not in (None, "", 0, "0"):
            continue
        tags = tag_comment(source.get("コメント", ""), reason_definitions)
        item.update({
            "key": source_key,
            "comment": source.get("コメント", ""),
            "primary_reason": tags[0],
        })
        picks.append(item)

    runner_normal = [
        row for row in runner_rows
        if row.get("abnormal_code") in (None, "", 0, "0")
        and row.get("final_popularity") not in (None, 99)
    ]

    audits = {
        "all_runners": {
            str(year): rank_audit([r for r in runner_normal if r["year"] == year])
            for year in (2024, 2025, 2026)
        },
        "all_picks": {
            str(year): rank_audit([r for r in picks if r["year"] == year])
            for year in (2024, 2025, 2026)
        },
        "surface_picks": {
            str(year): rank_audit([
                r for r in picks
                if r["year"] == year and r["primary_reason"] == "surface"
            ])
            for year in (2024, 2025, 2026)
        },
    }

    proxy_metrics = {}
    detail_rows = []
    for band in ("6-9", "5-10", "4-11"):
        proxy_metrics[band] = {}
        for period, years in (
            ("historical_2024_2025", {2024, 2025}),
            ("forward_2026", {2026}),
        ):
            selected = [
                r for r in picks
                if r["year"] in years
                and r["primary_reason"] == "surface"
                and proxy_band(to_int(r.get("base_win_rank")), band)
            ]
            target_overlap = [
                r for r in selected
                if r.get("final_popularity") is not None
                and 6 <= r["final_popularity"] <= 9
            ]
            m = metric(selected)
            m.update({
                "final_6_9_overlap_N": len(target_overlap),
                "final_6_9_share_pct": pct(len(target_overlap), len(selected)),
            })
            proxy_metrics[band][period] = m
            detail_rows.append({
                "proxy_band": band,
                "period": period,
                **m,
            })

    final_target_metrics = {
        period: metric([
            r for r in picks
            if r["year"] in years
            and r["primary_reason"] == "surface"
            and r.get("final_popularity") is not None
            and 6 <= r["final_popularity"] <= 9
        ])
        for period, years in (
            ("historical_2024_2025", {2024, 2025}),
            ("forward_2026", {2026}),
        )
    }

    summary = {
        "schema_version": "keibailuka-popularity-proxy-audit-v0.1",
        "reason_tag_version": reason_definitions["version"],
        "proxy_definition": "KYI base_win_rank / JRDB 基準人気順位",
        "proxy_is_market_popularity": False,
        "population": {
            "runner_rows": len(runner_rows),
            "normal_runner_rows": len(runner_normal),
            "matched_picks": len(picks),
            "unmatched_picks": len(unmatched),
            "ambiguous_picks": len(ambiguous),
        },
        "rank_audits": audits,
        "surface_proxy_metrics": proxy_metrics,
        "final_target_reference": final_target_metrics,
    }
    write_json(output_dir / "summary.json", summary)
    write_csv(output_dir / "proxy_surface_metrics.csv", detail_rows)
    write_csv(output_dir / "unmatched.csv", unmatched)
    write_csv(output_dir / "ambiguous.csv", ambiguous)
    write_csv(output_dir / "source_audit.csv", source_audit)

    lines = [
        "# keibailuka Popularity Proxy Audit v0.1",
        "",
        "- proxy: KYI 基準人気順位 (base_win_rank)",
        "- treated as market popularity: False",
        (
            f"- matched picks={len(picks)} unmatched={len(unmatched)} "
            f"ambiguous={len(ambiguous)}"
        ),
    ]
    for scope in ("all_runners", "all_picks", "surface_picks"):
        lines += ["", f"## Rank agreement: {scope}"]
        for year in ("2024", "2025", "2026"):
            a = audits[scope][year]
            b = a["bands"]["6-9"]
            lines.append(
                f"- {year}: N={a['N']} exact={a['exact_rank_pct']}% "
                f"within1={a['within_1_pct']}% within2={a['within_2_pct']}% "
                f"MAE={a['mean_abs_rank_diff']} corr={a['rank_pearson']} | "
                f"proxy6-9 precision={b['precision_pct']}% recall={b['recall_pct']}%"
            )

    lines += ["", "## Executable surface-comment proxy rules"]
    for band in ("6-9", "5-10", "4-11"):
        h = proxy_metrics[band]["historical_2024_2025"]
        f = proxy_metrics[band]["forward_2026"]
        lines.append(
            f"- base rank {band}: Historical N={h['N']} winROI={h['win_roi_pct']}% "
            f"placeROI={h['place_roi_pct']}% final6-9share={h['final_6_9_share_pct']}% | "
            f"2026 N={f['N']} winROI={f['win_roi_pct']}% "
            f"placeROI={f['place_roi_pct']}% final6-9share={f['final_6_9_share_pct']}%"
        )

    h = final_target_metrics["historical_2024_2025"]
    f = final_target_metrics["forward_2026"]
    lines += [
        "",
        "## Reference: post-result final popularity 6-9",
        f"- Historical N={h['N']} winROI={h['win_roi_pct']}% placeROI={h['place_roi_pct']}%",
        f"- 2026 N={f['N']} winROI={f['win_roi_pct']}% placeROI={f['place_roi_pct']}%",
    ]

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

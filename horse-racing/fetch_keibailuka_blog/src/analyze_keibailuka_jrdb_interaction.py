#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests

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


def download_drive(file_id: str, path: Path, sha256: str | None = None) -> None:
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
    if sha256:
        actual = hashlib.sha256(data).hexdigest()
        if actual.lower() != sha256.lower():
            raise RuntimeError(f"SHA mismatch for {path.name}: {actual}")


def download_drive_folder(folder_id: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "gdown",
            "--folder",
            f"https://drive.google.com/drive/folders/{folder_id}",
            "-O",
            str(output_dir),
            "--quiet",
        ],
        check=True,
    )


def find_unique(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {filename} under {root}, found {len(matches)}"
        )
    return matches[0]


def verify_sha(path: Path, expected_sha: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest.lower() != expected_sha.lower():
        raise RuntimeError(
            f"SHA mismatch for {path.name}: expected={expected_sha} actual={digest}"
        )


def fetch_sheet_rows(spreadsheet_id: str, sheet_name: str) -> list[dict[str, str]]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote(sheet_name)}"
    )
    text = get(url).content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def rank_bucket(value):
    rank = to_int(value)
    if rank is None:
        return "missing"
    if rank <= 3:
        return "1-3"
    if rank <= 5:
        return "4-5"
    if rank <= 9:
        return "6-9"
    return "10+"


def write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n",
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
    temporary_dir = Path(tempfile.mkdtemp(prefix="keibailuka_jrdb_"))

    sed_2024 = temporary_dir / "sed_2024.parquet"
    sed_2025 = temporary_dir / "sed_2025.parquet"
    download_drive(
        request["sed_2024_id"],
        sed_2024,
        request.get("sed_2024_sha"),
    )
    download_drive(
        request["sed_2025_id"],
        sed_2025,
        request.get("sed_2025_sha"),
    )

    kyi_staging = temporary_dir / "kyi_staging"
    download_drive_folder(request["kyi_staging_folder_id"], kyi_staging)

    kyi_2024 = find_unique(kyi_staging, request["kyi_2024_filename"])
    kyi_2025 = find_unique(kyi_staging, request["kyi_2025_filename"])
    verify_sha(kyi_2024, request["kyi_2024_sha"])
    verify_sha(kyi_2025, request["kyi_2025_sha"])

    spreadsheet_id = request["spreadsheet_id"]
    source_rows = fetch_sheet_rows(
        spreadsheet_id,
        request.get("sheet_name", "イルカ明細"),
    )
    correction_rows = fetch_sheet_rows(
        spreadsheet_id,
        request.get("correction_sheet_name", "研究join補正"),
    )

    correction_map = {}
    for row in correction_rows:
        if row.get("status") != "accepted_for_research_join":
            continue
        key = (row.get("key") or "").strip()
        candidate = (row.get("SED候補") or "").strip()
        if key and candidate:
            correction_map[key] = normalize_name(candidate)

    reason_definitions = load_reason_definitions()
    reason_labels = {
        definition["id"]: definition["label"]
        for definition in reason_definitions["tags"]
    }
    reason_labels["other"] = "その他・未分類"

    picks = []
    for source in source_rows:
        race_date = (source.get("日付") or "").strip()
        raw_horse = (source.get("馬名_raw") or "").strip()
        venue = (source.get("会場") or "").strip()
        if not (race_date.startswith("2024-") or race_date.startswith("2025-")):
            continue
        if not raw_horse or raw_horse == "🤡":
            continue
        match = re.fullmatch(r"(\d+)R", (source.get("R") or "").strip())
        if venue not in VENUE_CODES or not match:
            continue

        key = (source.get("key") or "").strip()
        raw_normalized = normalize_name(raw_horse)
        join_name = correction_map.get(key, raw_normalized)
        tags = tag_comment(source.get("コメント", ""), reason_definitions)

        picks.append(
            {
                "source_id": len(picks) + 1,
                "key": key,
                "race_date": race_date,
                "year": int(race_date[:4]),
                "venue": venue,
                "venue_code": VENUE_CODES[venue],
                "race_no": int(match.group(1)),
                "horse_name_raw": raw_normalized,
                "horse_name_join": join_name,
                "correction_applied": int(join_name != raw_normalized),
                "comment": source.get("コメント", ""),
                "reason_tags": tags,
                "primary_reason": tags[0],
            }
        )

    import duckdb

    connection = duckdb.connect()
    connection.execute(
        """
        CREATE TABLE picks(
            source_id INTEGER,
            key VARCHAR,
            race_date VARCHAR,
            year INTEGER,
            venue VARCHAR,
            venue_code VARCHAR,
            race_no INTEGER,
            horse_name_raw VARCHAR,
            horse_name_join VARCHAR,
            correction_applied INTEGER,
            comment VARCHAR,
            primary_reason VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                pick["source_id"],
                pick["key"],
                pick["race_date"],
                pick["year"],
                pick["venue"],
                pick["venue_code"],
                pick["race_no"],
                pick["horse_name_raw"],
                pick["horse_name_join"],
                pick["correction_applied"],
                pick["comment"],
                pick["primary_reason"],
            )
            for pick in picks
        ],
    )

    sed = (
        "read_parquet(["
        + ",".join(
            json.dumps(path.as_posix())
            for path in (sed_2024, sed_2025)
        )
        + "], union_by_name=true)"
    )
    kyi = (
        "read_parquet(["
        + ",".join(
            json.dumps(path.as_posix())
            for path in (kyi_2024, kyi_2025)
        )
        + "], union_by_name=true)"
    )

    # SED remains the settlement source.  KYI is joined only after the
    # historical pick has been resolved to an exact race_key_raw + horse_no.
    query = f"""
        WITH sed_join AS (
            SELECT
                p.*,
                COUNT(s.horse_no) OVER(PARTITION BY p.source_id) AS sed_match_count,
                s.race_key_raw,
                s.horse_no,
                s.finish,
                s.abnormal_code,
                s.final_win_odds,
                s.final_popularity,
                s.win_payout,
                s.place_payout
            FROM picks p
            LEFT JOIN {sed} s
              ON CAST(s.race_date AS VARCHAR) = p.race_date
             AND LPAD(CAST(s.venue_code AS VARCHAR), 2, '0') = p.venue_code
             AND CAST(s.race_no AS INTEGER) = p.race_no
             AND REPLACE(TRIM(CAST(s.horse_name AS VARCHAR)), '　', '') = p.horse_name_join
        ),
        kyi_ranked AS (
            SELECT
                k.*,
                RANK() OVER(
                    PARTITION BY race_key_raw
                    ORDER BY idm DESC NULLS LAST
                ) AS idm_rank_calc,
                RANK() OVER(
                    PARTITION BY race_key_raw
                    ORDER BY total_index DESC NULLS LAST
                ) AS total_index_rank_calc
            FROM {kyi} k
        )
        SELECT
            s.*,
            k.horse_name AS kyi_horse_name,
            k.idm,
            k.total_index,
            k.base_win_rank,
            k.base_win_odds,
            k.longshot_index,
            k.running_style_code,
            k.distance_fit_code,
            k.improvement_code,
            k.heavy_track_fit_code,
            k.turf_fit_code,
            k.dirt_fit_code,
            k.forecast_pace_code,
            k.pace_rank_front,
            k.pace_rank_pace,
            k.pace_rank_late,
            k.pace_rank_position,
            k.idm_rank_calc,
            k.total_index_rank_calc
        FROM sed_join s
        LEFT JOIN kyi_ranked k
          ON CAST(k.race_key_raw AS VARCHAR) = CAST(s.race_key_raw AS VARCHAR)
         AND CAST(k.horse_no AS INTEGER) = CAST(s.horse_no AS INTEGER)
        WHERE s.sed_match_count = 1
    """

    cursor = connection.execute(query)
    columns = [description[0] for description in cursor.description]
    joined = [dict(zip(columns, row)) for row in cursor.fetchall()]

    bettable = [
        row
        for row in joined
        if row.get("abnormal_code") in (None, "", 0, "0")
    ]
    kyi_joined = [
        row for row in bettable if row.get("kyi_horse_name") not in (None, "")
    ]

    for row in kyi_joined:
        row["final_popularity"] = to_int(row.get("final_popularity"))
        row["rank_base_win"] = rank_bucket(row.get("base_win_rank"))
        row["rank_idm"] = rank_bucket(row.get("idm_rank_calc"))
        row["rank_total"] = rank_bucket(row.get("total_index_rank_calc"))
        row["rank_pace_front"] = rank_bucket(row.get("pace_rank_front"))
        row["rank_pace_pace"] = rank_bucket(row.get("pace_rank_pace"))
        row["rank_pace_late"] = rank_bucket(row.get("pace_rank_late"))
        row["rank_pace_position"] = rank_bucket(row.get("pace_rank_position"))

    focus_reasons = ["pace_flow", "surface"]
    rank_features = [
        ("base_win_rank", "rank_base_win"),
        ("idm_rank", "rank_idm"),
        ("total_index_rank", "rank_total"),
        ("pace_rank_front", "rank_pace_front"),
        ("pace_rank_pace", "rank_pace_pace"),
        ("pace_rank_late", "rank_pace_late"),
        ("pace_rank_position", "rank_pace_position"),
    ]
    rank_bands = ["1-3", "4-5", "6-9", "10+", "missing"]

    rows_out = []
    summary = {
        "schema_version": "keibailuka-jrdb-interaction-v0.1",
        "reason_tag_version": reason_definitions["version"],
        "population": {
            "source_picks": len(picks),
            "sed_joined_bettable": len(bettable),
            "kyi_joined": len(kyi_joined),
            "kyi_join_rate_pct": pct(len(kyi_joined), len(bettable)),
        },
        "focus": {},
    }

    for reason in focus_reasons:
        reason_rows = [
            row
            for row in kyi_joined
            if row["primary_reason"] == reason
            and row["final_popularity"] is not None
            and 6 <= row["final_popularity"] <= 9
        ]
        reason_payload = {
            "label": reason_labels[reason],
            "baseline": metric(reason_rows),
            "features": {},
        }

        for feature_name, bucket_column in rank_features:
            feature_payload = {}
            for band in rank_bands:
                band_rows = [
                    row
                    for row in reason_rows
                    if row.get(bucket_column) == band
                ]
                years = {
                    str(year): metric(
                        [row for row in band_rows if int(row["year"]) == year]
                    )
                    for year in (2024, 2025)
                }
                result = {
                    "overall": metric(band_rows),
                    "by_year": years,
                }
                feature_payload[band] = result

                rows_out.append(
                    {
                        "reason_id": reason,
                        "reason_label": reason_labels[reason],
                        "feature": feature_name,
                        "band": band,
                        "N": result["overall"]["N"],
                        "win_rate_pct": result["overall"]["win_rate_pct"],
                        "place_rate_pct": result["overall"]["place_rate_pct"],
                        "win_roi_pct": result["overall"]["win_roi_pct"],
                        "place_roi_pct": result["overall"]["place_roi_pct"],
                        "N_2024": years["2024"]["N"],
                        "win_roi_2024": years["2024"]["win_roi_pct"],
                        "place_roi_2024": years["2024"]["place_roi_pct"],
                        "N_2025": years["2025"]["N"],
                        "win_roi_2025": years["2025"]["win_roi_pct"],
                        "place_roi_2025": years["2025"]["place_roi_pct"],
                    }
                )
            reason_payload["features"][feature_name] = feature_payload

        # Market-vs-JRDB disagreement cuts. These are fixed before seeing results.
        cuts = {
            "base_win_rank_le5": lambda row: to_int(row.get("base_win_rank")) is not None
            and to_int(row.get("base_win_rank")) <= 5,
            "base_win_rank_ge6": lambda row: to_int(row.get("base_win_rank")) is not None
            and to_int(row.get("base_win_rank")) >= 6,
            "idm_rank_le5": lambda row: to_int(row.get("idm_rank_calc")) is not None
            and to_int(row.get("idm_rank_calc")) <= 5,
            "idm_rank_ge6": lambda row: to_int(row.get("idm_rank_calc")) is not None
            and to_int(row.get("idm_rank_calc")) >= 6,
            "total_rank_le5": lambda row: to_int(row.get("total_index_rank_calc")) is not None
            and to_int(row.get("total_index_rank_calc")) <= 5,
            "total_rank_ge6": lambda row: to_int(row.get("total_index_rank_calc")) is not None
            and to_int(row.get("total_index_rank_calc")) >= 6,
            "jrdb_any_core_top5": lambda row: any(
                to_int(row.get(value)) is not None and to_int(row.get(value)) <= 5
                for value in ("base_win_rank", "idm_rank_calc", "total_index_rank_calc")
            ),
            "jrdb_no_core_top5": lambda row: all(
                to_int(row.get(value)) is None or to_int(row.get(value)) >= 6
                for value in ("base_win_rank", "idm_rank_calc", "total_index_rank_calc")
            ),
        }
        cut_payload = {}
        for cut_name, predicate in cuts.items():
            cut_rows = [row for row in reason_rows if predicate(row)]
            cut_payload[cut_name] = {
                "overall": metric(cut_rows),
                "by_year": {
                    str(year): metric(
                        [row for row in cut_rows if int(row["year"]) == year]
                    )
                    for year in (2024, 2025)
                },
            }
        reason_payload["cuts"] = cut_payload
        summary["focus"][reason] = reason_payload

    write_csv(output_dir / "jrdb_rank_band_metrics.csv", rows_out)
    write_json(output_dir / "summary.json", summary)

    lines = [
        "# keibailuka × JRDB KYI Interaction v0.1",
        "",
        (
            f"- SED bettable N: {summary['population']['sed_joined_bettable']} / "
            f"KYI joined: {summary['population']['kyi_joined']} "
            f"({summary['population']['kyi_join_rate_pct']:.2f}%)"
        ),
        "- focus: primary reason × final popularity 6-9",
    ]

    for reason in focus_reasons:
        payload = summary["focus"][reason]
        baseline = payload["baseline"]
        lines.extend(
            [
                "",
                f"## {payload['label']}",
                (
                    f"baseline N={baseline['N']} "
                    f"winROI={baseline['win_roi_pct']}% "
                    f"placeROI={baseline['place_roi_pct']}%"
                ),
            ]
        )
        for cut_name in (
            "base_win_rank_le5",
            "base_win_rank_ge6",
            "idm_rank_le5",
            "idm_rank_ge6",
            "total_rank_le5",
            "total_rank_ge6",
            "jrdb_any_core_top5",
            "jrdb_no_core_top5",
        ):
            item = payload["cuts"][cut_name]
            overall = item["overall"]
            y24 = item["by_year"]["2024"]
            y25 = item["by_year"]["2025"]
            lines.append(
                f"- {cut_name}: N={overall['N']} "
                f"winROI={overall['win_roi_pct']}% "
                f"placeROI={overall['place_roi_pct']}% | "
                f"2024 N={y24['N']} winROI={y24['win_roi_pct']}% | "
                f"2025 N={y25['N']} winROI={y25['win_roi_pct']}%"
            )

    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import io
import json
import re
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests


VENUE_CODES = {
    "札幌": "01",
    "函館": "02",
    "福島": "03",
    "新潟": "04",
    "東京": "05",
    "中山": "06",
    "中京": "07",
    "京都": "08",
    "阪神": "09",
    "小倉": "10",
}


def get(url: str, **kwargs):
    response = requests.get(url, timeout=90, **kwargs)
    response.raise_for_status()
    return response


def download_drive(file_id: str, path: Path, sha256: str | None = None) -> None:
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
    if sha256:
        actual = hashlib.sha256(data).hexdigest()
        if actual.lower() != sha256.lower():
            raise RuntimeError(f"SHA mismatch: {actual}")
    path.write_bytes(data)


def fetch_sheet_rows(spreadsheet_id: str, sheet_name: str) -> list[dict[str, str]]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote(sheet_name)}"
    )
    text = get(url).content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def pct(numerator: float, denominator: float):
    if not denominator:
        return None
    return round(numerator / denominator * 100, 3)


def metric(rows: list[dict]) -> dict:
    n = len(rows)
    wins = sum(to_int(row.get("finish")) == 1 for row in rows)
    places = sum((to_int(row.get("finish")) or 99) <= 3 for row in rows)
    win_return = sum(to_float(row.get("win_payout")) or 0 for row in rows)
    place_return = sum(to_float(row.get("place_payout")) or 0 for row in rows)
    return {
        "N": n,
        "wins": wins,
        "places": places,
        "win_rate_pct": pct(wins, n),
        "place_rate_pct": pct(places, n),
        "win_roi_pct": pct(win_return, n * 100),
        "place_roi_pct": pct(place_return, n * 100),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def normalize_name(value: str) -> str:
    return (
        unicodedata.normalize("NFKC", str(value or ""))
        .replace("　", "")
        .replace(" ", "")
        .strip()
    )


def popularity_bucket(value):
    popularity = to_int(value)
    if popularity is None:
        return None
    if popularity == 1:
        return "1人気"
    if popularity == 2:
        return "2人気"
    if popularity == 3:
        return "3人気"
    if 4 <= popularity <= 5:
        return "4〜5人気"
    if 6 <= popularity <= 9:
        return "6〜9人気"
    if popularity >= 10:
        return "10人気以下"
    return None


def odds_bucket(value):
    odds = to_float(value)
    if odds is None:
        return None
    if odds < 3:
        return "<3"
    if odds < 5:
        return "3〜4.9"
    if odds < 10:
        return "5〜9.9"
    if odds < 20:
        return "10〜19.9"
    if odds < 50:
        return "20〜49.9"
    return "50+"


def load_reason_definitions() -> dict:
    path = (
        Path(__file__).resolve().parent.parent
        / "research"
        / "comment_reason_tags_v0_1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def tag_comment(comment: str, definitions: dict) -> list[str]:
    text = comment or ""
    tags = []
    for definition in definitions["tags"]:
        if any(pattern in text for pattern in definition["patterns"]):
            tags.append(definition["id"])
    if not tags:
        tags.append("other")
    return tags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    request = json.load(open(args.request_json, encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import duckdb

    temporary_dir = Path(tempfile.mkdtemp(prefix="keibailuka_research_"))
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
            }
        )

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
            comment VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
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
            )
            for pick in picks
        ],
    )

    sed = (
        f"read_parquet(['{sed_2024.as_posix()}','{sed_2025.as_posix()}'],"
        "union_by_name=true)"
    )
    query = f"""
        SELECT
            p.*,
            COUNT(s.horse_no) OVER(PARTITION BY p.source_id) match_count,
            s.horse_no,
            s.result_key,
            s.horse_name sed_horse_name,
            s.finish,
            s.abnormal_code,
            s.final_win_odds,
            s.final_popularity,
            s.final_place_odds_lower,
            s.win_payout,
            s.place_payout
        FROM picks p
        LEFT JOIN {sed} s
          ON CAST(s.race_date AS VARCHAR) = p.race_date
         AND LPAD(CAST(s.venue_code AS VARCHAR), 2, '0') = p.venue_code
         AND CAST(s.race_no AS INTEGER) = p.race_no
         AND REPLACE(TRIM(CAST(s.horse_name AS VARCHAR)), '　', '') = p.horse_name_join
    """
    cursor = connection.execute(query)
    columns = [description[0] for description in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    by_source_id = defaultdict(list)
    for row in rows:
        by_source_id[row["source_id"]].append(row)

    matched = []
    unmatched = []
    ambiguous = []
    for pick in picks:
        candidate_rows = by_source_id[pick["source_id"]]
        match_count = int(candidate_rows[0].get("match_count") or 0)
        if match_count == 0:
            unmatched.append(pick)
        elif match_count == 1:
            matched.append(candidate_rows[0])
        else:
            ambiguous.extend(candidate_rows)

    unmatched_diagnostic = []
    for pick in unmatched:
        diagnostic_query = f"""
            SELECT
                CAST(horse_no AS INTEGER) horse_no,
                TRIM(CAST(horse_name AS VARCHAR)) horse_name,
                finish,
                abnormal_code
            FROM {sed}
            WHERE CAST(race_date AS VARCHAR) = ?
              AND LPAD(CAST(venue_code AS VARCHAR), 2, '0') = ?
              AND CAST(race_no AS INTEGER) = ?
            ORDER BY CAST(horse_no AS INTEGER)
        """
        candidates = connection.execute(
            diagnostic_query,
            [pick["race_date"], pick["venue_code"], pick["race_no"]],
        ).fetchall()

        target = normalize_name(pick["horse_name_raw"])
        scored = []
        for horse_no, horse_name, finish, abnormal_code in candidates:
            normalized_candidate = normalize_name(horse_name)
            similarity = 0.0
            if target and normalized_candidate:
                similarity = difflib.SequenceMatcher(
                    None,
                    target,
                    normalized_candidate,
                ).ratio()
            scored.append(
                (
                    similarity,
                    horse_no,
                    str(horse_name).strip(),
                    finish,
                    abnormal_code,
                )
            )

        scored.sort(reverse=True, key=lambda item: item[0])
        top = scored[0] if scored else (0.0, None, None, None, None)
        unmatched_diagnostic.append(
            {
                **pick,
                "same_race_candidate_count": len(candidates),
                "best_similarity": round(top[0], 4),
                "best_horse_no": top[1],
                "best_candidate": top[2],
                "best_finish": top[3],
                "best_abnormal_code": top[4],
                "same_race_horses": " | ".join(
                    f"{horse_no}:{horse_name}"
                    for _, horse_no, horse_name, _, _ in scored
                ),
            }
        )

    def is_normal(row: dict) -> bool:
        return row.get("abnormal_code") in (None, "", 0, "0")

    bettable = [row for row in matched if is_normal(row)]
    abnormal = [row for row in matched if not is_normal(row)]

    payout_audit = []
    winners = [
        row
        for row in bettable
        if to_int(row.get("finish")) == 1
        and to_float(row.get("win_payout"))
        and to_float(row.get("final_win_odds")) is not None
    ][:10]
    for row in winners:
        odds = to_float(row["final_win_odds"])
        payout = to_float(row["win_payout"])
        payout_audit.append(
            {
                "race_date": row["race_date"],
                "venue": row["venue"],
                "race_no": row["race_no"],
                "horse": row["horse_name_join"],
                "final_win_odds": odds,
                "win_payout": payout,
                "odds_x_100": round(odds * 100, 6),
                "difference": round(payout - odds * 100, 6),
                "place_payout": to_float(row.get("place_payout")),
            }
        )
    payout_unit_ok = bool(payout_audit) and all(
        abs(row["difference"]) < 0.01 for row in payout_audit
    )

    reason_definitions = load_reason_definitions()
    reason_labels = {
        definition["id"]: definition["label"]
        for definition in reason_definitions["tags"]
    }
    reason_labels["other"] = "その他・未分類"

    for row in bettable:
        tags = tag_comment(row.get("comment", ""), reason_definitions)
        row["reason_tags"] = tags
        row["primary_reason"] = tags[0]
        row["popularity_bucket"] = popularity_bucket(row.get("final_popularity"))
        row["odds_bucket"] = odds_bucket(row.get("final_win_odds"))

    summary = {
        "schema_version": "keibailuka-research-v0.3",
        "reason_tag_version": reason_definitions["version"],
        "source_population": {
            "total": len(picks),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "ambiguous": len(set(row["source_id"] for row in ambiguous)),
            "match_rate_pct": pct(len(matched), len(picks)),
            "correction_map_rows": len(correction_map),
            "correction_applied_and_matched": sum(
                int(row.get("correction_applied") or 0) for row in matched
            ),
        },
        "bettable_population": {
            "N": len(bettable),
            "abnormal_excluded": len(abnormal),
        },
        "payout_unit_audit": {
            "unit_confirmed_100yen": payout_unit_ok,
            "examples": payout_audit,
        },
        "overall": metric(bettable),
        "by_year": {},
        "by_popularity": {},
        "by_win_odds": {},
        "by_reason_multilabel": {},
        "by_primary_reason": {},
        "focus_by_reason": {},
    }

    for year in (2024, 2025):
        summary["by_year"][str(year)] = metric(
            [row for row in bettable if row["year"] == year]
        )

    popularity_order = [
        "1人気",
        "2人気",
        "3人気",
        "4〜5人気",
        "6〜9人気",
        "10人気以下",
    ]
    for bucket in popularity_order:
        summary["by_popularity"][bucket] = metric(
            [
                row
                for row in bettable
                if row.get("popularity_bucket") == bucket
            ]
        )

    odds_order = ["<3", "3〜4.9", "5〜9.9", "10〜19.9", "20〜49.9", "50+"]
    for bucket in odds_order:
        summary["by_win_odds"][bucket] = metric(
            [row for row in bettable if row.get("odds_bucket") == bucket]
        )

    tag_order = [definition["id"] for definition in reason_definitions["tags"]]
    tag_order.append("other")

    reason_metric_rows = []
    for tag in tag_order:
        tagged_rows = [
            row for row in bettable if tag in row.get("reason_tags", [])
        ]
        tagged_metric = metric(tagged_rows)
        summary["by_reason_multilabel"][tag] = tagged_metric
        reason_metric_rows.append(
            {
                "reason_id": tag,
                "reason_label": reason_labels[tag],
                **tagged_metric,
            }
        )

        primary_rows = [
            row for row in bettable if row.get("primary_reason") == tag
        ]
        summary["by_primary_reason"][tag] = metric(primary_rows)

    focus_conditions = {
        "pop_6_9": lambda row: row.get("popularity_bucket") == "6〜9人気",
        "odds_20_49_9": lambda row: row.get("odds_bucket") == "20〜49.9",
        "pop_6_9_and_odds_20_49_9": lambda row: (
            row.get("popularity_bucket") == "6〜9人気"
            and row.get("odds_bucket") == "20〜49.9"
        ),
    }

    focus_rows_output = []
    for condition_name, condition in focus_conditions.items():
        summary["focus_by_reason"][condition_name] = {}
        for tag in tag_order:
            rows_for_tag = [
                row
                for row in bettable
                if condition(row) and tag in row.get("reason_tags", [])
            ]
            total_metric = metric(rows_for_tag)
            by_year = {}
            for year in (2024, 2025):
                by_year[str(year)] = metric(
                    [row for row in rows_for_tag if row["year"] == year]
                )

            summary["focus_by_reason"][condition_name][tag] = {
                "overall": total_metric,
                "by_year": by_year,
            }
            focus_rows_output.append(
                {
                    "condition": condition_name,
                    "reason_id": tag,
                    "reason_label": reason_labels[tag],
                    "N": total_metric["N"],
                    "win_rate_pct": total_metric["win_rate_pct"],
                    "place_rate_pct": total_metric["place_rate_pct"],
                    "win_roi_pct": total_metric["win_roi_pct"],
                    "place_roi_pct": total_metric["place_roi_pct"],
                    "N_2024": by_year["2024"]["N"],
                    "win_roi_2024": by_year["2024"]["win_roi_pct"],
                    "place_roi_2024": by_year["2024"]["place_roi_pct"],
                    "N_2025": by_year["2025"]["N"],
                    "win_roi_2025": by_year["2025"]["win_roi_pct"],
                    "place_roi_2025": by_year["2025"]["place_roi_pct"],
                }
            )

    primary_focus_rows_output = []
    for condition_name, condition in focus_conditions.items():
        for tag in tag_order:
            rows_for_tag = [
                row
                for row in bettable
                if condition(row) and row.get("primary_reason") == tag
            ]
            total_metric = metric(rows_for_tag)
            year_2024 = metric([row for row in rows_for_tag if row["year"] == 2024])
            year_2025 = metric([row for row in rows_for_tag if row["year"] == 2025])
            primary_focus_rows_output.append(
                {
                    "condition": condition_name,
                    "reason_id": tag,
                    "reason_label": reason_labels[tag],
                    "N": total_metric["N"],
                    "win_rate_pct": total_metric["win_rate_pct"],
                    "place_rate_pct": total_metric["place_rate_pct"],
                    "win_roi_pct": total_metric["win_roi_pct"],
                    "place_roi_pct": total_metric["place_roi_pct"],
                    "N_2024": year_2024["N"],
                    "win_roi_2024": year_2024["win_roi_pct"],
                    "place_roi_2024": year_2024["place_roi_pct"],
                    "N_2025": year_2025["N"],
                    "win_roi_2025": year_2025["win_roi_pct"],
                    "place_roi_2025": year_2025["place_roi_pct"],
                }
            )

    overlap_tags = ["traffic_path", "pace_flow", "surface", "distance"]
    overlap_rows_output = []
    for condition_name, condition in focus_conditions.items():
        for index, left_tag in enumerate(overlap_tags):
            for right_tag in overlap_tags[index + 1:]:
                pair_rows = [
                    row
                    for row in bettable
                    if condition(row)
                    and left_tag in row.get("reason_tags", [])
                    and right_tag in row.get("reason_tags", [])
                ]
                pair_metric = metric(pair_rows)
                overlap_rows_output.append(
                    {
                        "condition": condition_name,
                        "left_reason": reason_labels[left_tag],
                        "right_reason": reason_labels[right_tag],
                        **pair_metric,
                    }
                )

    write_csv(output_dir / "join_unmatched.csv", unmatched)
    write_csv(
        output_dir / "join_unmatched_diagnostic.csv",
        unmatched_diagnostic,
    )
    write_csv(output_dir / "join_ambiguous.csv", ambiguous)
    write_csv(output_dir / "payout_unit_audit.csv", payout_audit)
    write_csv(output_dir / "reason_metrics.csv", reason_metric_rows)
    write_csv(output_dir / "reason_focus_metrics.csv", focus_rows_output)
    write_csv(
        output_dir / "primary_reason_focus_metrics.csv",
        primary_focus_rows_output,
    )
    write_csv(
        output_dir / "focus_tag_overlap_metrics.csv",
        overlap_rows_output,
    )

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    def format_value(value):
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    source_population = summary["source_population"]
    lines = [
        "# keibailuka Historical Research 2024-2025",
        "",
        (
            f"- total: {source_population['total']} / "
            f"matched: {source_population['matched']} / "
            f"unmatched: {source_population['unmatched']} / "
            f"ambiguous: {source_population['ambiguous']}"
        ),
        (
            f"- match rate: {format_value(source_population['match_rate_pct'])}% / "
            f"corrections matched: "
            f"{source_population['correction_applied_and_matched']} / "
            f"bettable N: {len(bettable)} / abnormal excluded: {len(abnormal)}"
        ),
        f"- payout 100yen unit confirmed: {payout_unit_ok}",
        f"- reason tag version: {reason_definitions['version']}",
        "",
        "## Overall",
    ]

    overall = summary["overall"]
    lines.append(
        f"N={overall['N']} wins={overall['wins']} places={overall['places']} "
        f"win%={format_value(overall['win_rate_pct'])} "
        f"place%={format_value(overall['place_rate_pct'])} "
        f"winROI={format_value(overall['win_roi_pct'])}% "
        f"placeROI={format_value(overall['place_roi_pct'])}%"
    )

    lines.extend(["", "## By reason (multi-label)"])
    for tag in tag_order:
        reason_metric = summary["by_reason_multilabel"][tag]
        lines.append(
            f"- {reason_labels[tag]}: N={reason_metric['N']} "
            f"win%={format_value(reason_metric['win_rate_pct'])} "
            f"place%={format_value(reason_metric['place_rate_pct'])} "
            f"winROI={format_value(reason_metric['win_roi_pct'])}% "
            f"placeROI={format_value(reason_metric['place_roi_pct'])}%"
        )

    lines.extend(["", "## Focus: 6〜9人気 × reason"])
    for tag in tag_order:
        focus_metric = summary["focus_by_reason"]["pop_6_9"][tag]["overall"]
        lines.append(
            f"- {reason_labels[tag]}: N={focus_metric['N']} "
            f"winROI={format_value(focus_metric['win_roi_pct'])}% "
            f"placeROI={format_value(focus_metric['place_roi_pct'])}%"
        )

    lines.extend(["", "## Focus: 20〜49.9倍 × reason"])
    for tag in tag_order:
        focus_metric = summary["focus_by_reason"]["odds_20_49_9"][tag]["overall"]
        lines.append(
            f"- {reason_labels[tag]}: N={focus_metric['N']} "
            f"winROI={format_value(focus_metric['win_roi_pct'])}% "
            f"placeROI={format_value(focus_metric['place_roi_pct'])}%"
        )

    lines.extend(["", "## Focus: 6〜9人気 AND 20〜49.9倍 × reason"])
    for tag in tag_order:
        focus_metric = summary["focus_by_reason"][
            "pop_6_9_and_odds_20_49_9"
        ][tag]["overall"]
        lines.append(
            f"- {reason_labels[tag]}: N={focus_metric['N']} "
            f"winROI={format_value(focus_metric['win_roi_pct'])}% "
            f"placeROI={format_value(focus_metric['place_roi_pct'])}%"
        )

    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()

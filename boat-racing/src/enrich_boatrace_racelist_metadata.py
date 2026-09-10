#!/usr/bin/env python3
"""BOAT RACE公式出走表CSVへ開催メタデータを付与する。

公式日別レース一覧から会場ごとの開催名・開催グレードを取得し、既存の
出走表CSVへ付与する。各Rページから取得済みの「レース種別」はそのまま保持する。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from fetch_boatrace_event_meta import fetch_event_meta

ADDED_COLUMNS = ["開催グレード", "開催名"]
INSERT_AFTER = "開催日目"


class MetadataEnrichmentError(ValueError):
    """開催メタデータ付与に失敗したことを表す。"""


def load_config(path: str) -> dict[str, Any]:
    """既存出走表取得設定を読み込む。"""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not config.get("date") or not config.get("venues"):
        raise MetadataEnrichmentError("configにdateとvenuesが必要です")
    return config


def enriched_columns(columns: list[str]) -> list[str]:
    """追加列を開催日目の直後へ一度だけ挿入する。"""
    base_columns = [column for column in columns if column not in ADDED_COLUMNS]
    if INSERT_AFTER not in base_columns:
        raise MetadataEnrichmentError(f"必須列がありません: {INSERT_AFTER}")
    position = base_columns.index(INSERT_AFTER) + 1
    return base_columns[:position] + ADDED_COLUMNS + base_columns[position:]


def build_event_map(date: str, venues: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """公式日別一覧を取得し、対象会場だけを開催メタデータへ変換する。"""
    official_rows = fetch_event_meta(date)
    by_venue = {row["会場"]: row for row in official_rows}
    event_map: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for venue in venues:
        name = str(venue["name"])
        row = by_venue.get(name)
        if row is None:
            errors.append(f"{name}: 開催情報なし")
            continue
        grade = str(row.get("グレード大分類", "")).strip()
        event_name = str(row.get("開催グレード", "")).strip()
        if not grade or grade == "未分類" or not event_name:
            errors.append(f"{name}: 開催グレードまたは開催名を解決できません")
            continue
        event_map[name] = {"開催グレード": grade, "開催名": event_name}
    if errors:
        raise MetadataEnrichmentError("; ".join(errors))
    return event_map


def enrich_csv(path: Path, event_map: dict[str, dict[str, str]]) -> None:
    """1つの出走表CSVを原子的にメタデータ付与して置換する。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        original_columns = list(reader.fieldnames or [])
        rows = list(reader)
    if not original_columns:
        raise MetadataEnrichmentError(f"CSVヘッダがありません: {path.name}")
    if "会場" not in original_columns or "レース種別" not in original_columns:
        raise MetadataEnrichmentError(f"必要列がありません: {path.name}")

    columns = enriched_columns(original_columns)
    for row in rows:
        venue = str(row.get("会場", "")).strip()
        metadata = event_map.get(venue)
        if metadata is None:
            raise MetadataEnrichmentError(f"{path.name}: {venue} の開催情報がありません")
        race_type = str(row.get("レース種別", "")).strip()
        if not race_type:
            raise MetadataEnrichmentError(f"{path.name}: {venue} {row.get('R', '')}R のレース種別が空欄です")
        row["開催グレード"] = metadata["開催グレード"]
        row["開催名"] = metadata["開催名"]

    temporary = path.with_name(path.name + ".metadata.tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def enrich_from_config(config_path: str) -> list[Path]:
    """設定に対応する原本CSV・予想入力CSVをともに更新する。"""
    config = load_config(config_path)
    date = str(config["date"])
    venues = list(config["venues"])
    output_dir = Path(config.get("output_dir", "output"))
    names = "_".join(str(venue["name"]) for venue in venues)
    paths = [
        output_dir / f"{date}_公式出走表原本_{names}.csv",
        output_dir / f"{date}_公式出走表_{names}.csv",
    ]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise MetadataEnrichmentError("出走表CSVがありません: " + ", ".join(missing))
    event_map = build_event_map(date, venues)
    for path in paths:
        enrich_csv(path, event_map)
    return paths


def main() -> int:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(description="出走表CSVへ公式開催グレード・開催名を付与")
    parser.add_argument("--config", required=True, help="出走表取得と同じ設定JSON")
    args = parser.parse_args()
    try:
        paths = enrich_from_config(args.config)
    except (OSError, json.JSONDecodeError, MetadataEnrichmentError) as exc:
        print(f"開催メタデータ付与失敗: {exc}", file=sys.stderr)
        return 2
    for path in paths:
        print(f"開催メタデータ付与完了: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Freeze official BOAT RACE event name/grade metadata for a race day."""

from __future__ import annotations

import argparse
import csv
import html
import re
import urllib.request
from pathlib import Path

OFFICIAL_INDEX = "https://www.boatrace.jp/owpc/pc/race/index?hd={date}"
GRADE_MAP = {"ippan": "一般", "G2b": "G2", "G1b": "G1", "SGb": "SG", "G3b": "その他"}
FIELDS = ["対象日", "会場", "開催グレード", "グレード大分類", "source", "source_file", "備考"]


def parse_official_index(source: str, ymd: str) -> list[dict[str, str]]:
    rows = []
    for block in re.findall(r"<tbody\b.*?</tbody>", source, flags=re.I | re.S):
        venue = re.search(r'<img[^>]+alt="([^"]+)"', block, flags=re.I)
        event = re.search(r'<a href="([^"]*raceindex\?jcd=\d+[^"]*)">(.*?)</a>', block, flags=re.I | re.S)
        grade = re.search(r'class="[^"]*\bis-(ippan|G1b|G2b|SGb|G3b)\b', block)
        if not venue or not event:
            continue
        event_name = html.unescape(re.sub(r"<[^>]+>", "", event.group(2))).strip()
        href = html.unescape(event.group(1))
        rows.append({
            "対象日": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}",
            "会場": html.unescape(venue.group(1)).strip(),
            "開催グレード": event_name,
            "グレード大分類": GRADE_MAP.get(grade.group(1), "未分類") if grade else "未分類",
            "source": "BOAT RACE オフィシャルウェブサイト",
            "source_file": urllib.request.urljoin("https://www.boatrace.jp", href),
            "備考": "公式日別レース一覧から取得" if grade else "公式ページでgrade未解決・要確認",
        })
    return rows


def fetch_event_meta(ymd: str) -> list[dict[str, str]]:
    if not re.fullmatch(r"\d{8}", ymd):
        raise ValueError("date must be YYYYMMDD")
    request = urllib.request.Request(OFFICIAL_INDEX.format(date=ymd), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return parse_official_index(response.read().decode("utf-8"), ymd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--venues", required=True, help="comma-separated venue names")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    wanted = [x.strip() for x in args.venues.split(",") if x.strip()]
    found = {row["会場"]: row for row in fetch_event_meta(args.date)}
    rows = [found.get(venue, {"対象日": f"{args.date[:4]}-{args.date[4:6]}-{args.date[6:]}",
            "会場": venue, "開催グレード": "", "グレード大分類": "未分類",
            "source": "BOAT RACE オフィシャルウェブサイト", "source_file": OFFICIAL_INDEX.format(date=args.date),
            "備考": "公式ページで開催情報未解決・要確認"}) for venue in wanted]
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    if any(row["グレード大分類"] == "未分類" for row in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

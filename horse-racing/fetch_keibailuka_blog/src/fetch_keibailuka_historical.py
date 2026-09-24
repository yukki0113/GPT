#!/usr/bin/env python3
"""Historical/monthly keibailuka crawler built on the canonical daily parser.

The historical path intentionally reuses \`\`fetch_keibailuka_blog.py\`\` for
article parsing/classification.  Its only additional responsibilities are:

- discover all target articles from Blogger's public feed for each month,
- group them by race date / venue,
- run the canonical 1R..12R parser and fail-closed validation,
- emit monthly and batch CSV/JSON artifacts suitable for ledger import.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from fetch_keibailuka_blog import (
    ARTICLE_PHRASE,
    BASE_URL,
    VALID_VENUES,
    ArticleSource,
    build_result,
    build_session,
    build_validation,
    body_lines,
    canonicalize_article_url,
    extract_feed_entry,
    fetch_article_html,
    fetch_response,
    normalize_text,
    parse_source,
    select_article_body,
)

SCHEMA_VERSION = "keibailuka-historical-v0.1"
MAX_MONTHS_PER_RUN = 12
PAGE_SIZE = 100
MAX_FEED_PAGES = 20
CANONICAL_VENUE_ORDER = [
    "札幌",
    "函館",
    "福島",
    "新潟",
    "東京",
    "中山",
    "中京",
    "京都",
    "阪神",
    "小倉",
]
VENUE_RANK = {venue: index for index, venue in enumerate(CANONICAL_VENUE_ORDER)}
TITLE_DATE_RE = re.compile(r"(?P<year>20\d{2})/(?P<month>\d{1,2})/(?P<day>\d{1,2})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch keibailuka historical articles by inclusive month range."
    )
    parser.add_argument("--start-month", required=True, help="YYYY-MM")
    parser.add_argument("--end-month", help="YYYY-MM; defaults to start-month")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--interval", type=float, default=0.8)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def parse_month(value: str) -> date:
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise ValueError("month must be YYYY-MM") from exc
    return parsed.replace(day=1)


def next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


def iter_months(start_month: date, end_month: date) -> list[date]:
    if end_month < start_month:
        raise ValueError("end-month must be >= start-month")
    months: list[date] = []
    current = start_month
    while current <= end_month:
        months.append(current)
        if len(months) > MAX_MONTHS_PER_RUN:
            raise ValueError(
                f"month range must contain at most {MAX_MONTHS_PER_RUN} months"
            )
        current = next_month(current)
    return months


def validate_runtime(interval: float, timeout: float) -> None:
    if interval < 0:
        raise ValueError("--interval must be >= 0")
    if timeout <= 0:
        raise ValueError("--timeout must be > 0")


def month_feed_url(month_start: date, start_index: int) -> str:
    end = next_month(month_start)
    published_min = datetime.combine(
        month_start - timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    published_max = datetime.combine(
        end + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    query = urlencode(
        {
            "alt": "json",
            "max-results": str(PAGE_SIZE),
            "start-index": str(start_index),
            "orderby": "published",
            "published-min": published_min.isoformat().replace("+00:00", "Z"),
            "published-max": published_max.isoformat().replace("+00:00", "Z"),
        }
    )
    return urljoin(BASE_URL, "feeds/posts/default?" + query)


def parse_target_title(title: str) -> tuple[date, str] | None:
    compact = re.sub(r"\s+", "", normalize_text(title))
    if ARTICLE_PHRASE not in compact:
        return None
    match = TITLE_DATE_RE.search(compact)
    if match is None:
        return None
    try:
        race_date = date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None
    venues = [venue for venue in VALID_VENUES if venue in compact]
    if len(venues) != 1:
        return None
    return race_date, venues[0]


def discover_month_sources(
    session: Any,
    month_start: date,
    timeout: float,
    interval: float,
) -> tuple[dict[tuple[date, str], ArticleSource], list[str], int]:
    sources: dict[tuple[date, str], ArticleSource] = {}
    errors: list[str] = []
    scanned_entries = 0
    seen_page_signatures: set[tuple[str, ...]] = set()

    for page_no in range(MAX_FEED_PAGES):
        start_index = 1 + page_no * PAGE_SIZE
        url = month_feed_url(month_start, start_index)
        payload = fetch_response(session, url, timeout, interval).json()
        entries = payload.get("feed", {}).get("entry", [])
        if not isinstance(entries, list) or not entries:
            break

        page_urls: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            scanned_entries += 1
            title, alternate_url, embedded_html = extract_feed_entry(entry)
            if alternate_url:
                page_urls.append(canonicalize_article_url(alternate_url))

            parsed = parse_target_title(title)
            if parsed is None:
                continue
            race_date, venue = parsed
            if race_date.year != month_start.year or race_date.month != month_start.month:
                continue
            if not alternate_url:
                errors.append(f"{race_date} {venue}: target feed entry has no alternate URL")
                continue

            key = (race_date, venue)
            source = ArticleSource(
                venue=venue,
                url=canonicalize_article_url(alternate_url),
                title=normalize_text(title),
                embedded_html=embedded_html,
                source_method="blogger_feed_content" if embedded_html else "blogger_feed_url",
            )
            existing = sources.get(key)
            if existing is None:
                sources[key] = source
            elif existing.url != source.url:
                errors.append(
                    f"{race_date} {venue}: duplicate target articles: "
                    f"{existing.url} / {source.url}"
                )

        signature = tuple(page_urls)
        if signature in seen_page_signatures:
            break
        seen_page_signatures.add(signature)
        if len(entries) < PAGE_SIZE:
            break
    else:
        errors.append("Blogger feed pagination exceeded safety limit")

    if not sources:
        errors.append(f"{month_start:%Y-%m}: no target articles discovered")
    return sources, errors, scanned_entries


def source_debug_lines(source: ArticleSource, html: str) -> list[str]:
    """Return the exact normalized visible lines used to diagnose parser failures."""

    if source.embedded_html is not None:
        soup = BeautifulSoup(source.embedded_html, "html.parser")
        return body_lines(soup)

    soup = BeautifulSoup(html, "html.parser")
    return body_lines(select_article_body(soup))


def write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_month(
    session: Any,
    month_start: date,
    output_dir: Path,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sources, discovery_errors, scanned_entries = discover_month_sources(
        session, month_start, timeout, interval
    )
    by_date: dict[date, list[ArticleSource]] = defaultdict(list)
    for (race_date, _venue), source in sources.items():
        by_date[race_date].append(source)

    errors = list(discovery_errors)
    day_reports: list[dict[str, Any]] = []
    base_rows: list[list[Any]] = []
    ledger_rows: list[list[Any]] = []

    for race_date in sorted(by_date):
        day_sources = sorted(
            by_date[race_date], key=lambda source: VENUE_RANK[source.venue]
        )
        venues = [source.venue for source in day_sources]
        results = []
        source_by_venue = {source.venue: source for source in day_sources}
        debug_by_venue: dict[str, dict[str, Any]] = {}

        for source in day_sources:
            html = ""
            try:
                if source.embedded_html is None:
                    html = fetch_article_html(session, source.url, timeout, interval)
                debug_by_venue[source.venue] = {
                    "source_url": source.url,
                    "source_method": source.source_method,
                    "article_title": source.title,
                    "lines": source_debug_lines(source, html),
                }
                results.append(parse_source(source, html, race_date))
            except Exception as exc:
                errors.append(f"{race_date} {source.venue}: {exc}")
                if source.venue not in debug_by_venue:
                    try:
                        debug_by_venue[source.venue] = {
                            "source_url": source.url,
                            "source_method": source.source_method,
                            "article_title": source.title,
                            "lines": source_debug_lines(source, html),
                        }
                    except Exception as debug_exc:
                        debug_by_venue[source.venue] = {
                            "source_url": source.url,
                            "source_method": source.source_method,
                            "article_title": source.title,
                            "debug_error": str(debug_exc),
                        }

        if len(results) != len(day_sources):
            day_reports.append(
                {
                    "date": race_date.isoformat(),
                    "venues": venues,
                    "validation_status": "failure",
                    "errors": ["one or more articles failed before validation"],
                    "debug_articles": debug_by_venue,
                }
            )
            continue

        validation = build_validation(race_date, venues, results)
        day_reports.append(
            {
                "date": race_date.isoformat(),
                "venues": venues,
                "validation_status": validation["validation_status"],
                "venue_reports": validation["venue_reports"],
                "errors": validation["errors"],
                **(
                    {"debug_articles": debug_by_venue}
                    if validation["validation_status"] != "success"
                    else {}
                ),
            }
        )
        if validation["validation_status"] != "success":
            errors.extend(f"{race_date}: {message}" for message in validation["errors"])
            continue

        payload = build_result(race_date, venues, results)
        result_by_venue = {result.venue: result for result in results}
        for entry in payload["entries"]:
            venue = str(entry["場所"])
            race = str(entry["R"])
            horse = str(entry["馬名"] or "")
            comment = normalize_text(str(entry["コメント"] or ""))
            source = source_by_venue[venue]
            article_title = result_by_venue[venue].article_title
            base_rows.append([race_date.isoformat(), venue, race, horse, comment])
            ledger_rows.append(
                [
                    race_date.isoformat(),
                    venue,
                    race,
                    horse,
                    "",
                    comment,
                    1 if horse == "🤡" else 0,
                    source.url,
                    source.source_method,
                    article_title,
                    month_start.strftime("%Y-%m"),
                ]
            )

    keys = [(row[0], row[1], row[2]) for row in base_rows]
    if len(keys) != len(set(keys)):
        errors.append("duplicate canonical key detected: date + venue + R")

    month_status = "success" if not errors else "failure"
    outputs: dict[str, Any] = {}
    compact_month = month_start.strftime("%Y%m")

    if month_status == "success":
        base_path = output_dir / f"keibailuka_month_{compact_month}.csv"
        ledger_path = output_dir / f"keibailuka_month_{compact_month}_ledger.csv"
        write_csv(base_path, ["日付", "会場", "R", "馬名", "コメント"], base_rows)
        write_csv(
            ledger_path,
            [
                "日付",
                "会場",
                "R",
                "馬名_raw",
                "馬名_resolved",
                "コメント",
                "masked_flag",
                "source_url",
                "source_method",
                "article_title",
                "source_month",
            ],
            ledger_rows,
        )
        outputs = {
            "canonical_csv": base_path.name,
            "canonical_csv_sha256": sha256_file(base_path),
            "ledger_csv": ledger_path.name,
            "ledger_csv_sha256": sha256_file(ledger_path),
        }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "validation_status": month_status,
        "month": month_start.strftime("%Y-%m"),
        "source_commit": os.environ.get("GITHUB_SHA", ""),
        "scanned_feed_entries": scanned_entries,
        "article_count": len(sources),
        "day_count": len(by_date),
        "row_count": len(base_rows),
        "masked_count": sum(1 for row in base_rows if row[3] == "🤡"),
        "day_reports": day_reports,
        "errors": errors,
        "outputs": outputs,
    }
    (output_dir / "month_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        validate_runtime(args.interval, args.timeout)
        start_month = parse_month(args.start_month)
        end_month = parse_month(args.end_month or args.start_month)
        months = iter_months(start_month, end_month)
        session = build_session()

        month_manifests = []
        for month_start in months:
            month_manifests.append(
                process_month(
                    session,
                    month_start,
                    output_root / month_start.strftime("%Y%m"),
                    args.timeout,
                    args.interval,
                )
            )

        successful = [m for m in month_manifests if m["validation_status"] == "success"]
        failed = [m for m in month_manifests if m["validation_status"] != "success"]
        batch_status = "success" if not failed else "failure"
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "validation_status": batch_status,
            "start_month": start_month.strftime("%Y-%m"),
            "end_month": end_month.strftime("%Y-%m"),
            "month_count": len(months),
            "successful_months": [m["month"] for m in successful],
            "failed_months": [m["month"] for m in failed],
            "totals": {
                "article_count": sum(m["article_count"] for m in successful),
                "day_count": sum(m["day_count"] for m in successful),
                "row_count": sum(m["row_count"] for m in successful),
                "masked_count": sum(m["masked_count"] for m in successful),
            },
            "months": month_manifests,
        }
        (output_root / "historical_batch_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0 if batch_status == "success" else 2
    except Exception as exc:
        (output_root / "historical_batch_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "validation_status": "failure",
                    "errors": [str(exc)],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())

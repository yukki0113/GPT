"""Low-rate KEIRIN.JP monthly historical raw collection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import html
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import urlopen

from .raw import SourceItem, acquire_source_list, fetch_source, write_immutable

SCHEDULE_URL = "https://keirin.jp/pc/raceschedule?scym={month:02d}&scyy={year:04d}"
RACELIST_URL = "https://keirin.jp/pc/racelist"
POLICY_STATUS = "personal_research_approved"


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def discover_events(schedule_html: str, *, year: int, month: int) -> list[SourceItem]:
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", schedule_html, re.I | re.S)
    sources: list[SourceItem] = []
    seen: set[str] = set()

    for row in rows:
        venue = re.search(
            r'href=["\']/pc/jyosellinfo\?jocd=(\d+)["\'][^>]*>(.*?)</a>',
            row,
            re.I | re.S,
        )
        if not venue:
            continue
        venue_code = venue.group(1)
        venue_name = _clean_text(venue.group(2))

        event_pattern = re.compile(
            r'<td\b[^>]*class=["\'][^"\']*bk_kaisai[^"\']*["\'][^>]*>(.*?)</td>',
            re.I | re.S,
        )
        event_ordinal = 0
        for cell_match in event_pattern.finditer(row):
            cell = cell_match.group(1)
            anchor = re.search(
                r'data-pprm-href=["\']/pc/racelist["\'][^>]*'
                r'data-pprm-encp=["\']([^"\']+)["\'][^>]*'
                r'data-pprm-dkbn=["\'](\d+)["\']',
                cell,
                re.I | re.S,
            )
            if not anchor:
                continue
            encp, dkbn = anchor.group(1), anchor.group(2)
            if encp in seen:
                continue
            seen.add(encp)
            event_ordinal += 1
            grade_match = re.search(r'/grade/ico_([a-z0-9]+)\.png', cell, re.I)
            grade = grade_match.group(1).upper() if grade_match else None
            duration_match = re.search(r'colspan=["\'](\d+)["\']', cell, re.I)
            duration_days = int(duration_match.group(1)) if duration_match else None
            disp = "PJ0301" if dkbn == "1" else "PJ0302"
            source_id = f"keirinjp_{year:04d}{month:02d}_j{venue_code}_e{event_ordinal:02d}"
            sources.append(
                SourceItem(
                    provider="keirin.jp",
                    source_id=source_id,
                    url=RACELIST_URL,
                    relative_path=f"{year:04d}/{month:02d}/events/{venue_code}_{event_ordinal:02d}.html",
                    policy_status=POLICY_STATUS,
                    request_method="POST",
                    form_data={"encp": encp, "disp": disp},
                    metadata={
                        "venue_code": venue_code,
                        "venue_name": venue_name,
                        "event_ordinal": event_ordinal,
                        "grade": grade,
                        "schedule_colspan_days": duration_days,
                        "referer": SCHEDULE_URL.format(year=year, month=month),
                    },
                )
            )
    return sources


def run_month(
    *,
    year: int,
    month: int,
    output_dir: Path,
    audit_dir: Path,
    delay_seconds: float = 3.0,
    timeout: float = 60.0,
    opener: Callable[..., object] = urlopen,
) -> dict[str, Any]:
    if not 2000 <= year <= 2100:
        raise ValueError("year must be 2000..2100")
    if not 1 <= month <= 12:
        raise ValueError("month must be 1..12")
    if delay_seconds < 2.0:
        raise ValueError("delay_seconds must be >= 2.0 for KEIRIN.JP monthly collection")

    schedule_url = SCHEDULE_URL.format(year=year, month=month)
    schedule_item = SourceItem(
        provider="keirin.jp",
        source_id=f"keirinjp_schedule_{year:04d}{month:02d}",
        url=schedule_url,
        relative_path=f"{year:04d}/{month:02d}/schedule.html",
        policy_status=POLICY_STATUS,
        metadata={"scope": "monthly_schedule"},
    )
    schedule_response = fetch_source(schedule_item, timeout=timeout, opener=opener)
    schedule_target = output_dir / schedule_item.relative_path
    schedule_write = write_immutable(schedule_target, schedule_response.content)
    schedule_text = schedule_response.content.decode("utf-8", errors="replace")
    event_sources = discover_events(schedule_text, year=year, month=month)
    if not event_sources:
        raise RuntimeError("no historical events discovered from monthly schedule")

    audit_dir.mkdir(parents=True, exist_ok=True)
    source_list_path = audit_dir / f"{year:04d}{month:02d}_source_list.jsonl"
    source_list_path.write_text(
        "".join(json.dumps({
            "provider": item.provider,
            "source_id": item.source_id,
            "url": item.url,
            "relative_path": item.relative_path,
            "policy_status": item.policy_status,
            "request_method": item.request_method,
            "form_data": item.form_data,
            "metadata": item.metadata,
        }, ensure_ascii=False) + "\n" for item in event_sources),
        encoding="utf-8",
    )

    events_manifest_path = audit_dir / f"{year:04d}{month:02d}_events_manifest.json"
    events_manifest = acquire_source_list(
        event_sources,
        output_dir=output_dir,
        manifest_path=events_manifest_path,
        delay_seconds=delay_seconds,
        timeout=timeout,
        opener=opener,
        continue_on_error=True,
    )

    discovered = len(event_sources)
    succeeded = int(events_manifest["successful_sources"])
    coverage = succeeded / discovered if discovered else 0.0
    summary = {
        "status": "success" if events_manifest["failed_sources"] == 0 else "partial_failure",
        "provider": "keirin.jp",
        "policy_status": POLICY_STATUS,
        "year": year,
        "month": month,
        "schedule_url": schedule_url,
        "schedule_http_status": schedule_response.status_code,
        "schedule_write_status": schedule_write,
        "schedule_size_bytes": len(schedule_response.content),
        "schedule_sha256": sha256(schedule_response.content).hexdigest(),
        "discovered_events": discovered,
        "successful_events": succeeded,
        "failed_events": int(events_manifest["failed_sources"]),
        "coverage": coverage,
        "delay_seconds": delay_seconds,
        "total_event_bytes": int(events_manifest["total_bytes"]),
        "source_list_path": str(source_list_path),
        "events_manifest_path": str(events_manifest_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = audit_dir / f"{year:04d}{month:02d}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect one month of KEIRIN.JP historical raw meet pages")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_month(
        year=args.year,
        month=args.month,
        output_dir=args.output_dir,
        audit_dir=args.audit_dir,
        delay_seconds=args.delay_seconds,
        timeout=args.timeout,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed_events"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

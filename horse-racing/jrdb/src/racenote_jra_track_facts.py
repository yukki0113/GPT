#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acquire independent pre-result weather and track condition from JRA.

The JRA track-information pages are venue-positioned rather than permanently
bound to one venue URL.  This module therefore checks page content for the
requested venue and fails closed when the publication date cannot be matched
to the requested target date.

Only weather and the requested surface's track condition are returned.  Odds,
results, popularity, and current JRDB consensus are outside this module.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from racenote_race_day_facts import validate_race_day_facts


DEFAULT_BASE_URL = "https://www.jra.go.jp/keiba/baba"
SOURCE_KIND = "JRA_OFFICIAL_BABA"
TRACK_STATES = {"良", "稍重", "重", "不良"}
JST = timezone(timedelta(hours=9))


class JraTrackFactsError(RuntimeError):
    """Raised when JRA pre-result track facts cannot be proven safely."""


class _VisibleTextParser(HTMLParser):
    """Collect visible-ish HTML text in source order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if (
            tag.lower() in {"script", "style", "noscript"}
            and self._hidden_depth > 0
        ):
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth > 0:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def _surface_label(surface: str) -> str:
    """Normalize a RaceNote surface label to JRA's page label."""
    value = surface.strip()
    if value.startswith("芝"):
        return "芝"
    if value.startswith("ダート") or value.startswith("ダ"):
        return "ダート"
    raise JraTrackFactsError(
        f"unsupported surface for JRA track facts: {surface!r}"
    )


def _visible_text(html: str) -> list[str]:
    """Return normalized text nodes in document order."""
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return parser.parts


def _status_as_of(
    status_heading: str,
    target_date: date,
) -> str:
    """Convert JRA's Japanese status heading to an ISO JST timestamp."""
    match = re.search(
        r"馬場状態（"
        r"(?P<month>\d{1,2})月"
        r"(?P<day>\d{1,2})日"
        r".*?"
        r"(?P<time>正午|\d{1,2}時(?:\d{1,2}分)?)"
        r"現在）",
        status_heading,
    )
    if match is None:
        raise JraTrackFactsError(
            "JRA track status timestamp could not be parsed"
        )

    month = int(match.group("month"))
    day = int(match.group("day"))
    time_text = match.group("time")

    hour = 12
    minute = 0
    if time_text != "正午":
        time_match = re.fullmatch(
            r"(?P<hour>\d{1,2})時(?:(?P<minute>\d{1,2})分)?",
            time_text,
        )
        if time_match is None:
            raise JraTrackFactsError(
                "JRA track status time could not be parsed"
            )
        hour = int(time_match.group("hour"))
        minute_text = time_match.group("minute")
        if minute_text is not None:
            minute = int(minute_text)

    try:
        published = datetime(
            target_date.year,
            month,
            day,
            hour,
            minute,
            tzinfo=JST,
        )
    except ValueError as exc:
        raise JraTrackFactsError(
            "JRA track status timestamp is invalid"
        ) from exc

    if published.date() != target_date:
        raise JraTrackFactsError(
            "JRA track status is not from the target race date: "
            f"{published.date().isoformat()} != {target_date.isoformat()}"
        )
    return published.isoformat()


def _weather_from_segment(segment: list[str]) -> str:
    """Extract the weather value from one venue status segment."""
    for index, token in enumerate(segment):
        compact = token.replace(" ", "")
        if compact.startswith("天候："):
            value = compact.split("天候：", 1)[1].strip()
            if value:
                return value
            if index + 1 < len(segment):
                next_value = segment[index + 1].strip()
                if next_value:
                    return next_value
    raise JraTrackFactsError(
        "JRA weather value was not found"
    )


def _track_state_from_segment(
    segment: list[str],
    surface: str,
) -> str:
    """Extract one surface's official track state."""
    label = _surface_label(surface)
    for index, token in enumerate(segment):
        if token.strip() != label:
            continue
        for candidate in segment[index + 1:index + 6]:
            value = candidate.strip()
            if value in TRACK_STATES:
                return value
    raise JraTrackFactsError(
        f"JRA track condition for {label} was not found"
    )


def parse_jra_baba_html(
    html: str,
    *,
    source_url: str,
    venue: str,
    surface: str,
    target_date: date,
) -> dict[str, object]:
    """Parse one JRA venue page into validated RaceNote race-day facts."""
    parts = _visible_text(html)
    venue_label = venue.strip() + "競馬場"
    if not any(venue_label in part for part in parts):
        raise JraTrackFactsError(
            f"requested venue not present on page: {venue_label}"
        )

    status_index = -1
    status_heading = ""
    for index, part in enumerate(parts):
        if part.startswith("馬場状態（") and part.endswith("現在）"):
            status_index = index
            status_heading = part
            break
    if status_index < 0:
        raise JraTrackFactsError(
            "JRA track status heading was not found"
        )

    segment_end = min(len(parts), status_index + 60)
    for index in range(status_index + 1, len(parts)):
        if (
            parts[index].startswith("芝のクッション値")
            or parts[index].startswith("含水率")
            or parts[index].startswith("週間情報")
        ):
            segment_end = index
            break

    segment = parts[status_index:segment_end]
    as_of = _status_as_of(
        status_heading,
        target_date,
    )
    weather = _weather_from_segment(segment)
    track_condition = _track_state_from_segment(
        segment,
        surface,
    )

    return validate_race_day_facts(
        {
            "source_kind": SOURCE_KIND,
            "source_url": source_url,
            "as_of": as_of,
            "weather": weather,
            "track_condition": track_condition,
            "result_independent": True,
        }
    )


def _decode_response(
    response: urllib.response.addinfourl,
    body: bytes,
) -> str:
    """Decode JRA HTML using the declared charset with safe fallbacks."""
    charset = response.headers.get_content_charset()
    candidates: list[str] = []
    if charset:
        candidates.append(charset)
    candidates.extend(["utf-8", "cp932"])

    for encoding in candidates:
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    raise JraTrackFactsError(
        "JRA page encoding could not be decoded"
    )


def _fetch_text(url: str, timeout_seconds: int) -> str:
    """Fetch one JRA page with a bounded timeout."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 RaceNote/Gen0.3 "
                "(pre-result track facts audit)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = response.read()
            return _decode_response(response, body)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise JraTrackFactsError(
            f"failed to fetch JRA track page: {url}: {exc}"
        ) from exc


def fetch_jra_race_day_facts(
    *,
    venue: str,
    surface: str,
    target_date: date,
    base_url: str = DEFAULT_BASE_URL,
    page_count: int = 3,
    timeout_seconds: int = 20,
) -> dict[str, object]:
    """Find the requested venue across JRA's active track-information pages."""
    if page_count < 1 or page_count > 6:
        raise JraTrackFactsError(
            "page_count must be within 1..6"
        )

    failures: list[str] = []
    normalized_base = base_url.rstrip("/")
    for page_number in range(1, page_count + 1):
        filename = "index.html"
        if page_number > 1:
            filename = f"index{page_number}.html"
        url = normalized_base + "/" + filename

        try:
            html = _fetch_text(
                url,
                timeout_seconds,
            )
        except JraTrackFactsError as exc:
            failures.append(str(exc))
            continue

        venue_label = venue.strip() + "競馬場"
        if venue_label not in html:
            continue

        try:
            return parse_jra_baba_html(
                html,
                source_url=url,
                venue=venue,
                surface=surface,
                target_date=target_date,
            )
        except JraTrackFactsError as exc:
            raise JraTrackFactsError(
                f"JRA venue page found but facts are unusable: {exc}"
            ) from exc

    detail = "; ".join(failures)
    if not detail:
        detail = "requested venue was not found"
    raise JraTrackFactsError(
        "no usable JRA track-information page: " + detail
    )


def main() -> int:
    """Fetch JRA pre-result track facts and write RaceNote contract JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue", required=True)
    parser.add_argument("--surface", required=True)
    parser.add_argument("--target-date", required=True)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
    )
    parser.add_argument(
        "--page-count",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(
            args.target_date
        )
    except ValueError as exc:
        raise JraTrackFactsError(
            "target-date must be YYYY-MM-DD"
        ) from exc

    facts = fetch_jra_race_day_facts(
        venue=args.venue,
        surface=args.surface,
        target_date=target_date,
        base_url=args.base_url,
        page_count=args.page_count,
        timeout_seconds=args.timeout_seconds,
    )
    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            facts,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                **facts,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

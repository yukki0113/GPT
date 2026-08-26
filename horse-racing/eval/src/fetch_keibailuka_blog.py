#!/usr/bin/env python3
"""Fetch and parse keibailuka Blogger race-pick articles.

Recurring use case:
    date + venue order -> discover article URLs -> parse 1R..12R ->
    omit no-pick/paid sections -> preserve masked picks as 🤡 -> JSON/TSV.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://keibailuka.blogspot.com/"
ARTICLE_PHRASE = "全レース中の強き不利馬達"
VALID_VENUES = {
    "札幌", "函館", "福島", "新潟", "東京",
    "中山", "中京", "京都", "阪神", "小倉",
}
RACE_HEADER_RE = re.compile(
    r"^(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)"
    r"\s*(1[0-2]|[1-9])R(?:\s+(.*))?$"
)
NOTE_CTA_RE = re.compile(
    r"[（(]\s*noteにスキボタン.*?馬名を表示.*?[）)]",
    flags=re.IGNORECASE,
)
FOOTER_MARKERS = (
    "コメントを投稿",
    "重賞予想or平場予想",
    "ラベル",
    "前の投稿",
    "次の投稿",
    "ホーム",
)


@dataclass
class RacePick:
    """Parsed state for one race section."""

    venue: str
    race_no: int
    horse: str | None
    comment: str
    status: str
    exclusion_reason: str | None


@dataclass
class VenueResult:
    """Parsed result for one venue article."""

    venue: str
    source_url: str
    article_title: str
    races: list[RacePick]


class FetchError(RuntimeError):
    """Raised when a blog resource cannot be fetched safely."""


class ParseError(RuntimeError):
    """Raised when an article structure is ambiguous."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Fetch and parse keibailuka Blogger articles."
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--venues", required=True, nargs="+", help="Display order")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--interval", type=float, default=0.8)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def normalize_text(value: str) -> str:
    """Normalize visible text without changing its meaning."""

    value = value.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", value).strip()


def validate_request(
    date_text: str,
    venues: list[str],
    interval: float,
    timeout: float,
) -> date:
    """Validate input values and return the parsed target date."""

    try:
        target_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("--date must be YYYY-MM-DD") from exc

    if not venues:
        raise ValueError("--venues must contain at least one venue")
    if len(set(venues)) != len(venues):
        raise ValueError("--venues must not contain duplicates")

    unknown = [venue for venue in venues if venue not in VALID_VENUES]
    if unknown:
        raise ValueError("Unsupported venue(s): " + ", ".join(unknown))
    if interval < 0:
        raise ValueError("--interval must be >= 0")
    if timeout <= 0:
        raise ValueError("--timeout must be > 0")

    return target_date


def build_session() -> requests.Session:
    """Build a browser-like HTTP session."""

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
            "Cache-Control": "no-cache",
        }
    )
    return session


def fetch_response(
    session: requests.Session,
    url: str,
    timeout: float,
    interval: float,
    attempts: int = 4,
) -> requests.Response:
    """Fetch one URL with retry/backoff for 429 and transient 5xx."""

    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        if interval > 0:
            time.sleep(interval)

        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(8.0, 1.5 ** attempt))
                continue
            break

        if response.status_code == 200:
            return response

        if response.status_code in {429, 500, 502, 503, 504}:
            last_error = FetchError(f"HTTP {response.status_code} from {url}")
            wait_seconds = min(8.0, 1.5 ** attempt)
            retry_after = response.headers.get("Retry-After", "").strip()
            if retry_after.isdigit():
                wait_seconds = min(10.0, float(retry_after))
            if attempt < attempts:
                time.sleep(wait_seconds)
                continue
            break

        raise FetchError(f"HTTP {response.status_code} from {url}")

    raise FetchError(f"Unable to fetch {url}: {last_error}")


def title_matches(title: str, target_date: date, venue: str) -> bool:
    """Check date, venue and fixed article-title phrase."""

    compact = re.sub(r"\s+", "", title)
    date_token = f"{target_date.year}/{target_date.month}/{target_date.day}"
    return (
        date_token in compact
        and venue in compact
        and ARTICLE_PHRASE in compact
    )


def canonicalize_article_url(url: str) -> str:
    """Drop query/fragment from a Blogger article URL."""

    absolute = urljoin(BASE_URL, url)
    parsed = urlsplit(absolute)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def discover_from_feed(
    session: requests.Session,
    target_date: date,
    venues: list[str],
    timeout: float,
    interval: float,
) -> dict[str, str]:
    """Try Blogger's public JSON feed first."""

    discovered: dict[str, str] = {}
    url = urljoin(BASE_URL, "feeds/posts/default?alt=json&max-results=100")

    try:
        payload = fetch_response(session, url, timeout, interval).json()
    except (FetchError, ValueError, requests.RequestException):
        return discovered

    entries = payload.get("feed", {}).get("entry", [])
    if not isinstance(entries, list):
        return discovered

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        title_node = entry.get("title", {})
        title = ""
        if isinstance(title_node, dict):
            title = str(title_node.get("$t", ""))

        alternate_url = ""
        links = entry.get("link", [])
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict) and link.get("rel") == "alternate":
                    alternate_url = str(link.get("href", ""))
                    break

        if not alternate_url:
            continue

        for venue in venues:
            if venue not in discovered and title_matches(title, target_date, venue):
                discovered[venue] = canonicalize_article_url(alternate_url)

    return discovered


def discovery_pages(target_date: date, venues: list[str]) -> list[str]:
    """Return root/archive/search pages used when feed lookup is insufficient."""

    first_of_month = target_date.replace(day=1)
    previous_month = (first_of_month - timedelta(days=1)).replace(day=1)
    pages = [
        BASE_URL,
        urljoin(BASE_URL, f"{first_of_month.year:04d}/{first_of_month.month:02d}/"),
        urljoin(BASE_URL, f"{previous_month.year:04d}/{previous_month.month:02d}/"),
    ]

    date_token = f"{target_date.year}/{target_date.month}/{target_date.day}"
    for venue in venues:
        query_text = f"{date_token} {venue} {ARTICLE_PHRASE}"
        pages.append(urljoin(BASE_URL, "search?q=" + quote(query_text)))

    return list(dict.fromkeys(pages))


def discover_article_urls(
    session: requests.Session,
    target_date: date,
    venues: list[str],
    timeout: float,
    interval: float,
) -> dict[str, str]:
    """Discover one article URL per requested venue without search-engine indexing."""

    discovered = discover_from_feed(
        session, target_date, venues, timeout, interval
    )

    for page_url in discovery_pages(target_date, venues):
        if len(discovered) == len(venues):
            break

        try:
            response = fetch_response(session, page_url, timeout, interval)
        except FetchError:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            title = normalize_text(anchor.get_text(" ", strip=True))
            if not title:
                title = normalize_text(str(anchor.get("title", "")))

            for venue in venues:
                if venue in discovered:
                    continue
                if title_matches(title, target_date, venue):
                    discovered[venue] = canonicalize_article_url(
                        str(anchor.get("href", ""))
                    )

    missing = [venue for venue in venues if venue not in discovered]
    if missing:
        raise FetchError(
            "Article URL discovery failed for venue(s): " + ", ".join(missing)
        )

    return discovered


def fetch_article_html(
    session: requests.Session,
    article_url: str,
    timeout: float,
    interval: float,
) -> str:
    """Fetch canonical article first, then mobile view as fallback."""

    canonical = canonicalize_article_url(article_url)
    errors: list[str] = []

    for candidate in (canonical, canonical + "?m=1"):
        try:
            return fetch_response(session, candidate, timeout, interval).text
        except FetchError as exc:
            errors.append(str(exc))

    raise FetchError("; ".join(errors))


def select_article_body(soup: BeautifulSoup) -> Any:
    """Select a Blogger post-body container."""

    for selector in (
        "div.post-body.entry-content",
        "div.post-body",
        "article .post-body",
        "article",
    ):
        body = soup.select_one(selector)
        if body is not None:
            return body

    raise ParseError("Article body container was not found")


def extract_article_title(soup: BeautifulSoup) -> str:
    """Extract the visible article title."""

    for selector in (
        "h3.post-title",
        "h2.post-title",
        "h1.post-title",
        "article h1",
        "article h2",
    ):
        element = soup.select_one(selector)
        if element is not None:
            title = normalize_text(element.get_text(" ", strip=True))
            if title:
                return title

    title_element = soup.find("title")
    if title_element is not None:
        return normalize_text(title_element.get_text(" ", strip=True))
    return ""


def body_lines(body: Any) -> list[str]:
    """Convert post-body visible strings into normalized lines."""

    lines: list[str] = []
    for value in body.stripped_strings:
        for raw_line in str(value).splitlines():
            line = normalize_text(raw_line)
            if line:
                lines.append(line)
    return lines


def trim_footer(lines: list[str]) -> list[str]:
    """Stop at Blogger footer/navigation text after 12R."""

    trimmed: list[str] = []
    for line in lines:
        if any(marker in line for marker in FOOTER_MARKERS):
            break
        trimmed.append(line)
    return trimmed


def clean_comment(lines: list[str]) -> str:
    """Remove URLs/CTA while leaving the author's meaning unchanged."""

    parts: list[str] = []
    for line in lines:
        if line.startswith("http://") or line.startswith("https://"):
            continue
        if "勝負レース" in line:
            continue

        cleaned = NOTE_CTA_RE.sub("", line)
        cleaned = normalize_text(cleaned)
        if cleaned:
            parts.append(cleaned)

    return normalize_text(" ".join(parts))


def classify_race(
    venue: str,
    race_no: int,
    horse_tail: str,
    section_lines: list[str],
) -> RacePick:
    """Classify one race section according to the recurring Chat rules."""

    section_lines = trim_footer(section_lines)
    combined = " ".join([horse_tail, *section_lines])

    if "該当無し" in combined:
        return RacePick(venue, race_no, None, "", "excluded", "no_selection")

    paid_url = any(
        "note.com/keibailuka/n/" in line for line in section_lines
    )
    if "勝負レース" in combined or paid_url:
        return RacePick(venue, race_no, None, "", "excluded", "paid_lead")

    if "🤡" in combined:
        return RacePick(
            venue,
            race_no,
            "🤡",
            clean_comment(section_lines),
            "included",
            None,
        )

    horse = normalize_text(horse_tail.replace("🐬", ""))
    if not horse:
        return RacePick(
            venue,
            race_no,
            None,
            clean_comment(section_lines),
            "parse_error",
            "horse_name_missing",
        )

    return RacePick(
        venue,
        race_no,
        horse,
        clean_comment(section_lines),
        "included",
        None,
    )


def parse_article(
    html: str,
    venue: str,
    source_url: str,
    target_date: date,
) -> VenueResult:
    """Parse exactly 12 race sections from one venue article."""

    soup = BeautifulSoup(html, "html.parser")
    title = extract_article_title(soup)
    if title and not title_matches(title, target_date, venue):
        raise ParseError(f"Article title does not match request: {title}")

    lines = body_lines(select_article_body(soup))
    headers: list[tuple[int, int, str]] = []

    for index, line in enumerate(lines):
        match = RACE_HEADER_RE.fullmatch(line)
        if match is None or match.group(1) != venue:
            continue
        headers.append(
            (index, int(match.group(2)), normalize_text(match.group(3) or ""))
        )

    race_numbers = [item[1] for item in headers]
    if race_numbers != list(range(1, 13)):
        raise ParseError(
            f"Expected race headers 1..12 for {venue}, got {race_numbers}"
        )

    races: list[RacePick] = []
    for header_index, header in enumerate(headers):
        line_index, race_no, horse_tail = header
        next_index = len(lines)
        if header_index + 1 < len(headers):
            next_index = headers[header_index + 1][0]

        races.append(
            classify_race(
                venue,
                race_no,
                horse_tail,
                lines[line_index + 1:next_index],
            )
        )

    return VenueResult(
        venue=venue,
        source_url=canonicalize_article_url(source_url),
        article_title=title,
        races=races,
    )


def build_validation(
    target_date: date,
    venues: list[str],
    results: list[VenueResult],
) -> dict[str, Any]:
    """Validate 1..12 structure and reject ambiguous parse results."""

    errors: list[str] = []
    venue_reports: list[dict[str, Any]] = []
    by_venue = {result.venue: result for result in results}

    for venue in venues:
        result = by_venue.get(venue)
        if result is None:
            errors.append(f"{venue}: result missing")
            continue

        parse_errors = [
            race.race_no for race in result.races if race.status == "parse_error"
        ]
        included = sum(1 for race in result.races if race.status == "included")
        excluded = sum(1 for race in result.races if race.status == "excluded")

        if parse_errors:
            errors.append(
                f"{venue}: parse error in race(s) "
                + ", ".join(str(value) for value in parse_errors)
            )
        if included + excluded != 12:
            errors.append(f"{venue}: included + excluded does not equal 12")

        venue_reports.append(
            {
                "venue": venue,
                "source_url": result.source_url,
                "included_count": included,
                "excluded_count": excluded,
                "parse_error_races": parse_errors,
            }
        )

    status = "success"
    if errors:
        status = "failure"

    return {
        "validation_status": status,
        "date": target_date.isoformat(),
        "venues": venues,
        "venue_reports": venue_reports,
        "errors": errors,
    }


def build_result(
    target_date: date,
    venues: list[str],
    results: list[VenueResult],
) -> dict[str, Any]:
    """Build full JSON payload and included entries in requested order."""

    entries: list[dict[str, Any]] = []
    source_urls: dict[str, str] = {}

    for venue in venues:
        result = next(item for item in results if item.venue == venue)
        source_urls[venue] = result.source_url
        for race in result.races:
            if race.status == "included":
                entries.append(
                    {
                        "場所": venue,
                        "R": f"{race.race_no}R",
                        "馬名": race.horse,
                        "コメント": race.comment,
                    }
                )

    return {
        "date": target_date.isoformat(),
        "venues": venues,
        "source_urls": source_urls,
        "entries": entries,
        "articles": [
            {
                "venue": result.venue,
                "source_url": result.source_url,
                "article_title": result.article_title,
                "races": [asdict(race) for race in result.races],
            }
            for result in results
        ],
    }


def write_outputs(
    output_dir: Path,
    target_date: date,
    payload: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    """Write JSON, TSV and validation files."""

    compact = target_date.strftime("%Y%m%d")
    (output_dir / f"keibailuka_{compact}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["場所\tR\t馬名\tコメント"]
    for entry in payload["entries"]:
        lines.append(
            "\t".join(
                [
                    str(entry["場所"]),
                    str(entry["R"]),
                    str(entry["馬名"] or ""),
                    normalize_text(str(entry["コメント"])),
                ]
            )
        )
    (output_dir / f"keibailuka_{compact}.tsv").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_failure(
    output_dir: Path,
    target_date: date | None,
    venues: list[str],
    error: Exception,
) -> None:
    """Persist an actionable failure report instead of returning partial data."""

    report = {
        "validation_status": "failure",
        "date": target_date.isoformat() if target_date is not None else None,
        "venues": venues,
        "venue_reports": [],
        "errors": [str(error)],
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "error.txt").write_text(str(error) + "\n", encoding="utf-8")


def main() -> int:
    """CLI entry point."""

    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    venues = [normalize_text(value) for value in args.venues]
    target_date: date | None = None

    try:
        target_date = validate_request(
            args.date,
            venues,
            args.interval,
            args.timeout,
        )
        session = build_session()
        urls = discover_article_urls(
            session,
            target_date,
            venues,
            args.timeout,
            args.interval,
        )

        results: list[VenueResult] = []
        for venue in venues:
            html = fetch_article_html(
                session,
                urls[venue],
                args.timeout,
                args.interval,
            )
            results.append(
                parse_article(html, venue, urls[venue], target_date)
            )

        validation = build_validation(target_date, venues, results)
        payload = build_result(target_date, venues, results)
        write_outputs(output_dir, target_date, payload, validation)

        if validation["validation_status"] != "success":
            return 2
        return 0

    except Exception as exc:
        write_failure(output_dir, target_date, venues, exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())

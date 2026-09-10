"""Small standard-library HTTP client for NAR monthly downloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

RACE_ENDPOINT = "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload"
ODDS_ENDPOINT = "https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload"
USER_AGENT = "Mozilla/5.0 (compatible; local-horse-racing-data-downloader/0.1)"


class NarDownloadError(RuntimeError):
    """NAR download failed before ZIP validation."""


@dataclass(frozen=True)
class HttpResponse:
    content: bytes
    status_code: int
    content_type: str
    content_disposition: str
    final_url: str


def monthly_url(kind: str, year: int, month: int) -> str:
    """Build one official monthly download URL."""
    if kind not in {"race", "odds"}:
        raise ValueError("kind must be 'race' or 'odds'")
    if year < 1998 or year > 2100:
        raise ValueError("year is outside the supported guard range 1998..2100")
    if month < 1 or month > 12:
        raise ValueError("month must be 1..12")

    endpoint = RACE_ENDPOINT if kind == "race" else ODDS_ENDPOINT
    query = urlencode({"type": "monthly", "k_year": year, "k_month": month})
    return f"{endpoint}?{query}"


def fetch_monthly(
    kind: str,
    year: int,
    month: int,
    *,
    timeout: float = 60.0,
    opener: Callable[..., object] = urlopen,
) -> HttpResponse:
    """Fetch a NAR monthly ZIP without transforming its bytes."""
    url = monthly_url(kind, year, month)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/zip,*/*;q=0.8"})

    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            content = response.read()
            headers = response.headers
            final_url = response.geturl()
    except Exception as exc:  # urllib raises several transport-specific subclasses
        raise NarDownloadError(f"NAR monthly download failed: {exc}") from exc

    if status != 200:
        raise NarDownloadError(f"NAR returned HTTP {status}")
    if not content:
        raise NarDownloadError("NAR returned an empty response")

    return HttpResponse(
        content=content,
        status_code=status,
        content_type=headers.get("Content-Type", ""),
        content_disposition=headers.get("Content-Disposition", ""),
        final_url=final_url,
    )

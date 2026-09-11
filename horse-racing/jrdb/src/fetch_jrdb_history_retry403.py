#!/usr/bin/env python3
"""JRDB history fetcher entrypoint with transient HTTP 403 retry enabled.

JRDB/Google Frontend was observed returning isolated HTTP 403 responses for daily
paths that later consistently resolved to HTTP 404. 403 is therefore treated only
as retryable transport noise here. It is never reclassified as NOT_FOUND directly:
- 403 -> retry -> 404: ordinary NOT_FOUND
- 403 -> retry -> 200: ordinary download
- persistent 403 through retry budget: hard FetchError

This wrapper keeps the canonical fetcher semantics unchanged apart from adding 403
to its retryable HTTP-code set.
"""
from __future__ import annotations

import fetch_jrdb_history as fetcher


def main() -> int:
    """Run the canonical fetcher with HTTP 403 included in transient retries."""
    fetcher.RETRYABLE_HTTP_CODES.add(403)
    return fetcher.main()


if __name__ == "__main__":
    raise SystemExit(main())

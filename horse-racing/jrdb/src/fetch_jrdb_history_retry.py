#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run fetch_jrdb_history with outer retries for transient network failures.

The canonical fetcher already retries retryable HTTP status codes. This wrapper
adds the same exponential-backoff behavior for transport-level failures such as
URLError, socket timeouts, and connection resets without changing the public
CLI contract.
"""
from __future__ import annotations

import sys
import time
import urllib.error
from pathlib import Path

import fetch_jrdb_history as base


ORIGINAL_DOWNLOAD = base.download


def retrying_download(
    url: str,
    dest: Path,
    kind: str,
    auth: str,
    timeout: float,
    max_retries: int,
    retry_backoff_seconds: float,
) -> tuple[str, dict]:
    """Retry transport failures while preserving the canonical downloader."""
    for attempt in range(max_retries + 1):
        try:
            return ORIGINAL_DOWNLOAD(
                url,
                dest,
                kind,
                auth,
                timeout,
                max_retries,
                retry_backoff_seconds,
            )
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as error:
            if attempt >= max_retries:
                raise
            retry_number = attempt + 1
            wait_seconds = min(
                retry_backoff_seconds * (2 ** max(0, retry_number - 1)),
                base.MAX_RETRY_WAIT_SECONDS,
            )
            print(
                f"[WAIT] Network error: retry {retry_number}/{max_retries} "
                f"in {wait_seconds:.1f}s: {url} ({error})",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)

    raise base.FetchError(f"Download did not complete after network retries: {url}")


def main() -> int:
    """Run the canonical fetcher with transport retry enabled."""
    base.download = retrying_download
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import io
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetch_jrdb_history as fetcher  # noqa: E402


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.status = 200
        self.headers = {
            "Content-Type": "application/x-zip-compressed",
            "Content-Length": str(len(payload)),
        }
        self._buffer = io.BytesIO(payload)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


def http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, f"HTTP {code}", {}, io.BytesIO(b""))


def valid_zip(kind: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{kind}260221.txt", b"fixture")
    return buffer.getvalue()


class Retry403Test(unittest.TestCase):
    def retryable_codes(self) -> set[int]:
        return set(fetcher.RETRYABLE_HTTP_CODES) | {403}

    def test_transient_403_then_404_becomes_not_found(self) -> None:
        url = "https://example.invalid/Bac/2026/BAC260220.zip"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "BAC260220.zip"
            with (
                patch.object(fetcher, "RETRYABLE_HTTP_CODES", self.retryable_codes()),
                patch.object(
                    fetcher.urllib.request,
                    "urlopen",
                    side_effect=[http_error(url, 403), http_error(url, 404)],
                ) as mocked_open,
                patch.object(fetcher.time, "sleep") as mocked_sleep,
            ):
                status, meta = fetcher.download(
                    url=url,
                    dest=destination,
                    kind="BAC",
                    auth="Basic fixture",
                    timeout=1.0,
                    max_retries=2,
                    retry_backoff_seconds=0.0,
                )

            self.assertEqual(status, "NOT_FOUND")
            self.assertEqual(meta["http_status"], 404)
            self.assertEqual(mocked_open.call_count, 2)
            self.assertEqual(mocked_sleep.call_count, 1)
            self.assertFalse(destination.exists())

    def test_transient_403_then_200_downloads_normally(self) -> None:
        url = "https://example.invalid/Bac/2026/BAC260221.zip"
        payload = valid_zip("BAC")
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "BAC260221.zip"
            with (
                patch.object(fetcher, "RETRYABLE_HTTP_CODES", self.retryable_codes()),
                patch.object(
                    fetcher.urllib.request,
                    "urlopen",
                    side_effect=[http_error(url, 403), FakeResponse(payload)],
                ) as mocked_open,
                patch.object(fetcher.time, "sleep") as mocked_sleep,
            ):
                status, meta = fetcher.download(
                    url=url,
                    dest=destination,
                    kind="BAC",
                    auth="Basic fixture",
                    timeout=1.0,
                    max_retries=2,
                    retry_backoff_seconds=0.0,
                )

            self.assertEqual(status, "DOWNLOADED")
            self.assertEqual(meta["http_status"], 200)
            self.assertEqual(mocked_open.call_count, 2)
            self.assertEqual(mocked_sleep.call_count, 1)
            self.assertTrue(destination.exists())
            self.assertEqual(destination.read_bytes(), payload)

    def test_persistent_403_remains_hard_failure(self) -> None:
        url = "https://example.invalid/Sed/2026/SED260219.zip"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "SED260219.zip"
            with (
                patch.object(fetcher, "RETRYABLE_HTTP_CODES", self.retryable_codes()),
                patch.object(
                    fetcher.urllib.request,
                    "urlopen",
                    side_effect=[
                        http_error(url, 403),
                        http_error(url, 403),
                        http_error(url, 403),
                    ],
                ) as mocked_open,
                patch.object(fetcher.time, "sleep") as mocked_sleep,
            ):
                with self.assertRaisesRegex(fetcher.FetchError, "HTTP 403"):
                    fetcher.download(
                        url=url,
                        dest=destination,
                        kind="SED",
                        auth="Basic fixture",
                        timeout=1.0,
                        max_retries=2,
                        retry_backoff_seconds=0.0,
                    )

            self.assertEqual(mocked_open.call_count, 3)
            self.assertEqual(mocked_sleep.call_count, 2)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()

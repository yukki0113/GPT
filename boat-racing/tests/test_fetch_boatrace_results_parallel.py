import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_boatrace_results import (
    InputError,
    RequestStartLimiter,
    TimingStats,
    fetch_official,
    validate_args,
)


class FakeResponse:
    def __init__(self, url):
        self.status = 200
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.content = b"<html><body>ok</body></html>"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _limit):
        return self.content


class FetchBoatRaceResultsParallelTest(unittest.TestCase):
    def test_request_start_limiter_is_shared_across_workers(self):
        limiter = RequestStartLimiter(0.03)

        def start_request(_):
            limiter.wait_until_ready()
            return time.monotonic()

        with ThreadPoolExecutor(max_workers=3) as executor:
            starts = list(executor.map(start_request, range(4)))

        ordered = sorted(starts)
        gaps = [right - left for left, right in zip(ordered, ordered[1:])]
        self.assertTrue(all(gap >= 0.025 for gap in gaps), gaps)

    def test_fetch_can_skip_ephemeral_cache_writes(self):
        url = "https://www.boatrace.jp/owpc/pc/race/raceresult?rno=1&jcd=04&hd=20260917"
        limiter = RequestStartLimiter(0)
        timing = TimingStats()

        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "1R.html"
            meta_path = Path(directory) / "1R.meta.json"
            with patch(
                "fetch_boatrace_results.urlopen",
                return_value=FakeResponse(url),
            ) as mocked_urlopen:
                fetched = fetch_official(
                    url,
                    html_path,
                    meta_path,
                    timeout=20,
                    retry=0,
                    limiter=limiter,
                    timing=timing,
                    cache_write=False,
                )

            self.assertEqual(fetched.http_status, 200)
            self.assertEqual(timing.request_count, 1)
            self.assertFalse(html_path.exists())
            self.assertFalse(meta_path.exists())
            mocked_urlopen.assert_called_once()

    def test_parallel_venues_is_limited_to_three(self):
        base = {
            "timeout": 20.0,
            "retry": 2,
            "interval": 1.0,
            "unit_stake": 100,
            "limit": None,
        }
        for value in (1, 2, 3):
            validate_args(SimpleNamespace(**base, parallel_venues=value))

        with self.assertRaises(InputError):
            validate_args(SimpleNamespace(**base, parallel_venues=4))


if __name__ == "__main__":
    unittest.main()

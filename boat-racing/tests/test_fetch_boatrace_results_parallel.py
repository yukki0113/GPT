import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_boatrace_results import (
    InputError,
    RequestStartLimiter,
    TimingStats,
    build_session,
    fetch_official,
    validate_args,
)


class FakeResponse:
    def __init__(self, url):
        self.status_code = 200
        self.url = url
        self.content = b"<html><body>ok</body></html>"
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout, allow_redirects):
        self.calls.append((url, timeout, allow_redirects, time.monotonic()))
        return FakeResponse(url)


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
        session = FakeSession()
        limiter = RequestStartLimiter(0)
        timing = TimingStats()

        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "1R.html"
            meta_path = Path(directory) / "1R.meta.json"
            fetched = fetch_official(
                session,
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
            self.assertEqual(len(session.calls), 1)

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

    def test_worker_session_has_result_fetch_headers(self):
        session = build_session()
        try:
            self.assertIn("BOATRACEOfficialResultAudit", session.headers["User-Agent"])
            self.assertEqual(session.headers["Accept"], "text/html")
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""出走表取得の会場並列化と全体リクエスト間隔を回帰確認する。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "fetch_boatrace_racelist.py"
SPEC = importlib.util.spec_from_file_location("fetch_boatrace_racelist_parallel_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("fetch_boatrace_racelist.py を読み込めません")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RacelistParallelFetchTest(unittest.TestCase):
    """限定並列化が安全条件と出力順を維持することを確認する。"""

    def test_shared_limiter_keeps_global_start_interval(self) -> None:
        """複数workerが同時に来ても、開始時刻を全体で直列化する。"""
        limiter = MODULE.RequestStartLimiter(0.04)
        barrier = threading.Barrier(3)
        recorded: list[float] = []
        recorded_lock = threading.Lock()

        def call_limiter() -> None:
            barrier.wait()
            limiter.wait_until_ready()
            with recorded_lock:
                recorded.append(time.monotonic())

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(call_limiter) for _ in range(3)]
            for future in futures:
                future.result()

        recorded.sort()
        gaps = [right - left for left, right in zip(recorded, recorded[1:])]
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all(gap >= 0.03 for gap in gaps), gaps)

    def test_collect_venues_uses_three_workers_and_restores_request_order(self) -> None:
        """完了順が前後してもCSV用の結果は入力会場順へ戻す。"""
        venues = [
            {"name": f"会場{index}", "code": f"{index:02d}", "day": "1日目"}
            for index in range(1, 7)
        ]
        state_lock = threading.Lock()
        active_workers = 0
        max_active_workers = 0
        limiter_ids: set[int] = set()

        def fake_collect_venue(
            date: str,
            venue_index: int,
            venue_count: int,
            venue: dict[str, object],
            logger: logging.Logger,
            delay: float,
            limiter: object,
            print_lock: object,
        ) -> object:
            nonlocal active_workers, max_active_workers
            del date, venue_count, logger, delay, print_lock
            with state_lock:
                active_workers += 1
                max_active_workers = max(max_active_workers, active_workers)
                limiter_ids.add(id(limiter))
            # 奇数会場を少し遅くし、futureの完了順を入力順から崩す。
            time.sleep(0.05 if venue_index % 2 else 0.02)
            with state_lock:
                active_workers -= 1
            timing = MODULE.TimingStats(request_count=12)
            return MODULE.VenueFetchResult(
                venue_index=venue_index,
                rows=[{"会場": str(venue["name"])}],
                reports=[{"会場": str(venue["name"])}],
                retry_total=0,
                timing=timing,
            )

        with patch.object(MODULE, "collect_venue", side_effect=fake_collect_venue):
            rows, reports, retries, timing = MODULE.collect_venues(
                "20260918", venues, logging.getLogger("test"), 1.0, 3
            )

        expected_names = [str(venue["name"]) for venue in venues]
        self.assertEqual([row["会場"] for row in rows], expected_names)
        self.assertEqual([report["会場"] for report in reports], expected_names)
        self.assertEqual(retries, 0)
        self.assertEqual(timing.request_count, 72)
        self.assertEqual(max_active_workers, 3)
        self.assertEqual(len(limiter_ids), 1)

    def test_parallel_venues_defaults_to_three_and_is_bounded(self) -> None:
        """設定省略時は3並列、4以上は入力エラーにする。"""
        base = {
            "date": "20260918",
            "venues": [{"name": "多摩川", "code": "05", "day": "3日目"}],
            "request_interval_seconds": 1.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
            args = argparse.Namespace(config=str(config_path), date=None, output=None)
            config = MODULE.load_config(args)
            self.assertEqual(config["parallel_venues"], 3)

            base["parallel_venues"] = 4
            config_path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "parallel_venues"):
                MODULE.load_config(args)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PWA_ROOT = PROJECT_ROOT / "pwa"
MOMOTARO_ROOT = PWA_ROOT / "momotaro"


class MomotaroPwaContractTest(unittest.TestCase):
    def test_member_and_iluka_contract(self) -> None:
        script = (MOMOTARO_ROOT / "momotaro.js").read_text(encoding="utf-8")
        readme = (MOMOTARO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn('{ key: "ryota", label: "りょーた" }', script)
        self.assertIn('{ key: "oji", label: "おーじ" }', script)
        self.assertIn('{ key: "kenshow", label: "けんしょー" }', script)
        self.assertNotIn("friend3", script)
        self.assertNotIn("3人目", script)

        self.assertIn('addons.keibailuka', readme)
        self.assertIn('りょーた / おーじ / けんしょー / 🐬', readme)
        self.assertIn('newspaperV2IlukaComment(iluka)', script)
        self.assertIn('newspaperV2ShowIlukaDetail(horse)', script)
        self.assertIn('colspan="4">予想</th>', script)
        self.assertIn('mark-ryota">りょ</th>', script)
        self.assertIn('mark-oji">王子</th>', script)
        self.assertIn('mark-kenshow">けん</th>', script)

    def test_history_and_short_comment_contract(self) -> None:
        html = (MOMOTARO_ROOT / "newspaper.html").read_text(encoding="utf-8")
        script = (MOMOTARO_ROOT / "momotaro.js").read_text(encoding="utf-8")

        self.assertIn("過去5走", html)
        self.assertNotIn('data-history-count="8"', html)
        self.assertIn("historyCount = 5", script)
        self.assertIn('{ length: 5 }', script)
        self.assertIn("3人の予想・短評", html)
        self.assertIn('heading.textContent === "RaceNote短評"', script)

    def test_operational_controls_are_hidden(self) -> None:
        html = (MOMOTARO_ROOT / "newspaper.html").read_text(encoding="utf-8")

        self.assertIn('<dl class="status-grid" hidden>', html)
        self.assertIn('<details class="recovery-panel newspaper-recovery-panel" hidden>', html)
        self.assertIn('id="newspaper-source-status" class="query-status" hidden', html)
        self.assertIn('<div class="button-row" hidden>', html)

    def test_prediction_list_groups_by_race_and_uses_basic_horse_name(self) -> None:
        html = (MOMOTARO_ROOT / "predictions.html").read_text(encoding="utf-8")
        script = (MOMOTARO_ROOT / "predictions.js").read_text(encoding="utf-8")

        self.assertIn('const basic = horse.basic || {};', script)
        self.assertIn('horse_name: predictionText(basic.horse_name, "")', script)
        self.assertIn('function groupVisibleRows()', script)
        self.assertIn('class="momotaro-race-card"', script)
        self.assertIn('source: "🐬"', script)
        self.assertIn('signal: "次走注目S"', script)
        self.assertIn('data-filter="keibailuka">🐬</button>', html)
        self.assertIn('id="prediction-refresh" type="button"', html)
        self.assertIn('<div class="button-row" hidden>', html)

    def test_prediction_column_widths_are_compact(self) -> None:
        css = (MOMOTARO_ROOT / "momotaro.css").read_text(encoding="utf-8")

        self.assertIn(".momotaro-newspaper-table .mark-ryota", css)
        self.assertIn("width:32px", css)
        self.assertIn(".momotaro-newspaper-table .mark-iluka", css)
        self.assertIn("width:34px", css)

    def test_browser_storage_is_isolated(self) -> None:
        newspaper = (MOMOTARO_ROOT / "newspaper.html").read_text(encoding="utf-8")
        fact_lite = (MOMOTARO_ROOT / "fact-lite.html").read_text(encoding="utf-8")
        manifest = (MOMOTARO_ROOT / "manifest.webmanifest").read_text(encoding="utf-8")
        service_worker = (MOMOTARO_ROOT / "service-worker.js").read_text(encoding="utf-8")

        self.assertIn('newspaperOpfsDir: "momotaro-newspaper"', newspaper)
        self.assertIn('newspaperCurrentBase: "./data/newspaper/current/"', newspaper)
        self.assertIn('factOpfsDir: "momotaro-fact-lite"', fact_lite)
        self.assertIn('"name": "桃太郎新聞"', manifest)
        self.assertIn('const CACHE_NAME = "momotaro-newspaper-shell-v7"', service_worker)


if __name__ == "__main__":
    unittest.main()

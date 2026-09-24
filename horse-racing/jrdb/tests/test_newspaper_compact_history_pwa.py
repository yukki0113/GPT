#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PWA_ROOT = PROJECT_ROOT / "pwa"
MOMOTARO_ROOT = PWA_ROOT / "momotaro"


class NewspaperCompactHistoryPwaTest(unittest.TestCase):
    def test_shared_renderer_has_standard_and_compact_modes(self) -> None:
        script = (PWA_ROOT / "newspaper-v4.js").read_text(encoding="utf-8")

        self.assertIn('NEWSPAPER_V4_HISTORY_MODE_STANDARD = "standard"', script)
        self.assertIn('NEWSPAPER_V4_HISTORY_MODE_COMPACT = "compact"', script)
        self.assertIn("function newspaperV4HistoryCellStandardHtml", script)
        self.assertIn("function newspaperV4HistoryCellCompactHtml", script)
        self.assertIn("function newspaperV4HistoryCellHtml", script)
        self.assertIn("newspaperV4HistoryTableClass()", script)

    def test_personal_surface_opts_in_before_shared_runtime_loads(self) -> None:
        html = (PWA_ROOT / "newspaper.html").read_text(encoding="utf-8")

        config_position = html.index('newspaperHistoryDisplayMode: "compact"')
        runtime_position = html.index('<script src="./newspaper.js?v=3"></script>')
        self.assertLess(config_position, runtime_position)
        self.assertIn('./newspaper-v4.css?v=7', html)
        self.assertIn('./newspaper-v4.js?v=8', html)

    def test_momotaro_opts_in_during_turn_3(self) -> None:
        html = (MOMOTARO_ROOT / "newspaper.html").read_text(encoding="utf-8")
        script = (MOMOTARO_ROOT / "momotaro.js").read_text(encoding="utf-8")

        self.assertIn('newspaperHistoryDisplayMode: "compact"', html)
        self.assertIn('historyCount = 5', script)
        self.assertIn('newspaperV4HistoryTableClass()', script)
        self.assertIn('../newspaper-v4.css?v=7', html)
        self.assertIn('../newspaper-v4.js?v=8', html)

    def test_compact_layout_uses_shared_dense_width_contract(self) -> None:
        css = (PWA_ROOT / "newspaper-v4.css").read_text(encoding="utf-8")

        self.assertIn("--newspaper-history-compact-width: 124px", css)
        self.assertIn("--newspaper-history-compact-width: 120px", css)
        self.assertIn(".newspaper-table-v4.newspaper-history-compact", css)
        self.assertIn(".newspaper-run-v4-compact", css)

    def test_compact_cell_keeps_primary_race_information(self) -> None:
        script = (PWA_ROOT / "newspaper-v4.js").read_text(encoding="utf-8")

        for token in (
            "newspaperV4RaceClass(run)",
            "newspaperV4ResultLine(run)",
            "newspaperV4TrackCondition(run.track_condition)",
            "formatRaceTime(run.time_sec)",
            "corners(run)",
            "newspaperV4Last3f(run)",
        ):
            self.assertIn(token, script)

    def test_detail_dialog_keeps_information_removed_from_compact_cell(self) -> None:
        script = (PWA_ROOT / "newspaper-v4.js").read_text(encoding="utf-8")

        for label in (
            '["着差",',
            '["騎手",',
            '["斤量",',
            '["馬体重",',
            '["IDM",',
            '["パドック",',
            '["レースコメント",',
        ):
            self.assertIn(label, script)

    def test_personal_service_worker_does_not_delete_other_pwa_caches(self) -> None:
        service_worker = (PWA_ROOT / "service-worker.js").read_text(encoding="utf-8")

        self.assertIn('const CACHE_NAME = "jrdb-pwa-shell-v58"', service_worker)
        self.assertIn('cacheName.startsWith("jrdb-pwa-shell-")', service_worker)
        self.assertIn('"./newspaper-v4.css?v=7"', service_worker)
        self.assertIn('"./newspaper-v4.js?v=8"', service_worker)


if __name__ == "__main__":
    unittest.main()

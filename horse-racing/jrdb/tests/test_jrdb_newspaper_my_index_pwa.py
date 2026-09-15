#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PWA_ROOT = PROJECT_ROOT / "pwa"


class NewspaperMyIndexPwaTest(unittest.TestCase):
    def test_independent_index_asset_is_loaded_and_cached(self) -> None:
        html = (PWA_ROOT / "newspaper.html").read_text(encoding="utf-8")
        service_worker = (PWA_ROOT / "service-worker.js").read_text(encoding="utf-8")
        script = (PWA_ROOT / "newspaper-v10.js").read_text(encoding="utf-8")

        self.assertIn('./newspaper-v10.js?v=1', html)
        self.assertIn('./newspaper-v10.js?v=1', service_worker)
        self.assertIn('const CACHE_NAME = "jrdb-pwa-shell-v43"', service_worker)
        self.assertIn('"training_edge_index"', script)
        self.assertIn('sources.my_index', script)
        self.assertIn('"指数○"', script)

    def test_independent_index_layer_does_not_recalculate_index(self) -> None:
        script = (PWA_ROOT / "newspaper-v10.js").read_text(encoding="utf-8")

        self.assertNotIn("training_score", script)
        self.assertNotIn("weight", script.lower())
        self.assertNotIn("rank(", script.lower())
        self.assertNotIn("percentile", script.lower())

    def test_independent_index_value_and_summary_smoke(self) -> None:
        node_path = shutil.which("node")
        if node_path is None:
            self.skipTest("node is not available")

        script_path = PWA_ROOT / "newspaper-v10.js"
        harness = f"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync({json.dumps(str(script_path))}, "utf8");
const context = {{
  number(value, digits = 1) {{
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return Number(value).toFixed(digits).replace(/\\.0$/, "");
  }},
  currentBundle: null,
  tableWrap: {{ querySelectorAll() {{ return []; }} }},
  renderTable() {{}},
  dayPackageSummary(value) {{
    return value && value.manifest ? "base" : "新聞データなし";
  }},
  window: {{ addEventListener() {{}} }}
}};
vm.createContext(context);
vm.runInContext(source, context);

const supplied = {{ addons: {{ my_index: {{ training_edge_index: 80.9 }} }} }};
if (context.newspaperV10MyIndexValue(supplied) !== "80.9") throw new Error("training_edge_index missing");

const missing = {{ addons: {{ my_index: {{ training_edge_index: null }} }} }};
if (context.newspaperV10MyIndexValue(missing) !== "—") throw new Error("null index should be dash");

const legacy = {{ addons: {{ my_index: {{ index: 47.4 }} }} }};
if (context.newspaperV10MyIndexValue(legacy) !== "47.4") throw new Error("legacy fallback missing");

const absent = {{ addons: {{}} }};
if (context.newspaperV10MyIndexValue(absent) !== "—") throw new Error("absent addon should be dash");

const ready = context.dayPackageSummary({{ manifest: {{ source_status: {{ my_index: {{ state: "READY" }} }} }} }});
if (ready !== "base / 指数○") throw new Error(`READY summary mismatch: ${{ready}}`);

const notReady = context.dayPackageSummary({{ manifest: {{ source_status: {{ my_index: {{ state: "NOT_FOUND" }} }} }} }});
if (notReady !== "base / 指数—") throw new Error(`NOT_FOUND summary mismatch: ${{notReady}}`);
"""

        result = subprocess.run(
            [node_path, "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()

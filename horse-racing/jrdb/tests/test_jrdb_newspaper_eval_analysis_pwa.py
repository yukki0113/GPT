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


class NewspaperEvalAnalysisPwaTest(unittest.TestCase):
    def test_eval_analysis_assets_are_loaded_and_cached(self) -> None:
        html = (PWA_ROOT / "newspaper.html").read_text(encoding="utf-8")
        service_worker = (PWA_ROOT / "service-worker.js").read_text(encoding="utf-8")
        script = (PWA_ROOT / "newspaper-v9.js").read_text(encoding="utf-8")

        self.assertIn('./newspaper-v9.css?v=1', html)
        self.assertIn('./newspaper-v9.js?v=1', html)
        self.assertIn('./newspaper-v9.css?v=1', service_worker)
        self.assertIn('./newspaper-v9.js?v=1', service_worker)
        self.assertEqual(html.count('id="newspaper-detail-dialog"'), 1)
        self.assertNotIn('createElement("dialog")', script)

    def test_eval_analysis_layer_has_no_condition_logic(self) -> None:
        script = (PWA_ROOT / "newspaper-v9.js").read_text(encoding="utf-8")

        self.assertIn("addon.analysis.comment", script)
        self.assertIn("newspaper-eval-analysis-link", script)
        self.assertNotIn("H1_PRE", script)
        self.assertNotIn("H2_PRE", script)
        self.assertNotIn('status === "WATCH"', script)
        self.assertNotIn('status === "MATCH"', script)

    def test_eval_analysis_gate_and_modal_smoke(self) -> None:
        node_path = shutil.which("node")
        if node_path is None:
            self.skipTest("node is not available")

        script_path = PWA_ROOT / "newspaper-v9.js"
        harness = f"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync({json.dumps(str(script_path))}, "utf8");
const context = {{
  text(value, fallback = "") {{
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }},
  escapeHtml(value) {{
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }},
  newspaperV2AddonDisplay(addon, keys) {{
    if (!addon) return "—";
    for (const key of keys) {{
      if (addon[key] !== null && addon[key] !== undefined && addon[key] !== "") {{
        return String(addon[key]);
      }}
    }}
    return "—";
  }},
  currentBundle: null,
  tableWrap: {{ querySelectorAll() {{ return []; }} }},
  dialogTitle: {{ textContent: "" }},
  dialogBody: {{ innerHTML: "" }},
  detailDialog: {{
    opened: false,
    showModal() {{ this.opened = true; }},
    setAttribute() {{ this.opened = true; }}
  }},
  renderTable() {{}},
  window: {{ addEventListener() {{}} }}
}};
vm.createContext(context);
vm.runInContext(source, context);

const oldHorse = {{ addons: {{ eval: {{ eval: 52 }} }}, basic: {{ horse_name: "通常馬" }} }};
if (context.newspaperV9EvalAnalysis(oldHorse) !== null) throw new Error("old JSON linked unexpectedly");

const emptyHorse = {{
  addons: {{ eval: {{ eval: 52, analysis: {{ comment: "   " }} }} }},
  basic: {{ horse_name: "通常馬" }}
}};
if (context.newspaperV9EvalAnalysis(emptyHorse) !== null) throw new Error("empty comment linked unexpectedly");

const highlightedHorse = {{
  addons: {{ eval: {{
    eval: 52,
    analysis: {{
      status: "WATCH",
      codes: ["H1_PRE", "TRAINING_SUPPORT"],
      title: "H1 Forward事前候補",
      comment: "1行目\\n2行目 <strong>raw</strong>",
      version: "phase2-comment-v0.1",
      asof: "2026-09-12T09:00:00+09:00"
    }}
  }} }},
  basic: {{ horse_name: "注目馬" }}
}};
if (!context.newspaperV9EvalAnalysis(highlightedHorse)) throw new Error("comment was not linked");
context.newspaperV9ShowEvalDetail(highlightedHorse);
if (!context.detailDialog.opened) throw new Error("dialog was not opened");
if (!context.dialogTitle.textContent.includes("注目馬 / Eval 52")) throw new Error("dialog title mismatch");
if (!context.dialogBody.innerHTML.includes("H1 Forward事前候補")) throw new Error("analysis title missing");
if (!context.dialogBody.innerHTML.includes("H1_PRE / TRAINING_SUPPORT")) throw new Error("analysis codes missing");
if (!context.dialogBody.innerHTML.includes("1行目\\n2行目")) throw new Error("comment line break missing");
if (!context.dialogBody.innerHTML.includes("&lt;strong&gt;raw&lt;/strong&gt;")) throw new Error("comment escaping missing");
if (!context.dialogBody.innerHTML.includes("phase2-comment-v0.1")) throw new Error("version missing");
if (!context.dialogBody.innerHTML.includes("2026-09-12T09:00:00+09:00")) throw new Error("as-of missing");
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

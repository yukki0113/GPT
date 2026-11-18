/* Execute actual Newspaper PWA renderer functions without touching production. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const PWA = path.resolve(__dirname, "../../jrdb/pwa");
const config = {newspaperHistoryDisplayMode: "standard"};
const scope = {
  window: {JRDB_PWA_CONFIG: config, addEventListener: () => {}},
  renderTable: () => {},
  renderBundle: () => {},
  showRunDetail: () => {},
  currentBundle: {
    metadata: {source_status: {racenote_prediction: {state: "READY"}}},
    horses: []
  },
  text: (value, fallback = "—") =>
    (value === null || value === undefined || value === "") ? fallback : String(value),
  escapeHtml: (value) => String(value),
  number: (value) => String(value),
  finishLabel: (run) => String(run.finish) + "着",
  shortDate: (date) => String(date).slice(5),
  corners: () => "",
  hasDetail: () => false,
  formatRaceTime: (v) => String(v),
};
vm.createContext(scope);
for (const f of ["newspaper-v4.js", "newspaper-v5.js"]) {
  vm.runInContext(fs.readFileSync(path.join(PWA, f), "utf8"), scope, {filename: f});
}

const run = {
  sequence: 1,
  source_layer: "detailed_recent_history",
  source_kind: "paci_previous_detail",
  date: "2026-02-14",
  venue_code: "80",
  venue: "80",
  race_no: null,
  race_name: null,
  class_label: null,
  grade_label: null,
  surface: "芝",
  distance_m: 1351,
  track_condition: null,
  field_size: 13,
  horse_no: 0,
  finish: 6,
  abnormal_code: "0",
  final_popularity: null,
  time_sec: null,
  time_gap_sec: null,
  last3f_sec: null,
  carried_weight_kg: null,
  body_weight_kg: null,
  notes: null,
  jrdb_result: null
};
const missingPastNo = {...run, horse_no: null};

for (const mode of ["standard", "compact"]) {
  config.newspaperHistoryDisplayMode = mode;
  const renderedZero = scope.newspaperV4HistoryCellHtml(run, 0, 0);
  const renderedNull = scope.newspaperV4HistoryCellHtml(missingPastNo, 0, 0);
  assert.equal(renderedZero, renderedNull, "PWA past-run display changed for 0 -> null (" + mode + ")");
  assert.match(renderedNull, /6着/);
  assert.match(renderedNull, /13頭/);
  assert.doesNotMatch(renderedNull, /0番/);
  assert.equal(scope.newspaperV4ResultLine(run), scope.newspaperV4ResultLine(missingPastNo));
}

for (const state of ["READY", "NOT_APPLICABLE", "PENDING", "ERROR"]) {
  scope.currentBundle.metadata.source_status.racenote_prediction.state = state;
  const get = (value) => scope.newspaperV5AddonValue(value, "racenote_prediction", ["mark"]);
  const missing = get(undefined);
  const explicitNull = get(null);
  assert.equal(missing, explicitNull, "PWA RN cell differs missing vs null: " + state);
  assert.equal(missing, (state === "READY" || state === "NOT_APPLICABLE") ? "" : "-");
  assert.equal(get({mark: "◎"}), "◎", "selected horse mark must survive candidate");
}
console.log("PASS: actual PWA v4 standard+compact past-run 0/null same display; v5 RN missing/null same display for 4 source states");

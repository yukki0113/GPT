"use strict";

/* Newspaper display v10: consume the supplied Training Edge independent index without recalculation. */

function newspaperV10MyIndexAddon(horse) {
  if (!horse || !horse.addons || !horse.addons.my_index || typeof horse.addons.my_index !== "object") {
    return null;
  }
  return horse.addons.my_index;
}

function newspaperV10MyIndexValue(horse) {
  const addon = newspaperV10MyIndexAddon(horse);
  if (!addon) return "—";

  if (Object.prototype.hasOwnProperty.call(addon, "training_edge_index")) {
    const supplied = addon.training_edge_index;
    if (supplied === null || supplied === undefined || supplied === "") return "";
    const numeric = Number(supplied);
    return Number.isFinite(numeric) ? number(numeric) : "";
  }

  for (const key of ["display_value", "index", "score", "value"]) {
    const value = addon[key];
    if (value === null || value === undefined || value === "") continue;
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return number(numeric);
  }
  return "—";
}

function newspaperV10ApplyMyIndex() {
  if (!currentBundle || !Array.isArray(currentBundle.horses) || !tableWrap) return;

  const horses = [...currentBundle.horses].sort(
    (a, b) => Number(a && a.key && a.key.horse_no) - Number(b && b.key && b.key.horse_no)
  );
  const rows = tableWrap.querySelectorAll("tbody tr");

  rows.forEach((row, index) => {
    const horse = horses[index];
    const cell = row.querySelector(".mark-my");
    if (!horse || !cell) return;
    cell.textContent = newspaperV10MyIndexValue(horse);
    cell.title = "独自指数（Training Edge）";
  });
}

const newspaperV10RenderTableBase = renderTable;
renderTable = function () {
  newspaperV10RenderTableBase();
  newspaperV10ApplyMyIndex();
};

dayPackageSummary = function (value) {
  if (!value || !value.manifest) return "新聞データなし";

  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  const edgeState = sources.edge_v05 && ["READY", "PARTIAL"].includes(sources.edge_v05.state) ? "Edge○" : "Edge—";
  const count = Array.isArray(value.races) ? value.races.length : 0;

  return `${value.manifest.date} / ${count}R / ${evalState} / ${ilukaState} / ${edgeState}`;
};

window.addEventListener("load", () => {
  if (currentBundle) newspaperV10ApplyMyIndex();
});

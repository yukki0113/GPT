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

  for (const key of ["training_edge_index", "display_value", "index", "score", "value"]) {
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

const newspaperV10DayPackageSummaryBase = dayPackageSummary;
dayPackageSummary = function (value) {
  const base = newspaperV10DayPackageSummaryBase(value);
  if (!value || !value.manifest) return base;

  const sources = value.manifest.source_status || {};
  const indexState = sources.my_index && sources.my_index.state === "READY" ? "指数○" : "指数—";
  return `${base} / ${indexState}`;
};

window.addEventListener("load", () => {
  if (currentBundle) newspaperV10ApplyMyIndex();
});

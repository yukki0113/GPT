"use strict";

/* Race-level confidence only. Horse comments and selection rules are untouched. */
function newspaperRaceConfidence(bundle, member, publicSurface) {
  if (!bundle || !Array.isArray(bundle.horses)) return "–";
  if (member === "oji") {
    // The current Oji horse rows contain retrospective stars, not a race grade.
    return "–";
  }
  if (member === "kenshow" && publicSurface) {
    const notes = bundle.race_notes || {};
    const value = notes.momotaro_race_confidence && notes.momotaro_race_confidence.kenshow;
    return ["A", "B", "C"].includes(value) ? value : "–";
  }
  const values = new Set();
  for (const horse of bundle.horses) {
    const addons = horse.addons || {};
    const source = member === "kenshow"
      ? addons.racenote_prediction
      : (addons.momotaro || {}).ryota;
    const value = source && typeof source.confidence === "string" ? source.confidence.trim() : "";
    if (value) values.add(value);
  }
  if (values.size !== 1) return "–";
  const value = [...values][0];
  return member === "kenshow" && !["A", "B", "C"].includes(value) ? "–" : value;
}

function newspaperApplyConfidenceHeaders(table, bundle, publicSurface) {
  if (!table) return;
  const markRow = table.querySelector(".newspaper-mark-head-row");
  if (!markRow) return;
  // The contributor labels and confidence values occupy *separate table rows*.
  // All non-contributor mark headers span both rows. The identity/history
  // headers span the group header plus both mark rows.
  const originalTopRow = markRow.previousElementSibling;
  if (originalTopRow) {
    originalTopRow.querySelectorAll('th[rowspan="2"]').forEach(head => {
      head.rowSpan = 3;
    });
  }
  const previous = table.querySelector(".newspaper-confidence-row");
  if (previous) previous.remove();

  const row = document.createElement("tr");
  row.className = "newspaper-confidence-row";
  const targets = new Map([
    [publicSurface ? "mark-kenshow" : "mark-rn", "kenshow"],
    ["mark-ryota", "ryota"],
    ["mark-oji", "oji"]
  ]);
  for (const head of markRow.querySelectorAll("th")) {
    const match = [...targets].find(([cls]) => head.classList.contains(cls));
    if (!match) {
      head.rowSpan = 2;
      continue;
    }
    const [cls, member] = match;
    const value = newspaperRaceConfidence(bundle, member, publicSurface);
    head.classList.add("newspaper-confidence-head");
    head.textContent = member === "kenshow" ? "けん" : member === "ryota" ? "りょ" : "王子";
    const confidence = document.createElement("th");
    confidence.className = "newspaper-mark-col newspaper-confidence-cell " + cls;
    confidence.textContent = value;
    row.appendChild(confidence);
  }
  markRow.after(row);
  // Sticky rows must use their actual rendered heights. Fixed 31px/50px
  // offsets do not match the grouped header height on narrow mobile tables.
  const groupHeight = originalTopRow ? originalTopRow.offsetHeight : 0;
  const labelHeight = markRow.offsetHeight;
  if (groupHeight > 0 && labelHeight > 0) {
    table.style.setProperty("--newspaper-group-header-height", groupHeight + "px");
    table.style.setProperty("--newspaper-label-header-height", labelHeight + "px");
  }
}

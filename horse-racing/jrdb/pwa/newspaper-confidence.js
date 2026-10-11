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
  for (const [member, selector, label] of [
    ["kenshow", publicSurface ? ".mark-kenshow" : ".mark-rn", "けん"],
    ["ryota", ".mark-ryota", "りょ"],
    ["oji", ".mark-oji", "王子"]
  ]) {
    const head = table.querySelector(`.newspaper-mark-head-row th${selector}`);
    if (!head) continue;
    const confidence = newspaperRaceConfidence(bundle, member, publicSurface);
    head.classList.add("newspaper-confidence-head");
    head.innerHTML = `<span class="newspaper-confidence-inner"><span class="newspaper-confidence-label">${label}</span>` +
      `<span class="newspaper-confidence-value">${escapeHtml(confidence)}</span></span>`;
  }
}

"use strict";

/* UI-only Newspaper v3 patch. Base storage/validation remains in newspaper.js v1. */
const NEWSPAPER_V2_MARK_LABELS = {
  total: "総", idm: "能", info: "情", jockey: "騎", stable: "厩", training: "調", longshot: "穴"
};

const NEWSPAPER_STYLE_SHORT = {
  "逃げ": "逃",
  "先行": "先",
  "好位差し": "好",
  "差し": "差",
  "追込": "追",
  "自在": "自"
};

function newspaperV2AddonDisplay(addon, keys) {
  if (!addon || typeof addon !== "object") return "—";
  for (const key of ["display_value", ...keys]) {
    const value = addon[key];
    if (value !== null && value !== undefined && value !== "") return text(value);
  }
  return "●";
}

function newspaperV2IlukaComment(addon) {
  if (!addon || typeof addon !== "object") return "";
  for (const key of ["short_comment", "comment", "summary", "text"]) {
    if (addon[key]) return text(addon[key], "");
  }
  return "";
}

function newspaperV2FrameClass(frameNo) {
  const value = Number(frameNo);
  return Number.isInteger(value) && value >= 1 && value <= 8 ? ` frame-${value}` : "";
}

function newspaperV2HorseInfoHtml(horse) {
  const basic = horse.basic || {};
  const sex = text(basic.sex_label, "").replace("セン", "セ");
  const age = text(basic.age, "");
  const weight = basic.carried_weight_kg !== null && basic.carried_weight_kg !== undefined
    ? number(basic.carried_weight_kg)
    : "";
  const jockey = text(basic.jockey_name, "");
  const style = NEWSPAPER_STYLE_SHORT[text(basic.running_style_label, "")] || text(basic.running_style_label, "");
  const profile = [
    `${sex}${age}`,
    weight,
    jockey,
    style
  ].filter(Boolean).join(" ");
  const sire = text(basic.sire_name, "");

  return `<div class="newspaper-horse-name" title="${escapeHtml(text(basic.horse_name))}">${escapeHtml(text(basic.horse_name))}</div>
    <div class="newspaper-horse-profile">${escapeHtml(profile)}</div>
    <div class="newspaper-horse-sire" title="${escapeHtml(sire)}">${escapeHtml(sire)}</div>`;
}

function newspaperV2MarkHtml(horse, horseIndex) {
  const jrdb = horse.jrdb || {};
  const marks = jrdb.marks || {};
  const ability = jrdb.ability || {};
  const training = jrdb.training || {};
  const summary = training.summary || {};
  const analysis = training.analysis || {};
  const addons = horse.addons || {};
  const activeMarks = Object.entries(marks).filter(([, value]) => value);
  const markLine = activeMarks.length
    ? activeMarks.map(([key, value]) => `${escapeHtml(NEWSPAPER_V2_MARK_LABELS[key] || key)}${escapeHtml(value)}`).join(" ")
    : "—";
  const trainingIndex = analysis.training_index ?? summary.training_index;
  const evalValue = newspaperV2AddonDisplay(addons.eval, ["eval", "score", "index", "value"]);
  const raceNoteValue = newspaperV2AddonDisplay(addons.racenote_prediction, ["mark", "symbol", "prediction_mark", "value"]);
  const myValue = newspaperV2AddonDisplay(addons.my_index, ["index", "score", "value"]);
  const iluka = addons.keibailuka;
  const ilukaValue = iluka ? "○" : "—";
  const ilukaMarkup = newspaperV2IlukaComment(iluka)
    ? `<button type="button" class="newspaper-addon-link newspaper-iluka-button" data-horse-index="${horseIndex}">${ilukaValue}</button>`
    : escapeHtml(ilukaValue);

  return `<div class="newspaper-mark-grid">
    <div><span>能力</span><strong>${number(ability.idm)}</strong></div>
    <div><span>調教</span><strong>${number(trainingIndex)} ${escapeHtml(text(summary.training_arrow, ""))}</strong></div>
    <div><span>Eval</span><strong>${escapeHtml(evalValue)}</strong></div>
    <div><span>RN</span><strong>${escapeHtml(raceNoteValue)}</strong></div>
    <div><span>🐬</span><strong>${ilukaMarkup}</strong></div>
    <div><span>My</span><strong>${escapeHtml(myValue)}</strong></div>
  </div><div class="newspaper-jrdb-marks">JRDB印 ${markLine}</div>`;
}

function newspaperV2HistoryCellHtml(run, horseIndex, runIndex) {
  if (!run) return `<div class="newspaper-history-empty">—</div>`;
  const compact = run.source_layer === "compact_older_history";
  const raceClass = run.grade_label || run.class_label || "";
  const track = [text(run.surface, ""), run.distance_m ? `${run.distance_m}m` : "", text(run.track_condition, "")]
    .filter(Boolean).join("");
  const result = [finishLabel(run), run.final_popularity ? `${run.final_popularity}人気` : ""].filter(Boolean).join(" ");
  const passage = corners(run);
  const performance = compact ? "" : [
    run.time_sec !== null && run.time_sec !== undefined && Number(run.time_sec) > 0 ? `T ${formatRaceTime(run.time_sec)}` : "",
    run.last3f_sec !== null && run.last3f_sec !== undefined ? `上 ${number(run.last3f_sec)}` : "",
    run.idm !== null && run.idm !== undefined ? `IDM ${number(run.idm)}` : ""
  ].filter(Boolean).join(" / ");
  const abnormal = text(run.abnormal_code, "0") !== "0"
    ? `<div class="newspaper-abnormal">${finishLabel(run)} / 異常区分 ${escapeHtml(text(run.abnormal_code))}</div>`
    : "";
  const detail = hasDetail(run)
    ? `<button type="button" class="newspaper-detail-button" data-horse-index="${horseIndex}" data-run-index="${runIndex}">詳細</button>`
    : "";
  return `<div class="newspaper-run ${compact ? "compact" : "detailed"}">
    <div class="newspaper-run-top"><span>${escapeHtml(shortDate(run.date))} ${escapeHtml(text(run.venue, ""))}${run.race_no ? `${run.race_no}R` : ""}</span>${compact ? '<span class="newspaper-source-pill">簡易</span>' : ""}</div>
    <div class="newspaper-run-title">${escapeHtml(runTitle(run))}</div>
    ${raceClass ? `<div class="newspaper-subline">${escapeHtml(raceClass)}</div>` : ""}
    <div class="newspaper-subline">${escapeHtml(track)}</div>
    <div class="newspaper-run-result">${escapeHtml(result)}</div>
    ${passage ? `<div class="newspaper-subline">通 ${escapeHtml(passage)}</div>` : ""}
    ${performance ? `<div class="newspaper-subline">${escapeHtml(performance)}</div>` : ""}
    ${abnormal}${detail}
  </div>`;
}

function newspaperV2ShowIlukaDetail(horse) {
  const addon = horse.addons ? horse.addons.keibailuka : null;
  dialogTitle.textContent = `${text(horse.basic && horse.basic.horse_name)} / イルカブログ`;
  const comment = newspaperV2IlukaComment(addon);
  dialogBody.innerHTML = `<p class="newspaper-addon-comment">${escapeHtml(comment || "掲載対象です。短評は未取得です。")}</p>`;
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function newspaperV2RenderRaceNotes() {
  const target = document.getElementById("newspaper-race-notes");
  if (!target || !currentBundle) return;
  const notes = currentBundle.race_notes || {};
  const items = Array.isArray(notes.items) ? notes.items : [];
  const blocks = [];
  if (notes.racenote_short_comment) {
    blocks.push(`<div class="newspaper-note-block"><strong>RaceNote</strong><p>${escapeHtml(text(notes.racenote_short_comment))}</p></div>`);
  }
  for (const item of items) {
    const unit = item.unit ? ` ${escapeHtml(text(item.unit))}` : "";
    blocks.push(`<div class="newspaper-note-item"><span>${escapeHtml(text(item.label))}</span><strong>${escapeHtml(text(item.value))}${unit}</strong><small>${escapeHtml(text(item.source, ""))}</small></div>`);
  }
  target.innerHTML = blocks.length
    ? blocks.join("")
    : `<div class="empty-state newspaper-note-empty">現時点ではレース短評・レース単位指標は未取得です。</div>`;
}

renderTable = function () {
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const historyHeaders = Array.from({ length: historyCount }, (_, index) => `<th class="newspaper-history-head">${index + 1}走前</th>`).join("");
  const rows = horses.map((horse, horseIndex) => {
    const history = horse.history || [];
    const frameNo = horse.key ? horse.key.frame_no : null;
    const historyCells = Array.from({ length: historyCount }, (_, runIndex) =>
      `<td class="newspaper-history-cell">${newspaperV2HistoryCellHtml(history[runIndex], horseIndex, runIndex)}</td>`
    ).join("");
    return `<tr>
      <td class="newspaper-frame${newspaperV2FrameClass(frameNo)}">${escapeHtml(text(frameNo))}</td>
      <td class="newspaper-horse-no">${escapeHtml(text(horse.key && horse.key.horse_no))}</td>
      <td class="newspaper-horse-info">${newspaperV2HorseInfoHtml(horse)}</td>
      <td class="newspaper-marks">${newspaperV2MarkHtml(horse, horseIndex)}</td>
      ${historyCells}<td class="newspaper-edge">${edgeHtml(horse)}</td>
    </tr>`;
  }).join("");

  tableWrap.innerHTML = `<table class="newspaper-table"><thead><tr>
    <th class="newspaper-frame">枠</th><th class="newspaper-horse-no">馬番</th><th class="newspaper-horse-info">馬情報</th><th class="newspaper-marks">印群</th>
    ${historyHeaders}<th class="newspaper-edge">Edge</th>
  </tr></thead><tbody>${rows}</tbody></table>`;

  tableWrap.querySelectorAll(".newspaper-detail-button").forEach(button => {
    button.addEventListener("click", () => {
      const horse = horses[Number(button.dataset.horseIndex)];
      showRunDetail(horse, horse.history[Number(button.dataset.runIndex)]);
    });
  });
  tableWrap.querySelectorAll(".newspaper-iluka-button").forEach(button => {
    button.addEventListener("click", () => newspaperV2ShowIlukaDetail(horses[Number(button.dataset.horseIndex)]));
  });
};

const newspaperV1RenderBundle = renderBundle;
renderBundle = function () {
  newspaperV1RenderBundle();
  newspaperV2RenderRaceNotes();
  const notesCardV2 = document.getElementById("newspaper-notes-card");
  if (notesCardV2) notesCardV2.hidden = false;
};

const newspaperV1ClearBundle = clearBundle;
clearBundle = async function () {
  await newspaperV1ClearBundle();
  const notesCardV2 = document.getElementById("newspaper-notes-card");
  if (notesCardV2) notesCardV2.hidden = true;
};

window.addEventListener("load", () => {
  if (currentBundle) renderBundle();
});

"use strict";

/* Newspaper display v4: compact sticky identity, one-column marks, rich past runs. */

const NEWSPAPER_V4_TRAINING_ARROW = {
  "デキ抜群": "↑↑",
  "上昇": "↑",
  "平行線": "→",
  "やや下降気味": "↘",
  "デキ落ち": "↓"
};

function newspaperV4TrainingValue(horse) {
  const training = horse.jrdb && horse.jrdb.training ? horse.jrdb.training : {};
  const summary = training.summary || {};
  const analysis = training.analysis || {};
  const arrowRaw = text(summary.training_arrow, "");
  const arrow = NEWSPAPER_V4_TRAINING_ARROW[arrowRaw] || arrowRaw;
  const indexValue = analysis.training_index ?? summary.training_index;
  return {
    display: arrow || (indexValue !== null && indexValue !== undefined ? number(indexValue) : "—"),
    title: [
      indexValue !== null && indexValue !== undefined ? `調教指数 ${number(indexValue)}` : "",
      arrowRaw
    ].filter(Boolean).join(" / ")
  };
}

function newspaperV4BasicInfoHtml(horse) {
  const basic = horse.basic || {};
  const sex = text(basic.sex_label, "").replace("セン", "セ");
  const age = text(basic.age, "");
  const weight = basic.carried_weight_kg !== null && basic.carried_weight_kg !== undefined
    ? `${number(basic.carried_weight_kg)}kg`
    : "";
  const jockey = text(basic.jockey_name, "");
  const sire = text(basic.sire_name, "");
  const style = text(basic.running_style_label, "");
  return `<div class="newspaper-basic-line newspaper-basic-main">${escapeHtml([`${sex}${age}`, weight].filter(Boolean).join(" "))}</div>
    <div class="newspaper-basic-line">${escapeHtml(jockey)}</div>
    <div class="newspaper-basic-line newspaper-basic-sire" title="${escapeHtml(sire)}">${sire ? `父 ${escapeHtml(sire)}` : "—"}</div>
    <div class="newspaper-basic-line">${escapeHtml(style || "—")}</div>`;
}

function newspaperV4HorseNameHtml(horse) {
  const name = text(horse.basic && horse.basic.horse_name);
  return `<div class="newspaper-horse-name-only" title="${escapeHtml(name)}">${escapeHtml(name)}</div>`;
}

function newspaperV4MarkCells(horse, horseIndex) {
  const jrdb = horse.jrdb || {};
  const marks = jrdb.marks || {};
  const ability = jrdb.ability || {};
  const addons = horse.addons || {};
  const training = newspaperV4TrainingValue(horse);
  const evalValue = newspaperV2AddonDisplay(addons.eval, ["eval", "score", "index", "value"]);
  const raceNoteValue = newspaperV2AddonDisplay(addons.racenote_prediction, ["mark", "symbol", "prediction_mark", "value"]);
  const myValue = newspaperV2AddonDisplay(addons.my_index, ["index", "score", "value"]);
  const iluka = addons.keibailuka;
  const ilukaValue = iluka ? "○" : "—";
  const ilukaMarkup = newspaperV2IlukaComment(iluka)
    ? `<button type="button" class="newspaper-addon-link newspaper-iluka-button" data-horse-index="${horseIndex}">○</button>`
    : escapeHtml(ilukaValue);
  const totalMark = text(marks.total, "—");

  return [
    `<td class="newspaper-mark-col mark-ability" title="JRDB能力/IDM">${escapeHtml(number(ability.idm))}</td>`,
    `<td class="newspaper-mark-col mark-training" title="${escapeHtml(training.title)}">${escapeHtml(training.display)}</td>`,
    `<td class="newspaper-mark-col mark-jrdb" title="JRDB総合印">${escapeHtml(totalMark)}</td>`,
    `<td class="newspaper-mark-col mark-eval">${escapeHtml(evalValue)}</td>`,
    `<td class="newspaper-mark-col mark-rn">${escapeHtml(raceNoteValue)}</td>`,
    `<td class="newspaper-mark-col mark-iluka">${ilukaMarkup}</td>`,
    `<td class="newspaper-mark-col mark-my">${escapeHtml(myValue)}</td>`
  ].join("");
}

function newspaperV4RaceClass(run) {
  const grade = text(run.grade_label, "");
  const klass = text(run.class_label, "");
  if (grade && klass && grade !== klass) return `${grade} ${klass}`;
  return grade || klass;
}

function newspaperV4FinishLabel(run) {
  return finishLabel(run).replace(/\/\d+/, "");
}

function newspaperV4ResultLine(run) {
  const parts = [];
  const finishText = newspaperV4FinishLabel(run);
  parts.push(`<strong>${escapeHtml(finishText)}</strong>`);
  if (run.field_size) parts.push(`${escapeHtml(text(run.field_size))}頭`);
  const pastHorseNo = run.horse_no ?? run.past_horse_no;
  if (pastHorseNo) parts.push(`${escapeHtml(text(pastHorseNo))}番`);
  if (run.final_popularity) parts.push(`${escapeHtml(text(run.final_popularity))}人気`);
  return parts.join(" ");
}

function newspaperV4BodyWeight(run) {
  if (run.body_weight_kg === null || run.body_weight_kg === undefined) return "";
  const change = run.body_weight_change_kg;
  const changeText = change === null || change === undefined
    ? ""
    : `(${Number(change) > 0 ? "+" : ""}${text(change)})`;
  return `${number(run.body_weight_kg)}kg${changeText}`;
}

function newspaperV4TimeGap(run) {
  const gap = run.time_gap_sec ?? run.first_second_time_diff_sec;
  if (gap === null || gap === undefined || Number.isNaN(Number(gap))) return "";
  let reference = text(run.time_gap_reference, "");
  if (!reference) {
    reference = Number(run.finish) === 1 ? "RUNNER_UP" : "WINNER";
  }
  const label = reference === "RUNNER_UP" ? "2着差" : "1着差";
  return `${label} ${number(gap)}`;
}

function newspaperV4Last3f(run) {
  if (run.last3f_sec === null || run.last3f_sec === undefined) return "";
  const rank = Number(run.last3f_rank ?? run.last3f_time_rank);
  const rankLabel = Number.isInteger(rank) && rank > 0 ? ` ${rank}` : "";
  const rankClass = Number.isInteger(rank) && rank >= 1 && rank <= 3 ? ` last3f-rank-${rank}` : "";
  return `<span class="newspaper-last3f${rankClass}">上${escapeHtml(number(run.last3f_sec))}${escapeHtml(rankLabel)}</span>`;
}

function newspaperV4TrackCondition(value) {
  const raw = text(value, "");
  const standard = {
    "速良": "良",
    "遅良": "良",
    "速稍重": "稍重",
    "遅稍重": "稍重",
    "速重": "重",
    "遅重": "重",
    "速不良": "不良",
    "遅不良": "不良"
  };
  return standard[raw] || raw;
}

function newspaperV4HistoryCellHtml(run, horseIndex, runIndex) {
  if (!run) return `<div class="newspaper-history-empty">—</div>`;
  const compact = run.source_layer === "compact_older_history";
  const datePlace = `${shortDate(run.date)} ${text(run.venue, "")}${run.race_no ? `${run.race_no}R` : ""}`;
  const raceClass = newspaperV4RaceClass(run);
  const raceName = text(run.race_name, "");
  const surfaceDistance = [text(run.surface, ""), run.distance_m ? `${run.distance_m}m` : ""]
    .filter(Boolean).join("");
  const track = [surfaceDistance, newspaperV4TrackCondition(run.track_condition)]
    .filter(Boolean).join(" ");
  const jockeyWeight = [
    text(run.jockey_name, ""),
    run.carried_weight_kg !== null && run.carried_weight_kg !== undefined ? `${number(run.carried_weight_kg)}` : "",
    newspaperV4BodyWeight(run)
  ].filter(Boolean).join(" ");
  const raceTime = run.time_sec !== null && run.time_sec !== undefined && Number(run.time_sec) > 0
    ? formatRaceTime(run.time_sec)
    : "";
  const timeGap = newspaperV4TimeGap(run);
  const passage = corners(run);
  const last3f = newspaperV4Last3f(run);
  const abnormal = text(run.abnormal_code, "0") !== "0"
    ? `<div class="newspaper-abnormal">${escapeHtml(finishLabel(run))}</div>`
    : "";
  const detail = hasDetail(run)
    ? `<button type="button" class="newspaper-detail-button" data-horse-index="${horseIndex}" data-run-index="${runIndex}">詳細</button>`
    : "";

  return `<div class="newspaper-run newspaper-run-v4 ${compact ? "compact" : "detailed"}">
    <div class="newspaper-run-top"><span>${escapeHtml(datePlace)}</span>${compact ? '<span class="newspaper-source-pill">簡易</span>' : ""}</div>
    <div class="newspaper-run-race-line">${raceClass ? `<strong>${escapeHtml(raceClass)}</strong>` : ""}${raceName ? `<span>${escapeHtml(raceName)}</span>` : ""}</div>
    <div class="newspaper-run-track">${escapeHtml(track || "—")}</div>
    <div class="newspaper-run-result-v4">${newspaperV4ResultLine(run)}</div>
    ${jockeyWeight ? `<div class="newspaper-run-person">${escapeHtml(jockeyWeight)}</div>` : ""}
    ${!compact && (raceTime || timeGap) ? `<div class="newspaper-run-time">${escapeHtml([raceTime, timeGap].filter(Boolean).join(" / "))}</div>` : ""}
    ${!compact && (passage || last3f) ? `<div class="newspaper-run-finish">${passage ? `<span>通 ${escapeHtml(passage)}</span>` : ""}${last3f}</div>` : ""}
    ${abnormal}${detail}
  </div>`;
}

showRunDetail = function (horse, run) {
  dialogTitle.textContent = `${text(horse.basic && horse.basic.horse_name)} / ${shortDate(run.date)} ${text(run.venue, "")}${run.race_no ? `${run.race_no}R` : ""}`;
  const notes = run.notes || {};
  const jrdb = run.jrdb_result || {};
  const noteRows = [
    ["レース", runTitle(run)],
    ["結果", newspaperV4FinishLabel(run)],
    ["パドック", notes.paddock_comment],
    ["脚元", notes.leg_comment],
    ["馬具・展開", notes.equipment_comment],
    ["レースコメント", notes.race_comment],
    ["素点", jrdb.raw_score],
    ["ペース", jrdb.pace_score],
    ["テン指数", jrdb.front_index],
    ["上がり指数", jrdb.late_index]
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  dialogBody.innerHTML = `<dl class="newspaper-detail-list">${noteRows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value))}</dd></div>`).join("")}</dl>`;
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
};

renderTable = function () {
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const historyTopHeaders = Array.from({ length: historyCount }, (_, index) => `<th class="newspaper-history-head" rowspan="2">${index + 1}走前</th>`).join("");
  const rows = horses.map((horse, horseIndex) => {
    const history = horse.history || [];
    const frameNo = horse.key ? horse.key.frame_no : null;
    const historyCells = Array.from({ length: historyCount }, (_, runIndex) =>
      `<td class="newspaper-history-cell">${newspaperV4HistoryCellHtml(history[runIndex], horseIndex, runIndex)}</td>`
    ).join("");
    return `<tr>
      <td class="newspaper-frame${newspaperV2FrameClass(frameNo)}">${escapeHtml(text(frameNo))}</td>
      <td class="newspaper-horse-no">${escapeHtml(text(horse.key && horse.key.horse_no))}</td>
      <td class="newspaper-horse-name-cell">${newspaperV4HorseNameHtml(horse)}</td>
      <td class="newspaper-basic-info">${newspaperV4BasicInfoHtml(horse)}</td>
      ${newspaperV4MarkCells(horse, horseIndex)}
      ${historyCells}
      <td class="newspaper-edge">${edgeHtml(horse)}</td>
    </tr>`;
  }).join("");

  tableWrap.innerHTML = `<table class="newspaper-table newspaper-table-v4">
    <thead>
      <tr>
        <th class="newspaper-frame" rowspan="2">枠</th>
        <th class="newspaper-horse-no" rowspan="2">馬</th>
        <th class="newspaper-horse-name-cell" rowspan="2">馬名</th>
        <th class="newspaper-basic-info" rowspan="2">基本</th>
        <th class="newspaper-mark-group-head" colspan="7">印・指数</th>
        ${historyTopHeaders}
        <th class="newspaper-edge" rowspan="2">Edge</th>
      </tr>
      <tr class="newspaper-mark-head-row">
        <th class="newspaper-mark-col mark-ability">能力</th>
        <th class="newspaper-mark-col mark-training">追切</th>
        <th class="newspaper-mark-col mark-jrdb">JR</th>
        <th class="newspaper-mark-col mark-eval">Eval</th>
        <th class="newspaper-mark-col mark-rn">RN</th>
        <th class="newspaper-mark-col mark-iluka">🐬</th>
        <th class="newspaper-mark-col mark-my">指数</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;

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

window.addEventListener("load", () => {
  if (currentBundle) renderBundle();
});

"use strict";

/* Newspaper display v6: requested seven-column order and compact JRDB race view. */

function newspaperV6ApplyMarkLayout() {
  if (!currentBundle || !tableWrap) return;
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;

  const groupHead = table.querySelector(".newspaper-mark-group-head");
  if (groupHead) groupHead.colSpan = 7;

  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow) {
    let trainingHead = headRow.querySelector(".mark-training");
    if (!trainingHead) {
      trainingHead = document.createElement("th");
      trainingHead.className = "newspaper-mark-col mark-training";
    }
    trainingHead.textContent = "追切";

    const myHead = headRow.querySelector(".mark-my");
    if (myHead) myHead.textContent = "独自";

    const orderedHeads = [
      headRow.querySelector(".mark-ability"),
      myHead,
      headRow.querySelector(".mark-eval"),
      trainingHead,
      headRow.querySelector(".mark-jrdb"),
      headRow.querySelector(".mark-rn"),
      headRow.querySelector(".mark-iluka")
    ];
    for (const cell of orderedHeads) {
      if (cell) headRow.appendChild(cell);
    }
  }

  const bodyRows = table.querySelectorAll("tbody tr");
  bodyRows.forEach((row, index) => {
    const horse = horses[index];
    if (!horse) return;

    let trainingCell = row.querySelector(".mark-training");
    if (!trainingCell) {
      trainingCell = document.createElement("td");
      trainingCell.className = "newspaper-mark-col mark-training";
    }
    const training = newspaperV4TrainingValue(horse);
    trainingCell.textContent = training.display && training.display !== "—"
      ? training.display
      : newspaperV5IntrinsicValue(null, "jrdb_base");
    trainingCell.title = training.title || "JRDB追切";

    const rnCell = row.querySelector(".mark-rn");
    const rnAddon = horse.addons && horse.addons.racenote_prediction
      ? horse.addons.racenote_prediction
      : null;
    const rnMark = text(rnAddon && rnAddon.mark, "");
    const rnComment = text(rnAddon && rnAddon.horse_short_comment, "");
    if (rnCell) {
      if (rnMark && rnComment) {
        rnCell.innerHTML = `<button type="button" class="newspaper-addon-link newspaper-racenote-button" data-horse-index="${index}" aria-label="${escapeHtml(text(horse.basic && horse.basic.horse_name, ""))}のRaceNote短評">${escapeHtml(rnMark)}</button>`;
      } else {
        rnCell.textContent = rnMark || newspaperV5IntrinsicValue(null, "racenote_prediction");
      }
    }

    const orderedCells = [
      row.querySelector(".mark-ability"),
      row.querySelector(".mark-my"),
      row.querySelector(".mark-eval"),
      trainingCell,
      row.querySelector(".mark-jrdb"),
      rnCell,
      row.querySelector(".mark-iluka")
    ];
    const anchor = row.querySelector(".newspaper-history-cell") || row.querySelector(".newspaper-edge");
    for (const cell of orderedCells) {
      if (cell && anchor) row.insertBefore(cell, anchor);
    }
  });

  tableWrap.querySelectorAll(".newspaper-racenote-button").forEach(button => {
    if (button.dataset.racenoteBound === "1") return;
    button.dataset.racenoteBound = "1";
    button.addEventListener("click", () => {
      const horse = horses[Number(button.dataset.horseIndex)];
      if (horse) newspaperV6ShowRaceNoteDetail(horse);
    });
  });
}

function newspaperV6ShowRaceNoteDetail(horse) {
  const addon = horse && horse.addons ? horse.addons.racenote_prediction : null;
  const name = text(horse && horse.basic && horse.basic.horse_name, "");
  const mark = text(addon && addon.mark, "");
  const rank = Number(addon && addon.prediction_rank);
  const confidence = text(addon && addon.confidence, "");
  const comment = text(addon && addon.horse_short_comment, "");
  dialogTitle.textContent = `${name} / RaceNote${mark ? ` ${mark}` : ""}`;
  const meta = [
    Number.isFinite(rank) && rank > 0 ? `予想順位 ${rank}位` : "",
    confidence ? `自信度 ${confidence}` : ""
  ].filter(Boolean).join(" / ");
  dialogBody.innerHTML = `${meta ? `<p class="newspaper-addon-meta">${escapeHtml(meta)}</p>` : ""}<p class="newspaper-addon-comment">${escapeHtml(comment || "単馬短評なし")}</p>`;
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function newspaperV6HorseLabel(horse) {
  const no = text(horse && horse.key && horse.key.horse_no, "");
  const name = text(horse && horse.basic && horse.basic.horse_name, "");
  return `${no} ${name}`.trim();
}

function newspaperV6ForecastOrder(horse, point) {
  const pace = horse && horse.jrdb && horse.jrdb.pace ? horse.jrdb.pace : {};
  const positions = pace.forecast_positions || {};
  const raw = positions[point];
  const value = Array.isArray(raw) ? raw[0] : (raw && typeof raw === "object" ? raw.order : null);
  const order = Number(value);
  return Number.isFinite(order) && order > 0 ? order : null;
}

function newspaperV6EscapeCandidates() {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return "なし";
  const rows = currentBundle.horses.map(horse => {
    const basic = horse.basic || {};
    const pace = horse.jrdb && horse.jrdb.pace ? horse.jrdb.pace : {};
    const ranks = pace.ranks || {};
    const symbol = text(pace.symbol, "");
    const symbolCode = text(pace.symbol_code, "");
    return {
      horse,
      style: text(basic.running_style_label, ""),
      symbol,
      symbolCode,
      midOrder: newspaperV6ForecastOrder(horse, "mid"),
      frontRank: Number(ranks.front),
      horseNo: Number(horse.key && horse.key.horse_no)
    };
  });

  let selected = rows.filter(row => row.symbol === "逃げ馬" || row.symbol === "逃馬" || row.symbolCode === "1");
  if (!selected.length) selected = rows.filter(row => row.style === "逃げ");
  if (!selected.length) {
    const validOrders = rows.map(row => row.midOrder).filter(value => value !== null);
    if (validOrders.length) {
      const bestOrder = Math.min(...validOrders);
      selected = rows.filter(row => row.midOrder === bestOrder);
    }
  }

  selected.sort((a, b) =>
    (a.midOrder ?? 999) - (b.midOrder ?? 999)
    || (Number.isFinite(a.frontRank) && a.frontRank > 0 ? a.frontRank : 999)
      - (Number.isFinite(b.frontRank) && b.frontRank > 0 ? b.frontRank : 999)
    || (Number.isFinite(a.horseNo) ? a.horseNo : 999)
      - (Number.isFinite(b.horseNo) ? b.horseNo : 999)
  );
  return selected.length ? selected.map(row => newspaperV6HorseLabel(row.horse)).join(" / ") : "なし";
}

function newspaperV6LateCandidates(limit = 3) {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return "なし";
  const rows = currentBundle.horses.map(horse => {
    const pace = horse.jrdb && horse.jrdb.pace ? horse.jrdb.pace : {};
    const indices = pace.indices || {};
    const ranks = pace.ranks || {};
    return {
      horse,
      value: Number(indices.late),
      rank: Number(ranks.late),
      horseNo: Number(horse.key && horse.key.horse_no)
    };
  }).filter(row => Number.isFinite(row.value));

  rows.sort((a, b) =>
    (Number.isFinite(a.rank) && a.rank > 0 ? a.rank : 999)
      - (Number.isFinite(b.rank) && b.rank > 0 ? b.rank : 999)
    || b.value - a.value
    || (Number.isFinite(a.horseNo) ? a.horseNo : 999)
      - (Number.isFinite(b.horseNo) ? b.horseNo : 999)
  );
  const selected = rows.slice(0, limit);
  return selected.length ? selected.map(row => newspaperV6HorseLabel(row.horse)).join(" / ") : "なし";
}

function newspaperV6LongshotCandidates() {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return "なし";
  const selected = currentBundle.horses.filter(horse => {
    const marks = horse.jrdb && horse.jrdb.marks ? horse.jrdb.marks : {};
    return Boolean(text(marks.longshot, ""));
  }).sort((a, b) => Number(a.key && a.key.horse_no) - Number(b.key && b.key.horse_no));
  return selected.length ? selected.map(newspaperV6HorseLabel).join(" / ") : "なし";
}

function newspaperV6RenderRaceInfo() {
  const target = document.getElementById("newspaper-race-notes");
  if (!target || !currentBundle) return;
  const notes = currentBundle.race_notes || {};
  const card = document.getElementById("newspaper-notes-card");
  const cardTitle = card && card.querySelector("h2");
  if (cardTitle) cardTitle.textContent = "レース情報・短評";

  const jrdbReady = newspaperV5SourceState("jrdb_base") === "READY";
  const jrdbMarkup = jrdbReady
    ? [
        ["予想ペース", newspaperV5ForecastPace() || "なし"],
        ["逃げ候補", newspaperV6EscapeCandidates()],
        ["上がり候補", newspaperV6LateCandidates(3)],
        ["激走候補", newspaperV6LongshotCandidates()]
      ].map(([label, value]) => newspaperV5RaceMetric(label, value)).join("")
    : `<div class="empty-state newspaper-note-empty">JRDBレース情報は未取得です。</div>`;

  const rnState = newspaperV5SourceState("racenote_prediction");
  const rnComment = text(notes.racenote_short_comment, "");
  const rnMarkup = rnComment
    ? `<p class="newspaper-v5-rn-comment">${escapeHtml(rnComment)}</p>`
    : (newspaperV5ReadyBlank(rnState)
      ? `<div class="empty-state newspaper-note-empty">短評なし</div>`
      : `<div class="empty-state newspaper-note-empty">RaceNote未取得</div>`);

  target.innerHTML = `
    <section class="newspaper-v5-note-section">
      <h3>JRDB レース情報</h3>
      <div class="newspaper-v5-race-metrics">${jrdbMarkup}</div>
    </section>
    <section class="newspaper-v5-note-section">
      <h3>RaceNote短評</h3>
      ${rnMarkup}
    </section>`;
}

const newspaperV6BaseRenderTable = renderTable;
renderTable = function () {
  newspaperV6BaseRenderTable();
  newspaperV6ApplyMarkLayout();
};

const newspaperV6BaseRenderBundle = renderBundle;
renderBundle = function () {
  newspaperV6BaseRenderBundle();
  newspaperV6RenderRaceInfo();
};

window.addEventListener("load", () => {
  if (currentBundle) {
    newspaperV6ApplyMarkLayout();
    newspaperV6RenderRaceInfo();
  }
});

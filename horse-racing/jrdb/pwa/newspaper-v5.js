"use strict";

/* Newspaper display v5: requested mark ordering/state semantics and split race notes. */

function newspaperV5SourceState(sourceKey) {
  const status = currentBundle && currentBundle.metadata && currentBundle.metadata.source_status;
  const state = status && status[sourceKey] ? text(status[sourceKey].state, "") : "";
  return state || "PENDING";
}

function newspaperV5ReadyBlank(state) {
  return state === "READY" || state === "NOT_APPLICABLE";
}

function newspaperV5AddonValue(addon, sourceKey, keys) {
  const state = newspaperV5SourceState(sourceKey);
  if (addon && typeof addon === "object") {
    for (const key of keys) {
      const value = addon[key];
      if (value !== null && value !== undefined && value !== "") return text(value);
    }
    return newspaperV5ReadyBlank(state) ? "" : "-";
  }
  return newspaperV5ReadyBlank(state) ? "" : "-";
}

function newspaperV5IntrinsicValue(value, sourceKey) {
  if (value !== null && value !== undefined && value !== "") return text(value);
  return newspaperV5ReadyBlank(newspaperV5SourceState(sourceKey)) ? "" : "-";
}

function newspaperV5ApplyMarkLayout() {
  if (!currentBundle || !tableWrap) return;
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;

  const groupHead = table.querySelector(".newspaper-mark-group-head");
  if (groupHead) groupHead.colSpan = 6;

  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow) {
    const head = {
      ability: headRow.querySelector(".mark-ability"),
      training: headRow.querySelector(".mark-training"),
      my: headRow.querySelector(".mark-my"),
      eval: headRow.querySelector(".mark-eval"),
      jrdb: headRow.querySelector(".mark-jrdb"),
      rn: headRow.querySelector(".mark-rn"),
      iluka: headRow.querySelector(".mark-iluka")
    };
    if (head.training) head.training.remove();
    if (head.ability) head.ability.textContent = "能力";
    if (head.my) head.my.textContent = "独自指数";
    if (head.eval) head.eval.textContent = "Eval";
    if (head.jrdb) head.jrdb.textContent = "JRDB";
    if (head.rn) head.rn.textContent = "RN";
    if (head.iluka) head.iluka.textContent = "🐬";
    for (const cell of [head.ability, head.my, head.eval, head.jrdb, head.rn, head.iluka]) {
      if (cell) headRow.appendChild(cell);
    }
  }

  const bodyRows = table.querySelectorAll("tbody tr");
  bodyRows.forEach((row, index) => {
    const horse = horses[index];
    if (!horse) return;
    const jrdb = horse.jrdb || {};
    const ability = jrdb.ability || {};
    const marks = jrdb.marks || {};
    const addons = horse.addons || {};
    const cells = {
      ability: row.querySelector(".mark-ability"),
      training: row.querySelector(".mark-training"),
      my: row.querySelector(".mark-my"),
      eval: row.querySelector(".mark-eval"),
      jrdb: row.querySelector(".mark-jrdb"),
      rn: row.querySelector(".mark-rn"),
      iluka: row.querySelector(".mark-iluka")
    };
    if (cells.training) cells.training.remove();

    if (cells.ability) {
      const value = ability.idm;
      cells.ability.textContent = value !== null && value !== undefined && value !== ""
        ? number(value)
        : newspaperV5IntrinsicValue(null, "jrdb_base");
    }
    if (cells.my) {
      cells.my.textContent = newspaperV5AddonValue(addons.my_index, "my_index", ["index", "score", "value", "display_value"]);
    }
    if (cells.eval) {
      cells.eval.textContent = newspaperV5AddonValue(addons.eval, "eval", ["eval", "score", "index", "value", "display_value"]);
    }
    if (cells.jrdb) {
      cells.jrdb.textContent = newspaperV5IntrinsicValue(marks.total, "jrdb_base");
    }
    if (cells.rn) {
      cells.rn.textContent = newspaperV5AddonValue(addons.racenote_prediction, "racenote_prediction", ["mark", "symbol", "prediction_mark", "value"]);
    }
    if (cells.iluka) {
      const state = newspaperV5SourceState("keibailuka");
      const comment = newspaperV2IlukaComment(addons.keibailuka);
      const button = cells.iluka.querySelector(".newspaper-iluka-button");
      if (addons.keibailuka && comment && button) {
        button.textContent = "○";
      } else if (addons.keibailuka) {
        cells.iluka.textContent = "○";
      } else {
        cells.iluka.textContent = newspaperV5ReadyBlank(state) ? "" : "-";
      }
    }

    const anchor = row.querySelector(".newspaper-history-cell") || row.querySelector(".newspaper-edge");
    for (const cell of [cells.ability, cells.my, cells.eval, cells.jrdb, cells.rn, cells.iluka]) {
      if (cell && anchor) row.insertBefore(cell, anchor);
    }
  });
}

function newspaperV5TopIndex(kind) {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return null;
  const rows = currentBundle.horses.map(horse => {
    const pace = horse.jrdb && horse.jrdb.pace ? horse.jrdb.pace : {};
    const indices = pace.indices || {};
    const ranks = pace.ranks || {};
    return {
      horse,
      value: indices[kind],
      rank: Number(ranks[kind])
    };
  }).filter(row => row.value !== null && row.value !== undefined && row.value !== "");
  if (!rows.length) return null;
  rows.sort((a, b) => {
    const ar = Number.isFinite(a.rank) && a.rank > 0 ? a.rank : 999;
    const br = Number.isFinite(b.rank) && b.rank > 0 ? b.rank : 999;
    return ar - br || Number(b.value) - Number(a.value);
  });
  const top = rows[0];
  const no = text(top.horse.key && top.horse.key.horse_no, "");
  const name = text(top.horse.basic && top.horse.basic.horse_name, "");
  return `${no} ${name} ${number(top.value)}`.trim();
}

function newspaperV5ForecastPace() {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return null;
  const values = [...new Set(currentBundle.horses.map(horse => {
    const pace = horse.jrdb && horse.jrdb.pace ? horse.jrdb.pace : {};
    return text(pace.forecast_pace, "");
  }).filter(Boolean))];
  if (!values.length) return null;
  return values.join(" / ");
}

function newspaperV5LongshotMarks() {
  if (!currentBundle || !Array.isArray(currentBundle.horses)) return null;
  const targets = currentBundle.horses.filter(horse => {
    const marks = horse.jrdb && horse.jrdb.marks ? horse.jrdb.marks : {};
    return Boolean(text(marks.longshot, ""));
  }).map(horse => `${text(horse.key && horse.key.horse_no, "")} ${text(horse.basic && horse.basic.horse_name, "")}`.trim());
  return targets.length ? targets.join(" / ") : "なし";
}

function newspaperV5RaceMetric(label, value) {
  return `<div class="newspaper-v5-race-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(text(value, "—"))}</strong></div>`;
}

function newspaperV5RenderRaceInfo() {
  const target = document.getElementById("newspaper-race-notes");
  if (!target || !currentBundle) return;
  const notes = currentBundle.race_notes || {};
  const card = document.getElementById("newspaper-notes-card");
  const cardTitle = card && card.querySelector("h2");
  if (cardTitle) cardTitle.textContent = "レース情報・短評";

  const jrdbReady = newspaperV5SourceState("jrdb_base") === "READY";
  let jrdbMarkup = "";
  if (jrdbReady) {
    const existingItems = Array.isArray(notes.items) ? notes.items : [];
    const metrics = [];
    for (const item of existingItems) {
      if (item && item.label && item.value !== null && item.value !== undefined && item.value !== "") {
        metrics.push(newspaperV5RaceMetric(text(item.label), item.unit ? `${text(item.value)} ${text(item.unit)}` : item.value));
      }
    }
    const derived = [
      ["ペース予測", newspaperV5ForecastPace()],
      ["テン指数1位", newspaperV5TopIndex("front")],
      ["ペース指数1位", newspaperV5TopIndex("pace")],
      ["上がり指数1位", newspaperV5TopIndex("late")],
      ["激走印", newspaperV5LongshotMarks()]
    ];
    const existingLabels = new Set(existingItems.map(item => text(item && item.label, "")));
    for (const [label, value] of derived) {
      if (!existingLabels.has(label) && value !== null && value !== undefined && value !== "") {
        metrics.push(newspaperV5RaceMetric(label, value));
      }
    }
    jrdbMarkup = metrics.length
      ? metrics.join("")
      : `<div class="empty-state newspaper-note-empty">JRDBレース指標は取得済みですが表示対象がありません。</div>`;
  } else {
    jrdbMarkup = `<div class="empty-state newspaper-note-empty">JRDBレース指標は未取得です。</div>`;
  }

  const rnState = newspaperV5SourceState("racenote_prediction");
  const rnComment = text(notes.racenote_short_comment, "");
  const rnMarkup = rnComment
    ? `<p class="newspaper-v5-rn-comment">${escapeHtml(rnComment)}</p>`
    : (newspaperV5ReadyBlank(rnState)
      ? `<div class="empty-state newspaper-note-empty">短評なし</div>`
      : `<div class="empty-state newspaper-note-empty">RaceNote未取得</div>`);

  target.innerHTML = `
    <section class="newspaper-v5-note-section">
      <h3>JRDB指数</h3>
      <div class="newspaper-v5-race-metrics">${jrdbMarkup}</div>
    </section>
    <section class="newspaper-v5-note-section">
      <h3>RaceNote短評</h3>
      ${rnMarkup}
    </section>`;
}

const newspaperV5BaseRenderTable = renderTable;
renderTable = function () {
  newspaperV5BaseRenderTable();
  newspaperV5ApplyMarkLayout();
};

const newspaperV5BaseRenderBundle = renderBundle;
renderBundle = function () {
  newspaperV5BaseRenderBundle();
  newspaperV5RenderRaceInfo();
};

window.addEventListener("load", () => {
  if (currentBundle) {
    newspaperV5ApplyMarkLayout();
    newspaperV5RenderRaceInfo();
  }
});

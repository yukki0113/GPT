"use strict";

/* Consume the supplied v0.5 addon without recalculating Edge conditions. */
const NEWSPAPER_V05_TIER_TEXT = {
  CONFIRMED: "再現確認",
  STILL_PLAUSIBLE: "一部維持",
  INSUFFICIENT_OOS: "観測不足",
  DECAYING: "低下傾向",
  CONTRADICTED: "反証傾向"
};

function newspaperV05Ids(horse) {
  const status = currentBundle && currentBundle.metadata && currentBundle.metadata.source_status;
  if (!status || !status.edge_v05 || !["PARTIAL", "READY"].includes(status.edge_v05.state)) return [];
  const addon = horse && horse.addons && horse.addons.edge_v05;
  const dictionary = currentBundle.edge_v05_candidates || {};
  if (!addon || !Array.isArray(addon.candidate_ids)) return [];
  return addon.candidate_ids.filter(id => typeof id === "string" && Object.prototype.hasOwnProperty.call(dictionary, id));
}

function newspaperV05Metric(n, value, kind) {
  if (!Number.isFinite(Number(n)) || Number(n) === 0) return "未観測";
  if (value === null || value === undefined || value === "") return "算出不可";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "算出不可";
  return `${(kind === "rate" ? numeric * 100 : numeric).toFixed(1)}%`;
}

function newspaperV05Detail(item) {
  const discovery = item.discovery || {};
  const oos = item.oos_2026 || {};
  const tier = NEWSPAPER_V05_TIER_TEXT[item.oos_tier] || "未分類";
  const fields = [
    ["該当条件", item.condition_text],
    ["2026診断", tier],
    ["2024–25", `${discovery.n ?? 0}頭 / 複勝率 ${newspaperV05Metric(discovery.n, discovery.place_rate, "rate")} / 複勝ROI ${newspaperV05Metric(discovery.n, discovery.place_roi, "roi")}`],
    ["2026", `${oos.n ?? 0}頭 / 複勝率 ${newspaperV05Metric(oos.n, oos.place_rate, "rate")} / 複勝ROI ${newspaperV05Metric(oos.n, oos.place_roi, "roi")}`],
    ["系列", item.family]
  ];
  return `<section class="newspaper-v05-detail"><dl class="newspaper-detail-list">${fields.map(([label, value]) =>
    `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value, ""))}</dd></div>`).join("")}</dl></section>`;
}

function newspaperV05ShowDetail(horse) {
  const ids = newspaperV05Ids(horse);
  if (!ids.length) return;
  const dictionary = currentBundle.edge_v05_candidates;
  dialogTitle.textContent = `${text(horse.basic && horse.basic.horse_name)} / Edge ${ids.length}件`;
  const lead = ids.slice(0, 2).map(id => newspaperV05Detail(dictionary[id])).join("");
  const other = ids.length > 2
    ? `<details class="newspaper-v05-other"><summary>その他のEdge（${ids.length - 2}件）</summary>${ids.slice(2).map(id => newspaperV05Detail(dictionary[id])).join("")}</details>`
    : "";
  dialogBody.innerHTML = lead + other + '<p class="newspaper-v05-disclaimer">2026診断は過去評価の説明で、正式な予測等級ではありません。複勝ROIは過去の条件別実績であり、この馬の予測勝率・推奨馬券・予想印ではありません。</p>';
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function newspaperV05ApplyColumn() {
  if (!currentBundle || !Array.isArray(currentBundle.horses) || !tableWrap) return;
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;

  // v4 renders the legacy special memo column. Keep its data, hide its cells.
  table.querySelectorAll("thead th.newspaper-edge, tbody td.newspaper-edge").forEach(cell => cell.remove());
  const groupHead = table.querySelector(".newspaper-mark-group-head");
  const firstHeadRow = groupHead && groupHead.parentElement;
  if (firstHeadRow && !firstHeadRow.querySelector("th.newspaper-edge-v05")) {
    const head = document.createElement("th");
    head.className = "newspaper-edge-v05";
    head.rowSpan = 2;
    head.textContent = "Edge";
    const historyHead = firstHeadRow.querySelector(".newspaper-history-head");
    if (historyHead) firstHeadRow.insertBefore(head, historyHead);
    else firstHeadRow.appendChild(head);
  }

  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  table.querySelectorAll("tbody tr").forEach((row, index) => {
    const horse = horses[index];
    if (!horse || row.querySelector("td.newspaper-edge-v05")) return;
    const cell = document.createElement("td");
    cell.className = "newspaper-edge-v05";
    if (newspaperV05Ids(horse).length) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "newspaper-addon-link newspaper-edge-v05-button";
      button.textContent = "○";
      button.setAttribute("aria-label", `${text(horse.basic && horse.basic.horse_name)}のEdge詳細`);
      button.addEventListener("click", () => newspaperV05ShowDetail(horse));
      cell.appendChild(button);
    }
    const history = row.querySelector(".newspaper-history-cell");
    if (history) row.insertBefore(cell, history);
    else row.appendChild(cell);
  });
}

const newspaperV05RenderTableBase = renderTable;
renderTable = function () {
  newspaperV05RenderTableBase();
  newspaperV05ApplyColumn();
};

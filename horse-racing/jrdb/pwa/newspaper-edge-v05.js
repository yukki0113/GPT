"use strict";

/* Consume the supplied v0.5 addon without recalculating Edge conditions. */
function newspaperV05Ids(horse) {
  const status = currentBundle && currentBundle.metadata && currentBundle.metadata.source_status;
  if (!status || !status.edge_v05 || !["PARTIAL", "READY"].includes(status.edge_v05.state)) return [];
  const addon = horse && horse.addons && horse.addons.edge_v05;
  const dictionary = currentBundle.edge_v05_candidates || {};
  if (!addon || !Array.isArray(addon.candidate_ids)) return [];
  return addon.candidate_ids.filter(id => typeof id === "string" && Object.prototype.hasOwnProperty.call(dictionary, id));
}

function newspaperV05Count(value) {
  return Number.isInteger(Number(value)) && value !== null && value !== "" && Number(value) >= 0
    ? `${Number(value)}頭` : "未提供";
}

function newspaperV05Roi(n, value) {
  if (n === null || n === undefined || n === "") return "算出不可";
  if (!Number.isInteger(Number(n)) || Number(n) < 0) return "算出不可";
  if (Number(n) === 0) return "未観測";
  if (value === null || value === undefined || value === "") return "算出不可";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "算出不可";
  return `${numeric.toFixed(1)}%`;
}

function newspaperV05Detail(item) {
  const discovery = item.discovery || {};
  const oos = item.oos_2026 || {};
  const fields = [
    ["該当条件", item.condition_text],
    ["2024–25", `${newspaperV05Count(discovery.n)} / 複勝ROI ${newspaperV05Roi(discovery.n, discovery.place_roi)}`],
    ["2026", `${newspaperV05Count(oos.n)} / 複勝ROI ${newspaperV05Roi(oos.n, oos.place_roi)}`]
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
  dialogBody.innerHTML = lead + other + '<p class="newspaper-v05-disclaimer">過去の条件別実績であり、今回の予測成績ではありません。</p>';
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
  const markRow = table.querySelector(".newspaper-mark-head-row");
  if (markRow && !markRow.querySelector("th.newspaper-edge-v05")) {
    const head = document.createElement("th");
    head.className = "newspaper-mark-col mark-edge newspaper-edge-v05";
    head.textContent = "Edge";
    markRow.appendChild(head);
  }
  if (groupHead && markRow) groupHead.colSpan = markRow.querySelectorAll("th.newspaper-mark-col").length;

  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  table.querySelectorAll("tbody tr").forEach((row, index) => {
    const horse = horses[index];
    if (!horse || row.querySelector("td.newspaper-edge-v05")) return;
    const cell = document.createElement("td");
    cell.className = "newspaper-mark-col mark-edge newspaper-edge-v05";
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

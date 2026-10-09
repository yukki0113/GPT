"use strict";

/* Preview only. The public newspaper keeps its current renderer and source. */
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
  if (!currentBundle || !tableWrap) return;
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;
  table.querySelectorAll("thead th.newspaper-edge, tbody td.newspaper-edge").forEach(cell => cell.remove());
  const groupHead = table.querySelector(".newspaper-mark-group-head");
  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow && !headRow.querySelector(".mark-edge")) {
    const head = document.createElement("th");
    head.className = "newspaper-mark-col mark-edge";
    head.textContent = "Edge";
    headRow.appendChild(head);
  }
  if (groupHead && headRow) groupHead.colSpan = headRow.querySelectorAll("th.newspaper-mark-col").length;
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  table.querySelectorAll("tbody tr").forEach((row, index) => {
    const horse = horses[index];
    if (!horse) return;
    if (row.querySelector("td.mark-edge")) return;
    const cell = document.createElement("td");
    cell.className = "newspaper-mark-col mark-edge";
    if (newspaperV05Ids(horse).length) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "newspaper-addon-link newspaper-v05-button";
      button.textContent = "○";
      button.setAttribute("aria-label", `${text(horse.basic && horse.basic.horse_name)}のEdge詳細`);
      button.addEventListener("click", () => newspaperV05ShowDetail(horse));
      cell.appendChild(button);
    }
    const anchor = row.querySelector(".newspaper-history-cell");
    if (anchor) row.insertBefore(cell, anchor);
    else row.appendChild(cell);
  });
}

const newspaperV05RenderTableBase = renderTable;
renderTable = function () {
  newspaperV05RenderTableBase();
  newspaperV05ApplyColumn();
};

dayPackageSummary = function (value) {
  if (!value || !value.manifest) return "新聞データなし";
  const sources = value.manifest.source_status || {};
  const evalState = sources.eval && sources.eval.state === "READY" ? "Eval○" : "Eval—";
  const rnState = sources.racenote_prediction && sources.racenote_prediction.state === "READY" ? "RN○" : "RN—";
  const ilukaState = sources.keibailuka && sources.keibailuka.state === "READY" ? "🐬○" : "🐬—";
  const count = Array.isArray(value.races) ? value.races.length : 0;
  const v05 = sources.edge_v05 ? sources.edge_v05.state : "未接続";
  return `${value.manifest.date} / ${count}R / ${evalState} / ${rnState} / ${ilukaState} / v0.5 preview ${v05}`;
};

refreshPublishedDay = async function () {
  if (!currentDayPackage) dayStatus.textContent = "v0.5 preview packageを手動で取り込んでください。";
  return false;
};

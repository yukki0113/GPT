"use strict";

/* Newspaper display v7: EdgeDB is exposed only as the user-facing 特注メモ column. */

function newspaperV7Memos(horse) {
  if (Array.isArray(horse.special_memos)) return horse.special_memos;
  if (Array.isArray(horse.edge_matches)) return horse.edge_matches;
  return [];
}

function newspaperV7Percent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return `${(numeric * 100).toFixed(1)}%`;
}

function newspaperV7RawConditions(memo) {
  let evidence = {};
  if (memo && memo.evidence && typeof memo.evidence === "object") {
    evidence = memo.evidence;
  }

  let conditions = {};
  if (evidence.conditions && typeof evidence.conditions === "object") {
    conditions = evidence.conditions;
  }

  const values = [];
  for (const sectionName of ["anchor", "modifiers"]) {
    const section = conditions[sectionName];
    if (!section || typeof section !== "object") continue;
    for (const [key, value] of Object.entries(section)) {
      if (value === null || value === undefined || value === "") continue;
      values.push(`${key}=${value}`);
    }
  }
  return values.join(" / ");
}

function newspaperV7ShowEdgeDetail(horse, memo) {
  const horseName = text(horse && horse.basic && horse.basic.horse_name);

  let evidence = {};
  if (memo && memo.evidence && typeof memo.evidence === "object") {
    evidence = memo.evidence;
  }

  let conditionText = newspaperV7RawConditions(memo);
  if (memo && memo.condition_text) {
    conditionText = memo.condition_text;
  }

  const rows = [
    ["特注メモ", memo && (memo.memo_text || memo.display_text)],
    ["条件", conditionText],
    ["複勝率", newspaperV7Percent(evidence.place_rate)],
    ["基準複勝率", newspaperV7Percent(evidence.baseline_place_rate)],
    ["信頼度", memo && memo.confidence_band],
    ["照合条件(RAW)", newspaperV7RawConditions(memo)]
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  dialogTitle.textContent = `${horseName} / 特注メモ`;
  dialogBody.innerHTML = `<dl class="newspaper-detail-list">${
    rows.map(([label, value]) =>
      `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value))}</dd></div>`
    ).join("")
  }</dl>`;

  if (typeof detailDialog.showModal === "function") {
    detailDialog.showModal();
  } else {
    detailDialog.setAttribute("open", "");
  }
}

edgeHtml = function (horse) {
  const memos = newspaperV7Memos(horse);
  if (!memos.length) return "—";

  let horseNo = "";
  if (horse && horse.key) {
    horseNo = text(horse.key.horse_no, "");
  }

  return memos.map(memo => {
    let value = memo && memo.display_text;
    if (memo && memo.memo_text) {
      value = memo.memo_text;
    }

    let edgeId = "";
    if (memo && memo.edge_id) {
      edgeId = text(memo.edge_id, "");
    }

    if (!edgeId) {
      return `<div class="newspaper-edge-item">${escapeHtml(text(value))}</div>`;
    }

    return `<div class="newspaper-edge-item"><button type="button" class="newspaper-addon-link newspaper-edge-link" data-horse-no="${escapeHtml(horseNo)}" data-edge-id="${escapeHtml(edgeId)}">${escapeHtml(text(value))}</button></div>`;
  }).join("");
};

const newspaperV7RenderTableBase = renderTable;
renderTable = function () {
  newspaperV7RenderTableBase();

  const header = tableWrap.querySelector("thead th.newspaper-edge");
  if (header) header.textContent = "特注メモ";

  tableWrap.querySelectorAll(".newspaper-edge-link").forEach(button => {
    button.addEventListener("click", () => {
      const horseNo = Number(button.dataset.horseNo);
      const edgeId = button.dataset.edgeId || "";
      const horse = currentBundle.horses.find(item =>
        Number(item && item.key && item.key.horse_no) === horseNo
      );
      if (!horse) return;

      const memo = newspaperV7Memos(horse).find(item =>
        text(item && item.edge_id, "") === edgeId
      );
      if (memo) newspaperV7ShowEdgeDetail(horse, memo);
    });
  });
};

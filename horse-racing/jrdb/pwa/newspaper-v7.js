"use strict";

/* Newspaper display v7: EdgeDB is exposed only as the user-facing 特注メモ column. */

edgeHtml = function (horse) {
  const memos = Array.isArray(horse.special_memos)
    ? horse.special_memos
    : (Array.isArray(horse.edge_matches) ? horse.edge_matches : []);
  if (!memos.length) return "—";
  return memos.map(memo => {
    const value = memo && memo.memo_text ? memo.memo_text : memo && memo.display_text;
    return `<div class="newspaper-edge-item">${escapeHtml(text(value))}</div>`;
  }).join("");
};

const newspaperV7RenderTableBase = renderTable;
renderTable = function () {
  newspaperV7RenderTableBase();
  const header = tableWrap.querySelector("thead th.newspaper-edge");
  if (header) header.textContent = "特注メモ";
};

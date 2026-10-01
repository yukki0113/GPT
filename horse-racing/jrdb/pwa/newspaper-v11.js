"use strict";

/* Newspaper display v11: reader-facing RaceReviewDB recommendation comments. */

function newspaperV11RRDBAddon(horse) {
  if (!horse || !horse.addons || !horse.addons.rrdb_recommendation) return null;
  const addon = horse.addons.rrdb_recommendation;
  return addon && typeof addon === "object" ? addon : null;
}

function newspaperV11RRDBComment(horse) {
  const addon = newspaperV11RRDBAddon(horse);
  return addon ? text(addon.comment, "").trim() : "";
}

function newspaperV11ShowRRDBDetail(horse) {
  const addon = newspaperV11RRDBAddon(horse);
  const name = text(horse && horse.basic && horse.basic.horse_name, "");
  const comment = newspaperV11RRDBComment(horse);
  dialogTitle.textContent = `${name} / RaceReviewDB`;
  dialogBody.innerHTML = `<p class="newspaper-addon-comment">${escapeHtml(comment || "短評なし")}</p>`;
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function newspaperV11ApplyRRDBColumn() {
  if (!currentBundle || !Array.isArray(currentBundle.horses) || !tableWrap) return;
  const horses = [...currentBundle.horses]
    .sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;

  const groupHead = table.querySelector(".newspaper-mark-group-head");
  if (groupHead) groupHead.colSpan = 8;

  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow && !headRow.querySelector(".mark-rrdb")) {
    const th = document.createElement("th");
    th.className = "newspaper-mark-col mark-rrdb";
    th.textContent = "RRDB";
    const rnHead = headRow.querySelector(".mark-rn");
    if (rnHead && rnHead.nextSibling) headRow.insertBefore(th, rnHead.nextSibling);
    else headRow.appendChild(th);
  }

  const rows = table.querySelectorAll("tbody tr");
  rows.forEach((row, index) => {
    const horse = horses[index];
    if (!horse) return;
    let cell = row.querySelector(".mark-rrdb");
    if (!cell) {
      cell = document.createElement("td");
      cell.className = "newspaper-mark-col mark-rrdb";
      const rnCell = row.querySelector(".mark-rn");
      if (rnCell && rnCell.nextSibling) row.insertBefore(cell, rnCell.nextSibling);
      else {
        const anchor = row.querySelector(".newspaper-history-cell") || row.querySelector(".newspaper-edge");
        if (anchor) row.insertBefore(cell, anchor);
      }
    }
    const comment = newspaperV11RRDBComment(horse);
    if (comment) {
      cell.innerHTML = `<button type="button" class="newspaper-addon-link newspaper-rrdb-button" data-horse-index="${index}" aria-label="${escapeHtml(text(horse.basic && horse.basic.horse_name, ""))}のRaceReviewDB短評">推</button>`;
      cell.title = comment;
    } else {
      cell.textContent = "—";
      cell.removeAttribute("title");
    }
  });

  tableWrap.querySelectorAll(".newspaper-rrdb-button").forEach(button => {
    if (button.dataset.rrdbBound === "1") return;
    button.dataset.rrdbBound = "1";
    button.addEventListener("click", () => {
      const horse = horses[Number(button.dataset.horseIndex)];
      if (horse) newspaperV11ShowRRDBDetail(horse);
    });
  });
}

const newspaperV11BaseRenderTable = renderTable;
renderTable = function () {
  newspaperV11BaseRenderTable();
  newspaperV11ApplyRRDBColumn();
};

const newspaperV11BaseDayPackageSummary = dayPackageSummary;
dayPackageSummary = function (value) {
  const base = newspaperV11BaseDayPackageSummary(value);
  if (!value || !value.manifest) return base;
  const sources = value.manifest.source_status || {};
  const state = sources.rrdb_recommendation && sources.rrdb_recommendation.state === "READY"
    ? "RRDB○"
    : "RRDB—";
  return `${base} / ${state}`;
};

window.addEventListener("load", () => {
  if (currentBundle) newspaperV11ApplyRRDBColumn();
});

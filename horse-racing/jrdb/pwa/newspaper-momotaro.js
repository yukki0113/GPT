"use strict";

/* Personal newspaper extension: add Momotaro marks and race comments without removing private JRDB/Eval content. */

const PERSONAL_MOMOTARO_CONTRIBUTORS = [
  { key: "ryota", label: "りょーた", short: "りょ" },
  { key: "oji", label: "おーじ", short: "王子" }
];

const PERSONAL_MOMOTARO_KENSHOW_JRDB_MARKS = new Set(["◎", "○", "▲"]);

function personalMomotaroPrediction(horse, key) {
  const addons = horse && horse.addons ? horse.addons : {};
  const momotaro = addons.momotaro || {};
  return momotaro[key] || {};
}

function personalMomotaroKenshowDisplay(horse) {
  const value = personalMomotaroPrediction(horse, "kenshow");
  const manualMark = text(value.mark, "");
  const manualBlank = text(value.tag, "") === "手動無印";
  const comment = text(value.comment, "");
  const jrdb = horse && horse.jrdb ? horse.jrdb : {};
  const marks = jrdb.marks || {};
  const jrdbMark = text(marks.total, "");
  const fallback = PERSONAL_MOMOTARO_KENSHOW_JRDB_MARKS.has(jrdbMark) ? jrdbMark : "";
  return manualBlank ? "" : (manualMark || fallback || (comment ? "注" : ""));
}

function personalMomotaroDisplayMark(horse, contributor) {
  const value = personalMomotaroPrediction(horse, contributor.key);
  if (contributor.key === "kenshow") return personalMomotaroKenshowDisplay(horse);
  return text(value.mark, "");
}

function personalMomotaroShowDetail(horse, contributor) {
  const value = personalMomotaroPrediction(horse, contributor.key);
  const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
  const mark = personalMomotaroDisplayMark(horse, contributor);
  const confidence = text(value.confidence, "");
  const tag = text(value.tag, "");
  const comment = text(value.comment, "");
  const meta = [
    confidence ? "自信度 " + confidence : "",
    value.review_horse === true && contributor.key === "ryota" ? "特注" : "",
    tag
  ].filter(Boolean).join(" / ");

  dialogTitle.textContent = horseName + " / " + contributor.label + (mark ? " " + mark : "");
  dialogBody.innerHTML =
    (meta ? '<p class="newspaper-addon-meta">' + escapeHtml(meta) + '</p>' : "") +
    (comment ? '<p class="newspaper-addon-comment">' + escapeHtml(comment) + '</p>' : "");

  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function personalMomotaroCell(horse, horseIndex, contributor) {
  const value = personalMomotaroPrediction(horse, contributor.key);
  const display = personalMomotaroDisplayMark(horse, contributor);
  const comment = text(value.comment, "");
  // 自信度・タグ・review_horseだけではモーダル化しない。馬単位の本文がある場合だけ開く。
  const hasDetail = Boolean(comment.trim());

  if (hasDetail) {
    return '<td class="newspaper-mark-col mark-momotaro mark-' + contributor.key + '">' +
      '<button type="button" class="newspaper-addon-link personal-momotaro-button" ' +
      'data-horse-index="' + horseIndex + '" data-contributor-key="' + contributor.key + '">' +
      escapeHtml(display) + '</button></td>';
  }
  return '<td class="newspaper-mark-col mark-momotaro mark-' + contributor.key + '">' +
    escapeHtml(display) + '</td>';
}

function personalMomotaroApplyMarks() {
  if (!currentBundle || !Array.isArray(currentBundle.horses) || !tableWrap) return;
  const table = tableWrap.querySelector(".newspaper-table-v4");
  if (!table) return;
  const horses = [...currentBundle.horses].sort(function (a, b) {
    return Number(a && a.key && a.key.horse_no) - Number(b && b.key && b.key.horse_no);
  });

  const groupHead = table.querySelector(".newspaper-mark-group-head");
  if (groupHead) groupHead.colSpan = 8;

  const headRow = table.querySelector(".newspaper-mark-head-row");
  if (headRow && !headRow.querySelector(".mark-ryota")) {
    const ilukaHead = headRow.querySelector(".mark-iluka");
    PERSONAL_MOMOTARO_CONTRIBUTORS.forEach(function (contributor) {
      const th = document.createElement("th");
      th.className = "newspaper-mark-col mark-momotaro mark-" + contributor.key;
      th.textContent = contributor.short;
      if (ilukaHead) headRow.insertBefore(th, ilukaHead);
      else headRow.appendChild(th);
    });
  }

  table.querySelectorAll("tbody tr").forEach(function (row, index) {
    const horse = horses[index];
    if (!horse || row.querySelector(".mark-ryota")) return;
    const ilukaCell = row.querySelector(".mark-iluka");
    const anchor = ilukaCell || row.querySelector(".newspaper-history-cell") || row.querySelector(".newspaper-edge");
    PERSONAL_MOMOTARO_CONTRIBUTORS.forEach(function (contributor) {
      const holder = document.createElement("tbody");
      holder.innerHTML = "<tr>" + personalMomotaroCell(horse, index, contributor) + "</tr>";
      const cell = holder.querySelector("td");
      if (cell && anchor) row.insertBefore(cell, anchor);
    });
  });

  table.querySelectorAll(".personal-momotaro-button").forEach(function (button) {
    button.addEventListener("click", function () {
      const horse = horses[Number(button.dataset.horseIndex)];
      const contributor = PERSONAL_MOMOTARO_CONTRIBUTORS.find(function (entry) {
        return entry.key === button.dataset.contributorKey;
      });
      if (horse && contributor) personalMomotaroShowDetail(horse, contributor);
    });
  });
}

function personalMomotaroAppendNotes() {
  if (!currentBundle) return;
  const target = document.getElementById("newspaper-race-notes");
  if (!target) return;
  const existing = target.querySelector(".personal-momotaro-race-notes");
  if (existing) existing.remove();

  const notes = currentBundle.race_notes || {};
  const comments = notes.momotaro_comments || {};
  const horses = Array.isArray(currentBundle.horses)
    ? [...currentBundle.horses].sort(function (a, b) {
        return Number(a && a.key && a.key.horse_no) - Number(b && b.key && b.key.horse_no);
      })
    : [];

  const ojiBlocks = horses.map(function (horse) {
    const value = personalMomotaroPrediction(horse, "oji");
    if (value.review_horse !== true) return "";
    const horseNo = text(horse && horse.key && horse.key.horse_no, "");
    const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
    const memo = text(value.comment, "");
    return '<div class="momotaro-race-note-review"><strong>' +
      escapeHtml(horseNo + "." + horseName) + '</strong>' +
      (memo ? '<p>' + escapeHtml(memo) + '</p>' : "") +
      '</div>';
  }).filter(Boolean).join("");

  function section(label, body) {
    return '<section class="momotaro-race-note-person">' +
      '<h3>' + escapeHtml(label) + '</h3>' +
      '<div class="momotaro-race-note-body">' + body + '</div>' +
      '</section>';
  }

  const ryota = text(comments.ryota, "");
  const kenshow = text(comments.kenshow, "");
  target.insertAdjacentHTML("beforeend",
    '<section class="newspaper-v5-note-section personal-momotaro-race-notes">' +
      '<h3>短評</h3>' +
      '<div class="momotaro-race-notes-grid">' +
        section("りょーた", ryota ? '<p>' + escapeHtml(ryota) + '</p>' : "") +
        section("おーじ", ojiBlocks) +
        section("けんしょー", kenshow ? '<p>' + escapeHtml(kenshow) + '</p>' : "") +
      '</div>' +
    '</section>'
  );
}

const personalMomotaroRenderBundleBase = renderBundle;
renderBundle = function () {
  personalMomotaroRenderBundleBase();
  personalMomotaroApplyMarks();
  personalMomotaroAppendNotes();
};

window.addEventListener("load", function () {
  if (currentBundle) {
    personalMomotaroApplyMarks();
    personalMomotaroAppendNotes();
  }
});

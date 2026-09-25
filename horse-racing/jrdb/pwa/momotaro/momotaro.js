"use strict";

const MOMOTARO_CONTRIBUTORS = [
  { key: "ryota", label: "りょーた" },
  { key: "oji", label: "おーじ" },
  { key: "kenshow", label: "けんしょー" }
];

const MOMOTARO_KENSHOW_JRDB_MARKS = new Set(["◎", "○", "▲", "注"]);

/**
 * RaceNote運用確定までの暫定表示。
 * JRDB総合印のうち ◎ / ○ / ▲ / 注 だけを、けん列へそのまま転記する。
 * addon化・短評化・予想一覧化はしない。
 */
function momotaroKenshowTemporaryMark(horse) {
  const jrdb = horse && horse.jrdb ? horse.jrdb : {};
  const marks = jrdb.marks || {};
  const mark = text(marks.total, "");
  return MOMOTARO_KENSHOW_JRDB_MARKS.has(mark) ? mark : "";
}

/**
 * 桃太郎専用予想addonを返す。
 * upstream未提供時は空objectを返し、既存新聞の意味論は変更しない。
 */
function momotaroPrediction(horse, key) {
  const addons = horse && horse.addons ? horse.addons : {};
  const momotaro = addons.momotaro || {};
  return momotaro[key] || {};
}

/**
 * 桃太郎予想に表示可能な値があるか判定する。
 */
function momotaroHasPrediction(value) {
  if (!value || typeof value !== "object") return false;
  return Boolean(
    text(value.mark, "") ||
    text(value.confidence, "") ||
    text(value.comment, "") ||
    value.review_horse === true
  );
}

/**
 * 友人予想の詳細dialogを表示する。
 */
function showMomotaroContributorDetail(horse, contributor) {
  const value = momotaroPrediction(horse, contributor.key);
  const horseName = text(horse && horse.basic && horse.basic.horse_name, "");
  const mark = text(value.mark, "");
  const confidence = text(value.confidence, "");
  const tag = text(value.tag, "");
  const comment = text(value.comment, "");
  const review = value.review_horse === true && contributor.key === "ryota" ? "特注" : "";
  const displayMark = contributor.key === "kenshow"
    ? (momotaroKenshowTemporaryMark(horse) || (comment ? "注" : ""))
    : mark;

  dialogTitle.textContent = horseName + " / " + contributor.label + (displayMark ? " " + displayMark : "");
  const meta = [
    confidence ? "自信度 " + confidence : "",
    review,
    contributor.key === "kenshow" ? tag : ""
  ].filter(Boolean).join(" / ");
  dialogBody.innerHTML =
    (meta ? '<p class="newspaper-addon-meta">' + escapeHtml(meta) + '</p>' : "") +
    '<p class="newspaper-addon-comment">' + escapeHtml(comment || "短評なし") + '</p>';

  if (typeof detailDialog.showModal === "function") {
    detailDialog.showModal();
  } else {
    detailDialog.setAttribute("open", "");
  }
}

/**
 * 桃太郎の人物印セルを生成する。
 */
function momotaroContributorCell(horse, horseIndex, contributor) {
  if (contributor.key === "kenshow") {
    const value = momotaroPrediction(horse, contributor.key);
    const comment = text(value.comment, "");
    const jrdbMark = momotaroKenshowTemporaryMark(horse);
    const display = jrdbMark || (comment ? "注" : "");

    if (comment) {
      return '<td class="newspaper-mark-col mark-momotaro mark-kenshow">' +
        '<button type="button" class="newspaper-addon-link momotaro-contributor-button" ' +
        'data-horse-index="' + horseIndex + '" data-contributor-key="kenshow" ' +
        'aria-label="' + escapeHtml(text(horse && horse.basic && horse.basic.horse_name, "")) + 'のけんしょー不利分析">' +
        escapeHtml(display) + '</button></td>';
    }

    return '<td class="newspaper-mark-col mark-momotaro mark-kenshow">' +
      escapeHtml(display) + '</td>';
  }

  const value = momotaroPrediction(horse, contributor.key);
  const mark = text(value.mark, "");
  const comment = text(value.comment, "");
  const display = mark || "";

  if (comment) {
    return '<td class="newspaper-mark-col mark-momotaro mark-' + escapeHtml(contributor.key) + '">' +
      '<button type="button" class="newspaper-addon-link momotaro-contributor-button" ' +
      'data-horse-index="' + horseIndex + '" data-contributor-key="' + escapeHtml(contributor.key) + '" ' +
      'aria-label="' + escapeHtml(text(horse && horse.basic && horse.basic.horse_name, "")) + "の" + escapeHtml(contributor.label) + '短評">' +
      escapeHtml(display || "・") + '</button></td>';
  }

  return '<td class="newspaper-mark-col mark-momotaro mark-' + escapeHtml(contributor.key) + '">' +
    escapeHtml(display) + '</td>';
}

/**
 * 個人PWAと同じ思想で、イルカは3人の印とは別の共通外部参考列として表示する。
 */
function momotaroIlukaCell(horse, horseIndex) {
  const addons = horse && horse.addons ? horse.addons : {};
  const iluka = addons.keibailuka;
  const state = newspaperV5SourceState("keibailuka");
  const comment = newspaperV2IlukaComment(iluka);

  if (iluka && comment) {
    return '<td class="newspaper-mark-col mark-iluka">' +
      '<button type="button" class="newspaper-addon-link newspaper-iluka-button" data-horse-index="' + horseIndex + '">○</button>' +
      '</td>';
  }
  if (iluka) {
    return '<td class="newspaper-mark-col mark-iluka">○</td>';
  }
  return '<td class="newspaper-mark-col mark-iluka">' +
    escapeHtml(newspaperV5ReadyBlank(state) ? "" : "-") +
    '</td>';
}

/**
 * 桃太郎新聞用の表を描画する。
 * 個人PWAの印・指数7列は持ち込まず、3人の印 + 共通外部参考の🐬だけを表示する。
 */
renderTable = function () {
  const horses = [...currentBundle.horses].sort(
    (a, b) => Number(a.key.horse_no) - Number(b.key.horse_no)
  );
  const historyTopHeaders = Array.from(
    { length: 5 },
    (_, index) => '<th class="newspaper-history-head" rowspan="2">' + (index + 1) + '走前</th>'
  ).join("");

  const rows = horses.map(function (horse, horseIndex) {
    const history = horse.history || [];
    const frameNo = horse.key ? horse.key.frame_no : null;
    const historyCells = Array.from(
      { length: 5 },
      (_, runIndex) =>
        '<td class="newspaper-history-cell">' +
        newspaperV4HistoryCellHtml(history[runIndex], horseIndex, runIndex) +
        '</td>'
    ).join("");

    const contributorCells = MOMOTARO_CONTRIBUTORS.map(function (contributor) {
      return momotaroContributorCell(horse, horseIndex, contributor);
    }).join("");

    return '<tr>' +
      '<td class="newspaper-frame' + newspaperV2FrameClass(frameNo) + '">' + escapeHtml(text(frameNo)) + '</td>' +
      '<td class="newspaper-horse-no">' + escapeHtml(text(horse.key && horse.key.horse_no)) + '</td>' +
      '<td class="newspaper-horse-name-cell">' + newspaperV4HorseNameHtml(horse) + '</td>' +
      '<td class="newspaper-basic-info">' + newspaperV4BasicInfoHtml(horse) + '</td>' +
      contributorCells +
      momotaroIlukaCell(horse, horseIndex) +
      historyCells +
      '</tr>';
  }).join("");

  tableWrap.innerHTML =
    '<table class="newspaper-table newspaper-table-v4 momotaro-newspaper-table ' + newspaperV4HistoryTableClass() + '">' +
    '<thead>' +
      '<tr>' +
        '<th class="newspaper-frame" rowspan="2">枠</th>' +
        '<th class="newspaper-horse-no" rowspan="2">馬</th>' +
        '<th class="newspaper-horse-name-cell" rowspan="2">馬名</th>' +
        '<th class="newspaper-basic-info" rowspan="2">基本</th>' +
        '<th class="newspaper-mark-group-head" colspan="4">予想</th>' +
        historyTopHeaders +
      '</tr>' +
      '<tr class="newspaper-mark-head-row">' +
        '<th class="newspaper-mark-col mark-ryota">りょ</th>' +
        '<th class="newspaper-mark-col mark-oji">王子</th>' +
        '<th class="newspaper-mark-col mark-kenshow">けん</th>' +
        '<th class="newspaper-mark-col mark-iluka">🐬</th>' +
      '</tr>' +
    '</thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table>';

  tableWrap.querySelectorAll(".newspaper-detail-button").forEach(function (button) {
    button.addEventListener("click", function () {
      const horse = horses[Number(button.dataset.horseIndex)];
      if (horse) showRunDetail(horse, horse.history[Number(button.dataset.runIndex)]);
    });
  });

  tableWrap.querySelectorAll(".newspaper-iluka-button").forEach(function (button) {
    button.addEventListener("click", function () {
      const horse = horses[Number(button.dataset.horseIndex)];
      if (horse) newspaperV2ShowIlukaDetail(horse);
    });
  });

  tableWrap.querySelectorAll(".momotaro-contributor-button").forEach(function (button) {
    button.addEventListener("click", function () {
      const horse = horses[Number(button.dataset.horseIndex)];
      const contributor = MOMOTARO_CONTRIBUTORS.find(function (entry) {
        return entry.key === button.dataset.contributorKey;
      });
      if (horse && contributor) showMomotaroContributorDetail(horse, contributor);
    });
  });
};

/**
 * 個人PWAのRaceNote短評は桃太郎では表示せず、JRDBレース情報だけ補助表示する。
 * 友人コメントの主表示は印セルのモーダルと予想一覧に統一する。
 */
function applyMomotaroRaceNotesLayout() {
  const card = document.getElementById("newspaper-notes-card");
  const target = document.getElementById("newspaper-race-notes");
  if (!card || !target) return;

  const title = card.querySelector("h2");
  if (title) title.textContent = "レース情報";

  const sections = Array.from(target.querySelectorAll(".newspaper-v5-note-section"));
  sections.forEach(function (section) {
    const heading = section.querySelector("h3");
    if (heading && heading.textContent === "RaceNote短評") {
      section.remove();
    }
  });
}

const momotaroBaseRenderBundle = renderBundle;
renderBundle = function () {
  historyCount = 5;
  momotaroBaseRenderBundle();
  applyMomotaroRaceNotesLayout();
};

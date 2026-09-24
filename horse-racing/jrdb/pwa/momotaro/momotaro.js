"use strict";

const MOMOTARO_CONTRIBUTORS = [
  { key: "ryota", label: "りょーた" },
  { key: "oji", label: "おーじ" },
  { key: "kenshow", label: "けんしょー" }
];

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
  const comment = text(value.comment, "");
  const review = value.review_horse === true ? "回顧馬" : "";

  dialogTitle.textContent = horseName + " / " + contributor.label + (mark ? " " + mark : "");
  const meta = [
    confidence ? "自信度 " + confidence : "",
    review
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
 * 3人分の印・短評を桃太郎専用カードへ描画する。
 */
function renderMomotaroFriends() {
  const card = document.getElementById("momotaro-friends-card");
  const container = document.getElementById("momotaro-friends");
  if (!card || !container || !currentBundle || !Array.isArray(currentBundle.horses)) return;

  const horsesWithPredictions = currentBundle.horses.filter(function (horse) {
    return MOMOTARO_CONTRIBUTORS.some(function (entry) {
      return momotaroHasPrediction(momotaroPrediction(horse, entry.key));
    });
  });

  if (horsesWithPredictions.length === 0) {
    container.innerHTML = '<div class="empty-state">桃太郎予想データはまだありません。</div>';
    card.hidden = false;
    return;
  }

  const rows = horsesWithPredictions.map(function (horse) {
    const horseNo = horse && horse.key ? horse.key.horse_no : "";
    const horseName = horse && horse.basic ? horse.basic.horse_name : "";
    const contributors = MOMOTARO_CONTRIBUTORS.map(function (entry) {
      const value = momotaroPrediction(horse, entry.key);
      const mark = text(value.mark, "");
      const confidence = text(value.confidence, "");
      const comment = text(value.comment, "");
      const review = value.review_horse === true ? "回顧馬" : "";
      const meta = [confidence ? "自信度 " + confidence : "", review].filter(Boolean).join(" / ");

      return '<div class="momotaro-contributor">' +
        '<div><strong>' + escapeHtml(entry.label) + '</strong></div>' +
        '<div class="momotaro-mark">' + escapeHtml(mark || "—") + '</div>' +
        (meta ? '<div class="query-status">' + escapeHtml(meta) + '</div>' : "") +
        '<div class="momotaro-comment">' + escapeHtml(comment || "短評なし") + '</div>' +
        '</div>';
    }).join("");

    return '<div class="momotaro-horse-card">' +
      '<strong>' + escapeHtml(text(horseNo, "")) + ' ' + escapeHtml(text(horseName, "")) + '</strong>' +
      '<div class="momotaro-contributors">' + contributors + '</div>' +
      '</div>';
  }).join("");

  container.innerHTML = rows;
  card.hidden = false;
}

/**
 * 個人PWAのRaceNote短評は桃太郎では表示せず、JRDBレース情報だけ補助表示する。
 * 短評の主表示は3人の予想・短評カードに統一する。
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
  renderMomotaroFriends();
  applyMomotaroRaceNotesLayout();
};

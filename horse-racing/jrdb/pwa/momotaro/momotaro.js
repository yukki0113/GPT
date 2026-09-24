"use strict";

const MOMOTARO_CONTRIBUTORS = [
  { key: "ryota", label: "りょーた" },
  { key: "oji", label: "おーじ" },
  { key: "friend3", label: "3人目" }
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
 * 3人分の印・短評を桃太郎専用カードへ描画する。
 */
function renderMomotaroFriends() {
  const card = document.getElementById("momotaro-friends-card");
  const container = document.getElementById("momotaro-friends");
  if (!card || !container || !currentBundle || !Array.isArray(currentBundle.horses)) return;

  const rows = currentBundle.horses.map(function (horse) {
    const horseNo = horse && horse.key ? horse.key.horse_no : "";
    const horseName = horse && horse.identity ? horse.identity.horse_name : "";
    const contributors = MOMOTARO_CONTRIBUTORS.map(function (entry) {
      const value = momotaroPrediction(horse, entry.key);
      const mark = text(value.mark, "—");
      const confidence = text(value.confidence, "");
      const comment = text(value.comment, "");
      const review = value.review_horse ? "回顧馬" : "";
      const meta = [confidence, review].filter(Boolean).join(" / ");
      return '<div class="momotaro-contributor">' +
        '<div><strong>' + escapeHtml(entry.label) + '</strong></div>' +
        '<div class="momotaro-mark">' + escapeHtml(mark) + '</div>' +
        (meta ? '<div class="query-status">' + escapeHtml(meta) + '</div>' : '') +
        '<div class="momotaro-comment">' + escapeHtml(comment || "—") + '</div>' +
        '</div>';
    }).join("");

    return '<div class="momotaro-horse-card">' +
      '<strong>' + escapeHtml(text(horseNo, "")) + ' ' + escapeHtml(text(horseName, "")) + '</strong>' +
      '<div class="momotaro-contributors">' + contributors + '</div>' +
      '</div>';
  }).join("");

  container.innerHTML = rows || '<div class="empty-state">桃太郎予想データはまだありません。</div>';
  card.hidden = false;
}

const momotaroBaseRenderBundle = renderBundle;
renderBundle = function () {
  historyCount = 3;
  momotaroBaseRenderBundle();
  renderMomotaroFriends();
};

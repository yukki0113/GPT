"use strict";
/* Research-only pedigree modal. No source-scoring or BRDB forecast integration. */
(function () {
  const dlg = document.getElementById("newspaper-blood-dialog");
  const title = document.getElementById("newspaper-blood-title");
  const body = document.getElementById("newspaper-blood-body");
  const table = document.getElementById("newspaper-table-wrap");
  if (!dlg || !title || !body || !table ||
      typeof newspaperV4HorseNameHtml !== "function") return;
  const priorNameRenderer = newspaperV4HorseNameHtml;
  const txt = v => v === null || v === undefined || v === "" ? "未取得" : String(v);
  const esc = v => escapeHtml(txt(v));
  const arr = v => Array.isArray(v) ? v : [];
  const validNo = v => Number.isInteger(v) && v >= 0;
  function candidate(horse) {
    const a = horse && horse.addons && horse.addons.brdb_pedigree_display;
    const key = horse && horse.key;
    const race = currentBundle && currentBundle.race;
    if (!a || !key || !race || a.contract_version !== "brdb-newspaper-pedigree-display-v0.1-candidate" ||
        a.release_status !== "RESEARCH_PREVIEW_ONLY" ||
        a.research_only !== true || a.prediction_safe !== false ||
        a.production_authorized !== false || a.as_of_status !== "AS_OF_UNVERIFIED" ||
        a.race_key !== race.race_key || a.horse_id !== key.horse_id ||
        a.horse_no !== key.horse_no || a.score !== null ||
        a.rank !== null || a.probability !== null ||
        !/^[0-9]{8}$/.test(String(a.horse_id || "")) ||
        !/^[0-9a-f]{64}$/.test(String(a.source_sha256 || ""))) return null;
    return a;
  }
  function section(name, content) {
    return '<section class="newspaper-blood-section"><h3>' + esc(name) +
      '</h3>' + content + '</section>';
  }
  const empty = message => '<p class="newspaper-blood-empty">' + esc(message) + '</p>';
  function status(value) {
    return ({AVAILABLE:"実績あり（記述統計）",LOW_SAMPLE:"サンプル少",
      NO_SAMPLE:"該当出走なし",SOURCE_UNAVAILABLE:"情報未取得",
      AS_OF_UNVERIFIED:"取得時点は未検証"})[value] || "未評価";
  }
  function fact(label,value) {
    return '<div><dt>' + esc(label) + '</dt><dd>' + esc(value) + '</dd></div>';
  }
  function render(horse) {
    const basic = horse.basic || {};
    const a = candidate(horse);
    const crosses = a ? arr(a.crosses) : [];
    const stats = a ? arr(a.condition_records) : [];
    const reviews = a ? arr(a.reviews) : [];
    const relatives = a ? arr(a.relatives) : [];
    const tips = a ? arr(a.tips) : [];
    const basics = '<dl class="newspaper-blood-facts">' +
      fact("馬名",basic.horse_name) + fact("父",basic.sire_name) +
      fact("母",basic.dam_name) + fact("母父",basic.broodmare_sire_name) + '</dl>';
    const crossesHtml = crosses.length ?
      '<ul class="newspaper-blood-items">' + crosses.filter(x => x && typeof x === "object")
      .map(x => '<li><strong>' + esc(x.ancestor) + '</strong> ' +
        esc(x.pattern) + '</li>').join("") + '</ul>' :
      empty("クロス情報は未取得です。系統照合後に表示します。");
    const statHtml = stats.length ? '<div class="newspaper-blood-records">' +
      stats.filter(x => x && typeof x === "object" &&
        validNo(x.starts) && validNo(x.wins) && validNo(x.top3) &&
        x.wins <= x.top3 && x.top3 <= x.starts).map(x =>
        '<article><strong>' + esc(x.label) + '</strong><p>' +
        x.starts + '走・' + x.wins + '勝・3着以内' + x.top3 + '回</p><p>3着内率 ' +
        (x.starts ? (100*x.top3/x.starts).toFixed(1)+'%' : '算出対象なし') +
        ' / ' + esc(status(x.status)) + '</p><small>' +
        esc(x.source_label) + '</small></article>').join("") + '</div>' :
      empty("今回の条件の産駒・母父実績はまだ接続されていません。");
    const reviewHtml = reviews.length ? '<div class="newspaper-blood-reviews">' +
      reviews.filter(x => x && typeof x === "object").map(x =>
        '<article><h4>' + esc(x.category) + '</h4><p>' + esc(x.text) +
        '</p><small>' + esc(status(x.status)) + ' / 根拠: ' +
        esc(x.evidence_label) + '</small></article>').join("") + '</div>' :
      empty("父産駒・母父・配合・近親のBRDBレビューは準備中です。");
    const relHtml = relatives.length ? '<ul class="newspaper-blood-items">' +
      relatives.filter(x => x && typeof x === "object").map(x =>
        '<li><strong>' + esc(x.name) + '</strong> ' +
        esc(x.relationship) + ' / ' + esc(x.note) + '</li>').join("") + '</ul>' :
      empty("近親に関する情報はまだ接続されていません。");
    const tipsHtml = tips.length ? '<ul class="newspaper-blood-items">' +
      tips.filter(x => x && x.kind === "CHECK" && typeof x.text === "string" &&
        typeof x.evidence_label === "string").map(x =>
        '<li>' + esc(x.text) + '<small>確認根拠: ' +
        esc(x.evidence_label) + '</small></li>').join("") + '</ul>' :
      '<ul class="newspaper-blood-items"><li>該当条件の出走数と対象期間を確認しましょう。</li>' +
      '<li>血統実績は、今回の馬の成績や馬券の優劣を保証しません。</li></ul>';
    title.textContent = txt(basic.horse_name) + " / 血統詳細";
    body.innerHTML =
      '<p class="newspaper-blood-caption">' +
      esc(a ? "BRDB研究データ（予測評価ではありません）" :
        "BRDBレビューは未接続です。現在は新聞の基本血統情報を表示します。") + '</p>' +
      section("基本血統", basics) + section("クロス・系統",crossesHtml) +
      section("今回の条件と血統実績",statHtml) + section("BRDB血統レビュー",reviewHtml) +
      section("母方近親",relHtml) + section("馬券検討Tips",tipsHtml) +
      '<p class="newspaper-blood-disclaimer">※血統情報は検討用の研究資料です。予測確率、評価印、購入推奨ではありません。</p>';
  }
  newspaperV4HorseNameHtml = function (horse) {
    const html = priorNameRenderer(horse);
    const key = horse && horse.key;
    const no = key && key.horse_no;
    const id = key && key.horse_id;
    if (!Number.isInteger(no) || no < 1 ||
        !/^[0-9]{8}$/.test(String(id || ""))) return html;
    return '<div class="newspaper-blood-name-wrap">' + html +
      '<button type="button" class="newspaper-blood-trigger" data-horse-no="' + no +
      '" data-horse-id="' + id + '" aria-label="' +
      esc(horse.basic && horse.basic.horse_name) + 'の血統詳細を開く">血統</button></div>';
  };
  table.addEventListener("click", function (event) {
    const button = event.target && event.target.closest &&
      event.target.closest(".newspaper-blood-trigger");
    if (!button || !currentBundle || !Array.isArray(currentBundle.horses)) return;
    const n = Number(button.dataset.horseNo);
    const id = button.dataset.horseId;
    const rows = currentBundle.horses.filter(h => h && h.key &&
      h.key.horse_no === n && h.key.horse_id === id);
    if (rows.length !== 1) return; // no name fallback
    render(rows[0]);
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  });
  window.NewspaperBloodPanel = {candidate, render, status};
})();

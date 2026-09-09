"use strict";

const NEWSPAPER_OPFS_DIR = "jrdb-newspaper";
const NEWSPAPER_OPFS_FILE = "current.json";

const networkBadge = document.getElementById("newspaper-network-badge");
const localStatus = document.getElementById("newspaper-local-status");
const opfsStatus = document.getElementById("newspaper-opfs-status");
const swStatus = document.getElementById("newspaper-sw-status");
const raceStatus = document.getElementById("newspaper-race-status");
const fileInput = document.getElementById("newspaper-file");
const importButton = document.getElementById("newspaper-import");
const clearButton = document.getElementById("newspaper-clear");
const importStatus = document.getElementById("newspaper-import-status");
const raceCard = document.getElementById("newspaper-race-card");
const tableCard = document.getElementById("newspaper-table-card");
const raceMeta = document.getElementById("newspaper-race-meta");
const raceTitle = document.getElementById("newspaper-race-title");
const raceSubtitle = document.getElementById("newspaper-race-subtitle");
const sourceStatus = document.getElementById("newspaper-source-status");
const tableWrap = document.getElementById("newspaper-table-wrap");
const historyButtons = Array.from(document.querySelectorAll(".newspaper-history-button"));
const detailDialog = document.getElementById("newspaper-detail-dialog");
const dialogTitle = document.getElementById("newspaper-dialog-title");
const dialogBody = document.getElementById("newspaper-dialog-body");

let currentBundle = null;
let historyCount = 3;
let opfsAvailable = false;

function updateNetworkStatus() {
  const online = navigator.onLine;
  networkBadge.textContent = online ? "オンライン" : "オフライン";
  networkBadge.classList.toggle("online", online);
  networkBadge.classList.toggle("offline", !online);
}

function text(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits).replace(/\.0$/, "");
}

function shortDate(value) {
  const raw = text(value, "");
  const match = raw.match(/^\d{4}-(\d{2})-(\d{2})$/);
  return match ? `${Number(match[1])}/${Number(match[2])}` : raw || "—";
}

function validateBundle(bundle) {
  if (!bundle || typeof bundle !== "object") throw new Error("JSON objectではありません。");
  if (bundle.schema_version !== "0.1") throw new Error(`未対応schema: ${text(bundle.schema_version)}`);
  if (bundle.bundle_kind !== "jrdb_pwa_newspaper_race") throw new Error("Newspaper race bundleではありません。");
  if (!bundle.race || typeof bundle.race !== "object") throw new Error("raceがありません。");
  if (!Array.isArray(bundle.horses) || bundle.horses.length === 0) throw new Error("horsesがありません。");

  const seen = new Set();
  for (const horse of bundle.horses) {
    const horseNo = horse && horse.key ? Number(horse.key.horse_no) : NaN;
    if (!Number.isInteger(horseNo) || horseNo < 1 || seen.has(horseNo)) {
      throw new Error(`馬番が不正または重複しています: ${text(horseNo)}`);
    }
    seen.add(horseNo);
    const history = horse.history || [];
    if (!Array.isArray(history) || history.length > 8) throw new Error(`過去走数が不正です: ${horseNo}番`);
    for (const [index, run] of history.entries()) {
      if (Number(run.sequence) !== index + 1) throw new Error(`過去走sequenceが不連続です: ${horseNo}番`);
      if (run.date && bundle.race.date && run.date >= bundle.race.date) {
        throw new Error(`対象日以降の過去走を検出しました: ${horseNo}番 ${run.date}`);
      }
    }
  }

  if (bundle.race.field_size && Number(bundle.race.field_size) !== bundle.horses.length) {
    throw new Error(`頭数不一致: race=${bundle.race.field_size} horses=${bundle.horses.length}`);
  }
  return bundle;
}

async function getNewspaperDirectory(create) {
  if (!navigator.storage || !navigator.storage.getDirectory) return null;
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(NEWSPAPER_OPFS_DIR, { create });
}

async function checkOpfs() {
  if (!navigator.storage || !navigator.storage.getDirectory) {
    opfsStatus.textContent = "非対応";
    opfsAvailable = false;
    return false;
  }
  try {
    await getNewspaperDirectory(true);
    opfsStatus.textContent = "利用可";
    opfsAvailable = true;
    return true;
  } catch (error) {
    console.error(error);
    opfsStatus.textContent = "利用不可";
    opfsAvailable = false;
    return false;
  }
}

async function saveBundle(bundle) {
  if (!opfsAvailable) return false;
  const directory = await getNewspaperDirectory(true);
  const handle = await directory.getFileHandle(NEWSPAPER_OPFS_FILE, { create: true });
  const writable = await handle.createWritable();
  await writable.write(JSON.stringify(bundle));
  await writable.close();
  localStatus.textContent = "保存済み";
  clearButton.disabled = false;
  return true;
}

async function restoreBundle() {
  if (!opfsAvailable) {
    localStatus.textContent = "利用不可";
    return false;
  }
  try {
    const directory = await getNewspaperDirectory(false);
    const handle = await directory.getFileHandle(NEWSPAPER_OPFS_FILE);
    const file = await handle.getFile();
    const bundle = validateBundle(JSON.parse(await file.text()));
    currentBundle = bundle;
    localStatus.textContent = `保存済み ${(file.size / 1024).toFixed(0)} KB`;
    clearButton.disabled = false;
    renderBundle();
    importStatus.textContent = "端末保存から新聞を復元しました。";
    return true;
  } catch (error) {
    if (error && error.name !== "NotFoundError") console.error(error);
    localStatus.textContent = "未保存";
    clearButton.disabled = true;
    return false;
  }
}

async function clearBundle() {
  if (!opfsAvailable) return;
  try {
    const directory = await getNewspaperDirectory(false);
    await directory.removeEntry(NEWSPAPER_OPFS_FILE);
  } catch (error) {
    if (error && error.name !== "NotFoundError") throw error;
  }
  currentBundle = null;
  localStatus.textContent = "未保存";
  raceStatus.textContent = "未読込";
  clearButton.disabled = true;
  raceCard.hidden = true;
  tableCard.hidden = true;
  importStatus.textContent = "端末保存を削除しました。";
}

function renderRaceHeader() {
  const race = currentBundle.race;
  raceMeta.textContent = `${text(race.date)}  ${text(race.venue)} ${text(race.race_no)}R  ${text(race.start_time)}`;
  raceTitle.textContent = text(race.race_name, `${text(race.venue)} ${text(race.race_no)}R`);
  raceSubtitle.textContent = [
    `${text(race.surface)}${text(race.distance_m)}m`,
    text(race.turn, ""),
    race.course_label ? `${race.course_label}コース` : "",
    text(race.grade_label || race.class_label, ""),
    race.field_size ? `${race.field_size}頭` : "",
    text(race.weight_rule_label, "")
  ].filter(Boolean).join(" / ");
  raceStatus.textContent = `${text(race.venue)} ${text(race.race_no)}R / ${currentBundle.horses.length}頭`;

  const status = currentBundle.metadata && currentBundle.metadata.source_status
    ? currentBundle.metadata.source_status.jrdb_history
    : null;
  if (status) {
    const coverage = status.coverage_complete === false ? "履歴一部未解決" : "履歴READY";
    sourceStatus.textContent = `${coverage} / detailed ${text(status.resolved_count, 0)} / compact ${text(status.supplemental_count, 0)}`;
  } else {
    sourceStatus.textContent = "履歴source metadataなし";
  }
}

function horseInfoHtml(horse) {
  const basic = horse.basic || {};
  const key = horse.key || {};
  const sexAge = `${text(basic.sex_label, "")}${text(basic.age, "")}`;
  const line2 = [sexAge, basic.carried_weight_kg !== null && basic.carried_weight_kg !== undefined ? `${number(basic.carried_weight_kg)}kg` : "", text(basic.jockey_name, "")].filter(Boolean).join(" ");
  const line3 = [basic.sire_name ? `父 ${basic.sire_name}` : "", text(basic.running_style_label, "")].filter(Boolean).join(" / ");
  return `<div class="newspaper-horse-name">${escapeHtml(text(basic.horse_name))}</div>
    <div class="newspaper-subline">${escapeHtml(line2)}</div>
    <div class="newspaper-subline">${escapeHtml(line3)}</div>`;
}

function markHtml(horse) {
  const jrdb = horse.jrdb || {};
  const marks = jrdb.marks || {};
  const activeMarks = Object.entries(marks).filter(([, value]) => value);
  const ability = jrdb.ability || {};
  const training = jrdb.training && jrdb.training.summary ? jrdb.training.summary : {};
  const markLine = activeMarks.length
    ? activeMarks.map(([key, value]) => `${escapeHtml(key)}:${escapeHtml(value)}`).join(" ")
    : "印なし";
  return `<div class="newspaper-mark-line">${markLine}</div>
    <div class="newspaper-subline">IDM ${number(ability.idm)} / 総 ${number(ability.total_index)}</div>
    <div class="newspaper-subline">調 ${number(training.training_index)} ${escapeHtml(text(training.training_arrow, ""))}</div>`;
}

function finishLabel(run) {
  const finish = Number(run.finish);
  const abnormal = text(run.abnormal_code, "0");
  if ((!finish || finish <= 0) && abnormal !== "0") return "競走中止";
  if (finish > 0) return `${finish}着${run.field_size ? `/${run.field_size}` : ""}`;
  return "—";
}

function runTitle(run) {
  return run.race_name || run.grade_label || run.class_label || `${text(run.venue)} ${text(run.race_no)}R`;
}

function corners(run) {
  if (!Array.isArray(run.corner_positions)) return "";
  const values = run.corner_positions.filter(value => Number(value) > 0);
  return values.length ? values.join("-") : "";
}

function hasDetail(run) {
  return run.detail_level === "detailed" && (run.notes || run.jrdb_result);
}

function historyCellHtml(run, horseIndex, runIndex) {
  if (!run) return `<div class="newspaper-history-empty">—</div>`;
  const compact = run.source_layer === "compact_older_history";
  const track = [text(run.surface, ""), run.distance_m ? `${run.distance_m}m` : "", text(run.track_condition, "")].filter(Boolean).join("");
  const result = [finishLabel(run), run.final_popularity ? `${run.final_popularity}人気` : ""].filter(Boolean).join(" ");
  const passage = corners(run);
  const performance = compact ? "" : [
    run.time_sec !== null && run.time_sec !== undefined && Number(run.time_sec) > 0 ? `T ${formatRaceTime(run.time_sec)}` : "",
    run.last3f_sec !== null && run.last3f_sec !== undefined ? `上 ${number(run.last3f_sec)}` : "",
    run.idm !== null && run.idm !== undefined ? `IDM ${number(run.idm)}` : ""
  ].filter(Boolean).join(" / ");
  const abnormal = text(run.abnormal_code, "0") !== "0" ? `<div class="newspaper-abnormal">異常区分 ${escapeHtml(text(run.abnormal_code))}</div>` : "";
  const detail = hasDetail(run) ? `<button type="button" class="newspaper-detail-button" data-horse-index="${horseIndex}" data-run-index="${runIndex}">詳細</button>` : "";
  return `<div class="newspaper-run ${compact ? "compact" : "detailed"}">
    <div class="newspaper-run-top"><span>${escapeHtml(shortDate(run.date))} ${escapeHtml(text(run.venue, ""))}${run.race_no ? `${run.race_no}R` : ""}</span>${compact ? '<span class="newspaper-source-pill">簡易</span>' : ""}</div>
    <div class="newspaper-run-title">${escapeHtml(runTitle(run))}</div>
    <div class="newspaper-subline">${escapeHtml(track)}</div>
    <div class="newspaper-run-result">${escapeHtml(result)}</div>
    ${passage ? `<div class="newspaper-subline">通 ${escapeHtml(passage)}</div>` : ""}
    ${performance ? `<div class="newspaper-subline">${escapeHtml(performance)}</div>` : ""}
    ${abnormal}
    ${detail}
  </div>`;
}

function edgeHtml(horse) {
  const edges = Array.isArray(horse.edge_matches) ? horse.edge_matches : [];
  if (!edges.length) return "—";
  return edges.map(edge => `<div class="newspaper-edge-item">${escapeHtml(text(edge.display_text))}</div>`).join("");
}

function renderTable() {
  const horses = [...currentBundle.horses].sort((a, b) => Number(a.key.horse_no) - Number(b.key.horse_no));
  const historyHeaders = Array.from({ length: historyCount }, (_, index) => `<th class="newspaper-history-head">${index + 1}走前</th>`).join("");
  const rows = horses.map((horse, horseIndex) => {
    const history = horse.history || [];
    const historyCells = Array.from({ length: historyCount }, (_, runIndex) => `<td class="newspaper-history-cell">${historyCellHtml(history[runIndex], horseIndex, runIndex)}</td>`).join("");
    return `<tr>
      <td class="newspaper-horse-no">${escapeHtml(text(horse.key && horse.key.horse_no))}</td>
      <td class="newspaper-horse-info">${horseInfoHtml(horse)}</td>
      <td class="newspaper-marks">${markHtml(horse)}</td>
      ${historyCells}
      <td class="newspaper-edge">${edgeHtml(horse)}</td>
    </tr>`;
  }).join("");

  tableWrap.innerHTML = `<table class="newspaper-table">
    <thead><tr>
      <th class="newspaper-horse-no">馬</th>
      <th class="newspaper-horse-info">馬情報</th>
      <th class="newspaper-marks">JRDB</th>
      ${historyHeaders}
      <th class="newspaper-edge">Edge</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;

  tableWrap.querySelectorAll(".newspaper-detail-button").forEach(button => {
    button.addEventListener("click", () => {
      const horse = horses[Number(button.dataset.horseIndex)];
      const run = horse.history[Number(button.dataset.runIndex)];
      showRunDetail(horse, run);
    });
  });
}

function showRunDetail(horse, run) {
  dialogTitle.textContent = `${text(horse.basic && horse.basic.horse_name)} / ${shortDate(run.date)} ${text(run.venue, "")}${run.race_no ? `${run.race_no}R` : ""}`;
  const notes = run.notes || {};
  const jrdb = run.jrdb_result || {};
  const noteRows = [
    ["レース", runTitle(run)],
    ["結果", finishLabel(run)],
    ["人気", run.final_popularity ? `${run.final_popularity}人気` : null],
    ["単勝オッズ", run.final_win_odds],
    ["騎手", run.jockey_name],
    ["斤量", run.carried_weight_kg !== null && run.carried_weight_kg !== undefined ? `${number(run.carried_weight_kg)}kg` : null],
    ["パドック", notes.paddock_comment],
    ["脚元", notes.leg_comment],
    ["馬具・展開", notes.equipment_comment],
    ["レースコメント", notes.race_comment],
    ["raw score", jrdb.raw_score],
    ["pace score", jrdb.pace_score],
    ["front index", jrdb.front_index],
    ["late index", jrdb.late_index]
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  dialogBody.innerHTML = `<dl class="newspaper-detail-list">${noteRows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(text(value))}</dd></div>`).join("")}</dl>`;
  if (typeof detailDialog.showModal === "function") detailDialog.showModal();
  else detailDialog.setAttribute("open", "");
}

function renderBundle() {
  if (!currentBundle) return;
  renderRaceHeader();
  renderTable();
  raceCard.hidden = false;
  tableCard.hidden = false;
}

function formatRaceTime(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "—";
  const minutes = Math.floor(value / 60);
  const secs = (value - minutes * 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${secs}`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function importSelectedFile() {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  importButton.disabled = true;
  importStatus.textContent = "JSONを検証しています…";
  try {
    const bundle = validateBundle(JSON.parse(await file.text()));
    currentBundle = bundle;
    renderBundle();
    const saved = await saveBundle(bundle);
    importStatus.textContent = saved
      ? `読込・端末保存しました。${(file.size / 1024).toFixed(0)} KB`
      : "読込しました。OPFS非対応のため端末保存はできません。";
  } catch (error) {
    console.error(error);
    importStatus.textContent = `読込失敗: ${error.message}`;
  } finally {
    importButton.disabled = !(fileInput.files && fileInput.files.length);
  }
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    swStatus.textContent = "非対応";
    return;
  }
  try {
    const registration = await navigator.serviceWorker.register("./service-worker.js");
    await registration.update().catch(() => undefined);
    swStatus.textContent = "登録済み";
  } catch (error) {
    console.error(error);
    swStatus.textContent = "登録失敗";
  }
}

fileInput.addEventListener("change", () => {
  importButton.disabled = !(fileInput.files && fileInput.files.length);
});
importButton.addEventListener("click", importSelectedFile);
clearButton.addEventListener("click", () => clearBundle().catch(error => {
  console.error(error);
  importStatus.textContent = `削除失敗: ${error.message}`;
}));
historyButtons.forEach(button => {
  button.addEventListener("click", () => {
    historyCount = Number(button.dataset.historyCount);
    historyButtons.forEach(item => item.classList.toggle("active", item === button));
    renderTable();
  });
});
window.addEventListener("online", updateNetworkStatus);
window.addEventListener("offline", updateNetworkStatus);

(async function bootstrap() {
  updateNetworkStatus();
  await registerServiceWorker();
  await checkOpfs();
  await restoreBundle();
})();

"use strict";

const SQL_JS_URL = "https://cdn.jsdelivr.net/npm/sql.js@1.14.1/dist/sql-wasm.js";
const SQL_WASM_URL = "https://cdn.jsdelivr.net/npm/sql.js@1.14.1/dist/sql-wasm.wasm";
const OPFS_DIR = "jrdb";
const OPFS_FILE = "current.sqlite";

const networkBadge = document.getElementById("network-badge");
const opfsStatus = document.getElementById("opfs-status");
const swStatus = document.getElementById("sw-status");
const dbStatus = document.getElementById("db-status");
const syncStatus = document.getElementById("sync-status");
const fileInput = document.getElementById("sqlite-file");
const importButton = document.getElementById("btn-import");
const clearButton = document.getElementById("btn-clear-db");
const aggregateButton = document.getElementById("btn-aggregate");
const resultArea = document.getElementById("result-area");
const queryStatus = document.getElementById("query-status");

const yearFrom = document.getElementById("q-year-from");
const yearTo = document.getElementById("q-year-to");
const venue = document.getElementById("q-venue");
const trackType = document.getElementById("q-track-type");
const distance = document.getElementById("q-distance");
const trackCondition = document.getElementById("q-track-condition");
const minStarts = document.getElementById("q-min-starts");

const tabs = Array.from(document.querySelectorAll(".tab"));

let SQL = null;
let db = null;
let activeAxis = "sire";

const AXIS_CONFIG = {
  sire: { label: "種牡馬", table: "mart_sire_yearly", key: "sire_name" },
  jockey: { label: "騎手", table: "mart_jockey_yearly", key: "jockey_name" },
  frame: { label: "枠", table: "mart_frame_yearly", key: "frame_no" }
};

function updateNetworkStatus() {
  if (navigator.onLine) {
    networkBadge.textContent = "オンライン";
    networkBadge.classList.add("online");
    networkBadge.classList.remove("offline");
    return;
  }

  networkBadge.textContent = "オフライン";
  networkBadge.classList.add("offline");
  networkBadge.classList.remove("online");
}

async function checkOpfsSupport() {
  if (!navigator.storage || !navigator.storage.getDirectory) {
    opfsStatus.textContent = "非対応";
    return false;
  }

  try {
    await navigator.storage.getDirectory();
    opfsStatus.textContent = "利用可能";
    return true;
  } catch (error) {
    console.error("OPFS check failed", error);
    opfsStatus.textContent = "利用不可";
    return false;
  }
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    swStatus.textContent = "非対応";
    return;
  }

  try {
    await navigator.serviceWorker.register("./service-worker.js", { scope: "./" });
    swStatus.textContent = "登録済み";
  } catch (error) {
    console.error("Service Worker registration failed", error);
    swStatus.textContent = "登録失敗";
  }
}

async function loadSqlJs() {
  if (window.initSqlJs) {
    SQL = await window.initSqlJs({ locateFile: function () { return SQL_WASM_URL; } });
    return;
  }

  await new Promise(function (resolve, reject) {
    const script = document.createElement("script");
    script.src = SQL_JS_URL;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });

  SQL = await window.initSqlJs({ locateFile: function () { return SQL_WASM_URL; } });
}

async function getJrdbDirectory(create) {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(OPFS_DIR, { create: create });
}

async function saveToOpfs(bytes) {
  const directory = await getJrdbDirectory(true);
  const fileHandle = await directory.getFileHandle(OPFS_FILE, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(bytes);
  await writable.close();
}

async function loadFromOpfs() {
  try {
    const directory = await getJrdbDirectory(false);
    const fileHandle = await directory.getFileHandle(OPFS_FILE, { create: false });
    const file = await fileHandle.getFile();
    const buffer = await file.arrayBuffer();
    return {
      bytes: new Uint8Array(buffer),
      size: file.size,
      modified: file.lastModified
    };
  } catch (error) {
    if (error && error.name === "NotFoundError") {
      return null;
    }
    throw error;
  }
}

async function clearOpfsDb() {
  try {
    const directory = await getJrdbDirectory(false);
    await directory.removeEntry(OPFS_FILE);
  } catch (error) {
    if (!error || error.name !== "NotFoundError") {
      throw error;
    }
  }
}

function formatBytes(bytes) {
  const mib = bytes / (1024 * 1024);
  return mib.toFixed(1) + " MiB";
}

function setDbLoaded(source, size, modified) {
  dbStatus.textContent = "読込済み / " + formatBytes(size);
  syncStatus.textContent = source + " / " + new Date(modified).toLocaleString("ja-JP");
  importButton.disabled = false;
  clearButton.disabled = false;
  aggregateButton.disabled = false;
  tabs.forEach(function (tab) { tab.disabled = false; });
  [yearFrom, yearTo, venue, trackType, distance, trackCondition, minStarts].forEach(function (element) {
    element.disabled = false;
  });
}

function closeDatabase() {
  if (db) {
    db.close();
    db = null;
  }
}

function openDatabase(bytes) {
  closeDatabase();
  db = new SQL.Database(bytes);
  validateDatabase();
}

function validateDatabase() {
  const requiredTables = ["mart_sire_yearly", "mart_jockey_yearly", "mart_frame_yearly"];
  const result = db.exec("SELECT name FROM sqlite_master WHERE type='table'");
  const names = new Set();

  if (result.length > 0) {
    result[0].values.forEach(function (row) { names.add(row[0]); });
  }

  requiredTables.forEach(function (tableName) {
    if (!names.has(tableName)) {
      throw new Error("必須テーブルがありません: " + tableName);
    }
  });

  const integrity = db.exec("PRAGMA integrity_check");
  if (integrity.length === 0 || integrity[0].values.length === 0 || integrity[0].values[0][0] !== "ok") {
    throw new Error("SQLite integrity_check が ok ではありません");
  }
}

async function importSelectedFile() {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    return;
  }

  importButton.disabled = true;
  dbStatus.textContent = "検証中...";

  try {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    openDatabase(bytes);
    await saveToOpfs(bytes);
    setDbLoaded("端末へ保存", file.size, Date.now());
    queryStatus.textContent = "Stats MartをOPFSへ保存しました。次回起動時は自動復元します。";
    runAggregation();
  } catch (error) {
    console.error("DB import failed", error);
    closeDatabase();
    dbStatus.textContent = "取込失敗";
    queryStatus.textContent = "取込失敗: " + error.message;
  } finally {
    importButton.disabled = false;
  }
}

async function restoreLocalDatabase() {
  const stored = await loadFromOpfs();
  if (!stored) {
    dbStatus.textContent = "未設定";
    syncStatus.textContent = "未同期";
    importButton.disabled = false;
    return;
  }

  dbStatus.textContent = "復元中...";
  try {
    openDatabase(stored.bytes);
    setDbLoaded("OPFSから復元", stored.size, stored.modified);
    runAggregation();
  } catch (error) {
    console.error("Stored DB restore failed", error);
    dbStatus.textContent = "保存DBエラー";
    queryStatus.textContent = "保存済みDBを開けませんでした: " + error.message;
  }
}

function buildAggregationQuery() {
  const config = AXIS_CONFIG[activeAxis];
  const clauses = ["year BETWEEN ? AND ?"];
  const params = [Number(yearFrom.value), Number(yearTo.value)];

  if (venue.value) {
    clauses.push("venue_code = ?");
    params.push(venue.value);
  }
  if (trackType.value) {
    clauses.push("track_type = ?");
    params.push(trackType.value);
  }
  if (distance.value) {
    clauses.push("distance = ?");
    params.push(Number(distance.value));
  }
  if (trackCondition.value) {
    clauses.push("track_condition_code = ?");
    params.push(trackCondition.value);
  }

  const sql = [
    "SELECT",
    "  " + config.key + " AS item,",
    "  SUM(starts) AS starts,",
    "  SUM(wins) AS wins,",
    "  SUM(seconds) AS seconds,",
    "  SUM(thirds) AS thirds,",
    "  SUM(top3) AS top3,",
    "  SUM(win_payout_sum) AS win_payout_sum,",
    "  SUM(place_payout_sum) AS place_payout_sum",
    "FROM " + config.table,
    "WHERE " + clauses.join(" AND "),
    "GROUP BY " + config.key,
    "HAVING SUM(starts) >= ?",
    "ORDER BY (1.0 * SUM(wins) / SUM(starts)) DESC, SUM(starts) DESC",
    "LIMIT 200"
  ].join("\n");

  params.push(Math.max(1, Number(minStarts.value) || 1));
  return { sql: sql, params: params };
}

function percent(numerator, denominator) {
  if (!denominator) {
    return "0.0%";
  }
  return (100 * numerator / denominator).toFixed(1) + "%";
}

function returnRate(payout, starts) {
  if (!starts) {
    return "0.0%";
  }
  return (payout / starts).toFixed(1) + "%";
}

function renderResults(rows) {
  if (rows.length === 0) {
    resultArea.innerHTML = '<div class="empty-state">該当データがありません。</div>';
    return;
  }

  let html = '<div class="table-wrap"><table><thead><tr>';
  html += '<th>対象</th><th>出走</th><th>勝率</th><th>複勝率</th><th>単回</th><th>複回</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function (row) {
    html += '<tr>';
    html += '<td>' + escapeHtml(String(row.item)) + '</td>';
    html += '<td>' + row.starts + '</td>';
    html += '<td>' + percent(row.wins, row.starts) + '</td>';
    html += '<td>' + percent(row.top3, row.starts) + '</td>';
    html += '<td>' + returnRate(row.win_payout_sum, row.starts) + '</td>';
    html += '<td>' + returnRate(row.place_payout_sum, row.starts) + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  resultArea.innerHTML = html;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function runAggregation() {
  if (!db) {
    return;
  }

  const started = performance.now();
  const query = buildAggregationQuery();
  const statement = db.prepare(query.sql);
  const rows = [];

  try {
    statement.bind(query.params);
    while (statement.step()) {
      rows.push(statement.getAsObject());
    }
  } finally {
    statement.free();
  }

  renderResults(rows);
  const elapsed = performance.now() - started;
  queryStatus.textContent = AXIS_CONFIG[activeAxis].label + " / " + rows.length + "件 / " + elapsed.toFixed(0) + " ms";
}

async function removeLocalDatabase() {
  if (!window.confirm("端末内に保存したStats Martを削除しますか？")) {
    return;
  }

  closeDatabase();
  await clearOpfsDb();
  dbStatus.textContent = "未設定";
  syncStatus.textContent = "未同期";
  clearButton.disabled = true;
  aggregateButton.disabled = true;
  resultArea.innerHTML = '<div class="empty-state">Stats Martを取り込むと集計結果を表示します。</div>';
  queryStatus.textContent = "";
}

function configureTabs() {
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      activeAxis = tab.dataset.axis;
      tabs.forEach(function (item) { item.classList.remove("active"); });
      tab.classList.add("active");
      runAggregation();
    });
  });
}

async function initialize() {
  updateNetworkStatus();
  registerServiceWorker();
  configureTabs();

  const opfsAvailable = await checkOpfsSupport();
  if (!opfsAvailable) {
    dbStatus.textContent = "OPFS非対応";
    return;
  }

  try {
    dbStatus.textContent = "sql.js準備中...";
    await loadSqlJs();
    importButton.disabled = false;
    await restoreLocalDatabase();
  } catch (error) {
    console.error("PWA initialization failed", error);
    dbStatus.textContent = "初期化失敗";
    queryStatus.textContent = "初期化失敗: " + error.message + "（初回はオンラインで開いてください）";
  }
}

fileInput.addEventListener("change", function () {
  importButton.disabled = !(fileInput.files && fileInput.files.length > 0);
});
importButton.addEventListener("click", importSelectedFile);
clearButton.addEventListener("click", removeLocalDatabase);
aggregateButton.addEventListener("click", runAggregation);
window.addEventListener("online", updateNetworkStatus);
window.addEventListener("offline", updateNetworkStatus);

initialize();

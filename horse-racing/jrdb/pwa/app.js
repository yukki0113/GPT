"use strict";

const SQL_JS_URL = "./vendor/sql-wasm.js";
const SQL_WASM_URL = "./vendor/sql-wasm.wasm";
const REMOTE_MANIFEST_URL = "./data/manifest.json";

const OPFS_DIR = "jrdb";
const OPFS_CURRENT = "current.sqlite";
const OPFS_PREVIOUS = "previous.sqlite";
const OPFS_INCOMING = "incoming.sqlite";
const OPFS_METADATA = "metadata.json";

const networkBadge = document.getElementById("network-badge");
const opfsStatus = document.getElementById("opfs-status");
const swStatus = document.getElementById("sw-status");
const dbStatus = document.getElementById("db-status");
const syncStatus = document.getElementById("sync-status");
const remoteStatus = document.getElementById("remote-status");
const syncProgress = document.getElementById("sync-progress");
const checkUpdateButton = document.getElementById("btn-check-update");
const syncButton = document.getElementById("btn-sync");
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
let localMetadata = null;
let remoteManifest = null;
let syncInProgress = false;

const AXIS_CONFIG = {
  sire: { label: "種牡馬", table: "mart_sire_yearly", key: "sire_name" },
  jockey: { label: "騎手", table: "mart_jockey_yearly", key: "jockey_name" },
  frame: { label: "枠", table: "mart_frame_yearly", key: "frame_no" }
};

/**
 * ネットワーク状態表示を更新する。
 */
function updateNetworkStatus() {
  if (navigator.onLine) {
    networkBadge.textContent = "オンライン";
    networkBadge.classList.add("online");
    networkBadge.classList.remove("offline");
    checkUpdateButton.disabled = false;
    return;
  }

  networkBadge.textContent = "オフライン";
  networkBadge.classList.add("offline");
  networkBadge.classList.remove("online");
  checkUpdateButton.disabled = true;
  syncButton.disabled = true;
  remoteStatus.textContent = "オフライン";
}

/**
 * OPFS の利用可否を確認する。
 */
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

/**
 * Service Worker を登録する。
 */
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

/**
 * 同一originに同梱した sql.js / WASM を読み込む。
 */
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

/**
 * PWA専用のJRDBディレクトリを取得する。
 */
async function getJrdbDirectory(create) {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(OPFS_DIR, { create: create });
}

/**
 * OPFSへバイナリを書き込む。
 */
async function writeOpfsFile(fileName, bytes) {
  const directory = await getJrdbDirectory(true);
  const fileHandle = await directory.getFileHandle(fileName, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(bytes);
  await writable.close();
}

/**
 * OPFSからバイナリを読み込む。存在しない場合はnullを返す。
 */
async function readOpfsFile(fileName) {
  try {
    const directory = await getJrdbDirectory(false);
    const fileHandle = await directory.getFileHandle(fileName, { create: false });
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

/**
 * OPFS上のファイルを削除する。存在しない場合は何もしない。
 */
async function removeOpfsFile(fileName) {
  try {
    const directory = await getJrdbDirectory(false);
    await directory.removeEntry(fileName);
  } catch (error) {
    if (!error || error.name !== "NotFoundError") {
      throw error;
    }
  }
}

/**
 * 同期メタデータを保存する。
 */
async function saveLocalMetadata(metadata) {
  const text = JSON.stringify(metadata, null, 2) + "\n";
  await writeOpfsFile(OPFS_METADATA, new TextEncoder().encode(text));
  localMetadata = metadata;
}

/**
 * 同期メタデータを読み込む。
 */
async function loadLocalMetadata() {
  const stored = await readOpfsFile(OPFS_METADATA);
  if (!stored) {
    return null;
  }

  try {
    return JSON.parse(new TextDecoder().decode(stored.bytes));
  } catch (error) {
    console.warn("Local metadata parse failed", error);
    return null;
  }
}

/**
 * バイト列のSHA-256を16進数で返す。
 */
async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map(function (value) { return value.toString(16).padStart(2, "0"); })
    .join("");
}

/**
 * SQLite必須テーブルとintegrity_checkを検証する。
 */
function validateDatabaseObject(database) {
  const requiredTables = ["mart_sire_yearly", "mart_jockey_yearly", "mart_frame_yearly"];
  const result = database.exec("SELECT name FROM sqlite_master WHERE type='table'");
  const names = new Set();

  if (result.length > 0) {
    result[0].values.forEach(function (row) { names.add(row[0]); });
  }

  requiredTables.forEach(function (tableName) {
    if (!names.has(tableName)) {
      throw new Error("必須テーブルがありません: " + tableName);
    }
  });

  const integrity = database.exec("PRAGMA integrity_check");
  if (integrity.length === 0 || integrity[0].values.length === 0 || integrity[0].values[0][0] !== "ok") {
    throw new Error("SQLite integrity_check が ok ではありません");
  }
}

/**
 * 現在利用中DBを閉じる。
 */
function closeDatabase() {
  if (db) {
    db.close();
    db = null;
  }
}

/**
 * バイト列を一時DBとして検証する。現在利用中DBには触れない。
 */
function validateDatabaseBytes(bytes) {
  const temporaryDatabase = new SQL.Database(bytes);
  try {
    validateDatabaseObject(temporaryDatabase);
  } finally {
    temporaryDatabase.close();
  }
}

/**
 * 現在利用中DBとして開く。
 */
function openDatabase(bytes) {
  closeDatabase();
  db = new SQL.Database(bytes);
  validateDatabaseObject(db);
}

function formatBytes(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
}

function formatDate(value) {
  if (!value) {
    return "不明";
  }
  return new Date(value).toLocaleString("ja-JP");
}

/**
 * DB利用可能時に集計UIを有効化する。
 */
function setDbLoaded(source, size, modified, metadata) {
  dbStatus.textContent = "読込済み / " + formatBytes(size);

  if (metadata && metadata.data_version) {
    syncStatus.textContent = source + " / " + metadata.data_version;
  } else {
    syncStatus.textContent = source + " / " + formatDate(modified);
  }

  clearButton.disabled = false;
  aggregateButton.disabled = false;
  tabs.forEach(function (tab) { tab.disabled = false; });
  [yearFrom, yearTo, venue, trackType, distance, trackCondition, minStarts].forEach(function (element) {
    element.disabled = false;
  });
}

/**
 * 手動選択したSQLiteを検証し、current.sqliteとして保存する。
 */
async function importSelectedFile() {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    return;
  }

  importButton.disabled = true;
  dbStatus.textContent = "検証中...";

  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    validateDatabaseBytes(bytes);
    const hash = await sha256Hex(bytes);

    await writeOpfsFile(OPFS_CURRENT, bytes);
    await removeOpfsFile(OPFS_INCOMING);

    const metadata = {
      artifact_type: "jrdb_stats_mart",
      schema_version: "1.1",
      data_version: "manual-" + hash.slice(0, 12),
      size: file.size,
      sha256: hash,
      synced_at: new Date().toISOString(),
      source: "manual_import"
    };
    await saveLocalMetadata(metadata);

    openDatabase(bytes);
    setDbLoaded("手動取込", file.size, Date.now(), metadata);
    syncProgress.textContent = "Stats Martを端末へ保存しました。";
    runAggregation();

    if (navigator.onLine) {
      await checkRemoteManifest(false);
    }
  } catch (error) {
    console.error("DB import failed", error);
    dbStatus.textContent = "取込失敗";
    syncProgress.textContent = "取込失敗: " + error.message;
  } finally {
    importButton.disabled = false;
  }
}

/**
 * OPFSのcurrent.sqliteを復元する。
 */
async function restoreLocalDatabase() {
  const stored = await readOpfsFile(OPFS_CURRENT);
  if (!stored) {
    dbStatus.textContent = "未設定";
    syncStatus.textContent = "未同期";
    return false;
  }

  dbStatus.textContent = "復元中...";

  try {
    openDatabase(stored.bytes);
    localMetadata = await loadLocalMetadata();

    if (!localMetadata || !localMetadata.sha256) {
      const hash = await sha256Hex(stored.bytes);
      localMetadata = {
        artifact_type: "jrdb_stats_mart",
        schema_version: "1.1",
        data_version: "local-" + hash.slice(0, 12),
        size: stored.size,
        sha256: hash,
        synced_at: new Date(stored.modified).toISOString(),
        source: "existing_opfs"
      };
      await saveLocalMetadata(localMetadata);
    }

    setDbLoaded("OPFSから復元", stored.size, stored.modified, localMetadata);
    runAggregation();
    return true;
  } catch (error) {
    console.error("Stored DB restore failed", error);
    dbStatus.textContent = "保存DBエラー";
    syncProgress.textContent = "保存済みDBを開けませんでした: " + error.message;
    return false;
  }
}

/**
 * 配布manifestの最低限の形式を検証する。
 */
function validateRemoteManifest(manifest) {
  const required = ["artifact_type", "schema_version", "data_version", "size", "sha256", "download"];
  required.forEach(function (key) {
    if (!Object.prototype.hasOwnProperty.call(manifest, key)) {
      throw new Error("manifest必須項目がありません: " + key);
    }
  });

  if (manifest.artifact_type !== "jrdb_stats_mart") {
    throw new Error("artifact_typeが不正です");
  }
  if (String(manifest.schema_version) !== "1.1") {
    throw new Error("未対応schema_versionです: " + manifest.schema_version);
  }
  if (!manifest.download.path) {
    throw new Error("download.pathがありません");
  }
}

/**
 * 最新manifestを取得し、ローカル版との新旧を判定する。
 */
async function checkRemoteManifest(autoSyncWhenMissing) {
  if (!navigator.onLine || syncInProgress) {
    return;
  }

  remoteStatus.textContent = "確認中...";
  checkUpdateButton.disabled = true;

  try {
    const response = await fetch(REMOTE_MANIFEST_URL + "?t=" + Date.now(), { cache: "no-store" });
    if (response.status === 404) {
      remoteManifest = null;
      remoteStatus.textContent = "配布データ未設定";
      return;
    }
    if (!response.ok) {
      throw new Error("manifest HTTP " + response.status);
    }

    const manifest = await response.json();
    validateRemoteManifest(manifest);
    remoteManifest = manifest;

    if (localMetadata && localMetadata.sha256 === manifest.sha256) {
      remoteStatus.textContent = "最新版 / " + manifest.data_version;
      syncButton.disabled = true;
      return;
    }

    remoteStatus.textContent = "更新あり / " + manifest.data_version;
    syncButton.disabled = false;

    if (autoSyncWhenMissing && !db) {
      await syncFromRemote();
    }
  } catch (error) {
    console.error("Remote manifest check failed", error);
    remoteStatus.textContent = "確認失敗";
    syncProgress.textContent = "最新版確認に失敗しました。ローカルDBはそのまま利用できます。";
  } finally {
    if (navigator.onLine && !syncInProgress) {
      checkUpdateButton.disabled = false;
    }
  }
}

/**
 * 配布版SQLiteを取得し、安全にcurrent.sqliteへ昇格する。
 */
async function syncFromRemote() {
  if (!remoteManifest || syncInProgress || !navigator.onLine) {
    return;
  }

  syncInProgress = true;
  syncButton.disabled = true;
  checkUpdateButton.disabled = true;
  syncProgress.textContent = "配布版をダウンロードしています...";

  try {
    const response = await fetch(remoteManifest.download.path + "?v=" + encodeURIComponent(remoteManifest.data_version), {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error("SQLite HTTP " + response.status);
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength !== Number(remoteManifest.size)) {
      throw new Error("サイズ不一致: expected=" + remoteManifest.size + " actual=" + bytes.byteLength);
    }

    syncProgress.textContent = "SHA-256とSQLiteを検証しています...";
    const actualHash = await sha256Hex(bytes);
    if (actualHash !== String(remoteManifest.sha256).toLowerCase()) {
      throw new Error("SHA-256が一致しません");
    }

    validateDatabaseBytes(bytes);
    await writeOpfsFile(OPFS_INCOMING, bytes);

    const current = await readOpfsFile(OPFS_CURRENT);
    if (current) {
      await writeOpfsFile(OPFS_PREVIOUS, current.bytes);
    }

    await writeOpfsFile(OPFS_CURRENT, bytes);
    await removeOpfsFile(OPFS_INCOMING);

    const metadata = {
      artifact_type: remoteManifest.artifact_type,
      schema_version: String(remoteManifest.schema_version),
      data_version: remoteManifest.data_version,
      period_from: remoteManifest.period_from || null,
      period_to: remoteManifest.period_to || null,
      size: Number(remoteManifest.size),
      sha256: String(remoteManifest.sha256).toLowerCase(),
      synced_at: new Date().toISOString(),
      source: "remote_manifest"
    };
    await saveLocalMetadata(metadata);

    openDatabase(bytes);
    setDbLoaded("自動同期", bytes.byteLength, Date.now(), metadata);
    remoteStatus.textContent = "最新版 / " + remoteManifest.data_version;
    syncProgress.textContent = "同期完了。オフライン利用できます。";
    runAggregation();
  } catch (error) {
    console.error("Remote sync failed", error);
    syncProgress.textContent = "同期失敗: " + error.message + "。既存のローカルDBは保持しています。";
    remoteStatus.textContent = "同期失敗";
  } finally {
    syncInProgress = false;
    if (navigator.onLine) {
      checkUpdateButton.disabled = false;
    }
  }
}

/**
 * 端末内DBと同期メタデータを削除する。
 */
async function removeLocalDatabase() {
  if (!window.confirm("端末内に保存したStats Martを削除しますか？")) {
    return;
  }

  closeDatabase();
  await removeOpfsFile(OPFS_CURRENT);
  await removeOpfsFile(OPFS_PREVIOUS);
  await removeOpfsFile(OPFS_INCOMING);
  await removeOpfsFile(OPFS_METADATA);
  localMetadata = null;

  dbStatus.textContent = "未設定";
  syncStatus.textContent = "未同期";
  clearButton.disabled = true;
  aggregateButton.disabled = true;
  tabs.forEach(function (tab) { tab.disabled = true; });
  [yearFrom, yearTo, venue, trackType, distance, trackCondition, minStarts].forEach(function (element) {
    element.disabled = true;
  });
  resultArea.innerHTML = '<div class="empty-state">Stats Martを同期すると集計結果を表示します。</div>';
  queryStatus.textContent = "";
  syncProgress.textContent = "端末DBを削除しました。";

  if (navigator.onLine) {
    await checkRemoteManifest(true);
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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

    const restored = await restoreLocalDatabase();
    if (navigator.onLine) {
      await checkRemoteManifest(!restored);
    }
  } catch (error) {
    console.error("PWA initialization failed", error);
    dbStatus.textContent = "初期化失敗";
    syncProgress.textContent = "初期化失敗: " + error.message;
  }
}

fileInput.addEventListener("change", function () {
  importButton.disabled = !(fileInput.files && fileInput.files.length > 0);
});
importButton.addEventListener("click", importSelectedFile);
clearButton.addEventListener("click", removeLocalDatabase);
aggregateButton.addEventListener("click", runAggregation);
checkUpdateButton.addEventListener("click", function () { checkRemoteManifest(false); });
syncButton.addEventListener("click", syncFromRemote);
window.addEventListener("online", function () {
  updateNetworkStatus();
  checkRemoteManifest(false);
});
window.addEventListener("offline", updateNetworkStatus);

initialize();

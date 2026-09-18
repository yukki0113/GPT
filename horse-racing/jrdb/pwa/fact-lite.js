"use strict";

const FACT_PARQUET_RUNTIME_WAIT_MS = 25;
const FACT_PARQUET_RUNTIME_WAIT_ATTEMPTS = 200;
const factNetworkBadge = document.getElementById("fact-network-badge");
const factDbStatus = document.getElementById("fact-db-status");
const factSyncStatus = document.getElementById("fact-sync-status");
const factRemoteStatus = document.getElementById("fact-remote-status");
const factOpfsStatus = document.getElementById("fact-opfs-status");
const factSyncProgress = document.getElementById("fact-sync-progress");
const factCheckButton = document.getElementById("fact-btn-check");
const factSyncButton = document.getElementById("fact-btn-sync");
const factAggregateButton = document.getElementById("fact-btn-aggregate");
const factClearButton = document.getElementById("fact-btn-clear");
const factResultArea = document.getElementById("fact-result-area");
const factQueryStatus = document.getElementById("fact-query-status");
const factTabs = Array.from(document.querySelectorAll("#fact-tabs .tab"));
const factYearFrom = document.getElementById("fact-year-from");
const factYearTo = document.getElementById("fact-year-to");
const factMonthFrom = document.getElementById("fact-month-from");
const factMonthTo = document.getElementById("fact-month-to");
const factVenue = document.getElementById("fact-venue");
const factTrackType = document.getElementById("fact-track-type");
const factDistanceFrom = document.getElementById("fact-distance-from");
const factDistanceTo = document.getElementById("fact-distance-to");
const factTrackCondition = document.getElementById("fact-track-condition");
const factRaceClass = document.getElementById("fact-race-class");
const factRaceName = document.getElementById("fact-race-name");
const factRaceNameNote = document.getElementById("fact-race-name-note");
const factMinStarts = document.getElementById("fact-min-starts");
const FACT_FILTER_ELEMENTS = [factYearFrom, factYearTo, factMonthFrom, factMonthTo, factVenue, factTrackType, factDistanceFrom, factDistanceTo, factTrackCondition, factRaceClass, factMinStarts];

const POPULARITY_EXPRESSION = "CASE WHEN f.final_win_popularity BETWEEN 1 AND 9 THEN CAST(f.final_win_popularity AS TEXT) WHEN f.final_win_popularity >= 10 THEN '10～' ELSE '不明' END";
const DISTANCE_CHANGE_EXPRESSION = "CASE WHEN f.prev_distance_delta IS NULL THEN 'unknown' WHEN f.prev_distance_delta > 0 THEN 'extend' WHEN f.prev_distance_delta = 0 THEN 'same' ELSE 'shorten' END";
const RACE_CLASS_EXPRESSION = "CASE WHEN f.grade_code = 1 THEN 11 WHEN f.grade_code = 2 THEN 10 WHEN f.grade_code = 3 THEN 9 WHEN f.grade_code = 4 THEN 12 WHEN f.grade_code = 6 THEN 8 WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A1' THEN 1 WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A2' THEN 2 WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A3' THEN 3 WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('04', '05') THEN 4 WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('08', '09', '10') THEN 5 WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('15', '16') THEN 6 WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'OP' THEN 7 ELSE 13 END";
const FACT_AXIS_CONFIG = {
  // DuckDB enforces GROUP BY semantics. Keep the former SQLite grouping key
  // (the dimension ID) and select the associated display label without
  // merging distinct IDs that happen to share a name.
  sire: { label: "種牡馬", select: "ANY_VALUE(s.name)", group: "f.sire_id", joins: "LEFT JOIN dim_sire AS s ON s.id = f.sire_id" },
  jockey: { label: "騎手", select: "ANY_VALUE(j.name)", group: "f.jockey_id", joins: "LEFT JOIN dim_jockey AS j ON j.id = f.jockey_id" },
  frame: { label: "枠", select: "f.frame_no", group: "f.frame_no", joins: "" },
  style: { label: "脚質", select: "f.running_style", group: "f.running_style", joins: "" },
  age: { label: "年齢", select: "f.age", group: "f.age", joins: "" },
  sex: { label: "性別", select: "f.sex_code", group: "f.sex_code", joins: "" },
  popularity: { label: "人気", select: POPULARITY_EXPRESSION, group: POPULARITY_EXPRESSION, joins: "" },
  distance_change: { label: "前走距離", select: DISTANCE_CHANGE_EXPRESSION, group: DISTANCE_CHANGE_EXPRESSION, joins: "" },
  prev_class: { label: "前走クラス", select: "f.prev_class_code", group: "f.prev_class_code", joins: "" }
};
const RUNNING_STYLE_LABELS = { 1: "逃げ", 2: "先行", 3: "差し", 4: "追込", 5: "好位差し", 6: "自在" };
const SEX_LABELS = { 1: "牡", 2: "牝", 3: "セン" };
const DISTANCE_CHANGE_LABELS = { extend: "距離延長", same: "同距離", shorten: "距離短縮", unknown: "前走不明" };
const PREVIOUS_CLASS_LABELS = { 1: "新馬", 2: "未出走", 3: "未勝利", 4: "1勝", 5: "2勝", 6: "3勝", 7: "オープン", 8: "L", 9: "G3", 10: "G2", 11: "G1", 12: "その他重賞", 13: "その他" };

let factDb = null;
let factQueryAdapter = null;
let factLocalMetadata = null;
let factSyncInProgress = false;
let factActiveAxis = "sire";
let factHasRaceNames = false;

function factProgress(stage, table) {
  const messages = { cache: "ローカルParquetを検証中…", manifest: "Parquet manifest確認中…", duckdb: "DuckDB初期化・schema/行数検証中…" };
  factSyncProgress.textContent = stage === "download" ? "Parquet取得・SHA-256検証中…（" + table + "）" : (messages[stage] || "Parquet状態を確認中…");
}

function updateFactNetworkStatus() {
  const online = navigator.onLine;
  factNetworkBadge.textContent = online ? "オンライン" : "オフライン";
  factNetworkBadge.classList.toggle("online", online);
  factNetworkBadge.classList.toggle("offline", !online);
  factCheckButton.disabled = !online || factSyncInProgress;
  factSyncButton.disabled = !online || factSyncInProgress;
  if (!online) factRemoteStatus.textContent = "オフライン";
}

async function waitForFactDuckDb() {
  for (let i = 0; i < FACT_PARQUET_RUNTIME_WAIT_ATTEMPTS; i += 1) {
    if (window.JRDBFactLiteDuckDB && window.JRDBFactLiteQueryAdapters) return window.JRDBFactLiteDuckDB;
    await new Promise(function (resolve) { setTimeout(resolve, FACT_PARQUET_RUNTIME_WAIT_MS); });
  }
  throw new Error("DuckDB-Wasm runtimeが読み込めません");
}

async function closeFactDatabase() {
  if (factQueryAdapter) await factQueryAdapter.close();
  if (factDb) await factDb.terminate();
  factDb = null;
  factQueryAdapter = null;
}

async function validateFactDatabaseObject(database, adapter) {
  const queryAdapter = adapter || factQueryAdapter;
  if (!queryAdapter) throw new Error("Fact Lite query adapterがありません");
  const names = await queryAdapter.tableNames();
  ["fact_stats_entry", "dim_sire", "dim_bms", "dim_jockey", "dim_race", "meta_pwa_fact_build"].forEach(function (name) {
    if (!names.has(name)) throw new Error("必須テーブルがありません: " + name);
  });
  const columns = await queryAdapter.tableColumns("fact_stats_entry");
  ["month", "race_id", "prev_distance_delta", "prev_class_code", "win5_leg_no"].forEach(function (name) {
    if (!columns.has(name)) throw new Error("Fact Lite必須列がありません: " + name);
  });
  return database;
}

function validateFactManifest() {}

async function refreshFactLocalCapabilities() {
  factHasRaceNames = false;
  if (factQueryAdapter) {
    const rows = await factQueryAdapter.query("SELECT COUNT(*) AS race_name_count FROM dim_race WHERE TRIM(COALESCE(race_name, '')) <> ''");
    factHasRaceNames = rows.length > 0 && Number(rows[0].race_name_count) > 0;
  }
  if (factHasRaceNames) {
    factRaceName.disabled = false; factRaceName.placeholder = "例: 記念 / 天皇賞"; factRaceNameNote.textContent = "部分一致で検索します";
  } else {
    factRaceName.value = ""; factRaceName.disabled = true; factRaceName.placeholder = "現配布データでは未収録"; factRaceNameNote.textContent = "現配布データにはレース名が未収録です";
  }
}

function formatFactBytes(bytes) { return (Number(bytes) / (1024 * 1024)).toFixed(1) + " MiB"; }
function factGenerationSize(manifest) { return Object.values(manifest.tables).reduce(function (sum, entry) { return sum + Number(entry.size_bytes); }, 0); }

async function setFactDbLoaded(source, size, metadata) {
  factDbStatus.textContent = "読込済み / " + formatFactBytes(size);
  factSyncStatus.textContent = source + " / " + metadata.current_generation;
  factAggregateButton.disabled = false; factClearButton.disabled = false;
  FACT_FILTER_ELEMENTS.forEach(function (element) { element.disabled = false; });
  factTabs.forEach(function (tab) { tab.disabled = false; });
  await refreshFactLocalCapabilities();
}

async function openFactCachedGeneration(cached, metadata, source) {
  const runtime = await waitForFactDuckDb();
  const database = await runtime.openCached(cached);
  const adapter = window.JRDBFactLiteQueryAdapters.createDuckDb(database);
  try {
    await validateFactDatabaseObject(database, adapter);
  } catch (error) {
    await adapter.close(); await database.terminate(); throw error;
  }
  await closeFactDatabase();
  factDb = database; factQueryAdapter = adapter; factLocalMetadata = metadata;
  await setFactDbLoaded(source, factGenerationSize(cached.manifest), metadata);
}

async function restoreFactDatabase() {
  const runtime = await waitForFactDuckDb();
  factDbStatus.textContent = "Parquet cacheを復元中…";
  const restored = await runtime.restoreCache(factProgress);
  if (!restored) { factDbStatus.textContent = "未設定"; return false; }
  await openFactCachedGeneration(restored.cached, restored.metadata, "OPFSから復元");
  factSyncProgress.textContent = "検証済みParquet cacheを復元しました。";
  await runFactAggregation();
  return true;
}

async function checkFactManifest(autoSyncWhenMissing) {
  if (!navigator.onLine || factSyncInProgress) return;
  const runtime = await waitForFactDuckDb();
  factCheckButton.disabled = true; factRemoteStatus.textContent = "確認中…"; factProgress("manifest");
  try {
    const remote = await runtime.fetchCurrent();
    const generation = remote.current.generation_id;
    if (factLocalMetadata && factLocalMetadata.current_generation === generation) {
      factRemoteStatus.textContent = "最新版 / " + generation; factSyncButton.disabled = true; return;
    }
    factRemoteStatus.textContent = "更新あり / " + generation; factSyncButton.disabled = false;
    if (autoSyncWhenMissing && !factDb) await syncFactFromRemote();
  } catch (error) {
    console.error("Fact Lite Parquet manifest check failed", error);
    factRemoteStatus.textContent = "確認失敗";
    factSyncProgress.textContent = "配布版を確認できませんでした。検証済みcacheは維持します。";
  } finally { updateFactNetworkStatus(); }
}

async function syncFactFromRemote() {
  if (!navigator.onLine || factSyncInProgress) return;
  factSyncInProgress = true; updateFactNetworkStatus();
  try {
    const runtime = await waitForFactDuckDb();
    const result = await runtime.synchronizeCache(fetch, factProgress);
    await openFactCachedGeneration(result.cached, result.metadata, result.updated ? "Parquet同期" : "OPFS cache再利用");
    factRemoteStatus.textContent = "最新版 / " + result.cached.generationId;
    factSyncProgress.textContent = result.updated ? "Parquet同期・検証が完了しました。次回はオフラインでも復元できます。" : "配布版とローカルcacheは同一generationです。";
    await runFactAggregation();
  } catch (error) {
    console.error("Fact Lite Parquet sync failed", error);
    factSyncProgress.textContent = factDb ? "同期に失敗しました。検証済みの既存cacheを継続利用します。" : "同期に失敗しました。検証済みcacheがないため集計を開始できません。";
  } finally { factSyncInProgress = false; updateFactNetworkStatus(); }
}

function buildFactWhere() {
  const clauses = ["f.year BETWEEN ? AND ?"];
  const params = [Number(factYearFrom.value), Number(factYearTo.value)];
  const extraJoins = [];
  const from = factMonthFrom.value, to = factMonthTo.value;
  if (from && to) { if (Number(from) <= Number(to)) { clauses.push("f.month BETWEEN ? AND ?"); params.push(Number(from), Number(to)); } else { clauses.push("(f.month >= ? OR f.month <= ?)"); params.push(Number(from), Number(to)); } }
  else if (from) { clauses.push("f.month >= ?"); params.push(Number(from)); } else if (to) { clauses.push("f.month <= ?"); params.push(Number(to)); }
  [[factVenue, "f.venue_code = ?"], [factTrackType, "f.track_type = ?"], [factDistanceFrom, "f.distance >= ?"], [factDistanceTo, "f.distance <= ?"], [factTrackCondition, "f.track_condition_code = ?"]].forEach(function (item) { if (item[0].value) { clauses.push(item[1]); params.push(Number(item[0].value)); } });
  if (factRaceClass.value) { clauses.push(RACE_CLASS_EXPRESSION + " = ?"); params.push(Number(factRaceClass.value)); }
  const raceName = factRaceName.value.trim();
  if (factHasRaceNames && raceName) { extraJoins.push("JOIN dim_race AS r ON r.id = f.race_id"); clauses.push("INSTR(COALESCE(r.race_name, ''), ?) > 0"); params.push(raceName); }
  return { clauses, params, extraJoins };
}

function buildFactQuery() {
  const config = FACT_AXIS_CONFIG[factActiveAxis], where = buildFactWhere();
  const sql = ["SELECT", "  " + config.select + " AS item,", "  COUNT(*) AS starts,", "  SUM(CASE WHEN f.finish = 1 THEN 1 ELSE 0 END) AS wins,", "  SUM(CASE WHEN f.finish = 2 THEN 1 ELSE 0 END) AS seconds,", "  SUM(CASE WHEN f.finish = 3 THEN 1 ELSE 0 END) AS thirds,", "  SUM(CASE WHEN f.finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS top3,", "  SUM(COALESCE(f.win_payout, 0)) AS win_payout_sum,", "  SUM(COALESCE(f.place_payout, 0)) AS place_payout_sum", "FROM fact_stats_entry AS f", config.joins, where.extraJoins.join("\n"), "WHERE " + where.clauses.join(" AND "), "GROUP BY " + config.group, "HAVING COUNT(*) >= ?"].filter(Boolean).join("\n");
  where.params.push(Math.max(1, Number(factMinStarts.value) || 1));
  return { sql, params: where.params };
}

function factPercent(numerator, denominator) { return !denominator ? "0.0%" : (100 * Number(numerator) / Number(denominator)).toFixed(1) + "%"; }
function factReturnRate(payout, starts) { return !starts ? "0.0%" : (Number(payout) / Number(starts)).toFixed(1) + "%"; }
function escapeFactHtml(value) { return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
function displayFactItem(item) {
  if (factActiveAxis === "style") return RUNNING_STYLE_LABELS[item] || item || "不明";
  if (factActiveAxis === "sex") return SEX_LABELS[item] || item || "不明";
  if (factActiveAxis === "distance_change") return DISTANCE_CHANGE_LABELS[item] || item || "前走不明";
  if (factActiveAxis === "prev_class") return item === null || item === undefined || item === "" ? "前走不明" : (PREVIOUS_CLASS_LABELS[item] || "その他");
  return item === null || item === undefined || item === "" ? "不明" : item;
}
function renderFactResults(rows) {
  if (!rows.length) { factResultArea.innerHTML = '<div class="empty-state">該当データがありません。</div>'; return; }
  let html = '<div class="table-wrap"><table><thead><tr><th>対象</th><th>出走</th><th>勝率</th><th>複勝率</th><th>単回</th><th>複回</th></tr></thead><tbody>';
  rows.forEach(function (row) { html += "<tr><td>" + escapeFactHtml(displayFactItem(row.item)) + "</td><td>" + row.starts + "</td><td>" + factPercent(row.wins, row.starts) + "</td><td>" + factPercent(row.top3, row.starts) + "</td><td>" + factReturnRate(row.win_payout_sum, row.starts) + "</td><td>" + factReturnRate(row.place_payout_sum, row.starts) + "</td></tr>"; });
  factResultArea.innerHTML = html + "</tbody></table></div>";
}
async function runFactAggregation() {
  if (!factQueryAdapter) return;
  const started = performance.now();
  try { const query = buildFactQuery(), rows = await factQueryAdapter.query(query.sql, query.params); renderFactResults(rows); factQueryStatus.textContent = FACT_AXIS_CONFIG[factActiveAxis].label + " / " + rows.length + "件 / " + (performance.now() - started).toFixed(0) + " ms"; }
  catch (error) { console.error("Fact Lite DuckDB aggregation failed", error); factQueryStatus.textContent = "集計に失敗しました。"; }
}
function configureFactTabs() { factTabs.forEach(function (tab) { tab.addEventListener("click", function () { factActiveAxis = tab.dataset.axis; factTabs.forEach(function (item) { item.classList.remove("active"); }); tab.classList.add("active"); void runFactAggregation(); }); }); }
function clearFactFilters() { factYearFrom.value = "2016"; factYearTo.value = "2026"; factMonthFrom.value = ""; factMonthTo.value = ""; factVenue.value = ""; factTrackType.value = ""; factDistanceFrom.value = ""; factDistanceTo.value = ""; factTrackCondition.value = ""; factRaceClass.value = ""; factRaceName.value = ""; factMinStarts.value = "20"; void runFactAggregation(); }

async function initializeFactLite() {
  updateFactNetworkStatus(); configureFactTabs();
  if (!navigator.storage || !navigator.storage.getDirectory) { factOpfsStatus.textContent = "非対応"; factDbStatus.textContent = "利用不可"; return; }
  try { await navigator.storage.getDirectory(); factOpfsStatus.textContent = "利用可能"; const restored = await restoreFactDatabase(); if (navigator.onLine) await checkFactManifest(!restored); }
  catch (error) { console.error("Fact Lite Parquet initialization failed", error); factDbStatus.textContent = "初期化失敗"; factSyncProgress.textContent = "Parquetを初期化できませんでした。"; }
}

factCheckButton.addEventListener("click", function () { void checkFactManifest(false); });
factSyncButton.addEventListener("click", function () { void syncFactFromRemote(); });
factAggregateButton.addEventListener("click", function () { void runFactAggregation(); });
factClearButton.addEventListener("click", clearFactFilters);
window.addEventListener("online", function () { updateFactNetworkStatus(); void checkFactManifest(false); });
window.addEventListener("offline", updateFactNetworkStatus);
window.addEventListener("load", function () { void initializeFactLite(); }, { once: true });

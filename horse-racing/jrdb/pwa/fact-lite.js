"use strict";

const FACT_SQL_JS_URL = "./vendor/sql-wasm.js";
const FACT_SQL_WASM_URL = "./vendor/sql-wasm.wasm";
const FACT_MANIFEST_URL = "./data/fact-lite/manifest.json";
const FACT_OPFS_DIR = "jrdb-fact-lite";
const FACT_CURRENT = "current.sqlite";
const FACT_PREVIOUS = "previous.sqlite";
const FACT_INCOMING = "incoming.sqlite";
const FACT_METADATA = "metadata.json";
const FACT_SCHEMA_VERSION = "0.2";

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

const FACT_FILTER_ELEMENTS = [
  factYearFrom,
  factYearTo,
  factMonthFrom,
  factMonthTo,
  factVenue,
  factTrackType,
  factDistanceFrom,
  factDistanceTo,
  factTrackCondition,
  factRaceClass,
  factMinStarts
];

const POPULARITY_EXPRESSION =
  "CASE " +
  "WHEN f.final_win_popularity BETWEEN 1 AND 9 THEN CAST(f.final_win_popularity AS TEXT) " +
  "WHEN f.final_win_popularity >= 10 THEN '10～' " +
  "ELSE '不明' END";

const DISTANCE_CHANGE_EXPRESSION =
  "CASE " +
  "WHEN f.prev_distance_delta IS NULL THEN 'unknown' " +
  "WHEN f.prev_distance_delta > 0 THEN 'extend' " +
  "WHEN f.prev_distance_delta = 0 THEN 'same' " +
  "ELSE 'shorten' END";

const RACE_CLASS_EXPRESSION =
  "CASE " +
  "WHEN f.grade_code = 1 THEN 11 " +
  "WHEN f.grade_code = 2 THEN 10 " +
  "WHEN f.grade_code = 3 THEN 9 " +
  "WHEN f.grade_code = 4 THEN 12 " +
  "WHEN f.grade_code = 6 THEN 8 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A1' THEN 1 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A2' THEN 2 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'A3' THEN 3 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('04', '05') THEN 4 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('08', '09', '10') THEN 5 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) IN ('15', '16') THEN 6 " +
  "WHEN TRIM(COALESCE(f.race_condition_code, '')) = 'OP' THEN 7 " +
  "ELSE 13 END";

const FACT_AXIS_CONFIG = {
  sire: {
    label: "種牡馬",
    select: "s.name",
    group: "f.sire_id",
    joins: "LEFT JOIN dim_sire AS s ON s.id = f.sire_id"
  },
  jockey: {
    label: "騎手",
    select: "j.name",
    group: "f.jockey_id",
    joins: "LEFT JOIN dim_jockey AS j ON j.id = f.jockey_id"
  },
  frame: {
    label: "枠",
    select: "f.frame_no",
    group: "f.frame_no",
    joins: ""
  },
  style: {
    label: "脚質",
    select: "f.running_style",
    group: "f.running_style",
    joins: ""
  },
  age: {
    label: "年齢",
    select: "f.age",
    group: "f.age",
    joins: ""
  },
  sex: {
    label: "性別",
    select: "f.sex_code",
    group: "f.sex_code",
    joins: ""
  },
  popularity: {
    label: "人気",
    select: POPULARITY_EXPRESSION,
    group: POPULARITY_EXPRESSION,
    joins: ""
  },
  distance_change: {
    label: "前走距離",
    select: DISTANCE_CHANGE_EXPRESSION,
    group: DISTANCE_CHANGE_EXPRESSION,
    joins: ""
  },
  prev_class: {
    label: "前走クラス",
    select: "f.prev_class_code",
    group: "f.prev_class_code",
    joins: ""
  }
};

const RUNNING_STYLE_LABELS = {
  1: "逃げ",
  2: "先行",
  3: "差し",
  4: "追込",
  5: "好位差し",
  6: "自在"
};

const SEX_LABELS = {
  1: "牡",
  2: "牝",
  3: "セン"
};

const DISTANCE_CHANGE_LABELS = {
  extend: "距離延長",
  same: "同距離",
  shorten: "距離短縮",
  unknown: "前走不明"
};

const PREVIOUS_CLASS_LABELS = {
  1: "新馬",
  2: "未出走",
  3: "未勝利",
  4: "1勝",
  5: "2勝",
  6: "3勝",
  7: "オープン",
  8: "L",
  9: "G3",
  10: "G2",
  11: "G1",
  12: "その他重賞",
  13: "その他"
};

let FACT_SQL = null;
let factDb = null;
let factLocalMetadata = null;
let factRemoteManifest = null;
let factSyncInProgress = false;
let factActiveAxis = "sire";
let factHasRaceNames = false;

function updateFactNetworkStatus() {
  if (navigator.onLine) {
    factNetworkBadge.textContent = "オンライン";
    factNetworkBadge.classList.add("online");
    factNetworkBadge.classList.remove("offline");
    factCheckButton.disabled = false;
    return;
  }

  factNetworkBadge.textContent = "オフライン";
  factNetworkBadge.classList.add("offline");
  factNetworkBadge.classList.remove("online");
  factCheckButton.disabled = true;
  factSyncButton.disabled = true;
  factRemoteStatus.textContent = "オフライン";
}

async function loadFactSqlJs() {
  if (!window.initSqlJs) {
    await new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = FACT_SQL_JS_URL;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  FACT_SQL = await window.initSqlJs({
    locateFile: function () {
      return FACT_SQL_WASM_URL;
    }
  });
}

async function getFactDirectory(create) {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(FACT_OPFS_DIR, { create: create });
}

async function writeFactFile(fileName, bytes) {
  const directory = await getFactDirectory(true);
  const handle = await directory.getFileHandle(fileName, { create: true });
  const writable = await handle.createWritable();
  await writable.write(bytes);
  await writable.close();
}

async function readFactFile(fileName) {
  try {
    const directory = await getFactDirectory(false);
    const handle = await directory.getFileHandle(fileName, { create: false });
    const file = await handle.getFile();
    return {
      bytes: new Uint8Array(await file.arrayBuffer()),
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

async function removeFactFile(fileName) {
  try {
    const directory = await getFactDirectory(false);
    await directory.removeEntry(fileName);
  } catch (error) {
    if (!error || error.name !== "NotFoundError") {
      throw error;
    }
  }
}

async function saveFactMetadata(metadata) {
  const bytes = new TextEncoder().encode(JSON.stringify(metadata, null, 2) + "\n");
  await writeFactFile(FACT_METADATA, bytes);
  factLocalMetadata = metadata;
}

async function loadFactMetadata() {
  const stored = await readFactFile(FACT_METADATA);
  if (!stored) {
    return null;
  }

  try {
    return JSON.parse(new TextDecoder().decode(stored.bytes));
  } catch (error) {
    console.warn("Fact Lite metadata parse failed", error);
    return null;
  }
}

async function factSha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map(function (value) {
      return value.toString(16).padStart(2, "0");
    })
    .join("");
}

function validateFactDatabaseObject(database) {
  const requiredTables = [
    "fact_stats_entry",
    "dim_sire",
    "dim_bms",
    "dim_jockey",
    "dim_race",
    "meta_pwa_fact_build"
  ];
  const tableResult = database.exec(
    "SELECT name FROM sqlite_master WHERE type='table'"
  );
  const tableNames = new Set();

  if (tableResult.length > 0) {
    tableResult[0].values.forEach(function (row) {
      tableNames.add(row[0]);
    });
  }

  requiredTables.forEach(function (tableName) {
    if (!tableNames.has(tableName)) {
      throw new Error("必須テーブルがありません: " + tableName);
    }
  });

  const factInfo = database.exec("PRAGMA table_info(fact_stats_entry)");
  const factColumns = new Set();
  if (factInfo.length > 0) {
    factInfo[0].values.forEach(function (row) {
      factColumns.add(row[1]);
    });
  }

  ["month", "race_id", "prev_distance_delta", "prev_class_code"].forEach(
    function (columnName) {
      if (!factColumns.has(columnName)) {
        throw new Error("Fact Lite v0.2列がありません: " + columnName);
      }
    }
  );

  const meta = database.exec(
    "SELECT schema_version FROM meta_pwa_fact_build " +
    "ORDER BY build_id DESC LIMIT 1"
  );
  if (
    meta.length === 0 ||
    meta[0].values.length === 0 ||
    String(meta[0].values[0][0]) !== FACT_SCHEMA_VERSION
  ) {
    throw new Error("Fact Lite v0.2ではない保存DBです");
  }

  const integrity = database.exec("PRAGMA integrity_check");
  if (
    integrity.length === 0 ||
    integrity[0].values.length === 0 ||
    integrity[0].values[0][0] !== "ok"
  ) {
    throw new Error("SQLite integrity_check が ok ではありません");
  }
}

function openFactDatabase(bytes) {
  const candidate = new FACT_SQL.Database(bytes);

  try {
    validateFactDatabaseObject(candidate);
  } catch (error) {
    candidate.close();
    throw error;
  }

  if (factDb) {
    factDb.close();
  }
  factDb = candidate;
  refreshFactLocalCapabilities();
}

function validateFactBytes(bytes) {
  const temporary = new FACT_SQL.Database(bytes);
  try {
    validateFactDatabaseObject(temporary);
  } finally {
    temporary.close();
  }
}

function refreshFactLocalCapabilities() {
  factHasRaceNames = false;

  if (factDb) {
    const result = factDb.exec(
      "SELECT COUNT(*) FROM dim_race " +
      "WHERE TRIM(COALESCE(race_name, '')) <> ''"
    );
    if (result.length > 0 && result[0].values.length > 0) {
      factHasRaceNames = Number(result[0].values[0][0]) > 0;
    }
  }

  if (factHasRaceNames) {
    factRaceName.disabled = false;
    factRaceName.placeholder = "例: 記念 / 天皇賞";
    factRaceNameNote.textContent = "部分一致で検索します";
    return;
  }

  factRaceName.value = "";
  factRaceName.disabled = true;
  factRaceName.placeholder = "現配布データでは未収録";
  factRaceNameNote.textContent = "現配布データにはレース名が未収録です";
}

function formatFactBytes(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
}

function setFactDbLoaded(source, size, metadata) {
  factDbStatus.textContent = "読込済み / " + formatFactBytes(size);
  if (metadata && metadata.data_version) {
    factSyncStatus.textContent = source + " / " + metadata.data_version;
  } else {
    factSyncStatus.textContent = source;
  }

  factAggregateButton.disabled = false;
  factClearButton.disabled = false;
  FACT_FILTER_ELEMENTS.forEach(function (element) {
    element.disabled = false;
  });
  factTabs.forEach(function (tab) {
    tab.disabled = false;
  });
  refreshFactLocalCapabilities();
}

function validateFactManifest(manifest) {
  const required = [
    "artifact_type",
    "schema_version",
    "data_version",
    "size",
    "sha256",
    "download"
  ];

  required.forEach(function (key) {
    if (!Object.prototype.hasOwnProperty.call(manifest, key)) {
      throw new Error("manifest必須項目がありません: " + key);
    }
  });

  if (manifest.artifact_type !== "jrdb_pwa_fact_lite") {
    throw new Error("artifact_typeが不正です");
  }
  if (String(manifest.schema_version) !== FACT_SCHEMA_VERSION) {
    throw new Error("未対応schema_versionです: " + manifest.schema_version);
  }
  if (!manifest.download.path) {
    throw new Error("download.pathがありません");
  }
}

async function restoreFactDatabase() {
  const stored = await readFactFile(FACT_CURRENT);
  if (!stored) {
    factDbStatus.textContent = "未設定";
    return false;
  }

  factDbStatus.textContent = "復元中...";
  try {
    openFactDatabase(stored.bytes);
    factLocalMetadata = await loadFactMetadata();
    setFactDbLoaded("OPFSから復元", stored.size, factLocalMetadata);
    runFactAggregation();
    return true;
  } catch (error) {
    console.warn("Fact Lite restore requires refresh", error);
    factDbStatus.textContent = "旧版DB / 更新待ち";
    factSyncProgress.textContent =
      "保存済みDBはv0.2互換ではないため、オンライン時に最新版へ更新します。";
    factDb = null;
    return false;
  }
}

async function checkFactManifest(autoSyncWhenMissing) {
  if (!navigator.onLine || factSyncInProgress) {
    return;
  }

  factCheckButton.disabled = true;
  factRemoteStatus.textContent = "確認中...";

  try {
    const response = await fetch(
      FACT_MANIFEST_URL + "?t=" + Date.now(),
      { cache: "no-store" }
    );
    if (response.status === 404) {
      factRemoteStatus.textContent = "配布データ未設定";
      return;
    }
    if (!response.ok) {
      throw new Error("manifest HTTP " + response.status);
    }

    const manifest = await response.json();
    validateFactManifest(manifest);
    factRemoteManifest = manifest;

    if (
      factDb &&
      factLocalMetadata &&
      factLocalMetadata.sha256 === manifest.sha256
    ) {
      factRemoteStatus.textContent = "最新版 / " + manifest.data_version;
      factSyncButton.disabled = true;
      return;
    }

    factRemoteStatus.textContent = "更新あり / " + manifest.data_version;
    factSyncButton.disabled = false;

    if (autoSyncWhenMissing && !factDb) {
      await syncFactFromRemote();
    }
  } catch (error) {
    console.error("Fact Lite manifest check failed", error);
    factRemoteStatus.textContent = "確認失敗";
    factSyncProgress.textContent = "最新版確認失敗: " + error.message;
  } finally {
    factCheckButton.disabled = !navigator.onLine;
  }
}

async function syncFactFromRemote() {
  if (!navigator.onLine || factSyncInProgress) {
    return;
  }

  if (!factRemoteManifest) {
    await checkFactManifest(false);
    if (!factRemoteManifest) {
      return;
    }
  }

  factSyncInProgress = true;
  factSyncButton.disabled = true;
  factCheckButton.disabled = true;
  factSyncProgress.textContent = "Fact Lite v0.2を取得中...";

  try {
    const response = await fetch(
      factRemoteManifest.download.path + "?t=" + Date.now(),
      { cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error("SQLite HTTP " + response.status);
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength !== Number(factRemoteManifest.size)) {
      throw new Error("size不一致");
    }

    await writeFactFile(FACT_INCOMING, bytes);
    factSyncProgress.textContent = "SHA-256 / SQLiteを検証中...";

    const hash = await factSha256Hex(bytes);
    if (hash !== factRemoteManifest.sha256) {
      throw new Error("SHA-256不一致");
    }
    validateFactBytes(bytes);

    const oldCurrent = await readFactFile(FACT_CURRENT);
    if (oldCurrent) {
      await writeFactFile(FACT_PREVIOUS, oldCurrent.bytes);
    }
    await writeFactFile(FACT_CURRENT, bytes);
    await removeFactFile(FACT_INCOMING);

    const metadata = {
      artifact_type: factRemoteManifest.artifact_type,
      schema_version: factRemoteManifest.schema_version,
      data_version: factRemoteManifest.data_version,
      period_from: factRemoteManifest.period_from,
      period_to: factRemoteManifest.period_to,
      size: factRemoteManifest.size,
      sha256: factRemoteManifest.sha256,
      capabilities: factRemoteManifest.capabilities || {},
      synced_at: new Date().toISOString(),
      source: "automatic_sync"
    };
    await saveFactMetadata(metadata);

    openFactDatabase(bytes);
    setFactDbLoaded("自動同期", bytes.byteLength, metadata);
    factRemoteStatus.textContent = "最新版 / " + factRemoteManifest.data_version;
    factSyncProgress.textContent = "同期完了。Fact Lite v0.2を利用できます。";
    runFactAggregation();
  } catch (error) {
    console.error("Fact Lite sync failed", error);
    await removeFactFile(FACT_INCOMING);
    factSyncProgress.textContent =
      "同期失敗: " + error.message + "。既存Fact Liteは維持します。";
  } finally {
    factSyncInProgress = false;
    factCheckButton.disabled = !navigator.onLine;
    factSyncButton.disabled = !navigator.onLine || (
      factRemoteManifest &&
      factLocalMetadata &&
      factRemoteManifest.sha256 === factLocalMetadata.sha256
    );
  }
}

function buildFactWhere() {
  const clauses = ["f.year BETWEEN ? AND ?"];
  const params = [Number(factYearFrom.value), Number(factYearTo.value)];
  const extraJoins = [];

  const monthFrom = factMonthFrom.value;
  const monthTo = factMonthTo.value;
  if (monthFrom && monthTo) {
    const fromValue = Number(monthFrom);
    const toValue = Number(monthTo);
    if (fromValue <= toValue) {
      clauses.push("f.month BETWEEN ? AND ?");
      params.push(fromValue, toValue);
    } else {
      clauses.push("(f.month >= ? OR f.month <= ?)");
      params.push(fromValue, toValue);
    }
  } else if (monthFrom) {
    clauses.push("f.month >= ?");
    params.push(Number(monthFrom));
  } else if (monthTo) {
    clauses.push("f.month <= ?");
    params.push(Number(monthTo));
  }

  if (factVenue.value) {
    clauses.push("f.venue_code = ?");
    params.push(Number(factVenue.value));
  }
  if (factTrackType.value) {
    clauses.push("f.track_type = ?");
    params.push(Number(factTrackType.value));
  }
  if (factDistanceFrom.value) {
    clauses.push("f.distance >= ?");
    params.push(Number(factDistanceFrom.value));
  }
  if (factDistanceTo.value) {
    clauses.push("f.distance <= ?");
    params.push(Number(factDistanceTo.value));
  }
  if (factTrackCondition.value) {
    clauses.push("f.track_condition_code = ?");
    params.push(Number(factTrackCondition.value));
  }
  if (factRaceClass.value) {
    clauses.push(RACE_CLASS_EXPRESSION + " = ?");
    params.push(Number(factRaceClass.value));
  }

  const raceName = factRaceName.value.trim();
  if (factHasRaceNames && raceName !== "") {
    extraJoins.push("JOIN dim_race AS r ON r.id = f.race_id");
    clauses.push("INSTR(COALESCE(r.race_name, ''), ?) > 0");
    params.push(raceName);
  }

  if (factAge.value) {
    if (factAge.value === "8") {
      clauses.push("f.age >= 8");
    } else {
      clauses.push("f.age = ?");
      params.push(Number(factAge.value));
    }
  }
  if (factSex.value) {
    clauses.push("f.sex_code = ?");
    params.push(Number(factSex.value));
  }
  if (factRunningStyle.value) {
    clauses.push("f.running_style = ?");
    params.push(Number(factRunningStyle.value));
  }
  if (factPopBand.value) {
    if (factPopBand.value === "1-3") {
      clauses.push("f.final_win_popularity BETWEEN 1 AND 3");
    } else if (factPopBand.value === "4-6") {
      clauses.push("f.final_win_popularity BETWEEN 4 AND 6");
    } else if (factPopBand.value === "7-9") {
      clauses.push("f.final_win_popularity BETWEEN 7 AND 9");
    } else if (factPopBand.value === "10+") {
      clauses.push("f.final_win_popularity >= 10");
    }
  }

  return {
    clauses: clauses,
    params: params,
    extraJoins: extraJoins
  };
}

function buildFactQuery() {
  const config = FACT_AXIS_CONFIG[factActiveAxis];
  const where = buildFactWhere();
  const sql = [
    "SELECT",
    "  " + config.select + " AS item,",
    "  COUNT(*) AS starts,",
    "  SUM(CASE WHEN f.finish = 1 THEN 1 ELSE 0 END) AS wins,",
    "  SUM(CASE WHEN f.finish = 2 THEN 1 ELSE 0 END) AS seconds,",
    "  SUM(CASE WHEN f.finish = 3 THEN 1 ELSE 0 END) AS thirds,",
    "  SUM(CASE WHEN f.finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS top3,",
    "  SUM(COALESCE(f.win_payout, 0)) AS win_payout_sum,",
    "  SUM(COALESCE(f.place_payout, 0)) AS place_payout_sum",
    "FROM fact_stats_entry AS f",
    config.joins,
    where.extraJoins.join("\n"),
    "WHERE " + where.clauses.join(" AND "),
    "GROUP BY " + config.group,
    "HAVING COUNT(*) >= ?",
    "ORDER BY " +
      "(1.0 * SUM(CASE WHEN f.finish = 1 THEN 1 ELSE 0 END) / COUNT(*)) DESC, " +
      "COUNT(*) DESC",
    "LIMIT 200"
  ].filter(Boolean).join("\n");

  where.params.push(Math.max(1, Number(factMinStarts.value) || 1));
  return { sql: sql, params: where.params };
}

function factPercent(numerator, denominator) {
  if (!denominator) {
    return "0.0%";
  }
  return (100 * Number(numerator) / Number(denominator)).toFixed(1) + "%";
}

function factReturnRate(payout, starts) {
  if (!starts) {
    return "0.0%";
  }
  return (Number(payout) / Number(starts)).toFixed(1) + "%";
}

function escapeFactHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function displayFactItem(item) {
  if (factActiveAxis === "style") {
    return RUNNING_STYLE_LABELS[item] || item || "不明";
  }
  if (factActiveAxis === "sex") {
    return SEX_LABELS[item] || item || "不明";
  }
  if (factActiveAxis === "distance_change") {
    return DISTANCE_CHANGE_LABELS[item] || item || "前走不明";
  }
  if (factActiveAxis === "prev_class") {
    if (item === null || item === undefined || item === "") {
      return "前走不明";
    }
    return PREVIOUS_CLASS_LABELS[item] || "その他";
  }
  if (item === null || item === undefined || item === "") {
    return "不明";
  }
  return item;
}

function renderFactResults(rows) {
  if (rows.length === 0) {
    factResultArea.innerHTML =
      '<div class="empty-state">該当データがありません。</div>';
    return;
  }

  let html = '<div class="table-wrap"><table><thead><tr>';
  html +=
    '<th>対象</th><th>出走</th><th>勝率</th><th>複勝率</th>' +
    '<th>単回</th><th>複回</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function (row) {
    html += '<tr>';
    html += '<td>' + escapeFactHtml(displayFactItem(row.item)) + '</td>';
    html += '<td>' + row.starts + '</td>';
    html += '<td>' + factPercent(row.wins, row.starts) + '</td>';
    html += '<td>' + factPercent(row.top3, row.starts) + '</td>';
    html += '<td>' + factReturnRate(row.win_payout_sum, row.starts) + '</td>';
    html += '<td>' + factReturnRate(row.place_payout_sum, row.starts) + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  factResultArea.innerHTML = html;
}

function runFactAggregation() {
  if (!factDb) {
    return;
  }

  const started = performance.now();
  const query = buildFactQuery();
  const statement = factDb.prepare(query.sql);
  const rows = [];

  try {
    statement.bind(query.params);
    while (statement.step()) {
      rows.push(statement.getAsObject());
    }
  } finally {
    statement.free();
  }

  renderFactResults(rows);
  const elapsed = performance.now() - started;
  factQueryStatus.textContent =
    FACT_AXIS_CONFIG[factActiveAxis].label +
    " / " + rows.length + "件 / " + elapsed.toFixed(0) + " ms";
}

function configureFactTabs() {
  factTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      factActiveAxis = tab.dataset.axis;
      factTabs.forEach(function (item) {
        item.classList.remove("active");
      });
      tab.classList.add("active");
      runFactAggregation();
    });
  });
}

function clearFactFilters() {
  factYearFrom.value = "2016";
  factYearTo.value = "2026";
  factMonthFrom.value = "";
  factMonthTo.value = "";
  factVenue.value = "";
  factTrackType.value = "";
  factDistanceFrom.value = "";
  factDistanceTo.value = "";
  factTrackCondition.value = "";
  factRaceClass.value = "";
  factRaceName.value = "";
  factAge.value = "";
  factSex.value = "";
  factPopBand.value = "";
  factRunningStyle.value = "";
  factMinStarts.value = "20";
  runFactAggregation();
}

async function initializeFactLite() {
  updateFactNetworkStatus();
  configureFactTabs();

  if (!navigator.storage || !navigator.storage.getDirectory) {
    factOpfsStatus.textContent = "非対応";
    factDbStatus.textContent = "利用不可";
    return;
  }

  try {
    await navigator.storage.getDirectory();
    factOpfsStatus.textContent = "利用可能";
    factDbStatus.textContent = "sql.js準備中...";
    await loadFactSqlJs();
    const restored = await restoreFactDatabase();
    if (navigator.onLine) {
      await checkFactManifest(!restored);
    }
  } catch (error) {
    console.error("Fact Lite initialization failed", error);
    factDbStatus.textContent = "初期化失敗";
    factSyncProgress.textContent = "初期化失敗: " + error.message;
  }
}

factCheckButton.addEventListener("click", function () {
  checkFactManifest(false);
});
factSyncButton.addEventListener("click", syncFactFromRemote);
factAggregateButton.addEventListener("click", runFactAggregation);
factClearButton.addEventListener("click", clearFactFilters);
window.addEventListener("online", function () {
  updateFactNetworkStatus();
  checkFactManifest(false);
});
window.addEventListener("offline", updateFactNetworkStatus);

initializeFactLite();

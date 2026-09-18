"use strict";

/* Fact Lite v0.3 capability layer.  The active engine is DuckDB-Wasm. */

const FACT_SUPPORTED_SCHEMA_VERSIONS = new Set(["0.3", "v0.3"]);
let factHasWin5LegNo = false;

function factQueryAdapterFor(adapter) {
  const resolved = adapter || factQueryAdapter;
  if (!resolved) throw new Error("Fact Lite query adapterがありません");
  return resolved;
}

async function factTableColumns(tableName, adapter) {
  return factQueryAdapterFor(adapter).tableColumns(tableName);
}

async function factLatestSchemaVersion(adapter) {
  const rows = await factQueryAdapterFor(adapter).query(
    "SELECT schema_version FROM meta_pwa_fact_build ORDER BY build_id DESC LIMIT 1"
  );
  return rows.length ? String(rows[0].schema_version) : "";
}

validateFactDatabaseObject = async function (database, adapter) {
  const queryAdapter = factQueryAdapterFor(adapter);
  const requiredTables = ["fact_stats_entry", "dim_sire", "dim_bms", "dim_jockey", "dim_race", "meta_pwa_fact_build"];
  const tableNames = await queryAdapter.tableNames();
  requiredTables.forEach(function (tableName) {
    if (!tableNames.has(tableName)) throw new Error("必須テーブルがありません: " + tableName);
  });
  const factColumns = await factTableColumns("fact_stats_entry", queryAdapter);
  ["month", "race_id", "prev_distance_delta", "prev_class_code", "win5_leg_no"].forEach(function (columnName) {
    if (!factColumns.has(columnName)) throw new Error("Fact Lite必須列がありません: " + columnName);
  });
  const schemaVersion = await factLatestSchemaVersion(queryAdapter);
  if (!FACT_SUPPORTED_SCHEMA_VERSIONS.has(schemaVersion)) throw new Error("未対応Fact Lite schemaです: " + schemaVersion);
  return database;
};

function installFactWin5Filter() {
  const jumpCheckbox = document.getElementById("fact-exclude-jumps");
  const checkbox = document.getElementById("fact-win5-only");
  if (!jumpCheckbox || !checkbox) return;

  async function refreshWin5Capability() {
    factHasWin5LegNo = false;
    if (factQueryAdapter) factHasWin5LegNo = (await factTableColumns("fact_stats_entry")).has("win5_leg_no");
    checkbox.disabled = !factDb || !factHasWin5LegNo;
    if (!factHasWin5LegNo) {
      checkbox.checked = false;
      checkbox.title = "WIN5列を含むParquet generationが必要です";
    } else {
      checkbox.removeAttribute("title");
    }
  }

  const originalBuildFactWhere = buildFactWhere;
  buildFactWhere = function () {
    const result = originalBuildFactWhere();
    if (checkbox.checked && factHasWin5LegNo) result.clauses.push("f.win5_leg_no IS NOT NULL");
    return result;
  };
  const originalClearFactFilters = clearFactFilters;
  clearFactFilters = function () { checkbox.checked = false; originalClearFactFilters(); };
  const originalSetFactDbLoaded = setFactDbLoaded;
  setFactDbLoaded = async function (source, size, metadata) {
    await originalSetFactDbLoaded(source, size, metadata);
    await refreshWin5Capability();
  };
  void refreshWin5Capability();
}

installFactWin5Filter();

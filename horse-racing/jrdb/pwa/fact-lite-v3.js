"use strict";

/* Fact Lite v0.3 compatibility: WIN5 filter with v0.2 read compatibility. */

const FACT_SUPPORTED_SCHEMA_VERSIONS = new Set(["0.2", "0.3"]);
let factHasWin5LegNo = false;

function factTableColumns(database, tableName) {
  const result = database.exec(`PRAGMA table_info(${tableName})`);
  const columns = new Set();
  if (result.length > 0) {
    result[0].values.forEach(function (row) {
      columns.add(String(row[1]));
    });
  }
  return columns;
}

function factLatestSchemaVersion(database) {
  const result = database.exec(
    "SELECT schema_version FROM meta_pwa_fact_build " +
    "ORDER BY build_id DESC LIMIT 1"
  );
  if (result.length === 0 || result[0].values.length === 0) {
    return "";
  }
  return String(result[0].values[0][0]);
}

validateFactDatabaseObject = function (database) {
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

  const factColumns = factTableColumns(database, "fact_stats_entry");
  ["month", "race_id", "prev_distance_delta", "prev_class_code"].forEach(
    function (columnName) {
      if (!factColumns.has(columnName)) {
        throw new Error("Fact Lite必須列がありません: " + columnName);
      }
    }
  );

  const schemaVersion = factLatestSchemaVersion(database);
  if (!FACT_SUPPORTED_SCHEMA_VERSIONS.has(schemaVersion)) {
    throw new Error("未対応Fact Lite schemaです: " + schemaVersion);
  }
  if (schemaVersion === "0.3" && !factColumns.has("win5_leg_no")) {
    throw new Error("Fact Lite v0.3列がありません: win5_leg_no");
  }

  const integrity = database.exec("PRAGMA integrity_check");
  if (
    integrity.length === 0 ||
    integrity[0].values.length === 0 ||
    integrity[0].values[0][0] !== "ok"
  ) {
    throw new Error("SQLite integrity_check が ok ではありません");
  }
};

validateFactManifest = function (manifest) {
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
  if (!FACT_SUPPORTED_SCHEMA_VERSIONS.has(String(manifest.schema_version))) {
    throw new Error("未対応schema_versionです: " + manifest.schema_version);
  }
  if (!manifest.download.path) {
    throw new Error("download.pathがありません");
  }
};

function installFactWin5Filter() {
  const minimumStartsInput = document.getElementById("fact-min-starts");
  const jumpCheckbox = document.getElementById("fact-exclude-jumps");
  if (!minimumStartsInput || !jumpCheckbox) {
    return;
  }

  const jumpLabel = jumpCheckbox.closest("label");
  if (!jumpLabel) {
    return;
  }

  let checkbox = document.getElementById("fact-win5-only");
  if (!checkbox) {
    const label = document.createElement("label");
    label.className = "fact-checkbox-field";

    checkbox = document.createElement("input");
    checkbox.id = "fact-win5-only";
    checkbox.type = "checkbox";
    checkbox.checked = false;
    checkbox.disabled = true;

    const text = document.createElement("span");
    text.textContent = "WIN5対象レースのみ";

    label.appendChild(checkbox);
    label.appendChild(text);
    jumpLabel.insertAdjacentElement("beforebegin", label);
  }

  function refreshWin5Capability() {
    factHasWin5LegNo = false;
    if (factDb) {
      factHasWin5LegNo = factTableColumns(factDb, "fact_stats_entry").has(
        "win5_leg_no"
      );
    }

    checkbox.disabled = !factDb || !factHasWin5LegNo;
    if (!factHasWin5LegNo) {
      checkbox.checked = false;
      checkbox.title = "Fact Lite v0.3配布後に利用できます";
    } else {
      checkbox.removeAttribute("title");
    }
  }

  const originalBuildFactWhere = buildFactWhere;
  buildFactWhere = function () {
    const result = originalBuildFactWhere();
    if (checkbox.checked && factHasWin5LegNo) {
      result.clauses.push("f.win5_leg_no IS NOT NULL");
    }
    return result;
  };

  const originalClearFactFilters = clearFactFilters;
  clearFactFilters = function () {
    checkbox.checked = false;
    originalClearFactFilters();
  };

  const originalSetFactDbLoaded = setFactDbLoaded;
  setFactDbLoaded = function (source, size, metadata) {
    originalSetFactDbLoaded(source, size, metadata);
    refreshWin5Capability();
  };

  refreshWin5Capability();
}

installFactWin5Filter();

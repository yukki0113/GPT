import * as duckdb from "./vendor/duckdb/duckdb-browser.mjs";

// This is deliberately a single-thread bundle.  The Fact Lite PWA must work
// without cross-origin isolation, including on iPhone Safari.
const FACT_DUCKDB_VERSION = "1.32.0";
const FACT_DUCKDB_BUNDLE = {
  mainModule: "./vendor/duckdb/duckdb-mvp.wasm",
  mainWorker: "./vendor/duckdb/duckdb-browser-mvp.worker.js"
};
const FACT_PARQUET_CURRENT_URL = "./data/fact-lite-parquet/current.json";
const FACT_PARQUET_REQUIRED_TABLES = [
  "fact_stats_entry",
  "dim_sire",
  "dim_bms",
  "dim_jockey",
  "dim_race",
  "meta_pwa_fact_build"
];

function fail(message) {
  throw new Error("Fact Lite Parquet: " + message);
}

function quoteIdentifier(value) {
  return '"' + String(value).replaceAll('"', '""') + '"';
}

function quoteLiteral(value) {
  return "'" + String(value).replaceAll("'", "''") + "'";
}

function asSafeRelativePath(value, label) {
  const text = String(value || "");
  if (!text || text.startsWith("/") || text.includes("\\") || text.split("/").includes("..")) {
    fail(label + " が不正です");
  }
  return text;
}

export function validateFactLiteParquetManifest(manifest, expectedGenerationId) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    fail("manifest JSON objectが必要です");
  }
  const expected = {
    artifact_type: "jrdb_fact_lite",
    schema_version: "v0.3",
    storage_format: "parquet",
    storage_version: "1",
    validation_status: "PASS"
  };
  Object.entries(expected).forEach(function ([key, value]) {
    if (manifest[key] !== value) fail("manifest " + key + " が未対応です");
  });
  if (!manifest.generation_id || manifest.generation_id !== expectedGenerationId) {
    fail("manifest generation_id がcurrentと一致しません");
  }
  if (!manifest.tables || typeof manifest.tables !== "object" || Array.isArray(manifest.tables)) {
    fail("manifest tables がありません");
  }
  if (Object.keys(manifest.tables).length !== FACT_PARQUET_REQUIRED_TABLES.length) {
    fail("manifest table set が不正です");
  }
  FACT_PARQUET_REQUIRED_TABLES.forEach(function (table) {
    const entry = manifest.tables[table];
    if (!entry || typeof entry !== "object") fail("必須tableがありません: " + table);
    asSafeRelativePath(entry.path, table + ".path");
    if (!Number.isInteger(Number(entry.size_bytes)) || Number(entry.size_bytes) < 0) {
      fail(table + ".size_bytes が不正です");
    }
    if (!/^[a-f0-9]{64}$/i.test(String(entry.sha256 || ""))) {
      fail(table + ".sha256 が不正です");
    }
    if (!Number.isInteger(Number(entry.rows)) || Number(entry.rows) < 0) {
      fail(table + ".rows が不正です");
    }
  });
  return manifest;
}

export async function fetchFactLiteParquetCurrent(fetchImpl = fetch) {
  const response = await fetchImpl(FACT_PARQUET_CURRENT_URL, { cache: "no-store" });
  if (!response.ok) fail("current.json HTTP " + response.status);
  const current = await response.json();
  if (!current || current.status !== "CURRENT" || !current.generation_id) {
    fail("current.json が不正です");
  }
  const manifestPath = asSafeRelativePath(current.manifest, "current.manifest");
  const expectedPath = "generations/" + current.generation_id + "/manifest.json";
  if (manifestPath !== expectedPath) fail("current.json manifest path が不正です");

  const manifestUrl = new URL(manifestPath, new URL(FACT_PARQUET_CURRENT_URL, window.location.href));
  const manifestResponse = await fetchImpl(manifestUrl, { cache: "no-store" });
  if (!manifestResponse.ok) fail("manifest HTTP " + manifestResponse.status);
  const manifest = validateFactLiteParquetManifest(
    await manifestResponse.json(),
    current.generation_id
  );
  return { current, manifest, manifestUrl };
}

export async function openFactLiteDuckDb(resolved, logger = new duckdb.VoidLogger()) {
  if (!resolved || !resolved.manifest || !resolved.manifestUrl) fail("解決済みmanifestが必要です");
  const worker = new Worker(FACT_DUCKDB_BUNDLE.mainWorker);
  const database = new duckdb.AsyncDuckDB(logger, worker);
  try {
    await database.instantiate(FACT_DUCKDB_BUNDLE.mainModule);
    const connection = await database.connect();
    try {
      for (const table of FACT_PARQUET_REQUIRED_TABLES) {
        const entry = resolved.manifest.tables[table];
        const fileName = "fact-lite/" + resolved.manifest.generation_id + "/" + entry.path;
        const fileUrl = new URL(entry.path, resolved.manifestUrl).toString();
        await database.registerFileURL(fileName, fileUrl, duckdb.DuckDBDataProtocol.HTTP, false);
        await connection.query(
          "CREATE OR REPLACE VIEW " + quoteIdentifier(table) +
          " AS SELECT * FROM read_parquet(" + quoteLiteral(fileName) + ")"
        );
      }
    } finally {
      await connection.close();
    }
    return database;
  } catch (error) {
    await database.terminate();
    throw error;
  }
}

export const FactLiteDuckDb = Object.freeze({
  version: FACT_DUCKDB_VERSION,
  currentUrl: FACT_PARQUET_CURRENT_URL,
  requiredTables: FACT_PARQUET_REQUIRED_TABLES.slice(),
  fetchCurrent: fetchFactLiteParquetCurrent,
  open: openFactLiteDuckDb,
  validateManifest: validateFactLiteParquetManifest
});

window.JRDBFactLiteDuckDB = FactLiteDuckDb;

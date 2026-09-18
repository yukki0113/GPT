import * as duckdb from "./vendor/duckdb/duckdb-browser.mjs";

// This is deliberately a single-thread bundle.  The Fact Lite PWA must work
// without cross-origin isolation, including on iPhone Safari.
const FACT_DUCKDB_VERSION = "1.32.0";
const FACT_DUCKDB_BUNDLE = {
  mainModule: "./vendor/duckdb/duckdb-mvp.wasm",
  mainWorker: "./vendor/duckdb/duckdb-browser-mvp.worker.js"
};
const FACT_PARQUET_CURRENT_URL = "./data/fact-lite-parquet/current.json";
const FACT_PARQUET_OPFS_DIR = "jrdb-fact-lite";
// SQLite still owns metadata.json until the consumer cutover.  Keeping this
// sidecar prevents the staged Parquet cache from changing the live reader.
const FACT_PARQUET_METADATA = "parquet-metadata.json";
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

async function getDirectory(root, pathParts, create) {
  let directory = root;
  for (const part of pathParts) {
    directory = await directory.getDirectoryHandle(part, { create });
  }
  return directory;
}

async function getFactParquetRoot(create) {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(FACT_PARQUET_OPFS_DIR, { create });
}

async function writeOpfsFile(directory, relativePath, bytes) {
  const parts = asSafeRelativePath(relativePath, "OPFS path").split("/");
  const fileName = parts.pop();
  const parent = await getDirectory(directory, parts, true);
  const handle = await parent.getFileHandle(fileName, { create: true });
  const writable = await handle.createWritable();
  await writable.write(bytes);
  await writable.close();
}

async function readOpfsFile(directory, relativePath) {
  try {
    const parts = asSafeRelativePath(relativePath, "OPFS path").split("/");
    const fileName = parts.pop();
    const parent = await getDirectory(directory, parts, false);
    const handle = await parent.getFileHandle(fileName, { create: false });
    const file = await handle.getFile();
    return new Uint8Array(await file.arrayBuffer());
  } catch (error) {
    if (error && error.name === "NotFoundError") return null;
    throw error;
  }
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map(function (value) { return value.toString(16).padStart(2, "0"); })
    .join("");
}

async function loadParquetMetadata(root) {
  const bytes = await readOpfsFile(root, FACT_PARQUET_METADATA);
  if (!bytes) return null;
  try {
    const metadata = JSON.parse(new TextDecoder().decode(bytes));
    if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
      fail("OPFS metadataが不正です");
    }
    return metadata;
  } catch (error) {
    if (error && String(error.message || "").startsWith("Fact Lite Parquet:")) throw error;
    fail("OPFS metadata JSONが不正です");
  }
}

async function saveParquetMetadata(root, metadata) {
  const bytes = new TextEncoder().encode(JSON.stringify(metadata, null, 2) + "\n");
  await writeOpfsFile(root, FACT_PARQUET_METADATA, bytes);
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

function manifestRelativePath(generationId) {
  return "generations/" + generationId + "/manifest.json";
}

function generationRelativePath(generationId, relativePath) {
  return "generations/" + generationId + "/" + relativePath;
}

async function readCachedFactLiteParquetGeneration(root, generationId) {
  if (!generationId) fail("cache generation_id がありません");
  const manifestBytes = await readOpfsFile(root, manifestRelativePath(generationId));
  if (!manifestBytes) fail("cache manifestがありません");
  let manifest;
  try {
    manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
  } catch (error) {
    fail("cache manifest JSONが不正です");
  }
  validateFactLiteParquetManifest(manifest, generationId);
  const files = {};
  for (const table of FACT_PARQUET_REQUIRED_TABLES) {
    const entry = manifest.tables[table];
    const bytes = await readOpfsFile(root, generationRelativePath(generationId, entry.path));
    if (!bytes) fail("cache Parquetがありません: " + table);
    if (bytes.byteLength !== Number(entry.size_bytes)) fail("cache size不一致: " + table);
    if (await sha256Hex(bytes) !== String(entry.sha256).toLowerCase()) {
      fail("cache SHA-256不一致: " + table);
    }
    files[table] = bytes;
  }
  return { generationId, manifest, files };
}

async function readArrowScalar(table, columnName) {
  const column = table.getChild(columnName);
  if (!column || column.length !== 1) fail("DuckDB query resultが不正です: " + columnName);
  return column.get(0);
}

async function validateDuckDbCachedGeneration(cached) {
  const database = await openFactLiteDuckDbFromCache(cached);
  try {
    const connection = await database.connect();
    try {
      for (const table of FACT_PARQUET_REQUIRED_TABLES) {
        const result = await connection.query(
          "SELECT COUNT(*) AS row_count FROM " + quoteIdentifier(table)
        );
        if (Number(await readArrowScalar(result, "row_count")) !== Number(cached.manifest.tables[table].rows)) {
          fail("DuckDB row count不一致: " + table);
        }
      }
      const factSchema = await connection.query("SELECT * FROM fact_stats_entry LIMIT 0");
      const columns = new Set(factSchema.schema.fields.map(function (field) { return field.name; }));
      ["month", "race_id", "prev_distance_delta", "prev_class_code", "win5_leg_no"].forEach(function (column) {
        if (!columns.has(column)) fail("Fact Lite必須列がありません: " + column);
      });
    } finally {
      await connection.close();
    }
  } finally {
    await database.terminate();
  }
}

export async function openFactLiteDuckDbFromCache(cached, logger = new duckdb.VoidLogger()) {
  if (!cached || !cached.manifest || !cached.files) fail("cache generationが必要です");
  validateFactLiteParquetManifest(cached.manifest, cached.generationId);
  const worker = new Worker(FACT_DUCKDB_BUNDLE.mainWorker);
  const database = new duckdb.AsyncDuckDB(logger, worker);
  try {
    await database.instantiate(FACT_DUCKDB_BUNDLE.mainModule);
    const connection = await database.connect();
    try {
      for (const table of FACT_PARQUET_REQUIRED_TABLES) {
        const entry = cached.manifest.tables[table];
        const bytes = cached.files[table];
        if (!(bytes instanceof Uint8Array)) fail("cache bytesが不正です: " + table);
        const fileName = "fact-lite/" + cached.generationId + "/" + entry.path;
        await database.registerFileBuffer(fileName, bytes);
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

export async function restoreFactLiteParquetCache() {
  let root;
  try {
    root = await getFactParquetRoot(false);
  } catch (error) {
    if (error && error.name === "NotFoundError") return null;
    throw error;
  }
  const metadata = await loadParquetMetadata(root);
  if (!metadata || !metadata.current_generation) return null;
  const cached = await readCachedFactLiteParquetGeneration(root, metadata.current_generation);
  await validateDuckDbCachedGeneration(cached);
  return { cached, metadata };
}

export async function synchronizeFactLiteParquetCache(fetchImpl = fetch) {
  const root = await getFactParquetRoot(true);
  const metadata = await loadParquetMetadata(root);
  const remote = await fetchFactLiteParquetCurrent(fetchImpl);
  if (metadata && metadata.current_generation === remote.current.generation_id) {
    const cached = await readCachedFactLiteParquetGeneration(root, metadata.current_generation);
    await validateDuckDbCachedGeneration(cached);
    return { updated: false, cached, metadata };
  }

  const files = {};
  for (const table of FACT_PARQUET_REQUIRED_TABLES) {
    const entry = remote.manifest.tables[table];
    const response = await fetchImpl(new URL(entry.path, remote.manifestUrl), { cache: "no-store" });
    if (!response.ok) fail("Parquet HTTP " + response.status + ": " + table);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength !== Number(entry.size_bytes)) fail("download size不一致: " + table);
    if (await sha256Hex(bytes) !== String(entry.sha256).toLowerCase()) {
      fail("download SHA-256不一致: " + table);
    }
    files[table] = bytes;
  }

  // The pointer is not changed until the complete candidate passes local
  // manifest, asset, relation, schema, and row-count validation.
  const candidate = { generationId: remote.current.generation_id, manifest: remote.manifest, files };
  for (const table of FACT_PARQUET_REQUIRED_TABLES) {
    await writeOpfsFile(
      root,
      generationRelativePath(candidate.generationId, candidate.manifest.tables[table].path),
      candidate.files[table]
    );
  }
  await writeOpfsFile(
    root,
    manifestRelativePath(candidate.generationId),
    new TextEncoder().encode(JSON.stringify(candidate.manifest, null, 2) + "\n")
  );
  const cached = await readCachedFactLiteParquetGeneration(root, candidate.generationId);
  await validateDuckDbCachedGeneration(cached);
  const nextMetadata = {
    current_generation: candidate.generationId,
    previous_generation: metadata && metadata.current_generation ? metadata.current_generation : null,
    synced_at: new Date().toISOString(),
    storage_format: "parquet",
    storage_version: "1"
  };
  await saveParquetMetadata(root, nextMetadata);
  return { updated: true, cached, metadata: nextMetadata };
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
  openCached: openFactLiteDuckDbFromCache,
  restoreCache: restoreFactLiteParquetCache,
  synchronizeCache: synchronizeFactLiteParquetCache,
  validateManifest: validateFactLiteParquetManifest
});

window.JRDBFactLiteDuckDB = FactLiteDuckDb;

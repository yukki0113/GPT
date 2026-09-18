// Fact Lite Parquet distribution contract.  This module intentionally has no
// DuckDB or OPFS dependency so the trust boundary is unit-testable in Node as
// well as in the browser.
export const FACT_PARQUET_REQUIRED_TABLES = Object.freeze([
  "fact_stats_entry",
  "dim_sire",
  "dim_bms",
  "dim_jockey",
  "dim_race",
  "meta_pwa_fact_build"
]);

// These are the columns required to establish the Fact Lite v0.3 data shape
// before a generation becomes usable.  Query migration will add its own
// compatibility checks in the later adapter phase.
export const FACT_STATS_ENTRY_REQUIRED_COLUMNS = Object.freeze([
  "month",
  "race_id",
  "prev_distance_delta",
  "prev_class_code",
  "win5_leg_no"
]);

export class FactLiteParquetContractError extends Error {
  constructor(message) {
    super("Fact Lite Parquet: " + message);
    this.name = "FactLiteParquetContractError";
  }
}

function fail(message) {
  throw new FactLiteParquetContractError(message);
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function isFactLiteGenerationId(value) {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(value);
}

export function asSafeFactLiteRelativePath(value, label = "path") {
  if (typeof value !== "string" || !value || value.startsWith("/") || value.includes("\\")) {
    fail(label + " が不正です");
  }
  const parts = value.split("/");
  if (parts.some(function (part) { return !part || part === "." || part === ".."; })) {
    fail(label + " が不正です");
  }
  return value;
}

function requireNonNegativeSafeInteger(entry, key, label) {
  if (!hasOwn(entry, key) || !Number.isSafeInteger(entry[key]) || entry[key] < 0) {
    fail(label + "." + key + " が不正です");
  }
}

export function validateFactLiteParquetCurrent(current) {
  if (!isPlainObject(current) || current.status !== "CURRENT" || !isFactLiteGenerationId(current.generation_id)) {
    fail("current.json が不正です");
  }
  const manifestPath = asSafeFactLiteRelativePath(current.manifest, "current.manifest");
  const expectedPath = "generations/" + current.generation_id + "/manifest.json";
  if (manifestPath !== expectedPath) fail("current.json manifest path が不正です");
  return current;
}

export function validateFactLiteParquetManifest(manifest, expectedGenerationId) {
  if (!isPlainObject(manifest)) fail("manifest JSON objectが必要です");
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
  if (!isFactLiteGenerationId(expectedGenerationId) || manifest.generation_id !== expectedGenerationId) {
    fail("manifest generation_id がcurrentと一致しません");
  }
  if (!isPlainObject(manifest.tables)) fail("manifest tables がありません");
  const actualTables = Object.keys(manifest.tables).sort();
  const expectedTables = FACT_PARQUET_REQUIRED_TABLES.slice().sort();
  if (actualTables.length !== expectedTables.length || actualTables.some(function (table, index) {
    return table !== expectedTables[index];
  })) {
    fail("manifest table set が不正です");
  }
  FACT_PARQUET_REQUIRED_TABLES.forEach(function (table) {
    const entry = manifest.tables[table];
    if (!isPlainObject(entry)) fail("必須tableがありません: " + table);
    asSafeFactLiteRelativePath(entry.path, table + ".path");
    requireNonNegativeSafeInteger(entry, "size_bytes", table);
    if (typeof entry.sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(entry.sha256)) {
      fail(table + ".sha256 が不正です");
    }
    requireNonNegativeSafeInteger(entry, "rows", table);
  });
  return manifest;
}

export async function sha256FactLiteBytes(bytes) {
  if (!(bytes instanceof Uint8Array)) fail("asset bytesが不正です");
  if (!globalThis.crypto || !globalThis.crypto.subtle) fail("SHA-256 APIが利用できません");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map(function (value) {
    return value.toString(16).padStart(2, "0");
  }).join("");
}

export async function validateFactLiteParquetAsset(table, entry, bytes, hashFn = sha256FactLiteBytes) {
  if (!FACT_PARQUET_REQUIRED_TABLES.includes(table)) fail("未知のtableです: " + table);
  if (!isPlainObject(entry)) fail("asset entryが不正です: " + table);
  asSafeFactLiteRelativePath(entry.path, table + ".path");
  requireNonNegativeSafeInteger(entry, "size_bytes", table);
  if (typeof entry.sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(entry.sha256)) {
    fail(table + ".sha256 が不正です");
  }
  if (!(bytes instanceof Uint8Array) || bytes.byteLength !== entry.size_bytes) {
    fail("asset size不一致: " + table);
  }
  if (String(await hashFn(bytes)).toLowerCase() !== entry.sha256.toLowerCase()) {
    fail("asset SHA-256不一致: " + table);
  }
  return bytes;
}

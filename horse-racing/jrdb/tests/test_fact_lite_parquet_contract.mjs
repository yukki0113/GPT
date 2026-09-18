import assert from "node:assert/strict";
import test from "node:test";

import {
  FactLiteParquetContractError,
  FACT_PARQUET_REQUIRED_TABLES,
  validateFactLiteParquetAsset,
  validateFactLiteParquetCurrent,
  validateFactLiteParquetManifest
} from "../pwa/fact-lite-parquet-contract.mjs";

const SHA = "a".repeat(64);
const GENERATION = "fact-lite-v0_3-20260913";

function manifest() {
  const tables = {};
  FACT_PARQUET_REQUIRED_TABLES.forEach(function (table) {
    tables[table] = {
      path: table + ".parquet",
      size_bytes: 3,
      sha256: SHA,
      rows: 1
    };
  });
  return {
    artifact_type: "jrdb_fact_lite",
    schema_version: "v0.3",
    storage_format: "parquet",
    storage_version: "1",
    validation_status: "PASS",
    generation_id: GENERATION,
    tables
  };
}

test("current pointer permits only the declared generation manifest", function () {
  const current = {
    status: "CURRENT",
    generation_id: GENERATION,
    manifest: "generations/" + GENERATION + "/manifest.json"
  };
  assert.equal(validateFactLiteParquetCurrent(current), current);
  assert.throws(function () {
    validateFactLiteParquetCurrent({ ...current, generation_id: "../other" });
  }, FactLiteParquetContractError);
  assert.throws(function () {
    validateFactLiteParquetCurrent({ ...current, manifest: "generations/other/manifest.json" });
  }, /manifest path/);
});

test("manifest rejects unknown tables and lossy numeric metadata", function () {
  const valid = manifest();
  assert.equal(validateFactLiteParquetManifest(valid, GENERATION), valid);

  const extra = manifest();
  extra.tables.unexpected = { path: "unexpected.parquet", size_bytes: 3, sha256: SHA, rows: 1 };
  assert.throws(function () { validateFactLiteParquetManifest(extra, GENERATION); }, /table set/);

  const missingSize = manifest();
  delete missingSize.tables.fact_stats_entry.size_bytes;
  assert.throws(function () { validateFactLiteParquetManifest(missingSize, GENERATION); }, /size_bytes/);

  const coercedRows = manifest();
  coercedRows.tables.fact_stats_entry.rows = "1";
  assert.throws(function () { validateFactLiteParquetManifest(coercedRows, GENERATION); }, /rows/);

  const unsafePath = manifest();
  unsafePath.tables.fact_stats_entry.path = "nested/../fact.parquet";
  assert.throws(function () { validateFactLiteParquetManifest(unsafePath, GENERATION); }, /path/);
});

test("asset checks reject both size and digest mismatches before caching", async function () {
  const entry = { path: "fact_stats_entry.parquet", size_bytes: 3, sha256: SHA, rows: 1 };
  const bytes = new Uint8Array([1, 2, 3]);
  await assert.doesNotReject(function () {
    return validateFactLiteParquetAsset("fact_stats_entry", entry, bytes, async function () { return SHA; });
  });
  await assert.rejects(function () {
    return validateFactLiteParquetAsset("fact_stats_entry", { ...entry, size_bytes: 4 }, bytes, async function () { return SHA; });
  }, /size/);
  await assert.rejects(function () {
    return validateFactLiteParquetAsset("fact_stats_entry", entry, bytes, async function () { return "b".repeat(64); });
  }, /SHA-256/);
});

"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const adapters = require("../pwa/fact-lite-query-adapter.js");

function arrowTable(columns) {
  const names = Object.keys(columns);
  return {
    schema: { fields: names.map(function (name) { return { name }; }) },
    getChild: function (name) {
      const values = columns[name];
      return values ? { length: values.length, get: function (index) { return values[index]; } } : null;
    }
  };
}

test("sql.js adapter preserves positional parameters and object-shaped rows", async function () {
  let bound = null;
  const database = {
    prepare: function () {
      let stepped = false;
      return {
        bind: function (params) { bound = params; },
        step: function () { if (stepped) return false; stepped = true; return true; },
        getAsObject: function () { return { item: "テスト", starts: 2 }; },
        free: function () {}
      };
    },
    exec: function (sql) {
      if (sql.startsWith("PRAGMA table_info")) {
        return [{ columns: ["cid", "name"], values: [[0, "month"], [1, "win5_leg_no"]] }];
      }
      if (sql.startsWith("SELECT name FROM sqlite_master")) {
        return [{ columns: ["name"], values: [["fact_stats_entry"], ["dim_race"]] }];
      }
      if (sql === "PRAGMA integrity_check") {
        return [{ columns: ["integrity_check"], values: [["ok"]] }];
      }
      throw new Error("unexpected SQL: " + sql);
    }
  };
  const adapter = adapters.createSqlJs(database);
  assert.deepEqual(await adapter.query("SELECT ?", [7]), [{ item: "テスト", starts: 2 }]);
  assert.deepEqual(bound, [7]);
  assert.deepEqual([...await adapter.tableColumns("fact_stats_entry")], ["month", "win5_leg_no"]);
  assert.equal(await adapter.integrityCheck(), true);
});

test("DuckDB adapter maps Arrow results and binds the same positional parameters", async function () {
  const prepared = [];
  const database = {
    connect: async function () {
      return {
        prepare: async function (sql) {
          return {
            query: async function (...params) {
              prepared.push({ sql, params });
              if (sql.includes("information_schema.columns")) {
                return arrowTable({ column_name: ["month", "race_id"] });
              }
              return arrowTable({ item: ["テスト"], starts: [2] });
            },
            close: async function () {}
          };
        },
        close: async function () {}
      };
    }
  };
  const adapter = adapters.createDuckDb(database);
  assert.deepEqual(await adapter.query("SELECT ?", [7]), [{ item: "テスト", starts: 2 }]);
  assert.deepEqual(await adapter.tableColumns("fact_stats_entry"), new Set(["month", "race_id"]));
  assert.deepEqual(prepared[0].params, [7]);
  assert.deepEqual(prepared[1].params, ["fact_stats_entry"]);
});

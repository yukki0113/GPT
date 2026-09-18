"use strict";

/*
 * The aggregation screen talks only to this small query contract. DuckDB-Wasm
 * is the Fact Lite runtime; the retained sql.js adapter is for query-contract
 * regression tests and is not selected by the Fact Lite page. Keeping this
 * boundary free of DOM/OPFS concerns preserves filters, labels, and rendered
 * values across storage-engine tests.
 */
(function (root) {
  function fail(message) {
    throw new Error("Fact Lite query adapter: " + message);
  }

  function assertSafeIdentifier(value) {
    if (typeof value !== "string" || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(value)) {
      fail("table identifierが不正です");
    }
    return value;
  }

  function sqliteRows(result) {
    if (!Array.isArray(result) || result.length === 0) return [];
    const first = result[0];
    return first.values.map(function (values) {
      const row = {};
      first.columns.forEach(function (column, index) {
        row[column] = values[index];
      });
      return row;
    });
  }

  function arrowRows(table) {
    if (!table || !table.schema || !Array.isArray(table.schema.fields)) {
      fail("DuckDB query resultが不正です");
    }
    const fields = table.schema.fields;
    if (fields.length === 0) return [];
    const columns = fields.map(function (field) {
      const column = table.getChild(field.name);
      if (!column) fail("DuckDB result columnがありません: " + field.name);
      return column;
    });
    const rows = [];
    for (let index = 0; index < columns[0].length; index += 1) {
      const row = {};
      fields.forEach(function (field, fieldIndex) {
        row[field.name] = columns[fieldIndex].get(index);
      });
      rows.push(row);
    }
    return rows;
  }

  function createSqlJsFactQueryAdapter(database) {
    if (!database || typeof database.exec !== "function" || typeof database.prepare !== "function") {
      fail("sql.js databaseが必要です");
    }
    return {
      engine: "sql.js",
      query: async function (sql, params) {
        const statement = database.prepare(sql);
        const rows = [];
        try {
          statement.bind(params || []);
          while (statement.step()) rows.push(statement.getAsObject());
        } finally {
          statement.free();
        }
        return rows;
      },
      tableColumns: async function (tableName) {
        const rows = sqliteRows(database.exec("PRAGMA table_info(" + assertSafeIdentifier(tableName) + ")"));
        return new Set(rows.map(function (row) { return String(row.name); }));
      },
      tableNames: async function () {
        const rows = sqliteRows(database.exec("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"));
        return new Set(rows.map(function (row) { return String(row.name); }));
      },
      integrityCheck: async function () {
        const rows = sqliteRows(database.exec("PRAGMA integrity_check"));
        return rows.length === 1 && rows[0].integrity_check === "ok";
      },
      close: async function () {}
    };
  }

  function createDuckDbFactQueryAdapter(database) {
    if (!database || typeof database.connect !== "function") {
      fail("DuckDB databaseが必要です");
    }
    let connectionPromise = null;
    async function connection() {
      if (!connectionPromise) connectionPromise = database.connect();
      return connectionPromise;
    }
    return {
      engine: "duckdb-wasm",
      query: async function (sql, params) {
        const statement = await (await connection()).prepare(sql);
        try {
          return arrowRows(await statement.query.apply(statement, params || []));
        } finally {
          await statement.close();
        }
      },
      tableColumns: async function (tableName) {
        const safeName = assertSafeIdentifier(tableName);
        const rows = await this.query(
          "SELECT column_name FROM information_schema.columns " +
          "WHERE table_schema = current_schema() AND table_name = ? ORDER BY ordinal_position",
          [safeName]
        );
        return new Set(rows.map(function (row) { return String(row.column_name); }));
      },
      tableNames: async function () {
        const rows = await this.query(
          "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        );
        return new Set(rows.map(function (row) { return String(row.table_name); }));
      },
      integrityCheck: async function () {
        // Asset SHA, row count, and schema are validated before DuckDB is
        // opened; DuckDB has no SQLite-equivalent integrity pragma.
        return true;
      },
      close: async function () {
        if (!connectionPromise) return;
        const active = await connectionPromise;
        await active.close();
        connectionPromise = null;
      }
    };
  }

  const api = Object.freeze({
    createSqlJs: createSqlJsFactQueryAdapter,
    createDuckDb: createDuckDbFactQueryAdapter
  });
  root.JRDBFactLiteQueryAdapters = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window === "undefined" ? globalThis : window);

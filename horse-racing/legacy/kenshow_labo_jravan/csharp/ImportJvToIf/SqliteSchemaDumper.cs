using System;
using System.Collections.Generic;
using Microsoft.Data.Sqlite;

namespace ImportJvToIf
{
    internal static class SqliteSchemaDumper
    {
        public static void DumpTablesAndColumns(string sqliteConnectionString)
        {
            // SQLiteへ接続する
            using (SqliteConnection conn = new SqliteConnection(sqliteConnectionString))
            {
                conn.Open();

                // テーブル一覧を取得する
                List<string> tables = new List<string>();
                using (SqliteCommand cmd = conn.CreateCommand())
                {
                    cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;";
                    using (SqliteDataReader reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            string? name = reader.GetString(0);
                            if (!string.IsNullOrWhiteSpace(name))
                            {
                                tables.Add(name);
                            }
                        }
                    }
                }

                // 各テーブルの列情報を出力する
                foreach (string table in tables)
                {
                    Console.WriteLine("======================================");
                    Console.WriteLine("TABLE: " + table);

                    using (SqliteCommand cmd = conn.CreateCommand())
                    {
                        cmd.CommandText = "PRAGMA table_info('" + table.Replace("'", "''") + "');";

                        using (SqliteDataReader reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                // PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
                                int cid = reader.GetInt32(0);
                                string colName = reader.IsDBNull(1) ? "" : reader.GetString(1);
                                string colType = reader.IsDBNull(2) ? "" : reader.GetString(2);
                                int notNull = reader.IsDBNull(3) ? 0 : reader.GetInt32(3);
                                string defaultValue = reader.IsDBNull(4) ? "" : reader.GetString(4);
                                int pk = reader.IsDBNull(5) ? 0 : reader.GetInt32(5);

                                Console.WriteLine(
                                    "  " + cid +
                                    "  name=" + colName +
                                    "  type=" + colType +
                                    "  notnull=" + notNull +
                                    "  default=" + defaultValue +
                                    "  pk=" + pk);
                            }
                        }
                    }
                }
            }
        }
    }
}

using System;
using System.IO;
using System.Data;
using Microsoft.Data.SqlClient;
using Microsoft.Data.Sqlite;
using KenshowLabo.Tools.Db;

namespace ExportSiteSQLite
{
    /// <summary>
    /// SQLServer → 配布SQLiteの全量生成ランナー。
    /// </summary>
    public sealed class ExportSqliteRunner
    {
        /// <summary>
        /// 実行する。
        /// </summary>
        public void Run(ProgramOptions options)
        {
            /* 出力ファイル確定 */
            string sqlitePath = Path.Combine(options.OutputDir, options.SnapshotFileName);

            /* 全量生成：既存があれば削除 */
            if (File.Exists(sqlitePath))
            {
                File.Delete(sqlitePath);
            }

            /* SQLite接続 */
            using (SqliteConnection sqlite = new SqliteConnection("Data Source=" + sqlitePath))
            {
                sqlite.Open();

                /* 高速化（全量生成時） */
                ExecuteNonQuery(sqlite, "PRAGMA journal_mode = OFF;");
                ExecuteNonQuery(sqlite, "PRAGMA synchronous = OFF;");
                ExecuteNonQuery(sqlite, "PRAGMA temp_store = MEMORY;");

                /* スキーマ作成 */
                SqliteSchemaInitializer schema = new SqliteSchemaInitializer();
                schema.CreateSchema(sqlite);

                using (SqliteTransaction tx = sqlite.BeginTransaction())
                {
                    // ============================================
                    // 1) dim_race（history）
                    // ============================================
                    DimRaceRow[] dimHistory = ReadDimRaceHistory(options);
                    SqliteWriters.InsertDimRaceHistory(sqlite, tx, dimHistory);

                    // ============================================
                    // 2) dim_race（weekend）UPSERT
                    // ============================================
                    DimRaceRow[] dimWeekend = ReadDimRaceWeekend(options);
                    SqliteWriters.UpsertDimRaceWeekend(sqlite, tx, dimWeekend);

                    // ============================================
                    // 3) result（history）
                    // ============================================
                    RaceResultRow[] results = ReadRaceResultsHistory(options);
                    SqliteWriters.InsertRaceResults(sqlite, tx, results);

                    // ============================================
                    // 4) payout（history）
                    // ============================================
                    if (options.IncludePayout)
                    {
                        PayoutRow[] payouts = ReadPayoutsHistory(options);
                        SqliteWriters.InsertPayouts(sqlite, tx, payouts);
                    }

                    // ============================================
                    // 5) entry（weekend）
                    // ============================================
                    RaceEntryRow[] entries = ReadRaceEntriesWeekend(options);
                    SqliteWriters.InsertRaceEntries(sqlite, tx, entries);

                    // ============================================
                    // 6) expectation（weekend）
                    // ============================================
                    ExpectationRow[] exp = ReadExpectationsWeekend(options);
                    SqliteWriters.InsertExpectations(sqlite, tx, exp);

                    // ============================================
                    // 7) pedigree（weekend horses only）
                    // ============================================
                    if (options.IncludePedigreeWeekendOnly)
                    {
                        PedigreeRow[] peds = ReadPedigreeWeekendOnly(options);
                        SqliteWriters.InsertPedigrees(sqlite, tx, peds);
                    }

                    tx.Commit();
                }

                ExecuteNonQuery(sqlite, "ANALYZE;");
            }
        }

        /// <summary>
        /// dim_race（過去）抽出。
        /// </summary>
        private static DimRaceRow[] ReadDimRaceHistory(ProgramOptions options)
        {
            System.Collections.Generic.List<DimRaceRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.DimRaceHistory,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.HistoryFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.HistoryToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.HistoryJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    DimRaceRow row = new DimRaceRow();
                    row.RaceId = r.GetString(0);
                    row.RaceDate = r.GetString(1);
                    row.JyoCd = r.GetString(2);
                    row.RaceNo = r.GetInt32(3);
                    row.RaceName = r.IsDBNull(4) ? null : r.GetString(4);
                    row.TrackName = r.IsDBNull(5) ? null : r.GetString(5);
                    row.SurfaceType = r.IsDBNull(6) ? null : r.GetString(6);
                    row.DistanceM = r.IsDBNull(7) ? (int?)null : r.GetInt32(7);
                    row.ClassSimple = r.IsDBNull(8) ? null : r.GetString(8);
                    row.Win5Flg = r.IsDBNull(9) ? 0 : r.GetInt32(9);
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// dim_race（週末）抽出。
        /// </summary>
        private static DimRaceRow[] ReadDimRaceWeekend(ProgramOptions options)
        {
            System.Collections.Generic.List<DimRaceRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.DimRaceWeekend,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.WeekendFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.WeekendToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.WeekendJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    DimRaceRow row = new DimRaceRow();
                    row.RaceId = r.GetString(0);
                    row.RaceDate = r.GetString(1);
                    row.JyoCd = r.GetString(2);
                    row.RaceNo = r.GetInt32(3);
                    row.RaceName = r.IsDBNull(4) ? null : r.GetString(4);
                    row.TrackName = r.IsDBNull(5) ? null : r.GetString(5);
                    row.SurfaceType = r.IsDBNull(6) ? null : r.GetString(6);
                    row.DistanceM = r.IsDBNull(7) ? (int?)null : r.GetInt32(7);
                    row.ClassSimple = r.IsDBNull(8) ? null : r.GetString(8);
                    row.Win5Flg = r.IsDBNull(9) ? 0 : r.GetInt32(9);
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// 過去結果抽出。
        /// </summary>
        private static RaceResultRow[] ReadRaceResultsHistory(ProgramOptions options)
        {
            System.Collections.Generic.List<RaceResultRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.RaceResultHistory,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.HistoryFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.HistoryToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.HistoryJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    RaceResultRow row = new RaceResultRow();
                    row.RaceId = r.GetString(0);
                    row.HorseId = r.GetString(1);
                    row.HorseName = r.GetString(2);
                    row.Umaban = r.IsDBNull(3) ? (int?)null : r.GetInt32(3);
                    row.Wakuban = r.IsDBNull(4) ? (int?)null : r.GetInt32(4);
                    row.FinishPos = r.IsDBNull(5) ? (int?)null : r.GetInt32(5);
                    row.TimeText = r.IsDBNull(6) ? null : r.GetString(6);
                    row.MarginText = r.IsDBNull(7) ? null : r.GetString(7);
                    row.JockeyName = r.IsDBNull(8) ? null : r.GetString(8);
                    row.WeightCarried = r.IsDBNull(9) ? (decimal?)null : r.GetDecimal(9);
                    row.Odds = r.IsDBNull(10) ? (decimal?)null : r.GetDecimal(10);
                    row.Popularity = r.IsDBNull(11) ? (int?)null : r.GetInt32(11);
                    return row;
                },
                300);

            return list.ToArray();
        }

        /// <summary>
        /// 払戻（単複）抽出。
        /// </summary>
        private static PayoutRow[] ReadPayoutsHistory(ProgramOptions options)
        {
            System.Collections.Generic.List<PayoutRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.PayoutHistoryWinPlace,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.HistoryFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.HistoryToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.HistoryJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    PayoutRow row = new PayoutRow();
                    row.RaceId = r.GetString(0);
                    row.BetType = r.GetString(1);
                    row.ComboText = r.GetString(2);
                    row.PayoutYen = r.GetInt32(3);
                    row.Popularity = r.IsDBNull(4) ? (int?)null : r.GetInt32(4);
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// 週末出馬抽出。
        /// </summary>
        private static RaceEntryRow[] ReadRaceEntriesWeekend(ProgramOptions options)
        {
            System.Collections.Generic.List<RaceEntryRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.RaceEntryWeekend,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.WeekendFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.WeekendToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.WeekendJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    RaceEntryRow row = new RaceEntryRow();
                    row.RaceId = r.GetString(0);
                    row.HorseId = r.IsDBNull(1) ? string.Empty : r.GetString(1);
                    row.HorseName = r.GetString(2);
                    row.Umaban = r.IsDBNull(3) ? (int?)null : r.GetInt32(3);
                    row.Wakuban = r.IsDBNull(4) ? (int?)null : r.GetInt32(4);
                    row.JockeyName = r.IsDBNull(5) ? null : r.GetString(5);
                    row.TrainerName = r.IsDBNull(6) ? null : r.GetString(6);
                    row.WeightCarried = r.IsDBNull(7) ? (decimal?)null : r.GetDecimal(7);
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// 週末指数抽出。
        /// </summary>
        private static ExpectationRow[] ReadExpectationsWeekend(ProgramOptions options)
        {
            System.Collections.Generic.List<ExpectationRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.ExpectationWeekend,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.WeekendFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.WeekendToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.WeekendJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    ExpectationRow row = new ExpectationRow();
                    row.RaceId = r.GetString(0);
                    row.Umaban = r.GetInt32(1);
                    row.HorseId = r.IsDBNull(2) ? null : r.GetString(2);
                    row.HorseName = r.IsDBNull(3) ? null : r.GetString(3);
                    row.Ability = r.IsDBNull(4) ? (double?)null : Convert.ToDouble(r.GetDecimal(4));
                    row.MultCourse = r.IsDBNull(5) ? (double?)null : Convert.ToDouble(r.GetDecimal(5));
                    row.MultStyle = r.IsDBNull(6) ? (double?)null : Convert.ToDouble(r.GetDecimal(6));
                    row.MultFrame = r.IsDBNull(7) ? (double?)null : Convert.ToDouble(r.GetDecimal(7));
                    row.MultBlood = r.IsDBNull(8) ? (double?)null : Convert.ToDouble(r.GetDecimal(8));
                    row.MultJockey = r.IsDBNull(9) ? (double?)null : Convert.ToDouble(r.GetDecimal(9));
                    row.ExpectedRaw = r.IsDBNull(10) ? (double?)null : Convert.ToDouble(r.GetDecimal(10));
                    row.Expected100 = r.IsDBNull(11) ? (double?)null : Convert.ToDouble(r.GetDecimal(11));
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// 週末出走馬の血統抽出。
        /// </summary>
        private static PedigreeRow[] ReadPedigreeWeekendOnly(ProgramOptions options)
        {
            System.Collections.Generic.List<PedigreeRow> list = DbUtil.QueryToList(
                options.ConnectionString,
                SqlServerQueries.PedigreeWeekendOnly,
                delegate (SqlParameterCollection p)
                {
                    p.Add(DbUtil.CreateParameter("@from_date", SqlDbType.Date, options.WeekendFromDate));
                    p.Add(DbUtil.CreateParameter("@to_date", SqlDbType.Date, options.WeekendToDate));
                    p.Add(DbUtil.CreateParameter("@jyo_cds", SqlDbType.NVarChar, options.WeekendJyoCdsCsv));
                },
                delegate (SqlDataReader r)
                {
                    PedigreeRow row = new PedigreeRow();
                    row.HorseId = r.GetString(0);
                    row.Sire = r.IsDBNull(1) ? null : r.GetString(1);
                    row.Dam = r.IsDBNull(2) ? null : r.GetString(2);
                    row.SireSire = r.IsDBNull(3) ? null : r.GetString(3);
                    return row;
                },
                120);

            return list.ToArray();
        }

        /// <summary>
        /// SQLite非クエリ実行。
        /// </summary>
        private static void ExecuteNonQuery(SqliteConnection conn, string sql)
        {
            using (SqliteCommand cmd = conn.CreateCommand())
            {
                cmd.CommandText = sql;
                cmd.ExecuteNonQuery();
            }
        }
    }

    // ============================================================
    // Rowモデル（まずはこのプロジェクト内に暫定配置 → 後で共通Row.csへ移動可）
    // ============================================================

    public sealed class DimRaceRow
    {
        public string RaceId { get; set; } = string.Empty;
        public string RaceDate { get; set; } = string.Empty;
        public string JyoCd { get; set; } = string.Empty;
        public int RaceNo { get; set; }
        public string? RaceName { get; set; }
        public string? TrackName { get; set; }
        public string? SurfaceType { get; set; }
        public int? DistanceM { get; set; }
        public string? ClassSimple { get; set; }
        public int Win5Flg { get; set; }
    }

    public sealed class RaceResultRow
    {
        public string RaceId { get; set; } = string.Empty;
        public string HorseId { get; set; } = string.Empty;
        public string HorseName { get; set; } = string.Empty;
        public int? Umaban { get; set; }
        public int? Wakuban { get; set; }
        public int? FinishPos { get; set; }
        public string? TimeText { get; set; }
        public string? MarginText { get; set; }
        public string? JockeyName { get; set; }
        public decimal? WeightCarried { get; set; }
        public decimal? Odds { get; set; }
        public int? Popularity { get; set; }
    }

    public sealed class PayoutRow
    {
        public string RaceId { get; set; } = string.Empty;
        public string BetType { get; set; } = string.Empty;
        public string ComboText { get; set; } = string.Empty;
        public int PayoutYen { get; set; }
        public int? Popularity { get; set; }
    }

    public sealed class RaceEntryRow
    {
        public string RaceId { get; set; } = string.Empty;
        public string HorseId { get; set; } = string.Empty;
        public string HorseName { get; set; } = string.Empty;
        public int? Umaban { get; set; }
        public int? Wakuban { get; set; }
        public string? JockeyName { get; set; }
        public string? TrainerName { get; set; }
        public decimal? WeightCarried { get; set; }
    }

    public sealed class ExpectationRow
    {
        public string RaceId { get; set; } = string.Empty;
        public int Umaban { get; set; }
        public string? HorseId { get; set; }
        public string? HorseName { get; set; }
        public double? Ability { get; set; }
        public double? MultCourse { get; set; }
        public double? MultStyle { get; set; }
        public double? MultFrame { get; set; }
        public double? MultBlood { get; set; }
        public double? MultJockey { get; set; }
        public double? ExpectedRaw { get; set; }
        public double? Expected100 { get; set; }
    }

    public sealed class PedigreeRow
    {
        public string HorseId { get; set; } = string.Empty;
        public string? Sire { get; set; }
        public string? Dam { get; set; }
        public string? SireSire { get; set; }
    }
}

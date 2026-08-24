using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Db.JvIf;
using KenshowLabo.Tools.Models.JvIf;
using Microsoft.Data.SqlClient;
using System;
using System.Collections.Generic;

namespace KenshowLabo.Tools.Domain.JvIf
{
    /// <summary>
    /// NL_SE_RACE_UMA → IF_JV_RaceUma の取り込みを担当します。
    /// </summary>
    public sealed class JvRaceUmaToIfImportService
    {
        private readonly string _sqlServerConnectionString;
        private readonly JvSqliteRaceUmaReader _reader;
        private readonly IfJvRaceUmaRepository _repo;

        /// <summary>
        /// コンストラクタ。
        /// </summary>
        public JvRaceUmaToIfImportService(string sqlServerConnectionString, string sqliteConnectionString)
        {
            _sqlServerConnectionString = sqlServerConnectionString;
            _reader = new JvSqliteRaceUmaReader(sqliteConnectionString);
            _repo = new IfJvRaceUmaRepository();
        }

        /// <summary>
        /// 年範囲で取り込みます（年ごとに DELETE→INSERT）。
        /// </summary>
        public void ImportByYearRange(int fromYear, int toYear)
        {
            if (toYear < fromYear)
            {
                int tmp = fromYear;
                fromYear = toYear;
                toYear = tmp;
            }

            for (int year = fromYear; year <= toYear; year++)
            {
                string fromYmd = year.ToString("0000") + "0101";
                string toYmd = year.ToString("0000") + "1231";

                // SQLiteから抽出
                List<IfJvRaceUmaRow> rows = _reader.ReadByYmdRange(fromYmd, toYmd);

                // SQL Serverへ反映（トランザクション）
                DbUtil.ExecuteInTransaction(_sqlServerConnectionString, (SqlConnection conn, SqlTransaction tx) =>
                {
                    _repo.DeleteByYmdRange(conn, tx, fromYmd, toYmd);
                    _repo.BulkInsert(conn, tx, rows);
                });

                Console.WriteLine("[IF_JV_RaceUma] year=" + year + " rows=" + rows.Count);
            }
        }
    }
}

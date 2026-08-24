using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Db.JvIf;
using KenshowLabo.Tools.Models.JvIf;
using Microsoft.Data.SqlClient;
using System;
using System.Collections.Generic;

namespace KenshowLabo.Tools.Domain.JvIf
{
    /// <summary>
    /// NL_RA_RACE → IF_JV_Race の取り込みを担当します。
    /// </summary>
    public sealed class JvRaceToIfImportService
    {
        private readonly string _sqlServerConnectionString;
        private readonly JvSqliteRaceReader _reader;
        private readonly IfJvRaceRepository _repo;

        /// <summary>
        /// コンストラクタ。
        /// </summary>
        public JvRaceToIfImportService(string sqlServerConnectionString, string sqliteConnectionString)
        {
            _sqlServerConnectionString = sqlServerConnectionString;
            _reader = new JvSqliteRaceReader(sqliteConnectionString);
            _repo = new IfJvRaceRepository();
        }

        /// <summary>
        /// 年範囲で取り込みます（年ごとに DELETE→INSERT）。
        /// </summary>
        public void ImportByYearRange(int fromYear, int toYear)
        {
            // 年範囲を正規化
            if (toYear < fromYear)
            {
                int tmp = fromYear;
                fromYear = toYear;
                toYear = tmp;
            }

            // 年ごとに処理
            for (int year = fromYear; year <= toYear; year++)
            {
                string fromYmd = year.ToString("0000") + "0101";
                string toYmd = year.ToString("0000") + "1231";

                // SQLiteから抽出
                List<IfJvRaceRow> rows = _reader.ReadByYmdRange(fromYmd, toYmd);

                // SQL Serverへ反映（トランザクション）
                DbUtil.ExecuteInTransaction(_sqlServerConnectionString, (SqlConnection conn, SqlTransaction tx) =>
                {
                    // 既存削除
                    _repo.DeleteByYmdRange(conn, tx, fromYmd, toYmd);

                    // 一括投入
                    _repo.BulkInsert(conn, tx, rows);
                });

                // 最低限の確認（ログは簡易）
                Console.WriteLine("[IF_JV_Race] year=" + year + " rows=" + rows.Count);
            }
        }
    }
}

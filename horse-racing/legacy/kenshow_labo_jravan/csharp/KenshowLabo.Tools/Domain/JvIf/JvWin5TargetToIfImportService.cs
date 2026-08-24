using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Db.JvIf;
using KenshowLabo.Tools.Models.JvIf;
using Microsoft.Data.SqlClient;
using System;
using System.Collections.Generic;

namespace KenshowLabo.Tools.Domain.JvIf
{
    public sealed class JvWin5TargetToIfImportService
    {
        private readonly string _sqlServerConnectionString;
        private readonly JvSqliteWin5TargetReader _reader;
        private readonly IfJvWin5TargetRepository _repo;

        public JvWin5TargetToIfImportService(string sqlServerConnectionString, string sqliteConnectionString)
        {
            _sqlServerConnectionString = sqlServerConnectionString;
            _reader = new JvSqliteWin5TargetReader(sqliteConnectionString);
            _repo = new IfJvWin5TargetRepository();
        }

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

                // SQLite抽出（開催日でフィルタ）
                List<IfJvWin5TargetRow> rows = _reader.ReadByKaisaiDateRange(fromYmd, toYmd);

                DateTime fromDate = new DateTime(year, 1, 1);
                DateTime toDate = new DateTime(year, 12, 31);

                DbUtil.ExecuteInTransaction(_sqlServerConnectionString, (SqlConnection conn, SqlTransaction tx) =>
                {
                    _repo.DeleteByDateRange(conn, tx, fromDate, toDate);
                    _repo.BulkInsert(conn, tx, rows);
                });

                Console.WriteLine("[IF_JV_Win5Target] year=" + year + " rows=" + rows.Count);
            }
        }
    }
}

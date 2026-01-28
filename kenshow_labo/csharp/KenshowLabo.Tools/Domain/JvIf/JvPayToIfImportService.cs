using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Db.JvIf;
using KenshowLabo.Tools.Models.JvIf;
using Microsoft.Data.SqlClient;
using System;
using System.Collections.Generic;

namespace KenshowLabo.Tools.Domain.JvIf
{
    public sealed class JvPayToIfImportService
    {
        private readonly string _sqlServerConnectionString;
        private readonly JvSqlitePayReader _reader;
        private readonly IfJvPayRepository _repo;

        public JvPayToIfImportService(string sqlServerConnectionString, string sqliteConnectionString)
        {
            _sqlServerConnectionString = sqlServerConnectionString;
            _reader = new JvSqlitePayReader(sqliteConnectionString);
            _repo = new IfJvPayRepository();
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

                List<IfJvPayRow> rows = _reader.ReadByYmdRange(fromYmd, toYmd);

                DbUtil.ExecuteInTransaction(_sqlServerConnectionString, (SqlConnection conn, SqlTransaction tx) =>
                {
                    _repo.DeleteByYear(conn, tx, year);
                    _repo.BulkInsert(conn, tx, rows);
                });

                System.Console.WriteLine("[IF_JV_Pay] year=" + year + " rows=" + rows.Count);
            }
        }
    }
}

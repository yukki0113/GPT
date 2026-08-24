using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    public sealed class IfJvWin5TargetRepository
    {
        public int DeleteByDateRange(SqlConnection conn, SqlTransaction tx, DateTime fromDate, DateTime toDate)
        {
            string sql =
                "DELETE FROM dbo.IF_JV_Win5Target " +
                "WHERE win5_date BETWEEN @fromDate AND @toDate;";

            using (SqlCommand cmd = new SqlCommand(sql, conn, tx))
            {
                cmd.CommandType = CommandType.Text;

                cmd.Parameters.Add(new SqlParameter("@fromDate", SqlDbType.Date) { Value = fromDate.Date });
                cmd.Parameters.Add(new SqlParameter("@toDate", SqlDbType.Date) { Value = toDate.Date });

                int affected = cmd.ExecuteNonQuery();
                return affected;
            }
        }

        public void BulkInsert(SqlConnection conn, SqlTransaction tx, List<IfJvWin5TargetRow> rows)
        {
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            DataTable table = CreateDataTable(rows);

            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, SqlBulkCopyOptions.Default, tx))
            {
                bulk.DestinationTableName = "dbo.IF_JV_Win5Target";

                bulk.ColumnMappings.Add("race_id", "race_id");
                bulk.ColumnMappings.Add("win5_date", "win5_date");
                bulk.ColumnMappings.Add("leg_no", "leg_no");
                bulk.ColumnMappings.Add("source_kubun", "source_kubun");
                bulk.ColumnMappings.Add("make_ymd", "make_ymd");

                bulk.WriteToServer(table);
            }
        }

        private static DataTable CreateDataTable(List<IfJvWin5TargetRow> rows)
        {
            DataTable table = new DataTable();

            table.Columns.Add("race_id", typeof(string));
            table.Columns.Add("win5_date", typeof(DateTime));
            table.Columns.Add("leg_no", typeof(byte));
            table.Columns.Add("source_kubun", typeof(string));
            table.Columns.Add("make_ymd", typeof(string));

            foreach (IfJvWin5TargetRow r in rows)
            {
                DataRow row = table.NewRow();

                row["race_id"] = r.RaceId;
                row["win5_date"] = r.Win5Date.Date;
                row["leg_no"] = r.LegNo;
                row["source_kubun"] = ToDbNull(r.SourceKubun);
                row["make_ymd"] = ToDbNull(r.MakeYmd);

                table.Rows.Add(row);
            }

            return table;
        }

        private static object ToDbNull(object? value)
        {
            if (value == null)
            {
                return DBNull.Value;
            }

            return value;
        }
    }
}

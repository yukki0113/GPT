using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    public sealed class IfJvPayRepository
    {
        public int DeleteByYear(SqlConnection conn, SqlTransaction tx, int year)
        {
            string prefix = year.ToString("0000") + "%";

            string sql =
                "DELETE FROM dbo.IF_JV_Pay " +
                "WHERE race_id LIKE @prefix;";

            using (SqlCommand cmd = new SqlCommand(sql, conn, tx))
            {
                cmd.CommandType = CommandType.Text;
                cmd.Parameters.Add(new SqlParameter("@prefix", SqlDbType.VarChar, 16) { Value = prefix });

                int affected = cmd.ExecuteNonQuery();
                return affected;
            }
        }

        public void BulkInsert(SqlConnection conn, SqlTransaction tx, List<IfJvPayRow> rows)
        {
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            DataTable table = CreateDataTable(rows);

            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, SqlBulkCopyOptions.Default, tx))
            {
                bulk.DestinationTableName = "dbo.IF_JV_Pay";

                bulk.ColumnMappings.Add("race_id", "race_id");
                bulk.ColumnMappings.Add("data_kubun", "data_kubun");
                bulk.ColumnMappings.Add("make_date", "make_date");

                bulk.ColumnMappings.Add("tansyo0_umaban", "tansyo0_umaban");
                bulk.ColumnMappings.Add("tansyo0_pay", "tansyo0_pay");
                bulk.ColumnMappings.Add("tansyo0_ninki", "tansyo0_ninki");

                bulk.ColumnMappings.Add("tansyo1_umaban", "tansyo1_umaban");
                bulk.ColumnMappings.Add("tansyo1_pay", "tansyo1_pay");
                bulk.ColumnMappings.Add("tansyo1_ninki", "tansyo1_ninki");

                bulk.ColumnMappings.Add("tansyo2_umaban", "tansyo2_umaban");
                bulk.ColumnMappings.Add("tansyo2_pay", "tansyo2_pay");
                bulk.ColumnMappings.Add("tansyo2_ninki", "tansyo2_ninki");

                bulk.ColumnMappings.Add("fukusyo0_umaban", "fukusyo0_umaban");
                bulk.ColumnMappings.Add("fukusyo0_pay", "fukusyo0_pay");
                bulk.ColumnMappings.Add("fukusyo0_ninki", "fukusyo0_ninki");

                bulk.ColumnMappings.Add("fukusyo1_umaban", "fukusyo1_umaban");
                bulk.ColumnMappings.Add("fukusyo1_pay", "fukusyo1_pay");
                bulk.ColumnMappings.Add("fukusyo1_ninki", "fukusyo1_ninki");

                bulk.ColumnMappings.Add("fukusyo2_umaban", "fukusyo2_umaban");
                bulk.ColumnMappings.Add("fukusyo2_pay", "fukusyo2_pay");
                bulk.ColumnMappings.Add("fukusyo2_ninki", "fukusyo2_ninki");

                bulk.ColumnMappings.Add("fukusyo3_umaban", "fukusyo3_umaban");
                bulk.ColumnMappings.Add("fukusyo3_pay", "fukusyo3_pay");
                bulk.ColumnMappings.Add("fukusyo3_ninki", "fukusyo3_ninki");

                bulk.ColumnMappings.Add("fukusyo4_umaban", "fukusyo4_umaban");
                bulk.ColumnMappings.Add("fukusyo4_pay", "fukusyo4_pay");
                bulk.ColumnMappings.Add("fukusyo4_ninki", "fukusyo4_ninki");

                bulk.WriteToServer(table);
            }
        }

        private static DataTable CreateDataTable(List<IfJvPayRow> rows)
        {
            DataTable table = new DataTable();

            table.Columns.Add("race_id", typeof(string));
            table.Columns.Add("data_kubun", typeof(string));
            table.Columns.Add("make_date", typeof(string));

            table.Columns.Add("tansyo0_umaban", typeof(string));
            table.Columns.Add("tansyo0_pay", typeof(int));
            table.Columns.Add("tansyo0_ninki", typeof(int));

            table.Columns.Add("tansyo1_umaban", typeof(string));
            table.Columns.Add("tansyo1_pay", typeof(int));
            table.Columns.Add("tansyo1_ninki", typeof(int));

            table.Columns.Add("tansyo2_umaban", typeof(string));
            table.Columns.Add("tansyo2_pay", typeof(int));
            table.Columns.Add("tansyo2_ninki", typeof(int));

            table.Columns.Add("fukusyo0_umaban", typeof(string));
            table.Columns.Add("fukusyo0_pay", typeof(int));
            table.Columns.Add("fukusyo0_ninki", typeof(int));

            table.Columns.Add("fukusyo1_umaban", typeof(string));
            table.Columns.Add("fukusyo1_pay", typeof(int));
            table.Columns.Add("fukusyo1_ninki", typeof(int));

            table.Columns.Add("fukusyo2_umaban", typeof(string));
            table.Columns.Add("fukusyo2_pay", typeof(int));
            table.Columns.Add("fukusyo2_ninki", typeof(int));

            table.Columns.Add("fukusyo3_umaban", typeof(string));
            table.Columns.Add("fukusyo3_pay", typeof(int));
            table.Columns.Add("fukusyo3_ninki", typeof(int));

            table.Columns.Add("fukusyo4_umaban", typeof(string));
            table.Columns.Add("fukusyo4_pay", typeof(int));
            table.Columns.Add("fukusyo4_ninki", typeof(int));

            foreach (IfJvPayRow r in rows)
            {
                DataRow row = table.NewRow();

                row["race_id"] = r.RaceId;
                row["data_kubun"] = ToDbNull(r.DataKubun);
                row["make_date"] = ToDbNull(r.MakeDate);

                row["tansyo0_umaban"] = ToDbNull(r.Tansyo0Umaban);
                row["tansyo0_pay"] = ToDbNull(r.Tansyo0Pay);
                row["tansyo0_ninki"] = ToDbNull(r.Tansyo0Ninki);

                row["tansyo1_umaban"] = ToDbNull(r.Tansyo1Umaban);
                row["tansyo1_pay"] = ToDbNull(r.Tansyo1Pay);
                row["tansyo1_ninki"] = ToDbNull(r.Tansyo1Ninki);

                row["tansyo2_umaban"] = ToDbNull(r.Tansyo2Umaban);
                row["tansyo2_pay"] = ToDbNull(r.Tansyo2Pay);
                row["tansyo2_ninki"] = ToDbNull(r.Tansyo2Ninki);

                row["fukusyo0_umaban"] = ToDbNull(r.Fukusyo0Umaban);
                row["fukusyo0_pay"] = ToDbNull(r.Fukusyo0Pay);
                row["fukusyo0_ninki"] = ToDbNull(r.Fukusyo0Ninki);

                row["fukusyo1_umaban"] = ToDbNull(r.Fukusyo1Umaban);
                row["fukusyo1_pay"] = ToDbNull(r.Fukusyo1Pay);
                row["fukusyo1_ninki"] = ToDbNull(r.Fukusyo1Ninki);

                row["fukusyo2_umaban"] = ToDbNull(r.Fukusyo2Umaban);
                row["fukusyo2_pay"] = ToDbNull(r.Fukusyo2Pay);
                row["fukusyo2_ninki"] = ToDbNull(r.Fukusyo2Ninki);

                row["fukusyo3_umaban"] = ToDbNull(r.Fukusyo3Umaban);
                row["fukusyo3_pay"] = ToDbNull(r.Fukusyo3Pay);
                row["fukusyo3_ninki"] = ToDbNull(r.Fukusyo3Ninki);

                row["fukusyo4_umaban"] = ToDbNull(r.Fukusyo4Umaban);
                row["fukusyo4_pay"] = ToDbNull(r.Fukusyo4Pay);
                row["fukusyo4_ninki"] = ToDbNull(r.Fukusyo4Ninki);

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

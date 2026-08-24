using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// IF_JV_HorsePedigree の投入（対象horse_idのみ DELETE→INSERT）
    /// </summary>
    public sealed class IfJvHorsePedigreeRepository
    {
        /// <summary>
        /// 対象horse_idを削除します（IN句バッチ）
        /// </summary>
        public void DeleteByHorseIds(SqlConnection conn, SqlTransaction tx, List<string> horseIds)
        {
            if (horseIds == null || horseIds.Count == 0)
            {
                return;
            }

            // IN句をパラメータで組み立て
            List<string> paramNames = new List<string>();
            for (int i = 0; i < horseIds.Count; i++)
            {
                paramNames.Add("@p" + i.ToString());
            }

            string sql = "DELETE FROM dbo.IF_JV_HorsePedigree WHERE horse_id IN (" + string.Join(",", paramNames) + ")";

            using (SqlCommand cmd = new SqlCommand(sql, conn, tx))
            {
                cmd.CommandType = CommandType.Text;
                cmd.CommandTimeout = 300;

                for (int i = 0; i < horseIds.Count; i++)
                {
                    SqlParameter p = new SqlParameter(paramNames[i], SqlDbType.Char, 10);
                    p.Value = horseIds[i];
                    cmd.Parameters.Add(p);
                }

                cmd.ExecuteNonQuery();
            }
        }

        /// <summary>
        /// 一括INSERT（SqlBulkCopy）
        /// </summary>
        public void BulkInsert(SqlConnection conn, SqlTransaction tx, List<IfJvHorsePedigreeRow> rows)
        {
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            DataTable table = CreateTable(rows);

            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, SqlBulkCopyOptions.Default, tx))
            {
                bulk.DestinationTableName = "dbo.IF_JV_HorsePedigree";
                bulk.BulkCopyTimeout = 600;
                bulk.BatchSize = 5000;

                // 列マッピング（DataTable列名＝テーブル列名で揃える）
                bulk.ColumnMappings.Add("horse_id", "horse_id");
                bulk.ColumnMappings.Add("horse_name", "horse_name");
                bulk.ColumnMappings.Add("sire", "sire");
                bulk.ColumnMappings.Add("dam", "dam");
                bulk.ColumnMappings.Add("dam_sire", "dam_sire");
                bulk.ColumnMappings.Add("dam_dam", "dam_dam");
                bulk.ColumnMappings.Add("sire_sire", "sire_sire");
                bulk.ColumnMappings.Add("sire_dam", "sire_dam");
                bulk.ColumnMappings.Add("data_kubun", "data_kubun");
                bulk.ColumnMappings.Add("make_date", "make_date");

                bulk.WriteToServer(table);
            }
        }

        /// <summary>
        /// BulkCopy用DataTableを作成します
        /// </summary>
        private static DataTable CreateTable(List<IfJvHorsePedigreeRow> rows)
        {
            DataTable table = new DataTable();

            table.Columns.Add("horse_id", typeof(string));
            table.Columns.Add("horse_name", typeof(string));
            table.Columns.Add("sire", typeof(string));
            table.Columns.Add("dam", typeof(string));
            table.Columns.Add("dam_sire", typeof(string));
            table.Columns.Add("dam_dam", typeof(string));
            table.Columns.Add("sire_sire", typeof(string));
            table.Columns.Add("sire_dam", typeof(string));
            table.Columns.Add("data_kubun", typeof(string));
            table.Columns.Add("make_date", typeof(string));

            for (int i = 0; i < rows.Count; i++)
            {
                IfJvHorsePedigreeRow r = rows[i];

                DataRow row = table.NewRow();
                row["horse_id"] = r.HorseId;
                row["horse_name"] = ToDbValue(r.HorseName);
                row["sire"] = ToDbValue(r.Sire);
                row["dam"] = ToDbValue(r.Dam);
                row["dam_sire"] = ToDbValue(r.DamSire);
                row["dam_dam"] = ToDbValue(r.DamDam);
                row["sire_sire"] = ToDbValue(r.SireSire);
                row["sire_dam"] = ToDbValue(r.SireDam);
                row["data_kubun"] = ToDbValue(r.DataKubun);
                row["make_date"] = ToDbValue(r.MakeDate);

                table.Rows.Add(row);
            }

            return table;
        }

        /// <summary>
        /// DataTableに入れる値を DBNull.Value に寄せる
        /// </summary>
        private static object ToDbValue(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return DBNull.Value;
            }

            return value.Trim();
        }
    }
}

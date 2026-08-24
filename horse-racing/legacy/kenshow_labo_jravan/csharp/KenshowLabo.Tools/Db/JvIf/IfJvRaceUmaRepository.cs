using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// IF_JV_RaceUma への永続化を担当します。
    /// </summary>
    public sealed class IfJvRaceUmaRepository
    {
        /// <summary>
        /// ymd 範囲で IF_JV_RaceUma を削除します。
        /// </summary>
        public int DeleteByYmdRange(SqlConnection conn, SqlTransaction tx, string fromYmd, string toYmd)
        {
            string sql =
                "DELETE FROM dbo.IF_JV_RaceUma " +
                "WHERE ymd BETWEEN @fromYmd AND @toYmd;";

            using (SqlCommand cmd = new SqlCommand(sql, conn, tx))
            {
                cmd.CommandType = CommandType.Text;

                cmd.Parameters.Add(new SqlParameter("@fromYmd", SqlDbType.Char, 8) { Value = fromYmd });
                cmd.Parameters.Add(new SqlParameter("@toYmd", SqlDbType.Char, 8) { Value = toYmd });

                int affected = cmd.ExecuteNonQuery();
                return affected;
            }
        }

        /// <summary>
        /// IF_JV_RaceUma に一括投入します（SqlBulkCopy）。
        /// </summary>
        public void BulkInsert(SqlConnection conn, SqlTransaction tx, List<IfJvRaceUmaRow> rows)
        {
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            DataTable table = CreateDataTable(rows);

            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, SqlBulkCopyOptions.Default, tx))
            {
                bulk.DestinationTableName = "dbo.IF_JV_RaceUma";

                bulk.ColumnMappings.Add("race_id", "race_id");
                bulk.ColumnMappings.Add("horse_no", "horse_no");
                bulk.ColumnMappings.Add("frame_no", "frame_no");
                bulk.ColumnMappings.Add("horse_id", "horse_id");
                bulk.ColumnMappings.Add("horse_name", "horse_name");
                bulk.ColumnMappings.Add("sex_cd", "sex_cd");
                bulk.ColumnMappings.Add("age", "age");
                bulk.ColumnMappings.Add("jockey_code", "jockey_code");
                bulk.ColumnMappings.Add("jockey_name", "jockey_name");
                bulk.ColumnMappings.Add("carried_weight", "carried_weight");
                bulk.ColumnMappings.Add("odds", "odds");
                bulk.ColumnMappings.Add("popularity", "popularity");
                bulk.ColumnMappings.Add("finish_pos", "finish_pos");
                bulk.ColumnMappings.Add("finish_time_raw", "finish_time_raw");
                bulk.ColumnMappings.Add("weight_raw", "weight_raw");
                bulk.ColumnMappings.Add("weight_diff_raw", "weight_diff_raw");
                bulk.ColumnMappings.Add("pos_c1", "pos_c1");
                bulk.ColumnMappings.Add("pos_c2", "pos_c2");
                bulk.ColumnMappings.Add("pos_c3", "pos_c3");
                bulk.ColumnMappings.Add("pos_c4", "pos_c4");
                bulk.ColumnMappings.Add("final_3f_raw", "final_3f_raw");
                bulk.ColumnMappings.Add("data_kubun", "data_kubun");
                bulk.ColumnMappings.Add("make_date", "make_date");
                bulk.ColumnMappings.Add("ymd", "ymd");

                bulk.WriteToServer(table);
            }
        }

        private static DataTable CreateDataTable(List<IfJvRaceUmaRow> rows)
        {
            DataTable table = new DataTable();

            table.Columns.Add("race_id", typeof(string));
            table.Columns.Add("horse_no", typeof(int));
            table.Columns.Add("frame_no", typeof(int));
            table.Columns.Add("horse_id", typeof(string));
            table.Columns.Add("horse_name", typeof(string));
            table.Columns.Add("sex_cd", typeof(string));
            table.Columns.Add("age", typeof(int));
            table.Columns.Add("jockey_code", typeof(string));
            table.Columns.Add("jockey_name", typeof(string));
            table.Columns.Add("carried_weight", typeof(decimal));
            table.Columns.Add("odds", typeof(decimal));
            table.Columns.Add("popularity", typeof(int));
            table.Columns.Add("finish_pos", typeof(int));
            table.Columns.Add("finish_time_raw", typeof(string));
            table.Columns.Add("weight_raw", typeof(string));
            table.Columns.Add("weight_diff_raw", typeof(string));
            table.Columns.Add("pos_c1", typeof(int));
            table.Columns.Add("pos_c2", typeof(int));
            table.Columns.Add("pos_c3", typeof(int));
            table.Columns.Add("pos_c4", typeof(int));
            table.Columns.Add("final_3f_raw", typeof(string));
            table.Columns.Add("data_kubun", typeof(string));
            table.Columns.Add("make_date", typeof(string));
            table.Columns.Add("ymd", typeof(string));

            foreach (IfJvRaceUmaRow r in rows)
            {
                DataRow row = table.NewRow();

                row["race_id"] = r.RaceId;
                row["horse_no"] = r.HorseNo;

                row["frame_no"] = ToDbNull(r.FrameNo);
                row["horse_id"] = ToDbNull(r.HorseId);
                row["horse_name"] = ToDbNull(r.HorseName);
                row["sex_cd"] = ToDbNull(r.SexCd);
                row["age"] = ToDbNull(r.Age);
                row["jockey_code"] = ToDbNull(r.JockeyCode);
                row["jockey_name"] = ToDbNull(r.JockeyName);

                row["carried_weight"] = ToDbNull(r.CarriedWeight);
                row["odds"] = ToDbNull(r.Odds);
                row["popularity"] = ToDbNull(r.Popularity);

                row["finish_pos"] = ToDbNull(r.FinishPos);
                row["finish_time_raw"] = ToDbNull(r.FinishTimeRaw);

                row["weight_raw"] = ToDbNull(r.WeightRaw);
                row["weight_diff_raw"] = ToDbNull(r.WeightDiffRaw);

                row["pos_c1"] = ToDbNull(r.PosC1);
                row["pos_c2"] = ToDbNull(r.PosC2);
                row["pos_c3"] = ToDbNull(r.PosC3);
                row["pos_c4"] = ToDbNull(r.PosC4);

                row["final_3f_raw"] = ToDbNull(r.Final3fRaw);

                row["data_kubun"] = ToDbNull(r.DataKubun);
                row["make_date"] = ToDbNull(r.MakeDate);
                row["ymd"] = r.Ymd;

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

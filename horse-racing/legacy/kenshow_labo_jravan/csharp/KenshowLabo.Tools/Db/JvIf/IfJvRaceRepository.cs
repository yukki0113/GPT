using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// IF_JV_Race への永続化を担当します。
    /// </summary>
    public sealed class IfJvRaceRepository
    {
        /// <summary>
        /// ymd 範囲で IF_JV_Race を削除します。
        /// </summary>
        public int DeleteByYmdRange(SqlConnection conn, SqlTransaction tx, string fromYmd, string toYmd)
        {
            // SQLを準備する
            string sql =
                "DELETE FROM dbo.IF_JV_Race " +
                "WHERE ymd BETWEEN @fromYmd AND @toYmd;";

            using (SqlCommand cmd = new SqlCommand(sql, conn, tx))
            {
                cmd.CommandType = CommandType.Text;

                // パラメータを設定する
                cmd.Parameters.Add(new SqlParameter("@fromYmd", SqlDbType.Char, 8) { Value = fromYmd });
                cmd.Parameters.Add(new SqlParameter("@toYmd", SqlDbType.Char, 8) { Value = toYmd });

                // 実行する
                int affected = cmd.ExecuteNonQuery();
                return affected;
            }
        }

        /// <summary>
        /// IF_JV_Race に一括投入します（SqlBulkCopy）。
        /// </summary>
        public void BulkInsert(SqlConnection conn, SqlTransaction tx, List<IfJvRaceRow> rows)
        {
            // 空なら何もしない
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            // DataTable を作る（列順は任意だが、Mappingは明示）
            DataTable table = CreateDataTable(rows);

            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, SqlBulkCopyOptions.Default, tx))
            {
                // 投入先
                bulk.DestinationTableName = "dbo.IF_JV_Race";

                // 取り込み列マッピング
                bulk.ColumnMappings.Add("race_id", "race_id");
                bulk.ColumnMappings.Add("ymd", "ymd");
                bulk.ColumnMappings.Add("jyo_cd", "jyo_cd");
                bulk.ColumnMappings.Add("race_num", "race_num");
                bulk.ColumnMappings.Add("kaiji", "kaiji");
                bulk.ColumnMappings.Add("nichiji", "nichiji");
                bulk.ColumnMappings.Add("data_kubun", "data_kubun");
                bulk.ColumnMappings.Add("make_date", "make_date");
                bulk.ColumnMappings.Add("race_name", "race_name");
                bulk.ColumnMappings.Add("jyoken_name", "jyoken_name");
                bulk.ColumnMappings.Add("grade_cd", "grade_cd");
                bulk.ColumnMappings.Add("track_cd", "track_cd");
                bulk.ColumnMappings.Add("distance_m", "distance_m");
                bulk.ColumnMappings.Add("hasso_time", "hasso_time");
                bulk.ColumnMappings.Add("weather_cd", "weather_cd");
                bulk.ColumnMappings.Add("baba_siba_cd", "baba_siba_cd");
                bulk.ColumnMappings.Add("baba_dirt_cd", "baba_dirt_cd");
                bulk.ColumnMappings.Add("jyoken_syubetu_cd", "jyoken_syubetu_cd");
                bulk.ColumnMappings.Add("jyoken_cd4", "jyoken_cd4");

                // 一括投入
                bulk.WriteToServer(table);
            }
        }

        /// <summary>
        /// DataTable を作成します（NULLは DBNull に変換）。
        /// </summary>
        private static DataTable CreateDataTable(List<IfJvRaceRow> rows)
        {
            DataTable table = new DataTable();

            // 列定義（IF定義に合わせる）
            table.Columns.Add("race_id", typeof(string));
            table.Columns.Add("ymd", typeof(string));
            table.Columns.Add("jyo_cd", typeof(string));
            table.Columns.Add("race_num", typeof(byte));
            table.Columns.Add("kaiji", typeof(short));
            table.Columns.Add("nichiji", typeof(short));
            table.Columns.Add("data_kubun", typeof(string));
            table.Columns.Add("make_date", typeof(string));
            table.Columns.Add("race_name", typeof(string));
            table.Columns.Add("jyoken_name", typeof(string));
            table.Columns.Add("grade_cd", typeof(string));
            table.Columns.Add("track_cd", typeof(string));
            table.Columns.Add("distance_m", typeof(int));
            table.Columns.Add("hasso_time", typeof(string));
            table.Columns.Add("weather_cd", typeof(string));
            table.Columns.Add("baba_siba_cd", typeof(string));
            table.Columns.Add("baba_dirt_cd", typeof(string));
            table.Columns.Add("jyoken_syubetu_cd", typeof(string));
            table.Columns.Add("jyoken_cd4", typeof(string));

            // 行を詰める
            foreach (IfJvRaceRow r in rows)
            {
                DataRow row = table.NewRow();

                row["race_id"] = r.RaceId;
                row["ymd"] = r.Ymd;
                row["jyo_cd"] = r.JyoCd;
                row["race_num"] = r.RaceNum;

                row["kaiji"] = ToDbNull(r.Kaiji);
                row["nichiji"] = ToDbNull(r.Nichiji);

                row["data_kubun"] = ToDbNull(r.DataKubun);
                row["make_date"] = ToDbNull(r.MakeDate);

                row["race_name"] = ToDbNull(r.RaceName);
                row["jyoken_name"] = ToDbNull(r.JyokenName);
                row["grade_cd"] = ToDbNull(r.GradeCd);
                row["track_cd"] = ToDbNull(r.TrackCd);
                row["distance_m"] = ToDbNull(r.DistanceM);

                row["hasso_time"] = ToDbNull(r.HassoTime);
                row["weather_cd"] = ToDbNull(r.WeatherCd);
                row["baba_siba_cd"] = ToDbNull(r.BabaSibaCd);
                row["baba_dirt_cd"] = ToDbNull(r.BabaDirtCd);

                row["jyoken_syubetu_cd"] = ToDbNull(r.JyokenSyubetuCd);
                row["jyoken_cd4"] = ToDbNull(r.JyokenCd4);

                table.Rows.Add(row);
            }

            return table;
        }

        /// <summary>
        /// NULL を DBNull に変換します。
        /// </summary>
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

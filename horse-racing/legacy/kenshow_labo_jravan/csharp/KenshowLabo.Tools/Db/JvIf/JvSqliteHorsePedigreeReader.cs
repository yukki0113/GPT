using System;
using System.Collections.Generic;
using System.Text;
using Microsoft.Data.Sqlite;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// SQLite（NL_UM_UMA）から血統情報を読み取る
    /// </summary>
    public sealed class JvSqliteHorsePedigreeReader
    {
        private readonly string _sqliteConnectionString;

        /// <summary>
        /// コンストラクタ
        /// </summary>
        public JvSqliteHorsePedigreeReader(string sqliteConnectionString)
        {
            _sqliteConnectionString = sqliteConnectionString;
        }

        /// <summary>
        /// 指定horse_id（KettoNum）群の血統情報を取得します（馬ごとに最新make_dateを採用）。
        /// </summary>
        public List<IfJvHorsePedigreeRow> ReadByHorseIds(List<string> horseIds)
        {
            List<IfJvHorsePedigreeRow> result = new List<IfJvHorsePedigreeRow>();

            if (horseIds == null || horseIds.Count == 0)
            {
                return result;
            }

            using (SqliteConnection conn = new SqliteConnection(_sqliteConnectionString))
            {
                conn.Open();

                // IN句をパラメータで組み立てる
                StringBuilder inClause = new StringBuilder();
                for (int i = 0; i < horseIds.Count; i++)
                {
                    if (i > 0)
                    {
                        inClause.Append(", ");
                    }
                    inClause.Append("@p");
                    inClause.Append(i.ToString());
                }

                string sql =
@"
SELECT
    headDataKubun,
    headMakeDate,
    KettoNum,
    Bamei,
    Ketto3Info0Bamei,
    Ketto3Info1Bamei,
    Ketto3Info2Bamei,
    Ketto3Info3Bamei,
    Ketto3Info4Bamei,
    Ketto3Info5Bamei
FROM NL_UM_UMA
WHERE KettoNum IN (" + inClause.ToString() + @")
ORDER BY KettoNum ASC, headMakeDate DESC
";

                using (SqliteCommand cmd = new SqliteCommand(sql, conn))
                {
                    // パラメータ設定
                    for (int i = 0; i < horseIds.Count; i++)
                    {
                        string name = "@p" + i.ToString();
                        cmd.Parameters.AddWithValue(name, horseIds[i]);
                    }

                    using (SqliteDataReader reader = cmd.ExecuteReader())
                    {
                        // KettoNumごとに最初の1件だけ採用（ORDER BY make_date DESC）
                        HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);

                        while (reader.Read())
                        {
                            string horseId = ReadText(reader, "KettoNum") ?? string.Empty;
                            horseId = horseId.Trim();

                            if (horseId.Length == 0)
                            {
                                continue;
                            }

                            if (seen.Contains(horseId))
                            {
                                continue;
                            }

                            seen.Add(horseId);

                            IfJvHorsePedigreeRow row = new IfJvHorsePedigreeRow();
                            row.HorseId = horseId;
                            row.HorseName = ReadText(reader, "Bamei");

                            // Ketto3Infoの並び確定（0父,1母,2父父,3父母,4母父,5母母）
                            row.Sire = ReadText(reader, "Ketto3Info0Bamei");
                            row.Dam = ReadText(reader, "Ketto3Info1Bamei");
                            row.SireSire = ReadText(reader, "Ketto3Info2Bamei");
                            row.SireDam = ReadText(reader, "Ketto3Info3Bamei");
                            row.DamSire = ReadText(reader, "Ketto3Info4Bamei");
                            row.DamDam = ReadText(reader, "Ketto3Info5Bamei");

                            row.DataKubun = ReadText(reader, "headDataKubun");
                            row.MakeDate = ReadText(reader, "headMakeDate");

                            result.Add(row);
                        }
                    }
                }
            }

            return result;
        }

        /// <summary>
        /// SQLiteのTEXTを安全に読む（NULLはnull）
        /// </summary>
        private static string? ReadText(SqliteDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);

            if (reader.IsDBNull(ordinal))
            {
                return null;
            }

            string value = reader.GetString(ordinal);
            if (value == null)
            {
                return null;
            }

            return value;
        }
    }
}

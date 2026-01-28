using System;
using System.Collections.Generic;
using Microsoft.Data.Sqlite;
using KenshowLabo.Tools.Domain;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// SQLite（NL_WF_INFO）から IF_JV_Win5Target 相当を抽出します。
    /// </summary>
    public sealed class JvSqliteWin5TargetReader
    {
        private readonly string _sqliteConnectionString;

        public JvSqliteWin5TargetReader(string sqliteConnectionString)
        {
            _sqliteConnectionString = sqliteConnectionString;
        }

        /// <summary>
        /// 開催日（yyyyMMdd）範囲で NL_WF_INFO を抽出し、leg1..5 を行展開します。
        /// </summary>
        public List<IfJvWin5TargetRow> ReadByKaisaiDateRange(string fromYmd, string toYmd)
        {
            List<IfJvWin5TargetRow> list = new List<IfJvWin5TargetRow>();

            using (SqliteConnection conn = new SqliteConnection(_sqliteConnectionString))
            {
                conn.Open();

                using (SqliteCommand cmd = conn.CreateCommand())
                {
                    // 必要列のみ（WFPayInfo系は不要）
                    cmd.CommandText =
                        "SELECT " +
                        " headDataKubun, headMakeDate, KaisaiDate, " +
                        " WFRaceInfo0JyoCD, WFRaceInfo0RaceNum, " +
                        " WFRaceInfo1JyoCD, WFRaceInfo1RaceNum, " +
                        " WFRaceInfo2JyoCD, WFRaceInfo2RaceNum, " +
                        " WFRaceInfo3JyoCD, WFRaceInfo3RaceNum, " +
                        " WFRaceInfo4JyoCD, WFRaceInfo4RaceNum " +
                        "FROM NL_WF_INFO " +
                        "WHERE KaisaiDate BETWEEN @fromYmd AND @toYmd;";

                    cmd.Parameters.AddWithValue("@fromYmd", fromYmd);
                    cmd.Parameters.AddWithValue("@toYmd", toYmd);

                    using (SqliteDataReader reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            // 開催日（win5_date）と race_id 生成用 ymd
                            string? kaisaiYmd = NormalizeYyyyMMdd(ReadText(reader, "KaisaiDate"));
                            if (kaisaiYmd == null)
                            {
                                continue;
                            }

                            DateTime? win5Date = ParseYyyyMMddToDateTime(kaisaiYmd);
                            if (win5Date == null)
                            {
                                continue;
                            }

                            // 管理情報
                            string? sourceKubun = TrimToLength(ReadText(reader, "headDataKubun"), 1);
                            string? makeYmd = NormalizeYyyyMMdd(ReadText(reader, "headMakeDate"));

                            // leg 0..4 を展開
                            for (int i = 0; i < 5; i++)
                            {
                                string? jyoCd = ReadText(reader, "WFRaceInfo" + i + "JyoCD");
                                string? raceNumText = ReadText(reader, "WFRaceInfo" + i + "RaceNum");

                                byte? raceNum = ParseNullableByte(raceNumText);

                                if (string.IsNullOrWhiteSpace(jyoCd) || jyoCd.Trim().Length != 2 || raceNum == null)
                                {
                                    // 欠けているlegはスキップ（部分欠けがあるデータも想定）
                                    continue;
                                }

                                string raceId = RaceIdBuilder.Build(kaisaiYmd, jyoCd.Trim(), (int)raceNum.Value);

                                IfJvWin5TargetRow row = new IfJvWin5TargetRow();
                                row.RaceId = raceId;
                                row.Win5Date = win5Date.Value;
                                row.LegNo = (byte)(i + 1);
                                row.SourceKubun = sourceKubun;
                                row.MakeYmd = makeYmd;

                                list.Add(row);
                            }
                        }
                    }
                }
            }

            return list;
        }

        private static string? ReadText(SqliteDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);
            if (reader.IsDBNull(ordinal))
            {
                return null;
            }
            return reader.GetString(ordinal);
        }

        private static string? TrimToLength(string? text, int maxLength)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            string s = text.Trim();
            if (s.Length <= maxLength)
            {
                return s;
            }

            return s.Substring(0, maxLength);
        }

        private static string? NormalizeYyyyMMdd(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            string s = text.Trim();
            if (s.Length >= 8)
            {
                s = s.Substring(0, 8);
            }

            int dummy;
            if (s.Length != 8 || !int.TryParse(s, out dummy))
            {
                return null;
            }

            return s;
        }

        private static DateTime? ParseYyyyMMddToDateTime(string ymd)
        {
            if (ymd.Length != 8)
            {
                return null;
            }

            int year;
            int month;
            int day;

            if (!int.TryParse(ymd.Substring(0, 4), out year))
            {
                return null;
            }
            if (!int.TryParse(ymd.Substring(4, 2), out month))
            {
                return null;
            }
            if (!int.TryParse(ymd.Substring(6, 2), out day))
            {
                return null;
            }

            try
            {
                return new DateTime(year, month, day);
            }
            catch
            {
                return null;
            }
        }

        private static byte? ParseNullableByte(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            byte value;
            if (!byte.TryParse(text.Trim(), out value))
            {
                return null;
            }

            return value;
        }
    }
}

using System;
using System.Collections.Generic;
using Microsoft.Data.Sqlite;
using KenshowLabo.Tools.Domain;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// SQLite（NL_HR_PAY）から IF_JV_Pay（Win/Place）相当を抽出します。
    /// </summary>
    public sealed class JvSqlitePayReader
    {
        private readonly string _sqliteConnectionString;

        public JvSqlitePayReader(string sqliteConnectionString)
        {
            _sqliteConnectionString = sqliteConnectionString;
        }

        public List<IfJvPayRow> ReadByYmdRange(string fromYmd, string toYmd)
        {
            List<IfJvPayRow> list = new List<IfJvPayRow>();

            using (SqliteConnection conn = new SqliteConnection(_sqliteConnectionString))
            {
                conn.Open();

                using (SqliteCommand cmd = conn.CreateCommand())
                {
                    cmd.CommandText =
                        "SELECT " +
                        " headDataKubun, headMakeDate," +
                        " idYear, idMonthDay, idJyoCD, idRaceNum," +
                        " PayTansyo0Umaban, PayTansyo0Pay, PayTansyo0Ninki," +
                        " PayTansyo1Umaban, PayTansyo1Pay, PayTansyo1Ninki," +
                        " PayTansyo2Umaban, PayTansyo2Pay, PayTansyo2Ninki," +
                        " PayFukusyo0Umaban, PayFukusyo0Pay, PayFukusyo0Ninki," +
                        " PayFukusyo1Umaban, PayFukusyo1Pay, PayFukusyo1Ninki," +
                        " PayFukusyo2Umaban, PayFukusyo2Pay, PayFukusyo2Ninki," +
                        " PayFukusyo3Umaban, PayFukusyo3Pay, PayFukusyo3Ninki," +
                        " PayFukusyo4Umaban, PayFukusyo4Pay, PayFukusyo4Ninki" +
                        " FROM NL_HR_PAY" +
                        " WHERE (idYear || idMonthDay) BETWEEN @fromYmd AND @toYmd;";

                    cmd.Parameters.AddWithValue("@fromYmd", fromYmd);
                    cmd.Parameters.AddWithValue("@toYmd", toYmd);

                    using (SqliteDataReader reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            string? idYear = ReadText(reader, "idYear");
                            string? idMonthDay = ReadText(reader, "idMonthDay");
                            string ymd = (idYear ?? "") + (idMonthDay ?? "");

                            string? jyoCd = ReadText(reader, "idJyoCD");
                            byte? raceNum = ParseNullableByte(ReadText(reader, "idRaceNum"));

                            if (ymd.Length != 8 || string.IsNullOrWhiteSpace(jyoCd) || jyoCd.Length != 2 || raceNum == null)
                            {
                                continue;
                            }

                            string raceId = RaceIdBuilder.Build(ymd, jyoCd, (int)raceNum.Value);

                            IfJvPayRow row = new IfJvPayRow();
                            row.RaceId = raceId;

                            row.DataKubun = TrimToLength(ReadText(reader, "headDataKubun"), 1);
                            row.MakeDate = NormalizeYyyyMMdd(ReadText(reader, "headMakeDate"));

                            row.Tansyo0Umaban = NormalizeUmaban2(ReadText(reader, "PayTansyo0Umaban"));
                            row.Tansyo0Pay = ParseNullableInt(ReadText(reader, "PayTansyo0Pay"));
                            row.Tansyo0Ninki = ParseNullableInt(ReadText(reader, "PayTansyo0Ninki"));

                            row.Tansyo1Umaban = NormalizeUmaban2(ReadText(reader, "PayTansyo1Umaban"));
                            row.Tansyo1Pay = ParseNullableInt(ReadText(reader, "PayTansyo1Pay"));
                            row.Tansyo1Ninki = ParseNullableInt(ReadText(reader, "PayTansyo1Ninki"));

                            row.Tansyo2Umaban = NormalizeUmaban2(ReadText(reader, "PayTansyo2Umaban"));
                            row.Tansyo2Pay = ParseNullableInt(ReadText(reader, "PayTansyo2Pay"));
                            row.Tansyo2Ninki = ParseNullableInt(ReadText(reader, "PayTansyo2Ninki"));

                            row.Fukusyo0Umaban = NormalizeUmaban2(ReadText(reader, "PayFukusyo0Umaban"));
                            row.Fukusyo0Pay = ParseNullableInt(ReadText(reader, "PayFukusyo0Pay"));
                            row.Fukusyo0Ninki = ParseNullableInt(ReadText(reader, "PayFukusyo0Ninki"));

                            row.Fukusyo1Umaban = NormalizeUmaban2(ReadText(reader, "PayFukusyo1Umaban"));
                            row.Fukusyo1Pay = ParseNullableInt(ReadText(reader, "PayFukusyo1Pay"));
                            row.Fukusyo1Ninki = ParseNullableInt(ReadText(reader, "PayFukusyo1Ninki"));

                            row.Fukusyo2Umaban = NormalizeUmaban2(ReadText(reader, "PayFukusyo2Umaban"));
                            row.Fukusyo2Pay = ParseNullableInt(ReadText(reader, "PayFukusyo2Pay"));
                            row.Fukusyo2Ninki = ParseNullableInt(ReadText(reader, "PayFukusyo2Ninki"));

                            row.Fukusyo3Umaban = NormalizeUmaban2(ReadText(reader, "PayFukusyo3Umaban"));
                            row.Fukusyo3Pay = ParseNullableInt(ReadText(reader, "PayFukusyo3Pay"));
                            row.Fukusyo3Ninki = ParseNullableInt(ReadText(reader, "PayFukusyo3Ninki"));

                            row.Fukusyo4Umaban = NormalizeUmaban2(ReadText(reader, "PayFukusyo4Umaban"));
                            row.Fukusyo4Pay = ParseNullableInt(ReadText(reader, "PayFukusyo4Pay"));
                            row.Fukusyo4Ninki = ParseNullableInt(ReadText(reader, "PayFukusyo4Ninki"));

                            list.Add(row);
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

        private static int? ParseNullableInt(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            int value;
            if (!int.TryParse(text.Trim(), out value))
            {
                return null;
            }

            return value;
        }

        private static string? NormalizeUmaban2(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            string s = text.Trim();

            int n;
            if (!int.TryParse(s, out n))
            {
                return TrimToLength(s, 2);
            }

            if (n <= 0)
            {
                return null;
            }

            return n.ToString("00");
        }
    }
}

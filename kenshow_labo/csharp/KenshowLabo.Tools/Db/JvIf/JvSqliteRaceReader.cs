using System;
using System.Collections.Generic;
using Microsoft.Data.Sqlite;
using KenshowLabo.Tools.Domain;
using KenshowLabo.Tools.Models.JvIf;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// SQLite（NL_RA_RACE）から IF_JV_Race 相当の情報を抽出します。
    /// </summary>
    public sealed class JvSqliteRaceReader
    {
        private readonly string _sqliteConnectionString;

        /// <summary>
        /// コンストラクタ。
        /// </summary>
        public JvSqliteRaceReader(string sqliteConnectionString)
        {
            _sqliteConnectionString = sqliteConnectionString;
        }

        /// <summary>
        /// ymd 範囲（yyyyMMdd）で NL_RA_RACE を抽出します。
        /// </summary>
        public List<IfJvRaceRow> ReadByYmdRange(string fromYmd, string toYmd)
        {
            // 結果格納
            List<IfJvRaceRow> list = new List<IfJvRaceRow>();

            // SQLiteへ接続する（参照専用）
            using (SqliteConnection conn = new SqliteConnection(_sqliteConnectionString))
            {
                conn.Open();

                // 必要列だけ抽出する（軽量化）
                using (SqliteCommand cmd = conn.CreateCommand())
                {
                    cmd.CommandText =
                        "SELECT " +
                        " headDataKubun, headMakeDate, " +
                        " idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum, " +
                        " RaceInfoHondai, JyokenName, GradeCD, TrackCD, Kyori, " +
                        " HassoTime, TenkoBabaTenkoCD, TenkoBabaSibaBabaCD, TenkoBabaDirtBabaCD, " +
                        " JyokenInfoSyubetuCD, JyokenInfoJyokenCD4 " +
                        "FROM NL_RA_RACE " +
                        "WHERE (idYear || idMonthDay) BETWEEN @fromYmd AND @toYmd;";

                    // パラメータ設定
                    cmd.Parameters.AddWithValue("@fromYmd", fromYmd);
                    cmd.Parameters.AddWithValue("@toYmd", toYmd);

                    // 実行して読み取る
                    using (SqliteDataReader reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            // ymd を組み立てる
                            string? idYear = ReadText(reader, "idYear");
                            string? idMonthDay = ReadText(reader, "idMonthDay");
                            string ymd = (idYear ?? "") + (idMonthDay ?? "");

                            // 必須キーを読む
                            string? jyoCd = ReadText(reader, "idJyoCD");
                            string? raceNumText = ReadText(reader, "idRaceNum");

                            // race_num を byte 化する（失敗はスキップ）
                            byte? raceNum = ParseNullableByte(raceNumText);
                            if (ymd.Length != 8 || string.IsNullOrWhiteSpace(jyoCd) || jyoCd.Length != 2 || raceNum == null)
                            {
                                continue;
                            }

                            // race_id 生成（2桁ゼロ埋めはBuilder側）
                            string raceId = RaceIdBuilder.Build(ymd, jyoCd, raceNum.Value);

                            // Row を構築する（型変換は安全第一）
                            IfJvRaceRow row = new IfJvRaceRow();
                            row.RaceId = raceId;
                            row.Ymd = ymd;
                            row.JyoCd = jyoCd;
                            row.RaceNum = raceNum.Value;

                            row.Kaiji = ParseNullableInt16(ReadText(reader, "idKaiji"));
                            row.Nichiji = ParseNullableInt16(ReadText(reader, "idNichiji"));

                            row.DataKubun = TrimToLength(ReadText(reader, "headDataKubun"), 1);
                            row.MakeDate = NormalizeYyyyMMdd(ReadText(reader, "headMakeDate"));

                            row.RaceName = TrimToLength(ReadText(reader, "RaceInfoHondai"), 50);
                            row.JyokenName = TrimToLength(ReadText(reader, "JyokenName"), 50);
                            row.GradeCd = TrimToLength(ReadText(reader, "GradeCD"), 2);
                            row.TrackCd = TrimToLength(ReadText(reader, "TrackCD"), 2);

                            row.DistanceM = ParseNullableInt32(ReadText(reader, "Kyori"));

                            row.HassoTime = NormalizeHhmm(ReadText(reader, "HassoTime"));

                            row.WeatherCd = TrimToLength(ReadText(reader, "TenkoBabaTenkoCD"), 1);
                            row.BabaSibaCd = TrimToLength(ReadText(reader, "TenkoBabaSibaBabaCD"), 1);
                            row.BabaDirtCd = TrimToLength(ReadText(reader, "TenkoBabaDirtBabaCD"), 1);

                            row.JyokenSyubetuCd = TrimToLength(ReadText(reader, "JyokenInfoSyubetuCD"), 10);
                            row.JyokenCd4 = TrimToLength(ReadText(reader, "JyokenInfoJyokenCD4"), 10);

                            list.Add(row);
                        }
                    }
                }
            }

            return list;
        }

        /// <summary>
        /// SQLiteのTEXT列を安全に取得します。
        /// </summary>
        private static string? ReadText(SqliteDataReader reader, string columnName)
        {
            int ordinal = reader.GetOrdinal(columnName);
            if (reader.IsDBNull(ordinal))
            {
                return null;
            }

            return reader.GetString(ordinal);
        }

        /// <summary>
        /// yyyyMMdd を正規化します（先頭8桁を採用、満たない場合は null）。
        /// </summary>
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

            if (s.Length != 8)
            {
                return null;
            }

            int dummy;
            if (!int.TryParse(s, out dummy))
            {
                return null;
            }

            return s;
        }

        /// <summary>
        /// HHmm を正規化します（4桁以外は null）。
        /// </summary>
        private static string? NormalizeHhmm(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            string s = text.Trim();
            if (s.Length != 4)
            {
                return null;
            }

            int dummy;
            if (!int.TryParse(s, out dummy))
            {
                return null;
            }

            return s;
        }

        /// <summary>
        /// 文字列を指定長に切り詰めます（null は null）。
        /// </summary>
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

        /// <summary>
        /// byte? へ安全に変換します。
        /// </summary>
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

        /// <summary>
        /// short? へ安全に変換します。
        /// </summary>
        private static short? ParseNullableInt16(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            short value;
            if (!short.TryParse(text.Trim(), out value))
            {
                return null;
            }

            return value;
        }

        /// <summary>
        /// int? へ安全に変換します。
        /// </summary>
        private static int? ParseNullableInt32(string? text)
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
    }
}

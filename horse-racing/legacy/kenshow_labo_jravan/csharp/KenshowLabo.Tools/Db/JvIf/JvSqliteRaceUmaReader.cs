using KenshowLabo.Tools.Domain;
using KenshowLabo.Tools.Models.JvIf;
using Microsoft.Data.Sqlite;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace KenshowLabo.Tools.Db.JvIf
{
    /// <summary>
    /// SQLite（NL_SE_RACE_UMA）から IF_JV_RaceUma 相当の情報を抽出します。
    /// </summary>
    public sealed class JvSqliteRaceUmaReader
    {
        private readonly string _sqliteConnectionString;

        /// <summary>
        /// コンストラクタ。
        /// </summary>
        public JvSqliteRaceUmaReader(string sqliteConnectionString)
        {
            _sqliteConnectionString = sqliteConnectionString;
        }

        /// <summary>
        /// ymd 範囲（yyyyMMdd）で NL_SE_RACE_UMA を抽出します。
        /// </summary>
        public List<IfJvRaceUmaRow> ReadByYmdRange(string fromYmd, string toYmd)
        {
            // 結果格納
            List<IfJvRaceUmaRow> list = new List<IfJvRaceUmaRow>();

            // SQLiteへ接続する
            using (SqliteConnection conn = new SqliteConnection(_sqliteConnectionString))
            {
                conn.Open();

                // 必要列だけ抽出する（軽量化）
                using (SqliteCommand cmd = conn.CreateCommand())
                {
                    cmd.CommandText =
                        "SELECT " +
                        " headDataKubun, headMakeDate," +
                        " idYear, idMonthDay, idJyoCD, idRaceNum," +
                        " Wakuban, Umaban," +
                        " KettoNum, Bamei, SexCD, Barei," +
                        " KisyuCode, KisyuRyakusyo," +
                        " Futan, Odds, Ninki," +
                        " NyusenJyuni, KakuteiJyuni, Time," +
                        " BaTaijyu, ZogenFugo, ZogenSa," +
                        " Jyuni1c, Jyuni2c, Jyuni3c, Jyuni4c," +
                        " HaronTimeL3" +
                        " FROM NL_SE_RACE_UMA" +
                        " WHERE (idYear || idMonthDay) BETWEEN @fromYmd AND @toYmd AND headDataKubun IN ('7','A','B') And Umaban != '00';";

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

                            // race_id生成に必要な値を読む
                            string? jyoCd = ReadText(reader, "idJyoCD");
                            byte? raceNum = ParseNullableByte(ReadText(reader, "idRaceNum"));

                            // horse_no を読む（必須）
                            int? horseNo = ParseNullableInt(ReadText(reader, "Umaban"));

                            // 必須が欠けている行はスキップする
                            if (ymd.Length != 8 || string.IsNullOrWhiteSpace(jyoCd) || jyoCd.Length != 2 || raceNum == null || horseNo == null)
                            {
                                continue;
                            }

                            // race_id を生成する
                            string raceId = RaceIdBuilder.Build(ymd, jyoCd, (int)raceNum.Value);

                            // Row を構築する
                            IfJvRaceUmaRow row = new IfJvRaceUmaRow();
                            row.RaceId = raceId;
                            row.Ymd = ymd;
                            row.HorseNo = horseNo.Value;

                            // 枠番
                            row.FrameNo = ParseNullableInt(ReadText(reader, "Wakuban"));

                            // 馬情報
                            row.HorseId = TrimToLength(ReadText(reader, "KettoNum"), 10);
                            row.HorseName = TrimToLength(ReadText(reader, "Bamei"), 30);
                            row.SexCd = TrimToLength(ReadText(reader, "SexCD"), 1);
                            row.Age = ParseNullableInt(ReadText(reader, "Barei"));

                            // 騎手
                            row.JockeyCode = TrimToLength(ReadText(reader, "KisyuCode"), 5);
                            row.JockeyName = TrimToLength(ReadText(reader, "KisyuRyakusyo"), 10);

                            // 斤量・オッズ・人気
                            string? futanText = ReadText(reader, "Futan");
                            decimal? cw = ParseCarriedWeight(futanText);
                            row.CarriedWeight = cw;
                            row.Odds = ParseNullableDecimal(ReadText(reader, "Odds"));
                            row.Popularity = ParseNullableInt(ReadText(reader, "Ninki"));

                            // 着順（確定を優先）
                            int? finishPos = ParseNullableInt(ReadText(reader, "KakuteiJyuni"));
                            if (finishPos == null)
                            {
                                finishPos = ParseNullableInt(ReadText(reader, "NyusenJyuni"));
                            }
                            row.FinishPos = finishPos;

                            // 走破タイム（RAW）
                            row.FinishTimeRaw = TrimToLength(ReadText(reader, "Time"), 16);

                            // 馬体重（RAW）
                            row.WeightRaw = TrimToLength(ReadText(reader, "BaTaijyu"), 8);

                            // 増減（RAW：+2 / -4 など）
                            row.WeightDiffRaw = BuildWeightDiffRaw(ReadText(reader, "ZogenFugo"), ReadText(reader, "ZogenSa"));

                            // コーナー順位
                            row.PosC1 = ParseNullableInt(ReadText(reader, "Jyuni1c"));
                            row.PosC2 = ParseNullableInt(ReadText(reader, "Jyuni2c"));
                            row.PosC3 = ParseNullableInt(ReadText(reader, "Jyuni3c"));
                            row.PosC4 = ParseNullableInt(ReadText(reader, "Jyuni4c"));

                            // 上がり3F（RAW）
                            row.Final3fRaw = TrimToLength(ReadText(reader, "HaronTimeL3"), 8);

                            // 管理情報
                            row.DataKubun = TrimToLength(ReadText(reader, "headDataKubun"), 1);
                            row.MakeDate = NormalizeYyyyMMdd(ReadText(reader, "headMakeDate"));

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

        private static decimal? ParseNullableDecimal(string? text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            string s = text.Trim();

            // 小数点を含む可能性があるため、Culture差を吸収する
            decimal value;
            if (decimal.TryParse(s, NumberStyles.Number, CultureInfo.InvariantCulture, out value))
            {
                return value;
            }

            if (decimal.TryParse(s, NumberStyles.Number, CultureInfo.CurrentCulture, out value))
            {
                return value;
            }

            return null;
        }

        private static string? BuildWeightDiffRaw(string? sign, string? diff)
        {
            if (string.IsNullOrWhiteSpace(diff))
            {
                return null;
            }

            string d = diff.Trim();
            int dummy;
            if (!int.TryParse(d, out dummy))
            {
                return null;
            }

            string s = "";
            if (!string.IsNullOrWhiteSpace(sign))
            {
                s = sign.Trim();
            }

            // sign が空でも差分だけ入れる（例： "2" ）
            return (s + d).Trim();
        }

        private static decimal? ParseCarriedWeight(string? text)
        {
            // NULL/空は NULL
            if (string.IsNullOrWhiteSpace(text))
            {
                return null;
            }

            // 前後空白除去＋全角数字を半角に
            string s = NormalizeDigits(text.Trim());

            // 小数も来る可能性があるので decimal を先に試す
            decimal decValue;
            if (decimal.TryParse(s, NumberStyles.Number, CultureInfo.InvariantCulture, out decValue))
            {
                // 540 のような値が decimal として読めた場合もあるので、10倍表現を補正
                if (decValue >= 100m)
                {
                    decValue = decValue / 10m;
                }

                decValue = Math.Round(decValue, 1);

                // IF定義 decimal(3,1) に収まらないものは NULL
                if (decValue > 99.9m || decValue < -99.9m)
                {
                    return null;
                }

                return decValue;
            }

            // それでもダメなら NULL
            return null;
        }

        private static string NormalizeDigits(string s)
        {
            StringBuilder sb = new StringBuilder(s.Length);

            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];

                // 全角数字 → 半角数字
                if (c >= '０' && c <= '９')
                {
                    char half = (char)('0' + (c - '０'));
                    sb.Append(half);
                    continue;
                }

                sb.Append(c);
            }

            return sb.ToString();
        }
    }
}

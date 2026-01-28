using System;

namespace KenshowLabo.Tools.Domain
{
    /// <summary>
    /// race_id（12桁）を生成します。
    /// race_id = yyyymmdd(8) + jyo_cd(2) + race_num(2)
    /// </summary>
    public static class RaceIdBuilder
    {
        /// <summary>
        /// race_id を生成します。
        /// </summary>
        public static string Build(string ymd, string jyoCd, int raceNum)
        {
            // ymd: yyyyMMdd を想定（仕様でC#側でも必ず埋める）
            if (string.IsNullOrWhiteSpace(ymd) || ymd.Length != 8)
            {
                throw new ArgumentException("ymd must be yyyyMMdd. ymd=" + ymd);
            }

            if (string.IsNullOrWhiteSpace(jyoCd) || jyoCd.Length != 2)
            {
                throw new ArgumentException("jyo_cd must be 2 chars. jyo_cd=" + jyoCd);
            }

            // race_num は2桁ゼロ埋め必須
            string raceNum2 = raceNum.ToString("00");

            return ymd + jyoCd + raceNum2;
        }
    }
}

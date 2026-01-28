using System;

namespace KenshowLabo.Tools.Models
{
    /// <summary>
    /// WIN5対象レースマスタ（MT_Win5Target）読み取り用Row DTOです。
    /// </summary>
    public sealed class Win5TargetRow
    {
        /// <summary>
        /// race_id（PK）
        /// </summary>
        public string RaceId { get; set; }

        /// <summary>
        /// win5_date
        /// </summary>
        public DateTime Win5Date { get; set; }

        /// <summary>
        /// leg_no（1〜5）
        /// </summary>
        public byte LegNo { get; set; }

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public Win5TargetRow()
        {
            this.RaceId = string.Empty;
            this.Win5Date = DateTime.MinValue;
            this.LegNo = 0;
        }
    }
}

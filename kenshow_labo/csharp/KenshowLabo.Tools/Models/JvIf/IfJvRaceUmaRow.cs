using System;

namespace KenshowLabo.Tools.Models.JvIf
{
    /// <summary>
    /// IF_JV_RaceUma 投入用の行データです。
    /// </summary>
    public sealed class IfJvRaceUmaRow
    {
        public string RaceId { get; set; } = "";
        public int HorseNo { get; set; }

        public int? FrameNo { get; set; }
        public string? HorseId { get; set; }
        public string? HorseName { get; set; }
        public string? SexCd { get; set; }
        public int? Age { get; set; }

        public string? JockeyCode { get; set; }
        public string? JockeyName { get; set; }

        public decimal? CarriedWeight { get; set; }
        public decimal? Odds { get; set; }
        public int? Popularity { get; set; }

        public int? FinishPos { get; set; }
        public string? FinishTimeRaw { get; set; }

        public string? WeightRaw { get; set; }
        public string? WeightDiffRaw { get; set; }

        public int? PosC1 { get; set; }
        public int? PosC2 { get; set; }
        public int? PosC3 { get; set; }
        public int? PosC4 { get; set; }

        public string? Final3fRaw { get; set; }

        public string? DataKubun { get; set; }
        public string? MakeDate { get; set; }

        public string Ymd { get; set; } = "";
    }
}

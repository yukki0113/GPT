using System;

namespace KenshowLabo.Tools.Models.JvIf
{
    /// <summary>
    /// IF_JV_Race 投入用の行データです。
    /// </summary>
    public sealed class IfJvRaceRow
    {
        public string RaceId { get; set; } = "";
        public string Ymd { get; set; } = "";
        public string JyoCd { get; set; } = "";
        public byte RaceNum { get; set; }

        public short? Kaiji { get; set; }
        public short? Nichiji { get; set; }

        public string? DataKubun { get; set; }
        public string? MakeDate { get; set; }

        public string? RaceName { get; set; }
        public string? JyokenName { get; set; }
        public string? GradeCd { get; set; }
        public string? TrackCd { get; set; }
        public int? DistanceM { get; set; }

        public string? HassoTime { get; set; }
        public string? WeatherCd { get; set; }
        public string? BabaSibaCd { get; set; }
        public string? BabaDirtCd { get; set; }
        public string? JyokenSyubetuCd { get; set; }
        public string? JyokenCd4 { get; set; }

    }
}

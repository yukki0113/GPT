using System;

namespace KenshowLabo.Tools.Models.JvIf
{
    /// <summary>
    /// IF_JV_Win5Target 投入用の行データです。
    /// </summary>
    public sealed class IfJvWin5TargetRow
    {
        public string RaceId { get; set; } = "";

        public DateTime Win5Date { get; set; }
        public byte LegNo { get; set; }

        public string? SourceKubun { get; set; }
        public string? MakeYmd { get; set; }
    }
}

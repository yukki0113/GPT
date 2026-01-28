namespace KenshowLabo.Tools.Models.JvIf
{
    /// <summary>
    /// IF_JV_Pay 投入用の行データです。
    /// </summary>
    public sealed class IfJvPayRow
    {
        public string RaceId { get; set; } = "";

        public string? DataKubun { get; set; }
        public string? MakeDate { get; set; }

        public string? Tansyo0Umaban { get; set; }
        public int? Tansyo0Pay { get; set; }
        public int? Tansyo0Ninki { get; set; }

        public string? Tansyo1Umaban { get; set; }
        public int? Tansyo1Pay { get; set; }
        public int? Tansyo1Ninki { get; set; }

        public string? Tansyo2Umaban { get; set; }
        public int? Tansyo2Pay { get; set; }
        public int? Tansyo2Ninki { get; set; }

        public string? Fukusyo0Umaban { get; set; }
        public int? Fukusyo0Pay { get; set; }
        public int? Fukusyo0Ninki { get; set; }

        public string? Fukusyo1Umaban { get; set; }
        public int? Fukusyo1Pay { get; set; }
        public int? Fukusyo1Ninki { get; set; }

        public string? Fukusyo2Umaban { get; set; }
        public int? Fukusyo2Pay { get; set; }
        public int? Fukusyo2Ninki { get; set; }

        public string? Fukusyo3Umaban { get; set; }
        public int? Fukusyo3Pay { get; set; }
        public int? Fukusyo3Ninki { get; set; }

        public string? Fukusyo4Umaban { get; set; }
        public int? Fukusyo4Pay { get; set; }
        public int? Fukusyo4Ninki { get; set; }
    }
}

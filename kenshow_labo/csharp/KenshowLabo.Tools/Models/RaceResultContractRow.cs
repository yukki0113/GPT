using System;

namespace KenshowLabo.Tools.Models
{
    /// <summary>
    /// dbo.VW_RaceResultContract_v1 読み取り用Row DTOです。
    /// 1行 = 1出走馬（race_id + 馬番）を想定します。
    /// </summary>
    public sealed class RaceResultContractRow
    {
        // =========================
        // Race（共通）
        // =========================
        public string RaceId { get; set; }
        public DateTime RaceDate { get; set; }
        public string RaceName { get; set; }
        public string ClassName { get; set; }
        public string ClassSimple { get; set; }
        public bool Win5Flg { get; set; }
        public string unified_class_cd { get; set; }

        public string Track { get; set; }
        public string Surface { get; set; }
        public int Distance { get; set; }
        public string Turn { get; set; }

        public string Meeting { get; set; }
        public string Going { get; set; }
        public string Weather { get; set; }
        public string TrackId { get; set; }

        // =========================
        // Entry（馬ごと）
        // =========================
        public int FrameNo { get; set; }
        public int HorseNo { get; set; }
        public string HorseId { get; set; }
        public string HorseName { get; set; }
        public string Sex { get; set; }
        public int Age { get; set; }
        public string Jockey { get; set; }
        public decimal CarriedWeight { get; set; }
        public int Popularity { get; set; }
        public decimal Odds { get; set; }
        public int? Finish { get; set; }
        public string Time { get; set; }
        public int BodyWeight { get; set; }
        public int BodyWeightDiff { get; set; }

        public int? Corner1 { get; set; }
        public int? Corner2 { get; set; }
        public int? Corner3 { get; set; }
        public int? Corner4 { get; set; }
        public decimal Last3f { get; set; }

        // =========================
        // Style（VIEW算出）
        // =========================
        public int FieldSize { get; set; }
        public string RunningStyle { get; set; }

        // =========================
        // Pedigree（LEFT JOIN）
        // =========================
        public string PedigreeHorseName { get; set; }
        public string Sire { get; set; }
        public string Dam { get; set; }
        public string DamSire { get; set; }
        public string DamDam { get; set; }
        public string SireSire { get; set; }
        public string SireDam { get; set; }

        // =========================
        // Payout（単勝/複勝）
        // =========================
        public int? WinPayout { get; set; }
        public int? WinPopularity { get; set; }
        public int? PlacePayout { get; set; }
        public int? PlacePopularity { get; set; }

        /// <summary>
        /// コンストラクタです（文字列は空文字に寄せます）。
        /// </summary>
        public RaceResultContractRow()
        {
            this.RaceId = string.Empty;
            this.RaceName = string.Empty;
            this.ClassName = string.Empty;
            this.ClassSimple = string.Empty;
            this.unified_class_cd = string.Empty;

            this.Track = string.Empty;
            this.Surface = string.Empty;
            this.Turn = string.Empty;

            this.Meeting = string.Empty;
            this.Going = string.Empty;
            this.Weather = string.Empty;
            this.TrackId = string.Empty;

            this.HorseId = string.Empty;
            this.HorseName = string.Empty;
            this.Sex = string.Empty;
            this.Jockey = string.Empty;
            this.Time = string.Empty;

            this.RunningStyle = string.Empty;

            this.PedigreeHorseName = string.Empty;
            this.Sire = string.Empty;
            this.Dam = string.Empty;
            this.DamSire = string.Empty;
            this.DamDam = string.Empty;
            this.SireSire = string.Empty;
            this.SireDam = string.Empty;
        }
    }
}

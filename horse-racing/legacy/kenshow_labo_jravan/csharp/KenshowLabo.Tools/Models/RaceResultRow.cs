using System;

namespace KenshowLabo.Tools.Models
{
    public sealed class RaceResultRow
    {
        // Race（共通）
        public string RaceId { get; set; }
        public DateTime RaceDate { get; set; }
        public string RaceName { get; set; }
        public string ClassName { get; set; }
        public string ClassSimple { get; set; }
        public bool Win5Target { get; set; }

        public string Track { get; set; }
        public string Surface { get; set; }
        public int Distance { get; set; }
        public string Turn { get; set; }

        public string Weather { get; set; }
        public string Going { get; set; }
        public string Meeting { get; set; }
        public string TrackId { get; set; }

        // Entry（馬ごと）
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
        public string RunningStyle { get; set; }

        public int Corner1 { get; set; }
        public int Corner2 { get; set; }
        public int Corner3 { get; set; }
        public int Corner4 { get; set; }
        public decimal Last3f { get; set; }

        public RaceResultRow()
        {
            this.RaceId = string.Empty;
            this.RaceName = string.Empty;
            this.ClassName = string.Empty;
            this.ClassSimple = string.Empty;

            this.Track = string.Empty;
            this.Surface = string.Empty;
            this.Turn = string.Empty;

            this.Weather = string.Empty;
            this.Going = string.Empty;
            this.Meeting = string.Empty;
            this.TrackId = string.Empty;

            this.HorseId = string.Empty;
            this.HorseName = string.Empty;
            this.Sex = string.Empty;
            this.Jockey = string.Empty;
            this.Time = string.Empty;
            this.RunningStyle = string.Empty;
        }
    }
}

using System;

namespace KenshowLabo.Tools.Models
{
    /// <summary>
    /// dbo.IF_RaceEntry の1行（1出走馬）を表すDTOです。
    /// </summary>
    public sealed class IfRaceEntryRow
    {
        // ----------------------------
        // Key
        // ----------------------------

        /// <summary>race_id（yyyyMMdd + 場CD(2) + R(2) の12桁）</summary>
        public long RaceId { get; set; }

        /// <summary>horse_id（現時点では netkeiba horse_id を格納。TR展開時にJVへ変換予定）</summary>
        public long HorseId { get; set; }

        // ----------------------------
        // Race
        // ----------------------------

        /// <summary>race_no（1～12）</summary>
        public byte RaceNo { get; set; }

        /// <summary>race_date</summary>
        public DateTime RaceDate { get; set; }

        /// <summary>race_name</summary>
        public string RaceName { get; set; }

        /// <summary>race_class</summary>
        public string RaceClass { get; set; }

        /// <summary>classSimple</summary>
        public string ClassSimple { get; set; }

        /// <summary>track_name（例：中山）</summary>
        public string TrackName { get; set; }

        /// <summary>surface_type（例：芝/ダ/障）</summary>
        public string SurfaceType { get; set; }

        /// <summary>distance_m</summary>
        public int DistanceM { get; set; }

        /// <summary>meeting</summary>
        public string Meeting { get; set; }

        /// <summary>turn（右/左）</summary>
        public string Turn { get; set; }

        /// <summary>course_inout（内/外。取れない場合は空）</summary>
        public string CourseInOut { get; set; }

        /// <summary>going（良/稍/重/不 等）</summary>
        public string Going { get; set; }

        /// <summary>weather</summary>
        public string Weather { get; set; }

        // ----------------------------
        // Entry
        // ----------------------------

        /// <summary>frame_no（未確定は null）</summary>
        public int? FrameNo { get; set; }

        /// <summary>horse_no（未確定は 101～118）</summary>
        public int HorseNo { get; set; }

        /// <summary>horse_name</summary>
        public string HorseName { get; set; }

        /// <summary>sex</summary>
        public string Sex { get; set; }

        /// <summary>age</summary>
        public int? Age { get; set; }

        /// <summary>jockey_name</summary>
        public string JockeyName { get; set; }

        /// <summary>carried_weight</summary>
        public decimal? CarriedWeight { get; set; }

        // ----------------------------
        // Manage
        // ----------------------------

        /// <summary>scraped_at</summary>
        public DateTime ScrapedAt { get; set; }

        /// <summary>source_url</summary>
        public string SourceUrl { get; set; }

        /// <summary>
        /// コンストラクタです（文字列は空文字で初期化）。
        /// </summary>
        public IfRaceEntryRow()
        {
            // 文字列はnullを避ける
            this.RaceName = string.Empty;
            this.RaceClass = string.Empty;
            this.ClassSimple = string.Empty;
            this.TrackName = string.Empty;
            this.SurfaceType = string.Empty;
            this.Meeting = string.Empty;
            this.Turn = string.Empty;
            this.CourseInOut = string.Empty;
            this.Going = string.Empty;
            this.Weather = string.Empty;

            this.HorseName = string.Empty;
            this.Sex = string.Empty;
            this.JockeyName = string.Empty;

            this.SourceUrl = string.Empty;

            // 日付は投入前に必ず上書きされる前提
            this.RaceDate = DateTime.MinValue;
            this.ScrapedAt = DateTime.MinValue;
        }
    }
}

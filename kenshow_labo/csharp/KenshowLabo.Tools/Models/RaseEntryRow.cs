using System;

namespace KenshowLabo.Tools.Models {
    /// <summary>
    /// dbo.TR_RaceEntry の1行（1出走馬）を表す Row DTO です。
    /// </summary>
    public sealed class RaceEntryRow {
        // ----------------------------
        // 主キー（TR側は id を主キーとする）
        // ----------------------------

        /// <summary>
        /// ID（IDENTITY）
        /// </summary>
        public int Id { get; set; }

        // ----------------------------
        // レース基本情報（TR_RaceResult に揃える）
        // ----------------------------

        /// <summary>
        /// race_id（CHAR(12)）
        /// </summary>
        public string RaceId { get; set; }

        /// <summary>
        /// race_date（DATE）
        /// </summary>
        public DateTime RaceDate { get; set; }

        /// <summary>
        /// race_name
        /// </summary>
        public string RaceName { get; set; }

        /// <summary>
        /// race_class（例：G1, 3歳以上1勝クラス 等）
        /// </summary>
        public string RaceClass { get; set; }

        /// <summary>
        /// classSimple（例：1勝クラス）
        /// </summary>
        public string ClassSimple { get; set; }

        /// <summary>
        /// track_name（例：東京）
        /// </summary>
        public string TrackName { get; set; }

        /// <summary>
        /// surface_type（例：芝/ダ/障害）
        /// </summary>
        public string SurfaceType { get; set; }

        /// <summary>
        /// distance_m（メートル）
        /// </summary>
        public int DistanceM { get; set; }

        /// <summary>
        /// meeting（例：1回東京6日目 等）
        /// </summary>
        public string Meeting { get; set; }

        /// <summary>
        /// turn（例：右/左）
        /// </summary>
        public string Turn { get; set; }

        /// <summary>
        /// going（例：良/重 等）
        /// </summary>
        public string Going { get; set; }

        /// <summary>
        /// weather
        /// </summary>
        public string Weather { get; set; }

        /// <summary>
        /// track_id（既存ID体系を踏襲）
        /// </summary>
        public int? TrackId { get; set; }

        // ----------------------------
        // 出走馬情報（出馬表）
        // ----------------------------

        /// <summary>
        /// 枠番（未確定なら null）
        /// </summary>
        public int? FrameNo { get; set; }

        /// <summary>
        /// 馬番（未確定なら null）
        /// </summary>
        public int? HorseNo { get; set; }

        /// <summary>
        /// horse_id（JVに統一できれば入れる。未確定なら null）
        /// </summary>
        public long? HorseId { get; set; }

        /// <summary>
        /// horse_name
        /// </summary>
        public string HorseName { get; set; }

        /// <summary>
        /// sex（牡/牝/セ など）
        /// </summary>
        public string Sex { get; set; }

        /// <summary>
        /// age
        /// </summary>
        public int? Age { get; set; }

        /// <summary>
        /// jockey_name
        /// </summary>
        public string JockeyName { get; set; }

        /// <summary>
        /// carried_weight（斤量）
        /// </summary>
        public decimal? CarriedWeight { get; set; }

        // ----------------------------
        // 管理用
        // ----------------------------

        /// <summary>
        /// source_url
        /// </summary>
        public string SourceUrl { get; set; }

        /// <summary>
        /// scraped_at（取得日時）
        /// </summary>
        public DateTime ScrapedAt { get; set; }

        /// <summary>
        /// コンストラクタです（文字列は空文字に寄せます）。
        /// </summary>
        public RaceEntryRow() {
            // 文字列は null を避け、空文字で初期化します
            this.RaceId = string.Empty;
            this.RaceName = string.Empty;
            this.RaceClass = string.Empty;
            this.ClassSimple = string.Empty;
            this.TrackName = string.Empty;
            this.SurfaceType = string.Empty;
            this.Meeting = string.Empty;
            this.Turn = string.Empty;
            this.Going = string.Empty;
            this.Weather = string.Empty;

            this.HorseName = string.Empty;
            this.Sex = string.Empty;
            this.JockeyName = string.Empty;

            this.SourceUrl = string.Empty;

            // 日時はとりあえず最小値（投入前に上書き）
            this.RaceDate = DateTime.MinValue;
            this.ScrapedAt = DateTime.MinValue;
        }
    }
}

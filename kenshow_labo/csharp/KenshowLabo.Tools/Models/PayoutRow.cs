namespace KenshowLabo.Tools.Models
{
    /// <summary>
    /// レース払戻（TR_Payout）読み取り用Row DTOです。
    /// </summary>
    public sealed class PayoutRow
    {
        /// <summary>
        /// id（IDENTITY）
        /// </summary>
        public int Id { get; set; }

        /// <summary>
        /// race_id（CHAR(12)）
        /// </summary>
        public string RaceId { get; set; }

        /// <summary>
        /// 式別（例：単勝/複勝/馬連…）
        /// </summary>
        public string BetType { get; set; }

        /// <summary>
        /// 馬番1（NULL可）
        /// </summary>
        public int? HorseNo1 { get; set; }

        /// <summary>
        /// 馬番2（NULL可）
        /// </summary>
        public int? HorseNo2 { get; set; }

        /// <summary>
        /// 馬番3（NULL可）
        /// </summary>
        public int? HorseNo3 { get; set; }

        /// <summary>
        /// 払戻金（円）
        /// </summary>
        public int Payout { get; set; }

        /// <summary>
        /// 人気（NULL可）
        /// </summary>
        public int? Popularity { get; set; }

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public PayoutRow()
        {
            this.RaceId = string.Empty;
            this.BetType = string.Empty;
            this.Payout = 0;
        }
    }
}

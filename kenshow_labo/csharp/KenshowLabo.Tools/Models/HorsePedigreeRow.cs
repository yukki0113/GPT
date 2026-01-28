namespace KenshowLabo.Tools.Models
{
    /// <summary>
    /// 血統マスタ（MT_HorsePedigree）読み取り用Row DTOです。
    /// </summary>
    public sealed class HorsePedigreeRow
    {
        /// <summary>
        /// horse_id（PK）
        /// </summary>
        public string HorseId { get; set; }

        /// <summary>
        /// 馬名（NULL可のため、DTOでは空文字に寄せます）
        /// </summary>
        public string HorseName { get; set; }

        /// <summary>
        /// 父
        /// </summary>
        public string Sire { get; set; }

        /// <summary>
        /// 母
        /// </summary>
        public string Dam { get; set; }

        /// <summary>
        /// 母父
        /// </summary>
        public string DamSire { get; set; }

        /// <summary>
        /// 母母
        /// </summary>
        public string DamDam { get; set; }

        /// <summary>
        /// 父父
        /// </summary>
        public string SireSire { get; set; }

        /// <summary>
        /// 父母
        /// </summary>
        public string SireDam { get; set; }

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public HorsePedigreeRow()
        {
            this.HorseId = string.Empty;
            this.HorseName = string.Empty;
            this.Sire = string.Empty;
            this.Dam = string.Empty;
            this.DamSire = string.Empty;
            this.DamDam = string.Empty;
            this.SireSire = string.Empty;
            this.SireDam = string.Empty;
        }
    }
}

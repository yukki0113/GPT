using System;

namespace KenshowLabo.Tools.Models.JvIf
{
    /// <summary>
    /// IF_JV_HorsePedigree 取り込み用（C#側の中間モデル）
    /// </summary>
    public sealed class IfJvHorsePedigreeRow
    {
        /// <summary>JVの血統番号（KettoNum）</summary>
        public string HorseId { get; set; } = string.Empty;

        public string? HorseName { get; set; }

        public string? Sire { get; set; }
        public string? Dam { get; set; }
        public string? DamSire { get; set; }
        public string? DamDam { get; set; }
        public string? SireSire { get; set; }
        public string? SireDam { get; set; }

        public string? DataKubun { get; set; }
        public string? MakeDate { get; set; }
    }
}

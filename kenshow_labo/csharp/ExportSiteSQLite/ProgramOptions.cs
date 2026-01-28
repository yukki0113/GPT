using System;

namespace ExportSiteSQLite
{
    /// <summary>
    /// 実行オプション（設定＋引数上書き用）。
    /// </summary>
    public sealed class ProgramOptions
    {
        /// <summary>SQL Server 接続文字列。</summary>
        public string ConnectionString { get; set; } = string.Empty;

        /// <summary>出力先フォルダ。</summary>
        public string OutputDir { get; set; } = string.Empty;

        /// <summary>出力ファイル名。</summary>
        public string SnapshotFileName { get; set; } = string.Empty;

        /// <summary>過去範囲: From。</summary>
        public DateTime HistoryFromDate { get; set; }

        /// <summary>過去範囲: To。</summary>
        public DateTime HistoryToDate { get; set; }

        /// <summary>過去対象場: CSV。</summary>
        public string HistoryJyoCdsCsv { get; set; } = string.Empty;

        /// <summary>週末範囲: From。</summary>
        public DateTime WeekendFromDate { get; set; }

        /// <summary>週末範囲: To。</summary>
        public DateTime WeekendToDate { get; set; }

        /// <summary>週末対象場: CSV。</summary>
        public string WeekendJyoCdsCsv { get; set; } = string.Empty;

        /// <summary>払戻を含める。</summary>
        public bool IncludePayout { get; set; }

        /// <summary>血統は週末出走馬のみを含める。</summary>
        public bool IncludePedigreeWeekendOnly { get; set; }
    }
}

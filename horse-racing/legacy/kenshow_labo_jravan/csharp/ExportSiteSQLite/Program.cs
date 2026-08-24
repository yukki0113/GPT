using System;
using System.IO;
using System.Text;
using Microsoft.Extensions.Configuration;
using KenshowLabo.Tools.Config;

namespace ExportSiteSQLite
{
    internal static class Program
    {
        /// <summary>
        /// エントリポイント。
        /// </summary>
        public static int Main(string[] args)
        {

            // ============================================
            // 1) 設定読込（appsettings.json / appsettings.local.json）
            // ============================================
            IConfigurationRoot config = AppConfigLoader.Load();

            // ============================================
            // 2) 設定値の取得（必須/任意）
            // ============================================
            string connectionString = AppConfigLoader.GetSqlServerConnectionString(config);

            string outputDirFromConfig = AppConfigLoader.GetRequiredString(config, "ExportSiteSQLite:OutputDir");
            string fileNameFromConfig = AppConfigLoader.GetRequiredString(config, "ExportSiteSQLite:SnapshotFileName");

            DateTime historyFrom = GetRequiredDate(config, "ExportSiteSQLite:History:FromDate");
            DateTime historyTo = GetRequiredDate(config, "ExportSiteSQLite:History:ToDate");
            string historyJyoCds = AppConfigLoader.GetRequiredString(config, "ExportSiteSQLite:History:JyoCdsCsv");

            DateTime weekendFrom = GetRequiredDate(config, "ExportSiteSQLite:Weekend:FromDate");
            DateTime weekendTo = GetRequiredDate(config, "ExportSiteSQLite:Weekend:ToDate");
            string weekendJyoCds = AppConfigLoader.GetRequiredString(config, "ExportSiteSQLite:Weekend:JyoCdsCsv");

            bool includePayout = GetBool(config, "ExportSiteSQLite:IncludePayout", true);
            bool includePedigreeWeekendOnly = GetBool(config, "ExportSiteSQLite:IncludePedigreeWeekendOnly", true);

            // ============================================
            // 3) 引数で上書き（任意）※まずは未実装でもOK
            // ============================================
            ProgramOptions options = new ProgramOptions();
            options.ConnectionString = connectionString;
            options.OutputDir = outputDirFromConfig;
            options.SnapshotFileName = fileNameFromConfig;

            options.HistoryFromDate = historyFrom;
            options.HistoryToDate = historyTo;
            options.HistoryJyoCdsCsv = historyJyoCds;

            options.WeekendFromDate = weekendFrom;
            options.WeekendToDate = weekendTo;
            options.WeekendJyoCdsCsv = weekendJyoCds;

            options.IncludePayout = includePayout;
            options.IncludePedigreeWeekendOnly = includePedigreeWeekendOnly;

            // ============================================
            // 4) OutputDir の正規化（相対パスは実行フォルダ基準にする）
            // ============================================
            string normalizedOutputDir = NormalizePath(options.OutputDir, AppContext.BaseDirectory);
            options.OutputDir = normalizedOutputDir;

            Directory.CreateDirectory(options.OutputDir);

            // ============================================
            // 5) 固有処理
            // ============================================
            try
            {
                ExportSqliteRunner runner = new ExportSqliteRunner();
                runner.Run(options);

                Console.WriteLine("Export completed.");
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.ToString());
                return 1;
            }
        }

        /// <summary>
        /// bool 設定を取得する（無ければ defaultValue）。
        /// </summary>
        private static bool GetBool(IConfigurationRoot config, string key, bool defaultValue)
        {
            string? raw = config[key];
            if (string.IsNullOrEmpty(raw))
            {
                return defaultValue;
            }

            bool parsed;
            if (bool.TryParse(raw, out parsed))
            {
                return parsed;
            }

            return defaultValue;
        }

        /// <summary>
        /// 必須Dateを取得する。
        /// </summary>
        private static DateTime GetRequiredDate(IConfigurationRoot config, string key)
        {
            string value = AppConfigLoader.GetRequiredString(config, key);

            DateTime dt;
            if (!DateTime.TryParse(value, out dt))
            {
                throw new InvalidOperationException("Date parse failed. key=" + key + " value=" + value);
            }

            return dt.Date;
        }

        /// <summary>
        /// パスを正規化する（相対パスは baseDir 基準）。
        /// </summary>
        private static string NormalizePath(string path, string baseDir)
        {
            if (Path.IsPathRooted(path))
            {
                return Path.GetFullPath(path);
            }

            string combined = Path.Combine(baseDir, path);
            return Path.GetFullPath(combined);
        }
    }
}

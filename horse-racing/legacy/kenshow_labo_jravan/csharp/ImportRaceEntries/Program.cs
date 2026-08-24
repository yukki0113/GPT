using ImportRaceEntries.Netkeiba;
using ImportRaceEntries.Netkeiba.Models;
using KenshowLabo.Tools.Config;
using Microsoft.Extensions.Configuration;
using System.Text;

namespace ImportRaceEntries {
    /// <summary>
    /// netkeiba出馬表HTMLを解析し、IFテーブルへ投入するコンソールアプリのエントリポイントです。
    /// </summary>
    internal static class Program {
        /// <summary>
        /// アプリケーションのメイン処理です。
        /// </summary>
        /// <remarks>
        /// 基本は appsettings(.local).json から設定を取得します。
        /// ただし引数が指定された場合は、引数で上書きします。
        ///
        /// 引数（任意）:
        ///   --htmlDir "C:\path"
        ///   --applyToTr
        /// </remarks>
        public static int Main(string[] args) {
            // 文字コード混在に備えて、Shift-JIS 等のコードページを許可します。
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

            // ============================================
            // 1) 設定読込（appsettings.json / appsettings.local.json）
            // ============================================
            IConfigurationRoot config = AppConfigLoader.Load();

            // ============================================
            // 2) 設定値の取得（必須/任意）
            // ============================================
            string connectionString = AppConfigLoader.GetSqlServerConnectionString(config);

            string htmlDirFromConfig = AppConfigLoader.GetRequiredString(config, "ImportRaceEntries:HtmlDir");
            bool applyToTrFromConfig = GetBool(config, "ImportRaceEntries:ApplyToTr", false);

            bool cleanupEnabled = GetBool(config, "ImportRaceEntries:IfCleanup:Enabled", false);
            int keepDays = GetInt(config, "ImportRaceEntries:IfCleanup:KeepDays", 21);

            // ============================================
            // 3) 引数で上書き（任意）
            // ============================================
            ProgramOptions options = new ProgramOptions();
            options.HtmlDir = htmlDirFromConfig;
            options.ConnectionString = connectionString;
            options.ApplyToTr = applyToTrFromConfig;

            bool argsOk = TryApplyArgs(args, options);
            if (!argsOk) {
                PrintUsage();
                return 1;
            }

            // ============================================
            // 4) HtmlDir の正規化（相対パスは実行フォルダ基準にする）
            // ============================================
            string normalizedHtmlDir = NormalizePath(options.HtmlDir, AppContext.BaseDirectory);
            options.HtmlDir = normalizedHtmlDir;

            if (!Directory.Exists(options.HtmlDir)) {
                LogError("HTMLフォルダが存在しません: " + options.HtmlDir);
                return 1;
            }

            // ============================================
            // 5) 依存コンポーネント
            // ============================================
            NetkeibaRaceEntryHtmlParser parser = new NetkeibaRaceEntryHtmlParser();
            HorseIdResolver horseIdResolver = new HorseIdResolver(options.ConnectionString);
            IfNetkeibaRepository ifRepo = new IfNetkeibaRepository(options.ConnectionString);

            // ============================================
            // 5.5) IFテーブルの過去分掃除（任意）
            // ============================================
            if (cleanupEnabled) {
                // KeepDays より古いデータを削除（正規化できていない残骸は scraped_at で落とす）
                DateTime cutoffDate = DateTime.Today.AddDays(-keepDays);
                DateTime cutoffScrapedAt = DateTime.Now.AddDays(-keepDays);

                int deleted = ifRepo.CleanupOldIfData(cutoffDate, cutoffScrapedAt);
                LogInfo("[CLEANUP] IF old rows deleted: " + deleted + " (keepDays=" + keepDays + ")");
            }

            // ============================================
            // 6) HTMLファイル列挙（Fetch有効なら先に取得）
            // ============================================
            bool fetchEnabled = GetBool(config, "ImportRaceEntries:Fetch:Enabled", false);

            string[] files;

            if (fetchEnabled) {
                NetkeibaHtmlFetcher fetcher = new NetkeibaHtmlFetcher(options.HtmlDir);
                NetkeibaFetchSettings fetchSettings = NetkeibaFetchSettings.FromConfig(config);

                string[] downloaded = fetcher.FetchAndSave(fetchSettings);

                // 取得できた分だけ処理（0件ならフォールバックでローカルの*.htmlを処理）
                if (downloaded.Length > 0) {
                    files = downloaded;
                    LogInfo("[FETCH] downloaded html files=" + downloaded.Length);
                }
                else {
                    files = Directory.GetFiles(options.HtmlDir, "*.html", SearchOption.TopDirectoryOnly);
                    LogInfo("[FETCH] no new files. fallback to local files count=" + files.Length);
                }
            }
            else {
                files = Directory.GetFiles(options.HtmlDir, "*.html", SearchOption.TopDirectoryOnly);
            }

            if (files.Length == 0) {
                LogInfo("HTMLファイルが見つかりません: " + options.HtmlDir);
                return 0;
            }
            int okCount = 0;
            int skipCount = 0;
            int errorCount = 0;

            // ============================================
            // 7) ファイル単位で処理
            // ============================================
            foreach (string filePath in files) {
                string fileName = Path.GetFileName(filePath);

                try {
                    // --------------------------------------------
                    // 7-1) HTML読み込み（BOM / meta charset を可能な範囲で考慮）
                    // --------------------------------------------
                    string html = ReadHtmlWithAutoEncoding(filePath);

                    // --------------------------------------------
                    // 7-2) importBatchId / scrapedAt
                    // --------------------------------------------
                    Guid importBatchId = Guid.NewGuid();
                    DateTime scrapedAt = File.GetLastWriteTime(filePath);

                    // --------------------------------------------
                    // 7-3) 解析（出馬表以外はスキップ）
                    // --------------------------------------------
                    NetkeibaRaceHeaderRaw header;
                    List<NetkeibaRaceEntryRowRaw> rows;

                    bool isEntry = parser.TryParse(
                        html,
                        importBatchId,
                        scrapedAt,
                        fileName,
                        out header,
                        out rows
                    );

                    if (!isEntry) {
                        skipCount++;
                        LogInfo("[SKIP] " + parser.LastError + " file=" + fileName);
                        continue;
                    }

                    // --------------------------------------------
                    // 7-4) 馬ID解決（バッチ）
                    // --------------------------------------------
                    List<string> warnings = horseIdResolver.ResolveForRows(rows);
                    foreach (string w in warnings) {
                        LogWarn("[WARN] " + w + " (file=" + fileName + ", race_id=" + header.RaceId + ")");
                    }

                    // --------------------------------------------
                    // 7-5) IF投入（Header + Rows）
                    // --------------------------------------------
                    ifRepo.InsertIf(header, rows);

                    // --------------------------------------------
                    // 7-6) 必要なら IF→TR 展開
                    // --------------------------------------------
                    if (options.ApplyToTr) {
                        ifRepo.ApplyToTr(header.ImportBatchId);
                    }

                    okCount++;
                    LogInfo("[OK] inserted IF: race_id=" + header.RaceId + " rows=" + rows.Count + " file=" + fileName);
                }
                catch (Exception ex) {
                    errorCount++;
                    LogError("[ERROR] file=" + fileName);
                    LogError(ex.ToString());
                }
            }

            // ============================================
            // 8) サマリ
            // ============================================
            LogInfo("Done. ok=" + okCount + " skip=" + skipCount + " error=" + errorCount);

            if (errorCount > 0) {
                return 2;
            }

            return 0;
        }

        /// <summary>
        /// 引数を options に適用します（指定されたものだけ上書き）。
        /// </summary>
        private static bool TryApplyArgs(string[] args, ProgramOptions options) {
            if (args == null || args.Length == 0) {
                // 引数無しはOK（設定ファイル運用）
                return true;
            }

            int i = 0;
            while (i < args.Length) {
                string a = args[i];

                if (string.Equals(a, "--htmlDir", StringComparison.OrdinalIgnoreCase)) {
                    if (i + 1 >= args.Length) {
                        return false;
                    }

                    options.HtmlDir = args[i + 1];
                    i += 2;
                    continue;
                }

                if (string.Equals(a, "--applyToTr", StringComparison.OrdinalIgnoreCase)) {
                    options.ApplyToTr = true;
                    i += 1;
                    continue;
                }

                // 未知引数はエラー
                return false;
            }

            return true;
        }

        /// <summary>
        /// bool設定を取得します（未定義/不正値は defaultValue）。
        /// </summary>
        private static bool GetBool(IConfiguration config, string key, bool defaultValue) {
            string? s = config[key];

            if (string.IsNullOrWhiteSpace(s)) {
                return defaultValue;
            }

            bool parsed;
            parsed = bool.TryParse(s, out bool b);

            if (!parsed) {
                return defaultValue;
            }

            return b;
        }

        /// <summary>
        /// Int設定を取得します（未定義/不正値は defaultValue）。
        /// </summary>
        private static int GetInt(IConfiguration config, string key, int defaultValue) {
            string? s = config[key];

            if (string.IsNullOrWhiteSpace(s)) {
                return defaultValue;
            }

            bool parsed;
            parsed = int.TryParse(s, out int i);

            if (!parsed) {
                return defaultValue;
            }

            return i;
        }

        /// <summary>
        /// 相対パスは baseDir 基準で絶対パスにします。
        /// </summary>
        private static string NormalizePath(string path, string baseDir) {
            if (string.IsNullOrWhiteSpace(path)) {
                return path;
            }

            if (Path.IsPathRooted(path)) {
                return path;
            }

            return Path.GetFullPath(Path.Combine(baseDir, path));
        }

        /// <summary>
        /// HTMLを読み込みます（BOM / meta charset を可能な範囲で考慮）。
        /// </summary>
        private static string ReadHtmlWithAutoEncoding(string filePath) {
            byte[] bytes = File.ReadAllBytes(filePath);

            Encoding? bomEnc = DetectBomEncoding(bytes);
            if (bomEnc != null) {
                return bomEnc.GetString(bytes);
            }

            Encoding? metaEnc = DetectMetaCharsetEncoding(bytes);
            if (metaEnc != null) {
                return metaEnc.GetString(bytes);
            }

            return Encoding.UTF8.GetString(bytes);
        }

        /// <summary>
        /// BOMからエンコーディングを推定します。見つからない場合は null を返します。
        /// </summary>
        private static Encoding? DetectBomEncoding(byte[] bytes) {
            if (bytes.Length >= 3) {
                if (bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF) {
                    return Encoding.UTF8;
                }
            }

            if (bytes.Length >= 2) {
                if (bytes[0] == 0xFF && bytes[1] == 0xFE) {
                    return Encoding.Unicode;
                }

                if (bytes[0] == 0xFE && bytes[1] == 0xFF) {
                    return Encoding.BigEndianUnicode;
                }
            }

            return null;
        }

        /// <summary>
        /// meta charset を探してエンコーディングを推定します。見つからない場合は null を返します。
        /// </summary>
        private static Encoding? DetectMetaCharsetEncoding(byte[] bytes) {
            int take = bytes.Length;
            if (take > 8192) {
                take = 8192;
            }

            string head = Encoding.ASCII.GetString(bytes, 0, take);

            int idx = head.IndexOf("charset=", StringComparison.OrdinalIgnoreCase);
            if (idx < 0) {
                idx = head.IndexOf("charset=\"", StringComparison.OrdinalIgnoreCase);
                if (idx < 0) {
                    return null;
                }
            }

            int start = idx + "charset=".Length;
            if (start >= head.Length) {
                return null;
            }

            if (head[start] == '"' || head[start] == '\'') {
                start++;
            }

            int end = start;
            while (end < head.Length) {
                char c = head[end];
                if (c == '"' || c == '\'' || c == ' ' || c == ';' || c == '>' || c == '\r' || c == '\n' || c == '\t') {
                    break;
                }
                end++;
            }

            if (end <= start) {
                return null;
            }

            string charset = head.Substring(start, end - start).Trim();
            if (string.IsNullOrWhiteSpace(charset)) {
                return null;
            }

            string normalized = charset;
            if (string.Equals(normalized, "shift-jis", StringComparison.OrdinalIgnoreCase)) {
                normalized = "shift_jis";
            }

            try {
                return Encoding.GetEncoding(normalized);
            }
            catch {
                return null;
            }
        }

        /// <summary>
        /// 使用方法を表示します。
        /// </summary>
        private static void PrintUsage() {
            Console.WriteLine("Usage:");
            Console.WriteLine("  ImportRaceEntries.exe [--htmlDir <dir>] [--applyToTr]");
            Console.WriteLine("Note: 기본은 appsettings(.local).json から読みます。");
        }

        /// <summary>
        /// 情報ログを出力します。
        /// </summary>
        private static void LogInfo(string message) {
            Console.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " [INFO] " + message);
        }

        /// <summary>
        /// 警告ログを出力します。
        /// </summary>
        private static void LogWarn(string message) {
            Console.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " [WARN] " + message);
        }

        /// <summary>
        /// エラーログを出力します。
        /// </summary>
        private static void LogError(string message) {
            Console.Error.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " [ERROR] " + message);
        }

        /// <summary>
        /// 実行オプションです。
        /// </summary>
        private sealed class ProgramOptions {
            public string HtmlDir { get; set; } = string.Empty;
            public string ConnectionString { get; set; } = string.Empty;
            public bool ApplyToTr { get; set; }
        }
    }
}

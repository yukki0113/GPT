using Microsoft.Extensions.Configuration;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace ImportRaceEntries.Netkeiba {
    /// <summary>
    /// netkeiba から出馬表HTMLを自動取得して、race_id.html で保存します。
    /// </summary>
    public sealed class NetkeibaHtmlFetcher {
        private readonly string _outputDir;

        public NetkeibaHtmlFetcher(string outputDir) {
            _outputDir = outputDir;
        }

        /// <summary>
        /// 設定に従って開催日を決め、race_id一覧を収集し、出馬表HTMLを保存します。
        /// 返り値は「今回保存（上書き含む）したファイルパス一覧」です。
        /// </summary>
        public string[] FetchAndSave(NetkeibaFetchSettings settings) {
            // 保存先を保証
            Directory.CreateDirectory(_outputDir);

            // 対象日付を決定
            List<DateTime> dates = ResolveTargetDates(settings);

            // 取得結果
            List<string> savedFiles = new List<string>();

            using (HttpClient client = CreateHttpClient()) {
                foreach (DateTime date in dates) {
                    // 1) レース一覧から race_id を抽出
                    List<string> raceIds = FetchRaceIdsForDate(client, date, settings.SleepMs);

                    // 2) race_id ごとに出馬表HTMLを保存
                    foreach (string raceId in raceIds) {
                        string filePath = Path.Combine(_outputDir, raceId + ".html");

                        // 上書きしない運用も可能（ただ、確定前→確定後を想定するなら上書き推奨）
                        if (!settings.Overwrite && File.Exists(filePath)) {
                            continue;
                        }

                        byte[] htmlBytes = FetchShutubaHtmlBytes(client, raceId, settings.SleepMs);

                        // そのままバイトで保存（文字コード判定は既存パーサに委ねる）
                        File.WriteAllBytes(filePath, htmlBytes);

                        savedFiles.Add(filePath);
                    }
                }
            }

            return savedFiles.ToArray();
        }

        /// <summary>
        /// 開催日(kaisai_date)のレース一覧から race_id を抽出します。
        /// </summary>
        private static List<string> FetchRaceIdsForDate(HttpClient client, DateTime date, int sleepMs) {
            string ymd = date.ToString("yyyyMMdd");

            // レース一覧（断片HTML）からrace_idリンクを拾う
            // 例: https://race.netkeiba.com/top/race_list_sub.html?kaisai_date=YYYYMMDD
            string url = "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date=" + ymd;

            string html = GetStringWithSleep(client, url, sleepMs);

            // href内の race_id=12桁 を拾う（重複は除外）
            Regex rx = new Regex(@"race_id=(\d{12})", RegexOptions.Compiled);
            MatchCollection matches = rx.Matches(html);

            HashSet<string> set = new HashSet<string>();

            foreach (Match m in matches) {
                if (m.Success && m.Groups.Count >= 2) {
                    string id = m.Groups[1].Value;
                    set.Add(id);
                }
            }

            List<string> list = new List<string>(set);
            list.Sort(StringComparer.Ordinal);
            return list;
        }

        /// <summary>
        /// 出馬表ページのHTMLをバイトで取得します。
        /// </summary>
        private static byte[] FetchShutubaHtmlBytes(HttpClient client, string raceId, int sleepMs) {
            // 出馬表
            string url = "https://race.netkeiba.com/race/shutuba.html?race_id=" + raceId;

            // Sleepしつつ取得
            Sleep(sleepMs, 20);
            byte[] bytes = client.GetByteArrayAsync(url).GetAwaiter().GetResult();
            return bytes;
        }

        /// <summary>
        /// GETして文字列として返します（取得前にSleep）。
        /// </summary>
        private static string GetStringWithSleep(HttpClient client, string url, int sleepMs) {
            Sleep(sleepMs, 20);

            byte[] bytes = client.GetByteArrayAsync(url).GetAwaiter().GetResult();

            // 一覧断片はUTF-8で返ることが多いため、まずはUTF-8で読む（ダメなら置換されるだけ）
            // ※ここは必要なら自動判定に拡張可能
            string html = Encoding.UTF8.GetString(bytes);
            return html;
        }

        /// <summary>
        /// HttpClient を作成します（最低限のヘッダを付与）。
        /// </summary>
        private static HttpClient CreateHttpClient() {
            HttpClientHandler handler = new HttpClientHandler();
            HttpClient client = new HttpClient(handler);

            // サイト側で弾かれにくいよう、最低限のUAを入れる（過度な偽装はしない）
            client.DefaultRequestHeaders.UserAgent.ParseAdd("KenshowLabo.Tools/1.0");

            return client;
        }

        /// <summary>
        /// 対象日付を決定します。
        /// </summary>
        private static List<DateTime> ResolveTargetDates(NetkeibaFetchSettings settings) {
            List<DateTime> list = new List<DateTime>();

            // 明示TargetDatesがあれば優先
            if (settings.TargetDates != null && settings.TargetDates.Count > 0) {
                foreach (DateTime d in settings.TargetDates) {
                    list.Add(d.Date);
                }

                return list;
            }

            // AutoWeekend：次の土日
            if (string.Equals(settings.Mode, "AutoWeekend", StringComparison.OrdinalIgnoreCase)) {
                DateTime today = DateTime.Today;
                int daysToSat = ((int)DayOfWeek.Saturday - (int)today.DayOfWeek + 7) % 7;
                DateTime sat = today.AddDays(daysToSat);
                DateTime sun = sat.AddDays(1);

                list.Add(sat);
                list.Add(sun);

                return list;
            }

            // デフォルト：当日
            list.Add(DateTime.Today);
            return list;
        }

        private static void Sleep(int sleepMs, int jitterPercent) {
            // 0以下なら何もしない
            if (sleepMs <= 0) {
                return;
            }

            // jitterPercent を安全な範囲に丸める（0～100）
            int safeJitterPercent = jitterPercent;
            if (safeJitterPercent < 0) {
                safeJitterPercent = 0;
            }
            if (safeJitterPercent > 100) {
                safeJitterPercent = 100;
            }

            // ジッター無しなら固定sleep
            if (safeJitterPercent == 0) {
                Thread.Sleep(sleepMs);
                return;
            }

            // 例：base=1200ms, jitter=20% -> min=960, max=1440
            int minMs = (int)Math.Round(sleepMs * (100.0 - safeJitterPercent) / 100.0);
            int maxMs = (int)Math.Round(sleepMs * (100.0 + safeJitterPercent) / 100.0);

            // 念のため下限・上限の破綻を防ぐ
            if (minMs < 0) {
                minMs = 0;
            }
            if (maxMs < minMs) {
                maxMs = minMs;
            }

            // GetInt32 は上限が「未満」なので +1 して含める
            int actualMs = RandomNumberGenerator.GetInt32(minMs, maxMs + 1);

            Thread.Sleep(actualMs);
        }
    }

    /// <summary>
    /// 取得設定です。
    /// </summary>
    public sealed class NetkeibaFetchSettings {
        public bool Enabled { get; set; }
        public string Mode { get; set; }
        public List<DateTime>? TargetDates { get; set; }
        public int SleepMs { get; set; }
        public bool Overwrite { get; set; }

        public NetkeibaFetchSettings() {
            Enabled = false;
            Mode = "AutoWeekend";
            TargetDates = new List<DateTime>();
            SleepMs = 1200;
            Overwrite = true;
        }

        /// <summary>
        /// IConfiguration から設定を読み取ります。
        /// </summary>
        public static NetkeibaFetchSettings FromConfig(IConfiguration config) {
            NetkeibaFetchSettings s = new NetkeibaFetchSettings();

            s.Enabled = GetBool(config, "ImportRaceEntries:Fetch:Enabled", false);
            s.Mode = GetString(config, "ImportRaceEntries:Fetch:Mode", "AutoWeekend");
            s.SleepMs = GetInt(config, "ImportRaceEntries:Fetch:SleepMs", 1200);
            s.Overwrite = GetBool(config, "ImportRaceEntries:Fetch:Overwrite", true);

            // TargetDates（YYYYMMDD配列）
            List<DateTime> dates = new List<DateTime>();

            IConfigurationSection sec = config.GetSection("ImportRaceEntries:Fetch:TargetDates");
            foreach (IConfigurationSection child in sec.GetChildren()) {
                string? v = child.Value;
                DateTime d;

                if (!string.IsNullOrWhiteSpace(v) && DateTime.TryParseExact(v, "yyyyMMdd", null, System.Globalization.DateTimeStyles.None, out d)) {
                    dates.Add(d.Date);
                }
            }

            s.TargetDates = dates;

            return s;
        }

        private static bool GetBool(IConfiguration config, string key, bool defaultValue) {
            string? value = config[key];
            bool parsed;

            if (string.IsNullOrWhiteSpace(value)) {
                return defaultValue;
            }

            if (!bool.TryParse(value, out parsed)) {
                return defaultValue;
            }

            return parsed;
        }

        private static int GetInt(IConfiguration config, string key, int defaultValue) {
            string? value = config[key];
            int parsed;

            if (string.IsNullOrWhiteSpace(value)) {
                return defaultValue;
            }

            if (!int.TryParse(value, out parsed)) {
                return defaultValue;
            }

            return parsed;
        }

        private static string GetString(IConfiguration config, string key, string defaultValue) {
            string? value = config[key];

            if (string.IsNullOrWhiteSpace(value)) {
                return defaultValue;
            }

            return value;
        }
    }
}
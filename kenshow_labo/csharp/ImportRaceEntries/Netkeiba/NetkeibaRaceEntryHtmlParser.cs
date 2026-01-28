using HtmlAgilityPack;
using ImportRaceEntries.Netkeiba.Models;
using System.Text.RegularExpressions;

namespace ImportRaceEntries.Netkeiba {
    /// <summary>
    /// netkeiba 出馬表HTML（手動保存）を解析します。
    /// テーブルの class 名ではなく「見出し文字」で出馬表テーブルを特定します。
    /// </summary>
    public sealed class NetkeibaRaceEntryHtmlParser {
        /// <summary>
        /// 直近の失敗理由（TryParseがfalseのとき参照）。
        /// </summary>
        public string LastError { get; private set; } = string.Empty;

        /// <summary>
        /// 出馬表HTMLを解析します。出馬表でない場合、または解析に失敗した場合は false を返します。
        /// </summary>
        public bool TryParse(
            string html,
            Guid importBatchId,
            DateTime scrapedAt,
            string sourceFile,
            out NetkeibaRaceHeaderRaw header,
            out List<NetkeibaRaceEntryRowRaw> rows) {
            // out初期化
            header = new NetkeibaRaceHeaderRaw();
            rows = new List<NetkeibaRaceEntryRowRaw>();
            LastError = string.Empty;

            // 入力チェック
            if (string.IsNullOrWhiteSpace(html)) {
                LastError = "html is empty.";
                return false;
            }

            // HTMLロード
            HtmlDocument doc = new HtmlDocument();
            doc.LoadHtml(html);

            // 1) 出馬表テーブルを特定（見出し判定）
            HtmlNode? table = FindEntryTable(doc);
            if (table == null) {
                LastError = "entry table not found (header-based detection failed).";
                return false;
            }

            // 2) race_id を取得（canonical / og:url / 本文から推定）
            string? raceId = TryExtractRaceId(doc, sourceFile);
            if (string.IsNullOrWhiteSpace(raceId)) {
                LastError = "race_id not found.";
                return false;
            }

            // 3) ヘッダ行（列マッピング）を作る
            Dictionary<string, int> col = BuildColumnIndexMap(table);
            if (!col.ContainsKey("馬名")) {
                // 見出し判定で拾っているので通常あり得ないが、防御
                LastError = "column '馬名' not found.";
                return false;
            }

            // 4) レースヘッダ（最低限）
            NetkeibaRaceHeaderRaw h = new NetkeibaRaceHeaderRaw();
            h.ImportBatchId = importBatchId;
            h.RaceId = raceId;
            h.ScrapedAt = scrapedAt;
            h.SourceFile = sourceFile;
            h.SourceUrl = TryExtractSourceUrl(doc);

            RaceExtraRaw x = ExtractRaceExtras(doc);

            h.MeetingRaw = x.MeetingRaw;
            h.TurnRaw = x.TurnRaw;
            h.RaceClassRaw = x.RaceClassRaw;
            h.HeadCountRaw = x.HeadCountRaw;

            h.StartTimeRaw = x.StartTimeRaw;
            h.TurnDirRaw = x.TurnDirRaw;
            h.CourseRingRaw = x.CourseRingRaw;
            h.CourseExRaw = x.CourseExRaw;
            h.CourseDetailRaw = x.CourseDetailRaw;

            h.SurfaceTypeRaw = x.SurfaceTypeRaw;
            h.DistanceMRaw = x.DistanceMRaw;

            // ★ヘッダは og:title / title を最優先にする（ここが最重要）
            ApplyHeaderFromTitle(doc, h);

            // ★距離（芝/ダ＋距離m）は RaceData01 を最優先にする
            h.SurfaceDistanceRaw = ExtractSurfaceDistanceRaw(doc);

            // ★フォールバック（titleから取れなかった場合のみ）
            if (string.IsNullOrWhiteSpace(h.RaceNameRaw)) {
                h.RaceNameRaw = TryExtractRaceName(doc) ?? string.Empty;
            }

            if (string.IsNullOrWhiteSpace(h.RaceNoRaw)) {
                // race_id末尾2桁（11Rなら "11"）を文字列化
                if (!string.IsNullOrWhiteSpace(raceId) && raceId.Length == 12) {
                    h.RaceNoRaw = int.Parse(raceId.Substring(10, 2)).ToString();
                }
                else {
                    h.RaceNoRaw = string.Empty;
                }
            }

            if (string.IsNullOrWhiteSpace(h.RaceDateRaw)) {
                h.RaceDateRaw = TryExtractRaceDateRaw(doc) ?? string.Empty;
            }

            if (string.IsNullOrWhiteSpace(h.TrackNameRaw)) {
                // titleから取れない場合の補助（今は空実装なら race_id からでもOK）
                h.TrackNameRaw = TryExtractTrackNameRaw(doc) ?? string.Empty;
            }

            // 5) 明細行を読む
            List<HtmlNode> trList = table.SelectNodes(".//tr")?.ToList() ?? new List<HtmlNode>();
            if (trList.Count == 0) {
                LastError = "entry table has no rows.";
                return false;
            }

            int rowNo = 0;

            foreach (HtmlNode tr in trList) {
                // 見出し行は th を含むことが多いので除外
                List<HtmlNode> tds = tr.SelectNodes("./td")?.ToList() ?? new List<HtmlNode>();
                if (tds.Count == 0) {
                    continue;
                }

                // 「馬名」列を取れない行は除外（広告/注記/空行対策）
                HtmlNode? horseNameTd = GetTd(tds, col, "馬名");
                if (horseNameTd == null) {
                    continue;
                }

                string horseName = NormalizeText(horseNameTd.InnerText);
                if (string.IsNullOrWhiteSpace(horseName)) {
                    continue;
                }

                string? nkHorseId = TryExtractNkHorseIdFromHorseCell(horseNameTd);

                NetkeibaRaceEntryRowRaw r = new NetkeibaRaceEntryRowRaw();
                r.ImportBatchId = importBatchId;
                r.RowNo = rowNo + 1;

                // raw列（DB側で型変換する前提）
                r.HorseNameRaw = horseName;
                r.NkHorseId = nkHorseId;
                r.JvHorseId = null;

                r.FrameNoRaw = NormalizeText(GetTdText(tds, col, "枠"));
                r.HorseNoRaw = NormalizeText(GetTdText(tds, col, "馬番"));
                r.SexAgeRaw = NormalizeText(GetTdText(tds, col, "性齢"));
                r.JockeyNameRaw = NormalizeText(GetTdText(tds, col, "騎手"));
                r.CarriedWeightRaw = NormalizeText(GetTdText(tds, col, "斤量"));

                rows.Add(r);
                rowNo++;
            }

            if (rows.Count == 0) {
                LastError = "entry rows parsed = 0 (table found but no horse rows). "
                          + "Possible causes: page not fully loaded when saved / structure changed.";
                return false;
            }

            header = h;
            return true;
        }

        /// <summary>
        /// 出馬表テーブルを「見出し」で探します。
        /// </summary>
        private static HtmlNode? FindEntryTable(HtmlDocument doc) {
            List<HtmlNode> tables = doc.DocumentNode.SelectNodes("//table")?.ToList() ?? new List<HtmlNode>();

            foreach (HtmlNode t in tables) {
                List<string> headers = ExtractHeaderTexts(t);

                // 出馬表として必要な見出し
                bool hasHorse = headers.Any(x => x.Contains("馬名"));
                bool hasSexAge = headers.Any(x => x.Contains("性齢") || x.Contains("性令"));
                bool hasJockey = headers.Any(x => x.Contains("騎手"));
                bool hasWeight = headers.Any(x => x.Contains("斤量"));

                // 結果ページの「着順」テーブルを誤検出しないための簡易フィルタ
                bool hasFinish = headers.Any(x => x.Contains("着順"));

                if (hasHorse && hasSexAge && hasJockey && hasWeight && !hasFinish) {
                    return t;
                }
            }

            return null;
        }

        /// <summary>
        /// テーブルの見出し（th）を抽出します。
        /// </summary>
        private static List<string> ExtractHeaderTexts(HtmlNode table) {
            List<string> list = new List<string>();

            HtmlNode? headerRow = table.SelectSingleNode(".//tr[.//th]");
            if (headerRow == null) {
                return list;
            }

            List<HtmlNode> ths = headerRow.SelectNodes("./th")?.ToList() ?? new List<HtmlNode>();
            foreach (HtmlNode th in ths) {
                string text = NormalizeText(th.InnerText);
                if (!string.IsNullOrWhiteSpace(text)) {
                    list.Add(text);
                }
            }

            return list;
        }

        /// <summary>
        /// 見出し→列Indexマップを作成します。
        /// </summary>
        private static Dictionary<string, int> BuildColumnIndexMap(HtmlNode table) {
            Dictionary<string, int> map = new Dictionary<string, int>(StringComparer.Ordinal);

            HtmlNode? headerRow = table.SelectSingleNode(".//tr[.//th]");
            if (headerRow == null) {
                return map;
            }

            List<HtmlNode> ths = headerRow.SelectNodes("./th")?.ToList() ?? new List<HtmlNode>();

            for (int i = 0; i < ths.Count; i++) {
                string text = NormalizeText(ths[i].InnerText);

                // よく使う見出しを正規化してキーにする
                if (text.Contains("枠")) {
                    map["枠"] = i;
                }
                else if (text.Contains("馬番")) {
                    map["馬番"] = i;
                }
                else if (text.Contains("馬名")) {
                    map["馬名"] = i;
                }
                else if (text.Contains("性齢") || text.Contains("性令")) {
                    map["性齢"] = i;
                }
                else if (text.Contains("騎手")) {
                    map["騎手"] = i;
                }
                else if (text.Contains("斤量")) {
                    map["斤量"] = i;
                }
            }

            return map;
        }

        private static HtmlNode? GetTd(List<HtmlNode> tds, Dictionary<string, int> map, string key) {
            if (!map.TryGetValue(key, out int idx)) {
                return null;
            }

            if (idx < 0 || idx >= tds.Count) {
                return null;
            }

            return tds[idx];
        }

        private static string GetTdText(List<HtmlNode> tds, Dictionary<string, int> map, string key) {
            HtmlNode? td = GetTd(tds, map, key);
            if (td == null) {
                return string.Empty;
            }

            return td.InnerText;
        }

        private static string NormalizeText(string? s) {
            if (string.IsNullOrWhiteSpace(s)) {
                return string.Empty;
            }

            // 全角スペースや改行を潰して整形
            string t = s.Replace("\u3000", " ");
            t = Regex.Replace(t, @"\s+", " ");
            return t.Trim();
        }

        private static string? TryExtractNkHorseIdFromHorseCell(HtmlNode horseNameTd) {
            // /horse/XXXX/ のリンクを探す
            HtmlNode? a = horseNameTd.SelectSingleNode(".//a[contains(@href,'/horse/')]");
            if (a == null) {
                return null;
            }

            string href = a.GetAttributeValue("href", string.Empty);
            Match m = Regex.Match(href, @"/horse/(\d+)");
            if (!m.Success) {
                return null;
            }

            return m.Groups[1].Value;
        }

        private static string? TryExtractRaceId(HtmlDocument doc, string sourceFile) {
            // 1) canonical / og:url
            string? url = TryExtractSourceUrl(doc);
            if (!string.IsNullOrWhiteSpace(url)) {
                // /race/123456789012
                Match m1 = Regex.Match(url, @"/race/(\d{12})");
                if (m1.Success) {
                    return m1.Groups[1].Value;
                }

                // shutuba.html?race_id=123456789012
                Match m2 = Regex.Match(url, @"[?&]race_id=(\d{12})");
                if (m2.Success) {
                    return m2.Groups[1].Value;
                }
            }

            // 2) HTML全体から拾う（URLが埋まっている・JS変数・リンク等）
            string allHtml = doc.DocumentNode.InnerHtml;

            // shutuba.html?race_id=...
            Match m3 = Regex.Match(allHtml, @"[?&]race_id=(\d{12})");
            if (m3.Success) {
                return m3.Groups[1].Value;
            }

            // /race/123456789012
            Match m4 = Regex.Match(allHtml, @"/race/(\d{12})");
            if (m4.Success) {
                return m4.Groups[1].Value;
            }

            // "race_id":"123456789012" や race_id = "123..."
            Match m5 = Regex.Match(allHtml, @"race[_\-]?id[""']?\s*[:=]\s*[""'](\d{12})[""']");
            if (m5.Success) {
                return m5.Groups[1].Value;
            }

            // 3) 最後の保険：ファイル名から組み立て
            string? fallback = TryBuildRaceIdFromFileName(sourceFile);
            if (!string.IsNullOrWhiteSpace(fallback)) {
                return fallback;
            }

            return null;
        }

        private static string? TryExtractSourceUrl(HtmlDocument doc) {
            // <link rel="canonical" href="...">
            HtmlNode? canonical = doc.DocumentNode.SelectSingleNode("//link[@rel='canonical']");
            if (canonical != null) {
                string href = canonical.GetAttributeValue("href", string.Empty);
                if (!string.IsNullOrWhiteSpace(href)) {
                    return href;
                }
            }

            // <meta property="og:url" content="...">
            HtmlNode? og = doc.DocumentNode.SelectSingleNode("//meta[@property='og:url']");
            if (og != null) {
                string content = og.GetAttributeValue("content", string.Empty);
                if (!string.IsNullOrWhiteSpace(content)) {
                    return content;
                }
            }

            return null;
        }

        private static string? TryExtractRaceName(HtmlDocument doc) {
            // よくある: h1
            HtmlNode? h1 = doc.DocumentNode.SelectSingleNode("//h1");
            if (h1 != null) {
                string t = NormalizeText(h1.InnerText);
                if (!string.IsNullOrWhiteSpace(t)) {
                    return t;
                }
            }

            return null;
        }

        private static string TryExtractRaceDateRaw(HtmlDocument doc) {
            string text = doc.DocumentNode.InnerText;

            Match m = Regex.Match(text, @"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日");
            if (!m.Success) {
                return string.Empty;
            }

            int y = int.Parse(m.Groups[1].Value);
            int mo = int.Parse(m.Groups[2].Value);
            int d = int.Parse(m.Groups[3].Value);

            DateTime dt = new DateTime(y, mo, d);
            return dt.ToString("yyyy-MM-dd");
        }

        private static string? TryExtractTrackNameRaw(HtmlDocument doc) {
            // まずはタイトル/本文から雑に拾う（後で必要なら精密化）
            string text = NormalizeText(doc.DocumentNode.InnerText);

            // 例: 中山, 阪神 などは race_id からも引ける設計だが、ここではrawで持つ
            // 必要ならここを強化
            return string.Empty;
        }

        private static string? TryExtractSurfaceDistanceRaw(HtmlDocument doc) {
            // 例: 芝2500m / ダ1800m などを本文から拾う
            string text = NormalizeText(doc.DocumentNode.InnerText);
            Match m = Regex.Match(text, @"(芝|ダート|ダ)\s*(\d{3,4})m");
            if (m.Success) {
                return m.Groups[1].Value + m.Groups[2].Value + "m";
            }

            return string.Empty;
        }

        private static string? TryBuildRaceIdFromFileName(string sourceFile) {
            // 例: 20260107_nakayama_11.html
            if (string.IsNullOrWhiteSpace(sourceFile)) {
                return null;
            }

            string name = Path.GetFileNameWithoutExtension(sourceFile);

            // yyyyMMdd_(track)_NN
            Match m = Regex.Match(name, @"^(?<ymd>\d{8})_(?<track>[^_]+)_(?<r>\d{1,2})");
            if (!m.Success) {
                return null;
            }

            string ymd = m.Groups["ymd"].Value;
            string track = m.Groups["track"].Value.ToLowerInvariant();
            string r = m.Groups["r"].Value;

            // 右側ゼロ埋め（11 -> "11", 1 -> "01"）
            string raceNo2 = int.Parse(r).ToString("00");

            // トラック名→場コード（JRA-VAN準拠の想定）
            string? jyoCd2 = TryResolveJyoCdFromToken(track);
            if (string.IsNullOrWhiteSpace(jyoCd2)) {
                return null;
            }

            return ymd + jyoCd2 + raceNo2;
        }

        private static string? TryResolveJyoCdFromToken(string trackToken) {
            // ローマ字・日本語どちらでも運用できるように最低限
            Dictionary<string, string> map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                { "sapporo",  "01" }, { "札幌", "01" },
                { "hakodate", "02" }, { "函館", "02" },
                { "fukushima","03" }, { "福島", "03" },
                { "niigata",  "04" }, { "新潟", "04" },
                { "tokyo",    "05" }, { "東京", "05" },
                { "nakayama", "06" }, { "中山", "06" },
                { "chukyo",   "07" }, { "中京", "07" },
                { "kyoto",    "08" }, { "京都", "08" },
                { "hanshin",  "09" }, { "阪神", "09" },
                { "kokura",   "10" }, { "小倉", "10" }
            };

            if (map.TryGetValue(trackToken, out string? cd)) {
                return cd;
            }

            return null;
        }

        private static string TryExtractOgTitleOrTitle(HtmlDocument doc) {
            HtmlNode? og = doc.DocumentNode.SelectSingleNode("//meta[@property='og:title']");
            if (og != null) {
                string content = og.GetAttributeValue("content", string.Empty);
                content = NormalizeText(content);
                if (!string.IsNullOrWhiteSpace(content)) {
                    return content;
                }
            }

            HtmlNode? title = doc.DocumentNode.SelectSingleNode("//title");
            if (title != null) {
                string t = NormalizeText(title.InnerText);
                if (!string.IsNullOrWhiteSpace(t)) {
                    return t;
                }
            }

            return string.Empty;
        }

        private static void ApplyHeaderFromTitle(HtmlDocument doc, NetkeibaRaceHeaderRaw header) {
            string title = TryExtractOgTitleOrTitle(doc);
            if (string.IsNullOrWhiteSpace(title)) {
                return;
            }

            // 例:
            // "フェアリーＳ(G3) 出馬表 | 2026年1月11日 中山11R レース情報(JRA) - netkeiba"
            Match m = Regex.Match(
                title,
                @"^(?<name>.+?)\s*出馬表\s*\|\s*(?<y>\d{4})年(?<mo>\d{1,2})月(?<d>\d{1,2})日\s*(?<track>.+?)(?<r>\d{1,2})R"
            );

            if (!m.Success) {
                return;
            }

            string name = m.Groups["name"].Value.Trim();
            int y = int.Parse(m.Groups["y"].Value);
            int mo = int.Parse(m.Groups["mo"].Value);
            int d = int.Parse(m.Groups["d"].Value);

            header.RaceNameRaw = name;
            header.RaceDateRaw = new DateTime(y, mo, d).ToString("yyyy-MM-dd");
            header.TrackNameRaw = m.Groups["track"].Value.Trim();
            header.RaceNoRaw = int.Parse(m.Groups["r"].Value).ToString();
        }

        private static string ExtractSurfaceDistanceRaw(HtmlDocument doc) {
            HtmlNode? n = doc.DocumentNode.SelectSingleNode("//div[contains(@class,'RaceData01')]");
            if (n == null) {
                // フォールバック（既存の本文検索でもOK）
                return TryExtractSurfaceDistanceRaw(doc) ?? string.Empty;
            }

            string t = NormalizeText(n.InnerText); // "15:45発走 / 芝1600m (右 外 C)"
            Match m = Regex.Match(t, @"(芝|ダート|ダ)\s*(\d{3,4})m");
            if (!m.Success) {
                return TryExtractSurfaceDistanceRaw(doc) ?? string.Empty;
            }

            string surface = m.Groups[1].Value;
            if (surface == "ダ") {
                surface = "ダート";
            }

            string dist = m.Groups[2].Value;

            // 表示は "芝1600m" / "ダ1600m" に寄せる
            if (surface == "ダート") {
                return "ダ" + dist + "m";
            }

            return "芝" + dist + "m";
        }

        private static RaceExtraRaw ExtractRaceExtras(HtmlAgilityPack.HtmlDocument doc) {
            RaceExtraRaw x = new RaceExtraRaw();

            // =========================================================
            // RaceData01 例: "15:45発走 / 芝1600m (右 外 C)"
            // =========================================================
            HtmlAgilityPack.HtmlNode? d1 = doc.DocumentNode.SelectSingleNode("//div[contains(@class,'RaceData01')]");
            if (d1 != null) {
                string t1 = NormalizeText(d1.InnerText);

                // start time: 15:45
                System.Text.RegularExpressions.Match tm = System.Text.RegularExpressions.Regex.Match(t1, @"\b(\d{1,2}:\d{2})\b");
                if (tm.Success) {
                    x.StartTimeRaw = tm.Groups[1].Value;
                }

                // surface + distance: 芝1600m / ダ1600m / ダート1600m
                System.Text.RegularExpressions.Match sd = System.Text.RegularExpressions.Regex.Match(t1, @"(芝|ダート|ダ)\s*(\d{3,4})m");
                if (sd.Success) {
                    string surface = sd.Groups[1].Value;
                    string dist = sd.Groups[2].Value;

                    if (surface == "ダート" || surface == "ダ") {
                        x.SurfaceTypeRaw = "ダ";
                    }
                    else {
                        x.SurfaceTypeRaw = "芝";
                    }

                    x.DistanceMRaw = dist;
                }

                // course detail inside parentheses: (右 外 C)
                System.Text.RegularExpressions.Match paren = System.Text.RegularExpressions.Regex.Match(t1, @"\((?<inside>[^)]+)\)");
                if (paren.Success) {
                    string inside = NormalizeText(paren.Groups["inside"].Value);
                    x.CourseDetailRaw = inside;

                    if (inside.Contains("右")) {
                        x.TurnDirRaw = "右";
                    }
                    else if (inside.Contains("左")) {
                        x.TurnDirRaw = "左";
                    }

                    // 内外（両方含むことは基本ない想定）
                    if (inside.Contains("内")) {
                        x.CourseRingRaw = "内";
                    }
                    else if (inside.Contains("外")) {
                        x.CourseRingRaw = "外";
                    }

                    // A/B/C 等（単独の英大文字）
                    System.Text.RegularExpressions.Match c = System.Text.RegularExpressions.Regex.Match(inside, @"\b([A-Z])\b");
                    if (c.Success) {
                        x.CourseExRaw = c.Groups[1].Value;
                    }
                }
            }

            // =========================================================
            // RaceData02: span 群から meeting/turn/class/headcount
            // =========================================================
            HtmlAgilityPack.HtmlNode? d2 = doc.DocumentNode.SelectSingleNode("//div[contains(@class,'RaceData02')]");
            if (d2 != null) {
                List<HtmlAgilityPack.HtmlNode> spans =
                    d2.SelectNodes(".//span")?.ToList()
                    ?? new List<HtmlAgilityPack.HtmlNode>();

                List<string> items = new List<string>();
                foreach (HtmlAgilityPack.HtmlNode s in spans) {
                    string text = NormalizeText(s.InnerText);
                    if (!string.IsNullOrWhiteSpace(text)) {
                        items.Add(text);
                    }
                }

                // 期待並び: 1回 / 中山 / 4日目 / サラ系３歳 / オープン / ... / 20頭
                if (items.Count >= 3) {
                    // meeting_raw = "1回中山"
                    x.MeetingRaw = items[0] + items[1];

                    // turn_raw = "4日目"
                    x.TurnRaw = items[2];
                }

                // head_count_raw: "20頭" -> "20"
                foreach (string it in items) {
                    System.Text.RegularExpressions.Match hm = System.Text.RegularExpressions.Regex.Match(it, @"(\d{1,2})頭");
                    if (hm.Success) {
                        x.HeadCountRaw = hm.Groups[1].Value;
                        break;
                    }
                }

                // race_class_raw: items[3] 以降を "頭数" の手前まで連結
                // （まずは生文字列でOK。後で正規化ルールを詰める）
                if (items.Count >= 4) {
                    List<string> cls = new List<string>();

                    for (int i = 3; i < items.Count; i++) {
                        bool isHeadCount = System.Text.RegularExpressions.Regex.IsMatch(items[i], @"\d{1,2}頭");
                        if (isHeadCount) {
                            break;
                        }

                        cls.Add(items[i]);
                    }

                    x.RaceClassRaw = string.Join(" ", cls).Trim();
                }
            }

            return x;
        }

        private sealed class RaceExtraRaw {
            public string SurfaceTypeRaw { get; set; } = string.Empty; // 芝/ダ
            public string DistanceMRaw { get; set; } = string.Empty;   // 1600
            public string TurnDirRaw { get; set; } = string.Empty;     // 右/左
            public string CourseRingRaw { get; set; } = string.Empty;  // 内/外
            public string CourseExRaw { get; set; } = string.Empty;    // A/B/C
            public string MeetingRaw { get; set; } = string.Empty;        // 例: "1回中山"
            public string TurnRaw { get; set; } = string.Empty;           // 例: "4日目"
            public string RaceClassRaw { get; set; } = string.Empty;      // 例: "サラ系３歳 オープン (国際) 牝(特指) 馬齢"
            public string HeadCountRaw { get; set; } = string.Empty;      // 例: "20"
            public string StartTimeRaw { get; set; } = string.Empty;      // 例: "15:45"
            public string CourseDetailRaw { get; set; } = string.Empty;   // 例: "右 外 C"
        }

    }
}

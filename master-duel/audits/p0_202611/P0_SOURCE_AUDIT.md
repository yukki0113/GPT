# P0 データソース監査
調査日 2026-11-09（JST）。結論は [P0_DECISION.md](P0_DECISION.md)。数値は [P0_COVERAGE.md](P0_COVERAGE.md)。
## 要約
候補は YAML Yugi（日本語／MD属性）、YGOJSON（MD生成可否・セットのスキーマ）、YGOPRODeck（基本情報）と公式OCG（照合）。**現時点で採用済み正本はない**。日本語テキストの権利、MD実際の文面・最新追従、母集団、現行規制の独立検証は未確定。
## 利用条件ゲート
「公開配布」はコンテンツの権利許諾ではない。下表の「未確認」は禁止の断定でも許可の断定でもない。
|出典|確認した内容と利用判断|更新・制限|
|---|---|---|
|[YAML Yugi](https://github.com/DawnbrandBots/yaml-yugi)|個別JSON/MD集約の配布リンクあり。コードはAGPL-3.0以降、カード本文は権利者の著作権表示。少量個別を監査した。一括ダウンロードの導線あり、本文のローカル継続保存・公開転載・商用は別途権利未確認。|更新頻度/SLA・APIレート未確認。個別36件で日本語文字列とMD rarityを観測。|
|[YGOPRODeck](https://ygoprodeck.com/api-guide/)|APIは公開、ローカルキャッシュ推奨。サンプルAPIを閲覧。公開Gitへの転載・商用・カード権利は未確認。対応言語に日本語なし。format=master duelの厳密な網羅保証は不明。card_setsは紙カードセット。|20リクエスト/秒、超過時1時間ブロック。cardinfoのキャッシュ2日、追加時手動クリア。|
|[YGOJSON](https://github.com/iconmaster5326/YGOJSON) / [schema](https://github.com/iconmaster5326/YGOJSON/blob/main/schema/v1/card.json)|MIT表記はコード等のライセンスであってカード本文の権利を保証しない。READMEはZIPの自動取得を案内。スキーマにMD在籍時のrarity/craftable、履歴、言語を定義するが、実データの網羅率・保存/転載/商用権は未確認。集約branchのrawは古く壊れていると明記。ゲーム限定カードは対象外。|日次再生成と記載、実際の最新反映は未検証。レート未確認。YAML Yugi等を入力としており独立正解ではない。|
|[公式OCG DB](https://www.db.yugioh-card.com/yugiohdb/)|日本語OCG名の個別照合に使用。MD表示・MD規制の証拠ではない。自動大量取得・保存・転載・商用の許諾は未確認。robotsを取得できず。|更新頻度・レート未確認。|
|[Master Duel Meta](https://www.masterduelmeta.com/cards/Ash%20Blossom%20%26%20Joyous%20Spring)|灰流うららの個別ページで入手経路の表示を確認。ただしページ表示にエラー、色による期限の機械判別も不可。規約ページは実質的な取得条件を確認できず、robots取得不可。自動収集・保存・転載・商用は未確認。|更新頻度・レート・公式API未確認。大量クロールせず。|
|[規制リスト別配布](https://github.com/DawnbrandBots/yaml-yugi-limit-regulation)|MD current.vectorの少量メタ情報を確認。権利・運用条件、欠番が無制限を意味するかは未検証。非公式のため独立公式照合が必要。|スナップショット日付2026-11-05。更新保証未確認。|
|[MD利用規約（Steam日本語）](https://store.steampowered.com/eula/1449850_eula_0?eulaLang=japanese)|商業利用、無断複製、データの逆解析、自動操作等の禁止条項を確認。ゲーム内部データの解析や自動操作は行わない。適用範囲は各プラットフォーム別に確認。|規約の版と適用条件に注意。|
公開Gitにはカード本文・画像・元データ・個人所持情報を保存しない。非公開保存先は未設定。規約上可能と未確認を混同しない。

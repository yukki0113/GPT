# BRDB ③-B — 上位50種牡馬マスタと祖先ネットワークの初回補完

- 日付: 2026-11-05
- 状態: **FIRST TOP-50 RESEARCH SEED COMPLETE / 2–3 GENERATIONS PARTIAL / NO PERSON-ID INFERENCE / NOT PRODUCTION**
- 結論: 上位50頭の父・母の名前は全100経路、2代前の名前は147/200経路を確認。**同名人物の公式JRDB-ID接続は大幅に不足**。3代前は名前20/400経路に限られる。個体ID確定と名前観測を混同しない。
- Source generation: `5279af0bd8226cde`、対象コホートは2022～2024年生まれの血統マスター12,018頭。
- JRDB: `pedigree_fact.parquet` SHA256 `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536` / `parent_relation.parquet` SHA256 `c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85`。
- Ranking input: `stage3a/recent_2022_2024_combined_ranking.csv` SHA256 `e982e7b5a1467af5bb18e74f583acd9315263a74516472ca439c88b0f2eaf362`。
- 仕様上の優先関係: ①～③ ＞ ④ ≫ ⑥⑦。地域ルーツ・条件適性は**この補完処理で生成しない**。

## 1. 初回登録の実績

| 入力・観測段階 | 確認件数 | 備考 |
|---|---:|---|
| 共通上位50種牡馬 | **50頭** | ③-A順位をそのまま使用 |
| JRDB`pedigree_fact`に一意プロフィールあり | **37頭** | 名前＋生年＋JRDB公式系統コード＋性別のガード。一意性確認 |
| 研究世代に未登録だがJBISで個体ページを確認 | **13頭** | 各馬の独立JBIS識別子とURL。**JRDB`horse_id`はNULL** |
| 父・母の名前 | **100／100経路** | `S`/`D` |
| 2代前の名前 | **147／200経路** | `SS,SD,DS,DD` |
| 3代前の名前 | **20／400経路** | 3代前は残件が多い |
| 正式JRDB個体IDに到達した1代前経路 | **36／100** | スロット数。名前の確認率とは異なる |
| 正式JRDB個体IDに到達した2代前経路 | **10／200** | 同上 |
| 正式JRDB個体IDに到達した3代前経路 | **0／400** | 同上 |
| 祖先の調査待ち集約キー | **148件** | (出典表示名, 観測生年)でまとめた**調査単位**。同一人物保証なし |

**注意**：`pedigree_fact`の直接`broodmare_sire_name`は、その種牡馬の`DS`（母父）ラベルとして利用できる。母本人のIDが分からない場合でも、名前を記録することと祖先IDを確定することは別。したがって`DS`の欠損名補完に使用したが、`jrdb_ancestor_id`はnullのまま。

## 2. 外部補完した13頭

`taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json` に原出典と、`S`/`D`/`SS`/`SD`/`DS`/`DD`の表示祖先名を分けて記録した。以下のURLは**各種牡馬自身のJBIS個別ページ**である。

| 順位 | 種牡馬 | JBIS個体ページ | 確認範囲 |
|---:|---|---|---|
| 10 | ハービンジャー | https://www.jbis.jp/horse/0001115148/ | 父Dansili・母Penang Pearl、祖父母 |
| 18 | ブリックスアンドモルタル | https://www.jbis.jp/horse/0001293348/ | 父Giant's Causeway→父父Storm Cat |
| 19 | ドレフォン | https://www.jbis.jp/horse/0001240055/ | 父Gio Ponti・母Eltimaas、祖父母 |
| 24 | エンパイアメーカー | https://www.jbis.jp/horse/0000749845/ | 父Unbridled・母Toussaud、祖父母 |
| 27 | ヘニーヒューズ | https://www.jbis.jp/horse/0001028940/ | 父Hennessy→父父Storm Cat |
| 34 | パイロ | https://www.jbis.jp/horse/0001085636/ | 父Pulpit→父父A.P. Indy |
| 37 | ナダル | https://www.jbis.jp/horse/0001328857/ | 父Blame・母Ascending Angel |
| 39 | デクラレーションオブウォー | https://www.jbis.jp/horse/0001181460/ | 父War Front→父父Danzig |
| 42 | シニスターミニスター | https://www.jbis.jp/horse/0001025279/ | 父Old Trieste→父父A.P. Indy |
| 44 | マインドユアビスケッツ | https://www.jbis.jp/horse/0001302899/ | 父Posse・母Jazzmane |
| 47 | カルフォルニアクローム | https://www.jbis.jp/horse/0001211258/ | 父Lucky Pulpit・母Love the Chase |
| 48 | ニューイヤーズデイ | https://www.jbis.jp/horse/0001298815/ | 父Street Cry・母Justwhistledixie |
| 50 | サンダースノー | https://www.jbis.jp/horse/0001226963/ | 父Helmet・母Eastern Joy |

上記は**種牡馬個体における出典表示位置の事実**。JRDB馬IDとの同一性や、内包血統12候補の本人IDまでの確証を得たことは意味しない。以前の工程②に記録した個別候補と同じ名前が出現しても、監査済みID対応がない限り別扱い。

## 3. 研究用の生成物・ソース

- `src/brdb_stage3b_top50_builder.py`：公式Parquet/③-Aランキング/外部source seedを読取り専用で結合する、GitHub登録済み再現用モジュール。S/Dを優先し、本人のJRDB`horse_id`が取れる場合だけparent_relationの`RESOLVED_EXACT/ALIAS`を深さ3まで再帰。未来情報の認定や推論は禁止。
- `taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json`：海外等13頭の個別JBIS ID、出典URL、深さ2までの**名前経路**。各祖先の外部個体IDを推測していない。
- 実行済みローカル成果物: `stage3b_top50_master_research.json`（50対象×観測位置）、`stage3b_unresolved_ancestor_queue.json`（調査台帳）、`stage3b_top50_status.csv`、`stage3b_backlog_top100.csv`。
- ローカル解析実行環境はDuckDB 1.1.3、Python 3.13。ソースSHAを検証。観測結果を2度生成しJSONファイルのSHA256が一致。**ただしGitHubコミット済みモジュールをGitHub Actions等で実行して同値性確認したわけではない**。
- 研究JSON: `stage3b_top50_master_research.json` SHA256 `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`（ローカル解析スクリプト版）。GitHub側モジュールの出力スキーマは内部フィールド名が異なるため、このSHAとのバイト完全一致を保証しない。数値・対象母集団・検出方針を照合する。

## 4. 未解決祖先の登録台帳と優先順位

`weighted_coverage_impact_upper_bound`は、その祖先の名前に依存する**上位50頭の登場延べ枠数の合計**。実際の追加カバー率ではない。馬ごとの重複出現、同姓・異名、同じ根拠由来の重複を差し引く前の、上限目安。

| 調査候補ラベル | 関連上位種牡馬数 | 延べ影響上限 | 検討対象 |
|---|---:|---:|---|
| サンデーサイレンス | 27 | 6,185 | 古い父系共通祖先。JBIS IDの正規接続 |
| ウインドインハーヘア | 9 | 2,406 | 母ラインの正規個体ID |
| キングマンボ | 6 | 1,952 | キングカメハメハ等へ共通祖先として接続 |
| マンファス | 6 | 1,952 | 母方の重複共有を監査 |
| クリスエス | — | 1,001 | シンボリクリスエスの父系接続 |
| ティーケイ | — | 1,001 | シンボリクリスエスの母系接続 |
| キャンペンガール | — | 833 | スペシャルウィーク経由の血統 |
| キロフプリミエール | — | 833 | 欧州系牝系の祖先名 |

特にSunday Silenceは以前の工程②でJBIS個別IDを登録済みである。③-Bではその外部subjectとの**本人同定crosswalk**を優先すると、より多くの現役種牡馬に波及する。ただし古い個体のJRDB IDを番号推測で埋めない。

## 5. 結論と残工程

本工程③-Bの**第一バッチ50頭に対する個体入口の登録と最大2世代の名前補完は実施**。3代前は20/400で未解決が大きく、**2〜3代を正式個体IDで結び終えたわけではない**。

次の補完バッチでは、(a)上記高頻度の古い共通祖先への一意外部ID接続、(b)37国内馬の未解決`S/D`からの外部母・父同定、(c)3代前の名前/個体ID補完、(d)各バッチごとの正式ID解決率と母集団の父・母父カバー率再測定を行う。

母母側は任意であり、父・母父レーンの運用を妨げない。

**BRDB CURRENT、凍結レビュー、RaceNote、PWA、Newspaper、本番Actions/workflowは変更しない。**

> **2026-11-10 M5-Aパイロット**：`engine_m5/`にテーマ名前一致/日本語引用の別関係、汎用札役割、PACKAGE/SINGLETON、MAIN/EX、代替部品、制約・EX枠評価を実装。PRIVATE seed SHA `f0498fddf6e2d2ac488a52aae44f5db05068720b137406e4ef76812338853188`、M5派生SQLite SHA `d70238c99ddc1c319ea7a02fdf3798ba3877981a66bf5abec1e9838efb1d5486`。実13,948枚、3テーマ/3バリアント、候補150、汎用役割7、制約5。Drive保存・SHA読戻し済み。**Source/所持/banlist/M4 indexを変更しない**。すべて候補、M6で採用合法性/所持/CP確認が必要。[監査](../engine_m5/M5_AUDIT_20261110.md)。

> **2026-11-10 M4開始**：効果のLexical Semantics v1を `effect_semantics_m4/` に追加。日本語効果13,948枚の根拠付き候補75,913行を、非公開Driveの独立SQLite ZIPへ保存（index SHA256 `9312109612b1ad38ec318a7c5d6745c9b82c97dc872613a2994a98d19c738451`）。抽出結果は`UNVERIFIED_INTERPRETATION`、原文オフセット/テキストSHA/版本保持、自己処理・条件・引用/参照・コスト等を別ロール。旧本番HEAD世代3・規制215・所持5種類は不変。**M4候補分類の基盤実装であり、人手による精度検証・テーマ関連確定は残る**。[監査](../effect_semantics_m4/M4_AUDIT_20261110.md)。

> **2026-11-10 MD規制の出典調査**：非公開vectorはDawnbrandBots/yaml-yugi-limit-regulationの2026-11-05版と完全同一。SQLite収録215/215一致、前回10/06からの9差分は公式告知と独立記事で整合。YAML Yugiの再掲載で215件独立検証済みとは言わない。ゲーム内で未確認の206継承行を含むためUNVERIFIED_SOURCEを維持。全215行はprivate Driveにのみ。[監査](../audits/p1_202611/M3_BANLIST_SOURCE_RECONCILIATION_20261110.md)。

> **2026-11-10 ユーザー運用決定**：生成可否 UNKNOWN=13,931 はM3/M6推薦のBlockerにしない。`PROVISIONAL_GO` として候補を許可し、カタログ状態はUNKNOWNを維持。カタログNO=17および以後の個別生成不可報告は必要枚数不足時にHOLD。出典付き私的例外レジストリを使用。MD禁止制限の一次データはKONAMIゲーム内一覧・お知らせ、現在の215件source/vectorはUNVERIFIED_SOURCE。[監査](../audits/p1_202611/M3_CRAFTABILITY_PROVISIONAL_GO_20261110.md)。

> **2026-11-10 M3 CP導入**：ユーザー確認済みのN/R/SR/UR別30CPを非公開Driveに独立JSON保存。USER_CONFIRMEDとGAME_VERIFIEDを分離し、SHA固定・日付選択。現本番世代3の規制215件はUNVERIFIED_SOURCEを維持。生成可否UNKNOWNをYESにせず、レアごとのCP残高も未申告につきUNKNOWN。[CP監査](../audits/p1_202611/M3_CP_USER_CONFIRMED_20261110.md)。以下過去履歴。

> **M3続編 2026-11-10**：Drive本番はHEAD世代2、所持5種類/計9枚。規制215件は非公開source/current.vector.jsonに候補として存在し、DB規制表はまだ空。候補をSQLiteへ `UNVERIFIED_SOURCE` としてインポートする検証・ローダーを追加。第三者との集計数一致をゲーム内全件確認に格上げしない。所持と合法採用枚数を分離する。[M3](../regulation_m3/README.md)。以下履歴。

> **2026-11-10 M3-2現在地**：M2所持5種類がDrive本番世代2に保存済。M3は2026-11-05施行215件候補を `UNVERIFIED_SOURCE` のままSQLite banlistに追加する取り込み層を実装。改訂差分9件の公開照合は一致、残206件の個別ゲーム内照合は未完。個人所持情報はGitへ置かない。[M3](../regulation_m3/README.md)。以下履歴。

> **2026-11-10 優先順位の一時変更**：M2実所持登録は本人が見比べられる状況で実施する。M3の規制・CPデータモデルと評価ロジックを先行。私的vectorの215件は元ファイル自体に確認状態がなく、実ID対応215/215 PASSでも「現行MD公式確認済み」とは言えない。ゲーム内確認が整うまでCANDIDATE_ONLY。Drive本番HEAD世代1・inventory0件を維持。[M3](../regulation_m3/README.md)。以下履歴。

> **2026-11-10 現行実装**：非公開本番DBはDrive世代1・13,948件・inventory0件。M1初期検索/費用評価済み。M2の正本HEAD結合・候補ZIP検証・独立読み戻し・HEAD昇格提案のコードを追加し、合成回帰110件（スキップ1）PASS。M2実所持登録は本人申告待ちで、実本番HEADは変更していない。出張/禁止制限はM5/M3で整備。[M2手順](../inventory_m2/README.md) / [全体残工程](../docs/INITIAL_GOAL_REMAINING_ROADMAP_20261110.md)。以下は履歴。

# Project Context — master-duel

> **2026-11-09 追加要件**: 収録パックDBの主要用途は「デッキ→有利なパック→解放するために生成するSR/UR」の逆引き。Game8個別パックのレア一覧はピックアップ**候補**であり、ゲーム内全件照合済みではない。P0-Cの固定30件の画面照合は完了（30/30）。残る入手先/ライセンス/販売時点は独立ゲート、P1-A1 NO-GO。正本：[PACK_UNLOCK_NAVIGATION_P0_20261109.md](../docs/PACK_UNLOCK_NAVIGATION_P0_20261109.md)。以下は履歴。


> **現行状態・Drive原本（2026-11-09）**: P0は実測監査済み部分があるが**未完了**。MD候補JSON（13,948件）、OCG JSON（14,416件）、禁止制限（215件）の3ファイルはDrive `source` フォルダ（ID `1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh`）でファイル名/サイズを確認済み。 **[docs/DRIVE_SOURCE_RESOLUTION.md](../docs/DRIVE_SOURCE_RESOLUTION.md) が探索手順の正本**。**個別File IDは更新で変わるため、フォルダから毎回再解決**。フォルダ・親フォルダの現在の共有設定はユーザー承認済みで、制限付き変更の再提案・反復警告は不要。P1未着手。下記「実データ未着手」は初回作成時の履歴とみなす。


## 正本・状態
- Repository: `yukki0113/GPT` / `main`
- Project root: `master-duel/`
- Basic design: `docs/BASIC_DESIGN.md` v0.1（2026-11-09）
- Current phase: **設計を保存したのみ。実装・実データ取得・検証は未着手。**

## ユーザー要件・決定事項
1. 日本語の正式カード名と効果テキストは必須。
2. カード属性・効果に加えて、MD固有レアリティ、入手パック、禁止・制限を保持する。
3. 単純な文章一致に限らず「ドロー」「関連サーチ」「テーマ外サポート」の意味検索を行う。
4. **最大優先**は「SR以下で組めるお手軽テーマ」。現在の所持汎用カードを採用し、新規UR生成なしの構築を探す。
5. 汎用カードは複数攻略サイト等の情報を参照するが、分類は固定的な正解としない。
6. 所持枚数は全カードで管理可能にし、UNKNOWNと確認済み0を分ける。
7. デモンスミス／スピードロイド／壊獣等の**出張パーツ／エンジン**も扱い、最小セット、制約、コスト、他テーマとの相性を記録する。
8. 完成レシピはMD現行規制、メイン／EX枠、所持数と生成CPを評価する。
9. 二次公開・販売は当面行わない。将来構想であり、公開する際は権利・データ源利用条件を再評価する。
10. データ収集と実装を開始する前に日本語、レアリティ、パック等のソース監査を行う。

## 読む順序
1. repository共通 `.gpt/GITHUB_OPERATION_POLICY.md` / `.gpt/README.md` / root `AGENTS.md`
2. 本 `README.md`
3. `.gpt/CONTEXT.md`
4. `.gpt/WORKFLOW.md`
5. `docs/BASIC_DESIGN.md`
6. 実装時にParquet/DuckDB処理するなら `tools/data-storage/README.md` を**先に読む**。

## 境界
- Gitは仕様・コード等の正本。所持カード実データ、権利条件が不明なカード全文データは公開Gitへ追加しない。
- 最新banlist・カードレアリティ等を過去の会話の数値で確定させない。
- 外部ソースの利用条件確認なく大量取得しない。
- 既存領域や共通文書に影響する変更は別途監査する。

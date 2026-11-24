# JPDB 開発進捗台帳（暫定・スレッド引継ぎ用）

更新: 2026-11-24 JST
状態: ACTIVE / M5–M8 優先 / JPDB単体初期リリース未達 / RaceNote本番未承認
作成時参照 main: b5041d2113b2b3dc387b262bdd414ba196131ad7

## 0. このファイルの運用

2026-11-24 ユーザー指示により、Libraryの継続性への懸念から、Gitに一時ファイルを置かない通常方針の例外として本台帳を設置する。JPDB開発の進捗・次工程・引継ぎを記録する単一の更新ファイルとし、作業ごとの一時ファイル乱立は行わない。正式仕様・研究証跡は既存の正本を参照し、本台帳で上書きしない。既存P/R番号は研究・実装の識別子として維持し、M番号は全体マイルストーン管理に用いる。

- 新スレッドでは最新mainのREADME、.gpt/CONTEXT、.gpt/WORKFLOW、.gpt/HANDOFF、共通Git運用規約と本台帳を確認し、次工程から再開する。Libraryの存在を前提にしない。個別のprivate資産は所在と既存証跡を参照し、実際に取得・照合できたものだけを使用する。
- 各作業区切りに本台帳の状態表、次工程、更新履歴を更新し、Gitのコミットと読み戻しを確認する。PASSは実行済み検証と証跡のある範囲に限定。計画・実装・合成テスト・実データ受入・本番承認は別状態。実行不能時は理由と再開条件を明記。
- Gitには進捗、非機密の集計、仕様・ソース・証跡参照のみ。JRDB等のライセンス対象原データ・個別馬/騎手のprivate出力・認証情報を掲載しない。Library/Driveのprivate成果物は既存の保存方針を維持する。
- 暫定台帳の廃止・正式資料への統合は利用者判断後。例外を他プロジェクトや他の一時ファイルへ拡張しない。

## 1. 目的・優先順位

JPDBをRaceNoteのためだけの加工モジュールとせず、独立した騎手分析基盤として実用化する。JPDB単体初期リリース条件はM8受入であり、RaceNote採用・BRDB完成を前提としない。M5→M6→M7→M8を優先し、その後M9〜M13の連携・研究を進める。既存P/R成果は再利用し、固定研究の承認範囲を拡張解釈しない。

## 2. マイルストーン

### Phase 1 基礎研究・設計

| MS | 内容 | 状態 | 完了条件・既存成果 |
|---|---|---|---|
| M1 | 騎手履歴・基本実績集計 | DONE_RESEARCH | P1/P1.2 固定履歴Reader受入 |
| M2 | 条件別実績・コース物理特性分析 | DONE_RESEARCH | P2 raw/physical、Course Masterの認証済み範囲で受入 |
| M3 | 馬質補正・騎手能力・相対条件傾向研究 | DONE_RESEARCH / 能力認定保留 | P3感度分析・R2記述的比較。因果能力認定とは区別 |
| M4 | 予定騎手プロファイル・Evidence契約 | PASS_FIXED_SOURCE | R1/R2・R3固定データ契約。開催前汎用実行は未受入 |

### Phase 2 JPDB実用基盤

| MS | 内容 | 状態 | 完了条件 |
|---|---|---|---|
| M5 | 履歴データ継続更新・世代管理 | IN_PROGRESS | 旧97日世代維持、新100日世代の正本選定・SHA/Parser/全件監査、追加更新・再実行・欠損/重複/差替え拒否、履歴世代固定と再現 |
| M6 | 開催前PACI対応Profile Builder | IN_PROGRESS | 歴史データと対象日PACI分離、R1 forward adapter・R2 per-target runner、対象日SED不要、旧R1/R2回帰、予定騎手・条件・全馬・cutoff・source pin検証 |
| M7 | 任意対象レース照会・Reader | TODO | 受入済みソース範囲内で騎手・条件・期間・過去時点・騎手間比較・指定レース全馬の一貫した照会契約。欠測/小母数/期間制限明示、再利用可能なCLI/API、回帰テスト |
| M8 | 実データE2E・運用受入 | TODO | 正本取得→履歴世代選定→照会/開催前Profile→監査を実データで完走、再現性・不正入力拒否・運用手順受入。JPDB単体初期リリース判定 |

### Phase 3 RaceNote連携・予想研究

| MS | 内容 | 状態 | 完了条件・既存成果 |
|---|---|---|---|
| M9 | JPDB×BRDB共通Evidence接続 | PASS_FIXED_SOURCE / FORWARD_PENDING | R3固定契約・新馬4R42頭受入済。M8後に同一開催前PACIと両DBのfresh receiptsでforward受入 |
| M10 | RaceNote Shadow・読解品質監査 | PARTIAL | R4初回PASS、全Reader比較と独立意味論監査は未完 |
| M11 | JPDB単独／BRDB単独／併用比較 | TODO | 独立した事前固定ablation計画・比較、共有履歴の重複と交絡を区別 |
| M12 | 50R比較研究・TRUE_FORWARD | PARTIAL | R5歴史pilot 3R40頭のみ完了。既存事前固定protocolを維持、A1 25R＋OTHER 25R、独立A/B Prediction→Confidence Freeze、結果開示後の固定指標比較、独立読解監査。50Rは性能認定の十分数ではない |
| M13 | RaceNote本番採否・接続 | NOT_AUTHORIZED | R6の独立受入と別承認。既存v056、Confidence Z、CURRENT/PWAを無断変更しない |

M8以降の研究は既存プロトコルと整合させる。M11のablationはM12の事前固定A/B試験と混ぜず、後知恵による変更・対象差替えを禁止する。

## 3. 現在地と次工程

**再開地点: M5 新履歴世代受入。**

1. 正本DriveのPACI/SEDを最新時点で直接棚卸し。2026-11-24先行監査時はPACI 100日、SED 100日（109ファイル）、新規11/21・22・23。旧97日とSEDサイズ一致95日、11/14・15不一致、同名重複9日。これはメタデータ監査のみ。実行時には再確認。
2. 旧固定世代のmanifest・SHAを保存したまま、同名候補をZIP/member SHA、正本Parserによる使用項目、race_key/horse_no/date/class、件数・異常結果・BAC整合で比較。サイズ・更新日時だけで選定しない。差分がある場合は根拠を記録し、別のrolling generationとして受入。旧バイトが取得不能なら再現性の制約を明示。
3. M6で既存R1のtarget PACIと歴史SED日付集合の束縛を解消し、固定BAC件数13431を無断緩和せず、別forward契約で独立検証した期待数を使用。既存R1固定契約を保護。R2のP3市場診断を開催前経路に混入させない。
4. M7/M8へ進み、実際の開催前PACIが必要な最終受入は配信・取得後に実施。合成テストや過去レースをTRUE_FORWARD扱いしない。現時点の前向き比較受入はA1 0/25、OTHER 0/25。

既存preflight: [実装](../src/jpdb_forward_input_preflight.py) / [テスト](../tests/test_jpdb_forward_input_preflight.py)。合成11/11 PASS、実Profile生成未接続。対象日capture・履歴raw・本番可用を認証するものではない。

## 4. 正本・再開用参照

- [R1基本再設計](JPDB_RACENOTE_JOCKEY_PROFILE_REDESIGN_20261120.md)
- [R1固定実装](JPDB_R1_JOCKEY_PROFILE_IMPLEMENTATION_20261124.md)
- [R2条件傾向](JPDB_R2_CONDITION_CONTEXT_RESEARCH_20261124.md)
- [R3契約](RACENOTE_R3_INDEPENDENT_EVIDENCE_CONTRACT_20261124.md) / [新馬受入](RACENOTE_R3_NEWCOMER_ACCEPTANCE_20261124.md)
- [R4 Shadow](RACENOTE_R4_SHADOW_AUDIT_20261124.md)
- [R5事前固定protocol](RACENOTE_R5_PAIRED_RESEARCH_PROTOCOL_20261124.md) / [初回pilot](RACENOTE_R5_INITIAL_PAIRED_PILOT_20261124.md)
- [開催前準備・実装blocker・棚卸し・再読](RACENOTE_R5_FORWARD_READINESS_20261124.md)
- [統合開発方針](racenote/RACENOTE_JPDB_BRDB_INDEPENDENT_EVIDENCE_POLICY_20261120.md)
- [共通Git運用規約](../../../.gpt/GITHUB_OPERATION_POLICY.md) / [共通Data Storage](../../../tools/data-storage/README.md)

private研究成果の保存場所・SHAは上記正式証跡を参照（Library /JPDB/R1〜R5等）。取得できない場合に成果物の内容を推測したり、同じ名前のファイルを代用したりしない。

## 5. 更新履歴

| 日付 JST | 実施内容 | 結果・次工程 |
|---|---|---|
| 2026-11-24 | R1〜R4固定研究、R5歴史pilot、根拠再読、forward preflight | 既存受入証跡参照。50R/TRUE_FORWARD未実施。preflight 11/11 PASS。進捗根拠commit c47e55fb7e5b846e2122dd81dc1136a28b42445d |
| 2026-11-24 | M1〜M13再整理、ユーザー指示によりGit暫定台帳設置 | M5〜M8最優先、M5から再開。コード・正式研究条件・本番設定は変更なし |

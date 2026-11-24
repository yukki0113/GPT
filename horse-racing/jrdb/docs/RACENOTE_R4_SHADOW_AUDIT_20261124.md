# R4 初回 Shadow 研究監査（2026-11-24）

判定: **初回両コホートの研究 Shadow PASS（v0.5.6封印済みReader 3R40頭）、R3固定6Rの全Reader比較はPARTIAL。R5未承認。** `research_only=true`, `prediction_safe=false`, `production_authorized=false`。既存R3・v0.5.6・BRDB B5契約は変更しない。

正本: [R1–R6方針](racenote/RACENOTE_JPDB_BRDB_INDEPENDENT_EVIDENCE_POLICY_20261120.md)、[R3受入](RACENOTE_R3_NEWCOMER_ACCEPTANCE_20261124.md)、[R4集計・証跡](evidence/racenote_r4_shadow_20261124.json)。

## 実測範囲

| コホート | R3照合 | JPDB | BRDB一般 | 現行Reader照合 | B5専用 |
|---|---:|---:|---:|---:|---:|
| 非A1（既走馬側） | 2R34頭 | 34 | 18 | 1R18頭 | 対象外 |
| A1新馬戦 | 4R42頭 | 42 | 42 | 2R22頭 | 4R42頭 |

同一PACIの全登録馬キー・条件・予定騎手・取消、R3詳細と軽量projection、受入SHA、履歴日、分母、制限付き根拠の非数値化、重複groupを検査。2026-11-15東京4/5/12Rはv056の封印済みReader manifest/session/operation/prediction・confidence handoffを検証。実Freeze recordsの内容と対象結果は開いていない。Readerには騎手コードが露出しないため予定騎手コードはPACIから別途照合。6/13の3R36頭には同版の封印済みReaderがなく、R3根拠監査だけ。6/13東京12R16頭のBRDBは未提供のまま。

- JPDB 3672件、BRDB一般900件、制限参照2451件。R2期間衝突10頭・15軸/比較器、同条件・同baselineで父/母父の差の符号反対24頭。低N/欠損を不適性扱いせず、符号は因果的矛盾や適性認定ではない。
- v056照合40頭全頭に騎手/厩舎指数と調教コンテキストが存在。血統コンテキストNONEも40頭。新馬22頭は近走/旧走0・RRDB NO_HISTORY、既走18頭RRDB AVAILABLE。騎手指数の重複可能性は構成概念の重複であり相関・寄与は未推定。新馬41/42頭に3Y新馬条件のn>=30セルあり。

## B5接続（R3残課題の同一対象受入）

BRDB独立開発branch `brdb/b1-debut-eligibility-audit-20261124` の既存B5 producer、固定契約/schema、B1–4依存、承認済みDuckDB 2.0.1/PyArrow 25.0.1/NumPy 2.2.4を再利用。元B5の別対象4R55頭とは区別し、固定2016–25履歴、2017–25母集団、2026-01-01 exclusive cutoffのままR3同一PACI 2日・4R42頭を新たに2回生成。各日のB5 review/receiptはバイト一致。分析10/10年、UKC10/10年、血統研究世代の固定SHA/size照合、B5元receiptとproducer/input pin照合。B5 JSON schema/全馬/取消/過去履歴時点/2×4×5セルの完全性を再監査。42/42頭に観測あり。

| B5母集団セル | 件数 |
|---|---:|
| DESCRIPTIVE | 655 |
| LOW_SAMPLE | 299 |
| NO_SAMPLE | 126 |
| SOURCE_UNAVAILABLE | 600 |
| 合計 | 1680 |

近親1230セル（LOW_SAMPLE408、NO_SAMPLE357、NO_PRIOR_OBSERVED_START295、FIRST_START_UNRESOLVED170）。A1実出走母集団と初出走観測候補を混同しない。全42頭の個体履歴はNO_PRIOR_START_OBSERVED_HISTORY_INCOMPLETE、2026履歴gapあり、生涯初出走認証なし、AS_OF_UNVERIFIED。B5は専用参照lane、一般出走BRDBやJPDBと合算しない。数値を現行Readerに露出しない。BRDB branchのmergeや昇格なし。

## 実装と再現

`src/racenote_r4_shadow_audit.py` は固定R3+PACI+Reader封印監査。`src/racenote_r4_debut_shadow_audit.py` は共通監査出力とB5別laneの参照監査。どちらも独立SHA固定のprivate manifestを受け、`--manifest --manifest-sha256 --output-dir` を指定。B5 producerは既存BRDB開発branchを使用し、schemaと依存sourceは固定SHAを検証して配置。出力はrepo外のみ。8/8新規テストPASS、両監査の独立2回生成一致。非公開Library `/JPDB/R4/JPDB_R4_20261124_private_shadow.zip` の読み戻しSHA一致。個体別原本・private manifestはGit非掲載。

## 次のゲート

初回Shadowは両コホートで実測済み。6R全部の現行Reader比較は未完了であり、6月分を同版で再演したと偽らない。今回の過去日ShadowはTRUE_FORWARDや厳密as-of認証ではない。R5では対象レース、baseline/candidate入力、評価指標、判断ルール、欠測の処理を事前固定し、同一レースで独立Freezeし双方のFreeze後にだけ対象結果を解禁。初回50R目安は性能認定ではない。R5実施承認と本番Reader/Confidence/Freeze変更は別ゲート。

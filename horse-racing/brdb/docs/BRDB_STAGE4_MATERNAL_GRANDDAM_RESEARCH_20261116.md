# BRDB ④：母母ライン（DD/DDS/DDD）任意補完・研究用監査

Date: 2026-11-16  
Status: **RESEARCH E2E PROVISIONAL / 150 source observations / 2 certified-person DD paths**  
Source generation: `5279af0bd8226cde`

## 目的と境界

父・母父の主工程を阻害せず、上位50種牡馬について母母（`DD`）、母母父（`DDS`）、母母母（`DDD`）の位置を任意補完する。③-BのJBIS血統表から「名前・生年・出典」を集めることと、③-Cの1辺1世代の認証済み親子グラフにより個体IDが確認できることを区別する。

`DD`は母の母、`DDS`は母の母の父、`DDD`は母の母の母である。`DS`（母父）と混同しない。

## 固定入力と出典

| 入力 | SHA256 |
|---|---|
| ③-B原本上位50研究JSON | `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0` |
| ③-B JBIS資料観測50頭 | `afb3ca403c200210e0bf4490c4c8400db1016a76fc489c0bb28075135b6fb78b` |
| ③-C正本研究用直接親子グラフ | `4c3a9315ae2e5742f17a0e8a5a7969e49d4843f13fbdda16971c5fb91ceb1ccd` |
| JRDB `pedigree_fact.parquet`（入口本人多項目確認） | `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536` |
| ③-B外部source-only seed | `28793703a85b3fcb4c41490dec70b49770457e7139e0443688d35a7688bc2602` |

③-B観測と外部seedはGitHub正本の現物をActionsから出力し、manifest SHAと比較。④のroot decisionも③-Bの多項目照合条件を固定Parquetとsourceプロフィールで再評価。

## 入口50頭の監査

| 入口同定状態 | 頭数 |
|---|---:|
| JRDB本人の姓名・生年月日・性別・父母名がJBISと一致 | 32 |
| 既存の独立審査済み本人crosswalk | 1 |
| JRDBプロフィールのないJBIS-only本人、source seedと多項目一致 | 12 |
| 個体ID対応または父母表記などに保留事項あり | 5 |
| **入口を検証済み** | **45** |

保留5頭はリアルスティール、シンボリクリスエス、ヘニーヒューズ、モズアスコット、タワーオブロンドン。これらの祖先観測は候補として記録するが、source人物IDとして自動承認しない。

## ④初回の実測（2026-11-16）

| 内容 | 数値・扱い |
|---|---:|
| 上位50頭×母母系3位置 | **150/150 観測** |
| `DD`の名前・生年source観測 | 50 |
| `DDS`の名前・生年source観測 | 50 |
| `DDD`の名前・生年source観測 | 50 |
| JRDB直接親子チェーンで個体IDまで裏付けられた位置 | **2**（ともに`DD`） |
| 入口確認済みだが祖先個体ID未確定（名前・生年・出典を保持） | **133** |
| 入口自体の同定が保留（3位置×5頭） | **15** |
| JBISの名前からJRDBまたはJBIS個体IDを推測で生成した件数 | **0** |

個体IDまで確認できた2件（いずれも公式JRDBの正本parent relationの2ステップ連結）：

- レイデオロ（root `JRDB:14106201`）→母 `JRDB:06103419`→母母 レディブロンド `JRDB:98110268`
- ルヴァンスレーヴ（root `JRDB:15104189`）→母 `JRDB:06102778`→母母 オータムブリーズ `JRDB:98101687`

JBISの同位置で観測した名前は、国表記の補助記号などが含まれ得るため、別フィールドの原文として保存する。source URLを保持し、母母父・母母母の正式個体IDを推測しない。

**150/150はあくまで「血統表の位置に祖先の名前・生年が記録されている」割合**であり、正式個体IDのカバー率ではない（確定2/150）。JBIS source観測はレース当日より後に取得されており、当時可用性は未検証。

## 実装成果物

- `src/brdb_stage4_maternal_granddam.py`：固定入力SHA、位置3種、source入れ替え禁止、JRDB/JBIS ID分離、認証済みdirect-parent chainの順序確認、未確認ID禁止を実装。
- `taxonomy/stage4_root_decisions_research_v0_1.json`：50頭全員の入口同定判断・出典識別。
- `tests/test_brdb_stage4_maternal_granddam.py`：安全契約の回帰テスト10件。
- `src/run_brdb_stage4_test_gate.py`：既存Stage3とStage4の一括回帰。
- `src/export_brdb_stage4_sources.py`：公開GitHub-trackedの資料とコードだけをSHA付きで出力。元JRDB Parquetは成果物に含めない。

## 不変条件と④完了の意味

- `AS_OF_UNVERIFIED`、`prediction_safe=false`、`can_override_review=false`
- 出典名のみからJRDB8桁馬ID・JBIS10桁個体IDを**生成しない**。
- ③-Cの親子エッジが各段すべて認証済みでなければ祖先個体IDを付与しない。
- ソース位置`DD/DDS/DDD`と父母父`DS`を取り違えない。
- ④は**任意補完工程**なので古い母母系統の個体ID全件完成を合格条件としない。出典名が揃い、ID不明分を明確に保留して研究用に保存できれば研究フェーズの区切りとする。
- ⑤D3で未認証の祖先個体IDを独立特徴量として使用しない。④から採点への自動接続は存在しない。

## 残作業

研究コードをGitHub PRで回帰テストし、正本出力を2回比較してshaを固定し、mainへ取り込む。取り込みは**研究用出典観測の確定**であり、母系適性・地域ルーツ・血統クロスの実運用認証ではない。

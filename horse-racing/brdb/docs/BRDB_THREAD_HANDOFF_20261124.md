# BRDB 研究再開・次スレッド引継ぎ — 2026-11-24 JST

## 0. 目的と読み方

本書は今後の研究の作業管理正本（新ロードマップ）とする。旧M0〜M8は歴史的な管理番号として保持し、完了済み研究を再度タスク化しない。未完了Issue/PRを勝手にclose/mergeしない。本書は研究・開発の引継ぎであり、本番昇格の許可ではない。

最上位目的：RaceNoteの過去走中心の評価に独立した血統根拠を加え、既走馬の別視点と、新馬戦・未出走馬の評価可能性を実証する。騎手プロファイルDB（JPDB）との将来併用を想定する。単純加点はしない。

基本設計正本: [BRDB_BASIC_DESIGN_AND_RESEARCH_POLICY_20261120.md](BRDB_BASIC_DESIGN_AND_RESEARCH_POLICY_20261120.md)。

## 1. 完了済み・凍結済みの研究資産（ここで区切る）

| 旧区分 | 受入済み範囲 |
|---|---|
| M0–M2 | ソース棚卸し、canonical horse_id、immutable Parquet、CURRENT/Reader、非採点Blood Review v0.1凍結 |
| M3 | 研究世代132,652頭、2016–2025年481,627出走結果、日付別血統候補481,503件（124件除外） |
| M4–M5 | 父・母父・配合・近親の条件別観測、D3記述研究、D4実PACI全頭研究。祖先・分類の未解決部分はAへ移管 |
| M6-R | 2021–2025 walk-forward 235,700出走行/17,239レース、簡易非血統モデル log loss 0.2612170907 → 血統追加 0.2608869015。研究受入済み |
| M7 | 2026-11-15東京12R race_key=05265412、18/18全頭研究統合v0.2/v0.3の決定的再演、近親75頭/375観測（285ゼロ）、新聞18/18照合と既存情報非干渉の監査受入 |

重要：M6-Rの2016–2025年次UKC/KYIはユーザー受入の提供元同等性前提で研究利用可。原配信日時・バイト一致の独立証明を再び歴史研究の必須条件としない。これは本番予測の独立as-of認証でも、実RaceNote改善/ROIの証明でもない。旧CONTEXTのM6一括BLOCKED表記より[11/18正式決定](BRDB_M6_HISTORICAL_EQUIVALENCE_POLICY_DECISION_20261118.md)と[#2395](https://github.com/yukki0113/GPT/issues/2395)の新定義を優先する。

詳細な過去の数値と監査証跡は[旧マイルストーン管理文書](BRDB_MILESTONE_RECONCILIATION_20261116.md)に保存。完了済み範囲の再実行は必要な回帰・入力変更・新しい検証目的がある場合だけ。

## 2. 再開地点（11/24確認）

- [PR #2655](https://github.com/yukki0113/GPT/pull/2655): Draft、未merge。branch `brdb/research-cross-discovery-v02-20261119`、確認HEAD `61c565d8eda27404ce05751f22aff6e423fc763f`。馬場横断発見v0.1–v0.6とprivate表示projection候補。
- v0.6：良/稍重/重/不良、父・母父・配合の別lane。実東京12Rで主要観測78、選別127、方向一致17。private近親接続14件/7頭、`PASS_RESEARCH_ONLY`。近親の馬場状態は未確認、lane間の独立支持は認定しない。
- 最新HEADの[BRDB CI](https://github.com/yukki0113/GPT/actions/runs/44664013534)と[横断CI](https://github.com/yukki0113/GPT/actions/runs/44664013519)はPASS。表示projectionは実データ受入未実施。
- [PR #2643](https://github.com/yukki0113/GPT/pull/2643): OPEN（非Draft）、未merge。血統モーダルUI候補。実データ接続・実機表示・公開未承認。
- [#2628](https://github.com/yukki0113/GPT/issues/2628): M7 A–G受入済み、H（解釈・consumer・昇格）未完。今後Cで追跡。
- [#2395](https://github.com/yukki0113/GPT/issues/2395): M6-P ACTIVE/未測定。今後Dで追跡。
- [#2637](https://github.com/yukki0113/GPT/issues/2637)/[#2638](https://github.com/yukki0113/GPT/issues/2638): 新聞schemaの既存欠陥。研究とは別。offline修正候補で326→0エラー、正式修正は未承認。
- 11/23 [#2720](https://github.com/yukki0113/GPT/pull/2720) merge済み。wheel-first GPT DuckDB実行が標準。

## 3. 新マイルストーン（未来の作業のみ）

A–Dは研究管理区分。既存Issue/PRのID、旧契約、完了判定を上書きしない。各サブ項目は未完了部分だけを対象とする。

### A. 血統発見研究（旧M4/M5の拡張）

| ID | 作業 | 完了条件 |
|---|---|---|
| A1 | v0.6研究候補の整合性・受入整理 | latest mainとの差分、実データreceipt、CI、契約を確認し研究候補のPR状態を整理 |
| A2 | 距離・芝ダ・馬場・競馬場/コースの条件変更研究 | 既走実績と条件変更を分離した母集団、比較baseline、全頭根拠、欠損/低Nを実測 |
| A3 | 成長時期・早熟性・配合・近親の条件分析 | Bの初戦研究と共通資産を再利用し、重複・対象条件・時系列を保持 |
| A4 | 祖先・クロス・地域/内包血統の残件 | 未解決canonical ID・alias・世代欠損を実査、仮説を検証し未解決を明示。全祖先完全化を他研究の必須条件にしない |
| A5 | 発見仮説の再現検証 | 探索期間と確認期間を分離、候補数・多重比較/依存・不確実性を記録。効果なしも研究完了可 |

### B. 新馬戦・初出走馬専用研究（新規）

| ID | 作業 | 完了条件 |
|---|---|---|
| B1 | データ適格性監査 | JRA/JRDBレース区分と個体初出走を分離。2016–2025年の抽出可否、履歴左端/海外等の初出走不明、件数、ID、欠損、時点を監査 |
| B2 | 父産駒の初戦成績 | 初出走/新馬戦を区別し芝ダ・距離・時期等の条件別成績と母集団を固定 |
| B3 | 母父・配合の初戦成績 | B2と同一条件比較、低N/重複明記 |
| B4 | 兄姉・母方近親の初戦/早期成績 | canonical relation、対象時点以前の結果、欠損、重複scopeを保持 |
| B5 | 新馬戦専用全頭レビュー | 非採点candidate schema、実PACI全頭E2E、再現性、NO_SAMPLE等の検査 |
| B6 | JPDBとの接続設計 | 実際の騎手DB契約確認、独立lane、同一race/horse照合、欠損と依存検査。勝手に騎手DB実装を変更しない |
| B7 | 新馬戦研究予想の比較 | 無情報等の事前固定baselineと血統/騎手/併用を別holdoutで比較。カバレッジと性能を区別。現行Zは承認まで維持 |

### C. 血統レビュー・競馬新聞（旧M7 H/M8表示）

| ID | 作業 | 完了条件 |
|---|---|---|
| C1 | v0.6→private表示JSON実データ受入 | #2655 projectionをレビューし、重複する5 scopeの合算を独立成績として表示しない。単一明示scopeまたはscope別表現へ整理。05265412で2回byte一致、Draft2020-12検証 |
| C2 | 実新聞・UI guard接続 | #2643の実JS guard、18/18 identity、in-memory添付のみ、既存addon非干渉 |
| C3 | モーダル表示確認 | Personal/Momotaro、欠損・低N・研究表示、実機確認。既存新聞schema残件は別途承認された修正で解消 |
| C4 | 総評・Tips | 根拠IDから追跡可能な説明、観測/仮説/検証済みを分離。未検証適性・予想印・推奨を生成しない |
| C5 | 表示内容承認 | ユーザーが文言・掲載項目・実機表示を確認 |
| C6 | 正式連携・公開判断 | 独立したconsumer回帰と公開承認。研究用参考表示と予測利用を別ゲートとし、M6-P未測定を理由に記述研究を無期限停止しない |

### D. RaceNote予測価値研究（旧M6-P/M8予測）

| ID | 作業 | 完了条件 |
|---|---|---|
| D1 | 比較設計を事前固定 | 同一race/date/field split、非血統baseline、血統/騎手追加、欠損、確率評価指標、時点・holdoutを定義 |
| D2 | 既走馬の追加効果実測 | RaceNote相当時系列再演または事前ペア保存で比較、log loss/Brier等・校正・不確実性を記録。印を事後的に勝率へ変換しない |
| D3 | 市場との評価差 | 人気帯、評価集中、価格時点固定、ROIは予測精度と別検証 |
| D4 | 血統＋JPDB統合比較 | 過去走のみ、血統のみ、騎手のみ、血統＋騎手、過去走＋各lane、全laneの比較。B7は新馬戦独立評価 |
| D5 | RaceNote接続・採否判断 | 改善なしでも研究完了可。採用条件と回帰確認、明示承認。CURRENT、印、自信度、本番予想を自動変更しない |

## 4. 再開順序・実行指示

1. **最初に A1/C1/C2**：前回の候補の区切り。#2655/#2643の実際のHEADとmain差分、既存private Library `/BRDB/M7/` 入力の可用性、SHAを確認。最新ソースでprivate表示接続を受入。旧完了済み研究を丸ごと再実行しない。
2. **B1を次の独立研究として開始**（Cの実機承認待ち等で止めない）。その後B2〜B5。
3. A2〜A5を順次拡張。C3〜C6は表示承認の進捗に合わせ並行。
4. B6/B7、D1〜D5へ。D1の設計は先行可能。長期の将来データ蓄積だけを必須としない。

作業報告は新ID、実施範囲、PASS/PARTIAL/BLOCKED/NOT EXECUTED、入力/出力SHA、source commit、次の未完了項目を短く更新する。今後の作業管理は本書、詳細仕様は基本設計・個別契約を参照。

## 5. 起動・実行環境・安全境界

- 最新mainのroot [.gpt/GITHUB_OPERATION_POLICY.md](../../../.gpt/GITHUB_OPERATION_POLICY.md)、[BRDB README](../README.md)、[CONTEXT](../.gpt/CONTEXT.md)、[WORKFLOW](../.gpt/WORKFLOW.md)、基本設計、対象source/tests/Issue/PRを確認。
- DuckDB/Parquetは共通 [Data Storage README](../../../tools/data-storage/README.md)、[runtime registry](../../../tools/data-storage/config/chatgpt_offline_runtime_v1.json)、[Phase 2 runbook](../../../tools/data-storage/docs/JRDB_CHATGPT_OFFLINE_RUNTIME_PHASE2_20261123.md) とbootstrapを使用。既存適合venvのcheck-depsを優先。Python 3.13 Linux x86_64で依存不一致ならnative Driveの承認済み3-wheel bundleをID/size/SHA照合して隔離venvへoffline導入。非対応時は通常pinned repair、その後条件付きfallback。Actions-nativeは維持。wheel成功≠BRDB E2E成功。
- Git正本module、JRDB parser、共通storageを再実装しない。個体はJRDB horse_id、race_key/horse_no厳格照合、馬名fallbackなし。
- private馬別データ・JRDB有料データ・鍵をGit/公開Issue/公開Actions artifactへ出さない。
- 時点・結果リーク・低N・条件重複・依存を保持。研究候補は `prediction_safe=false`、`production_authorized=false`、必要に応じて `AS_OF_UNVERIFIED`。
- 本番RaceNote/BRDB CURRENT/新聞/PWA、凍結v0.1/v0.2/v0.3契約を無断変更しない。未完PRのmergeや公開は各ゲートの承認後。
- 次スレッドは本書を読んだ後、最新main/対象branchを再取得し、A1/C1/C2から再開する。環境・成果物がスレッド間で永続すると仮定しない。

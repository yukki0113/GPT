# JRDB thread handoff

Last reviewed: 2026-09-13

この文書は、会話量上限・スレッド分割・担当変更後に **現在のJRDBプロジェクトを短時間で安全に再開するためのbootstrap** です。

固定SHAや一時的な件数を正本化する文書ではありません。再開時は必ず最新 `main` を確認し、対象subsystemのcurrent contract / sourceを読み直してください。

## 1. Restart order

新スレッドでは次の順に確認します。

1. `horse-racing/jrdb/README.md`
2. `horse-racing/jrdb/.gpt/HANDOFF.md`（この文書）
3. `horse-racing/jrdb/.gpt/CONTEXT.md`
4. `horse-racing/jrdb/.gpt/WORKFLOW.md`
5. latest `main` HEAD
6. 対象subsystemのcurrent docs / contract / audit / source / focused tests

RaceNote開発を再開する場合は、追加で次を読む。

1. `horse-racing/jrdb/docs/racenote/README.md`
2. `horse-racing/jrdb/docs/racenote/FORECAST_GEN0_PLAN.md`
3. legacy確認が必要な場合だけ `horse-racing/jrdb/docs/racenote/legacy/README.md`

会話メモだけを根拠にsourceを変更しません。逆に、古いhandoffや古いdesign docが最新sourceと矛盾する場合は、latest source + current contractを優先します。

## 2. Current architecture snapshot

```text
JRDB Raw / PACI
  -> Common Raw Reader
     ├─> Analysis Lite -> Stats Mart -> Fact Lite / condition-summary PWA
     ├─> RaceNote base -> history enrichment -> RaceNote v1.0 -> Reader View
     │                                                 -> GPT Forecast Gen0
     │                                                    -> pre-result audit / freeze
     │                                                    -> result join / evaluation
     ├─> Eval adapters
     ├─> Canonical / research materialization
     └─> Edge Current Facts -> Edge Matcher
                               -> edge_matches
                                  -> Forecast evidence where explicitly used
                                  -> Newspaper / PWA special memo
```

大きな原則は、**Raw解釈・evidence生成・予想判断・表示・結果評価を分離すること** です。

## 3. Current EdgeDB default

現行は EdgeDB v0.2 STANDARD servingです。

- operational current runner: `src/run_jrdb_edge_match_current_v0_2.py`
- normal default: `STANDARD`
- low-level matcher: `src/jrdb_edge_matcher_v0_2.py`
- low-level default: `CONFIRMED_ONLY` のまま。これは意図したfail-safe
- normal unified serving input: `edge_serving_catalog_v0_2.jsonl`
- current contract: `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md`
- activation audit: `docs/JRDB_Edge_v0_2_STANDARD_Activation_Audit_20260911.md`

絶対に混同しないこと:

- `SUGGESTIVE` はRegistry昇格ではない。通常 `registry_status=REJECTED` のまま
- ACTIVE thresholdをSUGGESTIVEのために緩めない
- Performance evidence と Value evidence は別channel
- Performance-positiveを「馬券妙味あり」と言い換えない
- CONFIRMED / SUGGESTIVEやoverlap Edgeのstrength・ROI・lift・qを加算しない
- current matchingはpre-race exact match。SED結果、着順、払戻、最終オッズ等を混入させない
- consumer側でEdge条件を再実装しない
- v0.1 matcherはbackward compatibility資産。v0.2仕様を直接混ぜない

## 4. RaceNote current prediction direction

RaceNote authoritative bundleは観測データとprovenanceを渡す層です。Reader Viewもprediction modelではありません。

現在の予想研究系は **RaceNote Forecast Gen0** です。

正本方針:

- `docs/racenote/README.md`
- `docs/racenote/FORECAST_GEN0_PLAN.md`
- origin reference: `docs/RaceNote_Prediction_Handoff_v0_1.md`

Gen0では、RaceNote v1.0 / validated Reader ViewをGPTが読み、レース条件、基礎能力、条件適性、展開、調教・状態、近走、長期履歴、補助統計、coverageを横比較して予想します。

固定weightや単一gateをcurrent defaultにしません。

```text
pre-race evidence
 -> GPT comparison
 -> prediction
 -> pre-result self-audit
 -> immutable freeze
 -> result acquisition
 -> post-race reading audit
 -> 原則約50R単位の改善
```

### Legacy boundary

過去のv0.2 control / v1.1-P gated predictionは、historical reproducibility / benchmarkとして保持しますがcurrent defaultではありません。

特に以下をGen0の隠れた決定規則として使わないこと:

- top5固定候補
- Good差 `<= 0.04`
- stronger Edge polarityによる機械的な◎昇格
- v1.1-Pの順位をGen0初期順位として無条件継承

詳細は `docs/racenote/legacy/README.md`。

旧系統からは、pre-race guard、as-of boundary、provenance、hash、immutable freeze、result-after-freeze、presentation immutable check等の**検証インフラ**を再利用してよい。予想ロジックと研究インフラを分ける。

### Existing presentation assets

`src/racenote_prediction_presentation_v0_2.py` 等は、freeze済みの旧Edge axis decisionを読者向けへ投影する既存表示資産として残します。

current reader contract:

`docs/RaceNote_Presentation_Comment_Contract_v0_2.md`

これは既存consumer / historical freezeの表示互換に関するcontractであり、v1.1-PをGen0のcurrent prediction policyへ戻す根拠にはしません。

表示層は予想を再計算しません。

## 5. Newspaper / PWA Edge boundary

主要module:

- `src/jrdb_newspaper_merge_edge.py`
- `src/jrdb_newspaper_edge_adapter.py`
- `src/jrdb_newspaper_merge_external.py`
- `src/jrdb_newspaper_publish_current.py`

Newspaperはmatcher outputを受け取るconsumerです。Edge条件を再判定しません。

`jrdb_newspaper_edge_adapter.py` はdisplay boundaryです。

- raw condition / `display_text` / evidenceはaudit用に保持
- reader-facing condition / memoだけを人間向けへ翻訳
- 系統code等の内部codeは、masterで解決できる場合は読者名へ変換
- unknown codeは意味を捏造せずfail-safe / fallback

join identityは `race_key / race_horse_key / horse_no` を中心に扱います。

PWA / Newspaperの都合でForecast policyを決めません。predictionを先にfreezeし、consumerはそのcontractを表示します。

## 6. Post-race Analysis / Mart / Fact Lite

開催後更新は一つの世代として考えます。

```text
completed race results
  -> Analysis date-level update
  -> Analysis validation / canonical save
  -> affected Stats Mart refresh
  -> Fact Lite regenerate + validate + publish
  -> condition-summary PWA current generation update
```

Analysisだけ最新化し、条件別集計PWAを旧Analysis世代に残さないことを標準とします。

認証済みJRDB取得・正式artifact chain・publication証跡が必要な部分は `.gpt/WORKFLOW.md` の Route D を使います。既取得入力だけで完結する検証・集計はRoute Cを優先します。

## 7. Stable data rules

- Fixed-length interpretation: `src/jrdb_raw.py`
- `race_key` は文字列保持。日部分hexをdecimalへ勝手に正規化しない
- `race_horse_key = race_key + horse_no`
- `result_key = blood_registration_no + YYYYMMDD`
- optional joinは原則LEFT / fail-closed
- current predictionはpre-race only
- historical reconstructionはas-of boundaryを必ず守る
- Canonical / Archive / Reader ViewはRaw source truthを置換しない

JRDB codeの意味はマスタコード定義を参照し、数字だけをreader-facing proseへ直接出さないよう確認します。

## 8. Execution routing

詳細は `.gpt/WORKFLOW.md`。現在の標準は以下です。

- **A Read / Audit**: GitHub read/search/fetch。確認目的のIssue不要
- **B Git Change**: source/test/docs/configのUTF-8変更をlatest mainへdirect write
- **C Pure Deterministic Execution**: focused tests、既取得artifact監査、hash/count/join/report
- **D Actions-Native**: Secrets、長時間Full build、immutable freeze/publication、正式run evidence

`[gpt-git-update]` を通常のテキスト修正経路へ戻しません。

旧v1.1-P TRUE_FORWARD workflowがActions-nativeであることと、今後のすべてのRaceNote作業をIssue/Actions経由にすることは別です。新しいGen0作業でも、実行要件に応じてA/B/C/Dを選びます。

## 9. Before changing code or docs

必ず:

1. latest mainを取得
2. path存在確認
3. current content / blob SHA取得
4. relevant contract / sourceの現行状態確認
5. 最小差分を設計
6. write後readback
7. focused test / regression / deterministic audit
8. default・contract・entrypoint・handoff情報が変わった場合はこの文書も更新対象か判定

## 10. Documents that can become stale

次はcurrent truthと決めつけません。

- 日付付きaudit
- 過去Issue本文
- old handoff
- `Status: IN PROGRESS` の旧development note
- fixed artifact ID / run ID / commit SHA
- exploratory counts

これらは履歴・再現性証跡として重要ですが、運用defaultはlatest source / current contractで再確認します。

2026-09-13のv1.1-P TRUE_FORWARD freeze等もhistorical immutable evidenceです。後からGen0形式へ上書きしません。

## 11. What a new thread should be able to answer after bootstrap

最低限、次を再質問せず判断できる状態を目標とします。

- 何がGit正本で何がDrive/Release正本か
- Rawのoffsetをどこで解釈するか
- RaceNote data layerとpredictionの責務境界
- current RaceNote prediction researchがForecast Gen0であること
- v1.1-Pはlegacy logicで、検証インフラだけ再利用可能であること
- EdgeDBのSTANDARD / CONFIRMED_ONLYの違い
- SUGGESTIVEがACTIVEではないこと
- PerformanceとValueを混ぜないこと
- Newspaper/PWAがEdge条件を再計算しないこと
- 読者表示と監査rawを分離すること
- post-race更新後にFact Lite/PWAまで同一世代へ進めること
- GitHub Actionsを使うべき作業とChatで直接行う作業の違い

この項目のどれかが将来変わった場合、source変更だけで終わらせず、README / CONTEXT / HANDOFF / current RaceNote docs / contractのどこへ反映すべきかを同時に確認してください。

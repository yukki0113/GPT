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
6. 対象subsystemのcurrent contract / audit / source / focused tests

会話メモだけを根拠にsourceを変更しません。逆に、古いhandoffや古いdesign docが最新sourceと矛盾する場合は、latest source + current contractを優先します。

## 2. Current architecture snapshot

```text
JRDB Raw / PACI
  -> Common Raw Reader
     ├─> Analysis Lite -> Stats Mart -> Fact Lite / condition-summary PWA
     ├─> RaceNote base -> history enrichment -> RaceNote v1.0
     ├─> Eval adapters
     ├─> Canonical / research materialization
     └─> Edge Current Facts -> Edge Matcher
                               -> edge_matches
                                  -> RaceNote prediction/presentation
                                  -> Newspaper / PWA special memo
```

大きな原則は、**Raw解釈・evidence生成・予想判断・表示を分離すること** です。

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

## 4. RaceNote / prediction presentation boundary

RaceNoteは観測データとprovenanceを渡す層です。Reader Viewもprediction modelではありません。

Edge-aware prediction presentationは `src/racenote_prediction_presentation_v0_2.py` が担当し、すでにfreezeされた印・軸判断を説明するだけです。

current reader contract:

`docs/RaceNote_Presentation_Comment_Contract_v0_2.md`

読者向けの基本翻訳:

- internal `good` -> `基礎総合評価`
- axis guard / eligible -> `逆転許容圏内 / 圏外`
- Performance Edge polarity -> `プラス / 中立 / マイナス`
- axis change -> `◎へ変更`
- unchanged -> `◎据え置き`

各馬コメントは **その馬固有の強み・リスク・印の理由** を中心にします。レース短評は **レース全体の選定方法・必要なら軸逆転の説明** を担当します。同じ逆転mechanicsを全馬へ繰り返しません。

`good`は複合基礎評価です。能力、適性、状態、JRDBゴール予測等、すでにbaseへ含まれるcomponentをEdge後の独立voteとして再加算・二重説明しません。

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

## 11. What a new thread should be able to answer after bootstrap

最低限、次を再質問せず判断できる状態を目標とします。

- 何がGit正本で何がDrive/Release正本か
- Rawのoffsetをどこで解釈するか
- RaceNoteとpredictionの責務境界
- EdgeDBのSTANDARD / CONFIRMED_ONLYの違い
- SUGGESTIVEがACTIVEではないこと
- PerformanceとValueを混ぜないこと
- Newspaper/PWAがEdge条件を再計算しないこと
- 読者表示と監査rawを分離すること
- post-race更新後にFact Lite/PWAまで同一世代へ進めること
- GitHub Actionsを使うべき作業とChatで直接行う作業の違い

この項目のどれかが将来変わった場合、source変更だけで終わらせず、README / CONTEXT / HANDOFF / contractのどこへ反映すべきかを同時に確認してください。

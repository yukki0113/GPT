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

### Current artifact retention

Analysis LiteのDrive正本は**current世代だけ**を通常保持する。新Analysisを所定の共有フォルダへuploadし、filename・size・SHA-256・ZIP/SQLite検査を再確認したうえでFact Lite/PWA公開が成功した場合、直前のcurrent Analysisを削除する。失敗時は旧currentを残し、切替を行わない。

Stats MartやRaw、監査artifact、RaceNote Archiveなど、再現性のため明示的に保持する資産にはこの削除規則を適用しない。

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
- 明示的な日次PACI/SED/HJC取得依頼を、既存Raw再利用と区別して安全に実行できること

この項目のどれかが将来変わった場合、source変更だけで終わらせず、README / CONTEXT / HANDOFF / current RaceNote docs / contractのどこへ反映すべきかを同時に確認してください。

## 12. Daily JRDB Raw acquisition / delivery thread

この運用は、ユーザーからの短い依頼、たとえば「0913のPACIを取得」「0905・0906のSEDを取得」に対して、JRDB公式Rawを取得・検証し、ユーザーへinner ZIPを返す定型作業を想定する。

### Scope and intent

- 明示的に「PACI / SED / HJCを取得してください」と依頼された場合は、**fresh official acquisition request** と解釈する。
- この場合は `docs/JRDB_2026_Raw_Drive_Reference.md` の「既存Drive Rawを優先する」という下流処理向け再利用原則より、ユーザーのfresh取得意図を優先し、JRDB upstreamをRoute Dで取得する。
- 一方、Analysis / Eval / RaceNote / research等の処理が「入力として2026 Rawを必要とする」だけなら、Drive inventoryを先にresolveし、既存Rawを再利用する。
- ユーザーが明示的にDrive再利用を指定した場合は、その指定を優先する。
- Raw取得スレッドでは、RaceNote生成、Analysis更新、Stats Mart更新、Edge matching、Eval enrichment等を**自動で続行しない**。追加依頼がある場合だけ別工程へ進む。

### Source / workflow

- PACI downloader: `src/fetch_jrdb_paci.py`
- SED / HJC daily downloader: `src/fetch_jrdb_history.py`
- Actions entrypoint: `.github/workflows/jrdb_raw_fetch_issue.yml`
- Issue prefix: `[JRDB_RAW_FETCH_REQUEST]`
- Secrets: `JRDB_USER`, `JRDB_PASSWORD`

PACIは `fetch_jrdb_paci.py --date YYYYMMDD --out-dir <dir>`、SED/HJCは `fetch_jrdb_history.py --date YYYYMMDD --kinds <KIND> --output-dir <dir>` が正本CLI。

### Request contract

Issue bodyはraw JSON。

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI"]
}
```

同一日の複数kindを取得する場合は、可能なら1 Issueへまとめる。

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI", "SED"]
}
```

異なる日付は別requestとする。

Issue作成前にはlatest mainと `.github/workflows/jrdb_raw_fetch_issue.yml` のparser / accepted kindsを確認する。request JSONは機械的にserializeし、余計なMarkdown fenceをIssue bodyへ混ぜない。

### Success contract

成功コメントmarker:

```text
JRDB_RAW_FETCH_RESULT
```

最低限、次を確認する。

- top-level `status == "success"`
- `manifest.date` が依頼日と一致
- requested `kind` が全てmanifestに存在
- `file_name` が対象kind/dateと一致
- `size_bytes > 0`
- `sha256` が64桁hex
- `members` が空でない
- `run_id` と `artifact_name` が取得可能

### Artifact recovery and local validation

Actions artifactは搬送用outer ZIPであり、ユーザーへ返す標準成果物はその中のrequested inner ZIP。

現在のworkflow layout:

- PACI: artifact展開rootに `PACIyymmdd.zip`
- SED: artifact内 `SED/SEDyymmdd.zip`
- HJC: artifact内 `HJC/HJCyymmdd.zip`

artifact回収後、Chat側で次をPure Deterministic Executionとして行う。

1. outer artifactを展開
2. requested inner ZIPを特定
3. ZIPとして読めることを確認
4. `zipfile.testzip()` 相当でcorrupt memberがないことを確認
5. member一覧を確認
6. local file sizeをmanifest `size_bytes` と照合
7. local SHA-256をmanifest `sha256` と照合
8. ユーザー向けに `/mnt/data/<inner ZIP名>` 等へflattenして返却

ユーザーへ通常返すのは `PACIyymmdd.zip` / `SEDyymmdd.zip` / `HJCyymmdd.zip` であり、`jrdb-raw-YYYYMMDD.zip` outer artifactではない。

### Failure / retry rule

- generic failure commentだけを見て「未公開」「データなし」と推測しない。
- failed step / job logを確認し、認証、HTTP status、parser、ZIP validation、artifact upload等のどこで失敗したかを特定する。
- `404` 等、upstream不在を直接示す観測がある場合だけ、その事実を報告する。
- 同一requestをblind rerunしない。latest mainとfailed stepを確認してからretryする。
- retry時も、取得そのもの以外の確認・SHA比較・ZIP検査のために追加Issueを作らない。

### Delivery report

正常時の最終報告は簡潔でよいが、最低限次を含める。

- 対象日 / kind
- inner ZIPへのダウンロードリンク
- ZIP破損検査結果
- member数またはmember確認済みである旨
- SHA-256
- Actions manifestとの一致

このsectionは、日次Raw取得専用スレッドへ引っ越した際に、過去会話を参照しなくても同じ安全な取得・検証・返却手順を再現するための運用正本とする。

# JRDB Newspaper — current PACI-only operation

## Phase 3 retirement boundary — Issue #2334

EdgeDB/Training Edge専用のworkflow・計算/取込/preview・config・専用テストを通常の実行場所から撤去し、`horse-racing/jrdb/archive/retired-edge-training/README.md` に証跡を集約した。旧ファイルを直接起動・復元しない。RaceNoteの独立した凍結実験adapter、馬コース適性のcanonical utility、RRDBのprevious-start ledgerは現行依存のため保持する。独立JRDB追切/training_indexと廃止Training Edgeを混同しない。

通常NewspaperはPACI-onlyで起動し、Eval/RaceNote/RRDB/イルカ/桃太郎の既存経路を維持する。`jrdb_newspaper_retired_sources.py` と旧データ非伝播テストは恒久保持。Release/Drive/immutable revisionおよびActions履歴は削除しない。全域監査と本番確認の範囲は `horse-racing/jrdb/newspaper/PHASE3_AUDIT.md` を参照。

日次運用は `.gpt/DAILY_WORK_CONTRACT.md` と `DAY_REQUEST_V2.md` を参照。以下は現行のPACI-only経路です。旧資産はarchiveおよび `PHASE3_AUDIT.md` に分離済みです。

## Module boundary

Status: OPERATIONAL / DAILY PACKAGE + EXTERNAL MERGE + CURRENT PUBLISH + PWA DELIVERY

このディレクトリは、JRDB PWA向け「自分用競馬新聞」の日次生成・外部source merge・配布契約を独立管理するためのmodule boundaryです。

## PWA display data limits (2026-10-12)

両PWAの「けん」ヘッダは検証済み RaceNote レース自信度だけを表示し、値がなければ `–`（未提供）を表示する。2026-10-12 の frozen `records.json` はレース自信度を持たず、正式な `jrdb_newspaper_kensho_merge_issue.yml` の疎形式変換も空欄とするため、この日の実データは個人版・桃太郎版とも `–` となる。画像用出力や他 revision から A/B/C を補わない。将来、正本に確定値が追加された場合は、正式な変換・merge 経路の確認と実データでの受け入れテストが必要。

## Design source of truth

- `../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- `../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`
- `../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- `../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- `.gpt/WORKFLOW.md`
- `.gpt/REQUEST_CONTRACT.md`
- `.gpt/DAILY_WORK_CONTRACT.md`
- `.gpt/WORK_THREAD_BOOTSTRAP.md`
- `.gpt/HANDOFF.md`
- `../../eval/docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`

日次Workの通常運用契約は `.gpt/DAILY_WORK_CONTRACT.md` を正本とし、新しい専用Workスレッドの起動には `.gpt/WORK_THREAD_BOOTSTRAP.md` を使用します。

会話量上限やスレッド移動からの再開には `.gpt/HANDOFF.md` を使用します。日付付きの過去auditや固定SHAは証跡であり、current truthにはしません。再開時は必ずlatest mainのcontractとsourceを優先します。

## Architecture boundary

NewspaperはRaceNoteの派生consumerではありません。

禁止する依存:

```text
RaceNote v1.0 bundle -> Newspaper base
racenote_jrdb.py -> Newspaper base
racenote_history_engine.py -> Newspaper history
その他 racenote_* の内部ロジック -> Newspaper JRDB base/history
```

基本構造:

```text
JRDB Raw / PACI
  -> neutral JRDB layer
     -> Newspaper Base / history
     -> external addon merge
        - Eval
        - RaceNote prediction output
        - keibailuka
        - RRDB recommendation
```

RaceNoteの予想結果・印・短評は外部addonとして `addons.racenote_prediction` とrace-level noteへmergeできます。RaceNote内部実装はNewspaper Base/historyの依存にしません。

## Implemented data pipeline

- `../src/jrdb_newspaper_build.py`: 1レースNewspaper Base生成
- `../src/jrdb_newspaper_day_build.py`: 1日分のmanifest + race JSON群生成
- `../src/jrdb_newspaper_merge_external.py`: 外部sourceのnamespace-safe merge + day-package生成
- `../src/jrdb_newspaper_publish_current.py`: Drive canonicalからCurrent Publish候補を検証・配布
- `../src/audit_jrdb_newspaper_poc.py`: real-data PoC監査
- `../pwa/newspaper.html`: Newspaper PWA
- `../pwa/newspaper-day.js`: 1日パッケージ読込・OPFS保存・レース切替
- `../pwa/newspaper-v9.js`: Eval分析コメントを持つEval値だけのモーダル表示

Base/historyはCommon Reader / neutral JRDB accessから生成し、最大8走を保持します。初期表示3走、切替5走/8走。外部source欠損はBase失敗にせずnull/PENDINGで保持します。

## Retired EdgeDB / Training Edge input boundary

EdgeDB STANDARD/v0.5および旧Training Edge `my_index` は日次要求・merge・配信から廃止済みです。旧入力CSVや `--my-index-csv` を新規に取り込まず、旧Currentから廃止データを引き継ぎません。旧形式の読み取り互換と非伝播guardは維持します。独立したJRDB追切・`training_index` は別機能です。

## Eval PWA analysis comment

Eval側が条件判定・注目馬選定・コメント作成を所有します。Newspaperは `YYYYMMDD_Eval_PWA提出CSV_v0_1.csv` をexact joinして、分析6列を `addons.eval.analysis` へ透過的に格納するだけです。

- `eval_analysis_codes` は `;` 区切りをJSON arrayへ変換する
- コメントなしは `analysis: null`
- `NONE / WATCH / MATCH` をNewspaper/PWA側で再判定・独自解釈しない
- `date + venue_code + race_no + horse_no`、horse_name完全一致、`join_status == MATCHED` の監査を維持する
- auditではEval merged rows、analysis comment rows、status別件数を記録する

詳細契約は `../../eval/docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` を優先します。旧形式のEval完成CSVも利用可能で、その場合は `analysis: null` とします。

## 2026-09-05 full-day acceptance

2026-09-05の札幌・中山・阪神36Rを用いた1日分実データテストを実施済みです。

- 36R / 455頭を日次生成
- detailed history + Analysis compact historyを統合
- Eval完成CSV: 455/455 exact match
- keibailuka: 22件中20件 exact match、2件は推測補正せずunmatched保持
- 1日パッケージJSONをiPhoneへ保存
- 機内モードでレース切替・過去走詳細モーダル表示を確認
- 外部情報表示を確認
- 実機で十分に快適な表示速度を確認

この09/05データをv0.1の実機受入基準として扱います。

## External source ownership

- Eval merger: `addons.eval`（WATCH/MATCHと分析コメント）
- RaceNote prediction merger: `addons.racenote_prediction` + race-level note
- RRDB recommendation merger: `addons.rrdb_recommendation`
- keibailuka merger: `addons.keibailuka`
- 桃太郎member predictions: 独立projectionの所有namespace

join keyは `date + venue_code + race_no + horse_no` のexact identity。馬名の近似・推測joinを標準経路へ導入しません。廃止したEdgeDB/Training Edge namespaceを新規生成しません。

## GitHub routing standard — 2026-09-10

このsubsystemではルート/JRDBのGitHub運用方針に従い、Issue駆動を既定にしません。

- Read / Audit: GitHub read/search/fetchを直接使用
- Git Change: UTF-8 source/test/docs/config/workflowはGitHubへdirect commit
- Pure Deterministic Execution: 取得済みPACI/Analysis/CSV/JSONに対するbuild・merge・schema validation・SHA・集計はGPTローカル実行
- Actions-Native: JRDB Secretsを使う公式データ取得、長時間/大容量、artifact chain、immutable freeze、正式監査run、Pages deployment等のみ

PACIを既に取得できている場合、Newspaper builderを動かすだけのためにIssue / Actionsを起動しません。PACIが未取得で認証取得が必要な場合だけ、ActionsでJRDB公式取得を行い、取得後のbuild/mergeは原則ローカルへ戻します。

## Routine Work target

専用Workスレッドでは、通常ユーザーは次の1文だけを指示します。

```text
MMDDの競馬新聞用JSONを作成し、アップロードしてください。
```

詳細な通常運用契約は `.gpt/DAILY_WORK_CONTRACT.md` を正本とします。

要点:

- 添付 -> File Library -> Drive canonical -> verified artifact の順で入力をresolveする
- PACI / JRDB RawをBase必須sourceとする
- Eval / RaceNote prediction / RaceReviewDB recommendation / keibailuka等の独立sourceをoptional addonとして扱う
- optional addonが未着でも処理を止めず、その時点の完成JSONを正式revisionとして保存・公開する
- source状態は `READY / NOT_FOUND / ERROR / NOT_EXPECTED` で報告する
- 同日更新は既存JSONへの直接追記ではなく、verified inputsから再構成してimmutable revisionを上げる
- 遅着sourceは次revisionへidempotent mergeし、旧revisionを保持したままcurrent pointerを更新する
- ユーザーの「アップロード」は通常、Drive canonical保存 -> current更新 -> Current Publish -> Pages反映確認までを含む

標準処理:

1. target date確定
2. 添付 / Library / Drive / 既存artifactから入力をresolve
3. PACIがなければActions-Nativeで公式取得のみ実施
4. GitHub `main` の正本moduleを取得してローカルで日次Base生成
5. 利用可能なEval / RaceNote prediction / RRDB / keibailuka等の独立sourceをmerge
6. schema / key / headcount / as-of / source coverage / SHA / idempotenceを監査
7. day-package.jsonを生成
8. immutable revisionとしてDrive canonical保存
9. current pointer更新 / Current Publish / Pages反映
10. 各sourceの状態と成果物を報告

ローカル生成物には可能な限り `source_commit`, module/source SHA, input SHA, generated_at, output SHAを残し、正本moduleの再現実行であることを追跡可能にします。

## Storage / delivery

日次生成物・JRDB Raw・PACI・秘密情報はGit管理外です。Gitはcode / schema / docsを正本管理します。

```text
Drive canonical
  -> publish
  -> GitHub Pages
  -> PWA
  -> OPFS offline copy
```

Pages deploymentそのものはGitHub Actions環境を使いますが、PWA source変更はGitHubへdirect commitし、そのpush triggerでPages workflowを起動するのを標準とします。


## RaceReviewDB recommendation comments

RRDB recommendation for Newspaper/PWA is intentionally reader-facing and sparse.

Canonical handoff:
`../docs/RaceReviewDB_Newspaper_Handoff_v0_1.md`

Newspaper consumes only exact target identity + the RRDB-supplied short comment.
It does not expose or recompute RRDB signal IDs, signal count, raw strength or
S/A grade. Matched horses are projected to `addons.rrdb_recommendation`.

PWA presentation reuses the existing RaceNote mark cell:
- existing RaceNote mark -> keep the mark and make it tappable;
- no RaceNote mark -> display `注` and make it tappable;
- modal -> preserve any RaceNote horse comment and add the RRDB short comment.

No standalone RRDB mark column is created.

### Retired-source verification

通常NewspaperではEdgeDB Query/Previewを起動しません。新revisionのレースJSON・manifest・配信projectionに旧 `edge`、`edge_v05`、`special_memos`、`edge_matches`、`my_index` が再伝播しないことを `../tests/test_newspaper_source_retirement.py` と `PHASE3_AUDIT.md` で確認します。研究資産は `../archive/retired-edge-training/` の履歴へ分離済みです。

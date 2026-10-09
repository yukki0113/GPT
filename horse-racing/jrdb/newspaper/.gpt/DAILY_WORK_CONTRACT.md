# JRDB Newspaper Daily Work Contract

Status: OPERATIONAL CONTRACT / 2026-10-09

この文書は、専用Workスレッドから中央競馬の「競馬新聞」日次JSONを生成・保存・公開する通常運用の正本契約です。

## 1. User-facing target command

通常運用では、ユーザーは原則として次の1文だけを指示すればよいものとします。

```text
MMDDの競馬新聞用JSONを作成し、アップロードしてください。
```

Workは対象日を確定し、利用可能な入力を自律的に探索・検証し、その時点で作成可能な完全性の範囲で日次JSONを最後まで生成・保存・公開します。

外部addonの一部が未生成・未着でも、Newspaper Baseを生成できる限り処理を止めません。

## 2. Daily source set

日次Newspaperは次のsourceを扱います。

### Required base

- JRDB Raw / PACI
  - Newspaper Base / historyの土台
  - current race / runner identity / headcountを確定する必須source

### Optional addons

- independent index / 独自指数
- keibailuka / イルカブログ
- Eval
- RaceNote prediction output
- STANDARD EdgeDB Query output
- EdgeDB v0.5 production addon

### Eval PWA analysis submission

Evalのcanonical sourceとして、従来の完成CSVに加えて次を受け入れます。

```text
YYYYMMDD_Eval_PWA提出CSV_v0_1.csv
```

このCSVに分析6列がある場合は、同日の旧Eval完成CSVより、検証済みのPWA提出CSVを優先します。

- `eval_analysis_status`
- `eval_analysis_codes`
- `eval_analysis_title`
- `eval_analysis_comment`
- `eval_analysis_version`
- `eval_analysis_asof`

Eval側が注目馬選定、条件判定、`NONE / WATCH / MATCH` の意味、H1/H2等のコード、コメント内容を所有します。Newspaperは分析列を削除・補正・再判定せず、`addons.eval.analysis` へ透過的に格納します。`eval_analysis_codes` だけは入力contractどおり`;`区切りからJSON arrayへ変換します。

PWA提出CSVのanalysis contract違反は推測補正しません。Evalだけ安全に除外できる場合はEvalを`ERROR`として他sourceを継続し、Baseを停止させません。詳細は `../../eval/docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` を正本とします。

### Training Edge / 独自指数

対象日のverified `独自指数_YYYYMMDD.csv` が見つかった場合は、`jrdb_newspaper_merge_external.py --my-index-csv` へ渡します。必須列は次です。

```text
date,venue_code,race_no,horse_no,training_edge_index
```

独自指数はcomplete all-horse sourceです。`date + venue_code + race_no + horse_no` の全馬exact joinを要求し、CSV extra row・Newspaper missing row・duplicate key・非数値/非finite値はfail-closedとします。`training_edge_index` の空欄行も有効なCSV行であり、`addons.my_index.training_edge_index: null` を明示してmergeします。空欄行を未取込扱いにしたり、`0` をnull扱いにしたりしません。

Newspaperは値の再計算・補正・丸め・順位化・他指数との合成を行いません。source未発見日はoptional addonとして `NOT_FOUND`（運用上対象外なら `NOT_EXPECTED`）を記録し、Baseを停止させません。取り込んだ日はauditへ merged/value/null件数とper-race内訳、manifest/race statusへ `my_index: READY` を残します。

RaceNoteは完成済みprediction outputのみをaddonとして利用し、RaceNote bundleやRaceNote内部実装をNewspaper Base/historyへ流用しません。

STANDARD EdgeDBは `jrdb_edgedb_query.py --profile STANDARD` の照合結果をconsumer入力とし、Newspaper側で条件を再実装・再判定しません。`special_memos` は旧表示互換・監査互換のため保持してよいですが、通常PWAの旧「特注メモ」列は表示しません。

EdgeDB v0.5は日次生成時に既存frozen cohort / 既存matcherを使って照合し、馬単位の `addons.edge_v05.candidate_ids` とレース単位の `edge_v05_candidates` を生成します。PWAはこの確定済み結果だけをconsumeし、ブラウザ側でEdge条件・2026診断・ROIを再計算しません。

EdgeDB v0.5の現在のsource stateは完全対応ではないため、正常な部分対応は `PARTIAL`、完全対応は `READY`、生成またはjoin異常は `ERROR` とします。`PARTIAL` / `READY` のときだけ候補を表示し、`ERROR` ではEdge列を空欄にして他addonを維持します。

## 3. Input resolution order

対象日の各sourceは、原則として次の順で探索します。

```text
1. current Work thread attachments
2. File Library
3. Google Drive canonical storage
4. existing verified GitHub Actions artifacts / frozen artifacts
```

同一source候補が複数ある場合は、target date、revision/version、canonical key、SHA/provenanceを確認して採用します。

ファイル名が似ている、馬名が似ている等の理由だけで自動採用・近似joinしません。

## 4. Source state model

各sourceは必ず次の4状態のいずれかで報告します。

- `READY`
  - 対象日の正しい入力を発見し、検証・mergeまで完了
- `NOT_FOUND`
  - 対象日の入力がまだ見つからない、または未着
- `ERROR`
  - 入力候補は存在するが、日付・schema・key・SHA・内容不整合等により安全に採用できない
- `NOT_EXPECTED`
  - 現在の運用上、そのsource自体が生成対象外または未稼働

`NOT_FOUND` / `NOT_EXPECTED` はNewspaper Base生成を止める理由にしません。

optional addonが `ERROR` の場合も、他sourceを壊さず除外できるならそのsourceだけをERRORとして日次処理を完走します。

## 5. Hard stop policy

Hard StopはNewspaper Baseを安全に成立させられない場合に限定します。

代表例:

- PACIそのものが未取得で、公式取得も実行できない
- PACIが破損している
- target date / race identity / runner identity / headcountを確定できない
- canonical key重複等によりBaseの一意性を保証できない

PACI未取得かつJRDB認証取得が可能な場合は、Actions-Native routeで公式PACI取得を試み、その後ローカル/deterministic buildへ戻ります。

Eval、RaceNote、RaceReviewDB recommendation、keibailuka、EdgeDB、独自指数の欠損だけを理由にHard Stopしません。

## 6. Build and merge policy

標準処理は次の順です。

```text
PACI / neutral JRDB layer
  -> Newspaper Base / history
  -> canonical Analysis resolve
  -> STANDARD EdgeDB Query
  -> EdgeDB v0.5 addon
  -> available external addons merge
  -> audit
  -> day package
  -> Drive canonical save
  -> current pointer update
  -> Current Publish
  -> JRDB PWA Pages
  -> public PWA check
```

mergeはnamespace ownershipとexact-key joinを守ります。

基本canonical key:

```text
date + venue_code + race_no + horse_no
```

source固有のより強いidentity keyがある場合は、その正式contractを使用します。

他sourceの値を上書き・再解釈しません。近似馬名・推測補正による自動joinは行いません。

historical dataは必ず `history_date < target_date` とし、target raceの結果・最終オッズ等の未来情報を混入させません。

## 7. Partial completion is a valid publication

optional sourceが未着でも、その時点で安全に作成可能なNewspaper JSONを正式なrevisionとして生成します。

例:

```text
PACI       READY
Eval       READY
RaceNote   READY
keibailuka NOT_FOUND
EdgeDB     READY
my_index   NOT_FOUND
```

この状態でも日次JSONを生成・Drive保存・公開します。

ユーザーに追加ファイル到着待ちを要求して処理全体を保留しません。

## 8. Immutable revision and current pointer

同日成果物は物理上書きではなくimmutable revisionで管理します。

例:

```text
JRDB_Newspaper_20260912_DayPackage_r1.json
JRDB_Newspaper_20260912_DayPackage_r2.json
```

新しいrevision公開時は旧revisionを削除・改変せず、`current.json` 等のcurrent pointerを最新revisionへ更新します。

ユーザーが「アップロード」「UPDATE」と表現した場合も、内部では原則として次を意味します。

```text
new immutable revision
  -> Drive canonical save
  -> current pointer update
  -> publish
  -> Pages refresh
```

## 9. Late-arriving source update

同日のJSON公開後に、未着だったsourceが到着した場合は、ユーザーは自然文で追加更新を依頼できます。

例:

```text
イルカブログ分が取り込めました。09/12の競馬新聞を更新してください。
```

この場合、既存JSONへ直接追記・手編集しません。

標準処理:

```text
previous revisionで使用したverified inputs
+ newly arrived source
  -> clean rebuild / idempotent re-merge
  -> full audit
  -> next revision
  -> Drive save
  -> current pointer update
  -> republish
```

同一source versionを重複付与せず、既存sourceを欠落させず、差分sourceを安全に追加します。

新規sourceの採用によって既存READY sourceの内容が予期せず変化した場合はERRORとして差分を報告します。

## 10. Required audit

少なくとも次を監査します。

- target date
- venue / race_no identity
- race count
- runner headcount
- canonical key uniqueness
- exact-key merge coverage
- STANDARD EdgeDB query/merge state
- EdgeDB v0.5 `source_status.edge_v05.state`
- EdgeDB v0.5 matched runner / signal count where available
- EdgeDB v0.5 `missing_join_count` / `extra_join_count` (normally both 0)
- history as-of / leakage
- schema validity
- source state / source coverage
- input SHA-256 where available
- source/module commit or version where available
- output SHA-256
- merge idempotence for same revision inputs

Eval PWA提出CSVを採用した場合は、追加で次を監査します。

- Eval merged rows
- analysis comment rows
- `NONE / WATCH / MATCH` 件数
- commentなしは `analysis: null`
- commentありはtitle/comment/version/asofが非空、codesに空要素なし

optional sourceの未着はaudit failureではなく、source stateとして記録します。

## 11. Publication semantics

ユーザーの標準指示にある「アップロード」は、特段の指定がなければ次までを含みます。

```text
1. day-package JSON生成
2. Google Drive canonical保存
3. revision/current metadata更新
4. Newspaper Current Publish
5. downstream `JRDB PWA Pages` 反映
6. public Newspaper表示確認
7. publication run / result確認
```

Pagesや正式publicationはActions-Native Executionとして扱います。

日次JSON、PACI、JRDB Raw、秘密情報はGitへcommitしません。Gitはcode / schema / docs / publish metadataを正本管理します。

## 12. GitHub execution routing

2026-09-10以降のルート運用方針に従います。

- A `Read / Audit`
  - GitHub read/search/fetchで直接確認。確認だけのIssueは作らない。
- B `Git Change`
  - UTF-8 source/test/docs/config/workflowはlatest mainを確認してdirect commit。
- C `Pure Deterministic Execution`
  - 取得済みPACI/CSV/JSON/SQLite等へのbuild・merge・schema validation・SHA・集計はローカル実行。
- D `Actions-Native Execution`
  - JRDB Secrets利用、長時間/大容量、artifact chain、immutable freeze、正式publication/audit、Pages deployment等のみ。

Issue駆動を通常日次処理の既定経路に戻しません。

## 13. Final report contract

Workは1回の依頼を可能な限り最後まで完遂し、最終報告で少なくとも次を簡潔に示します。

```text
Target: 2026-09-12
Revision: r1

PACI: READY
Eval: READY
RaceNote: READY
keibailuka: NOT_FOUND
STANDARD EdgeDB: READY
EdgeDB v0.5: PARTIAL
independent index: NOT_EXPECTED

Races / runners: 36R / NNN頭
Audit: PASS
Drive canonical: SAVED
Current Publish: SUCCESS
Pages: SUCCESS
Public PWA: VERIFIED

Pending:
- keibailuka: target-date source not found
```

Eval PWA提出CSVを使用した場合は、Eval行に `analysis comments` と `NONE / WATCH / MATCH` の受領集計を追記します。これは受領データの集計だけであり、条件判定の再計算ではありません。

`ERROR` がある場合は、該当source、理由、他sourceを含む日次処理を完走できたかを明示します。

Hard Stopの場合は、停止理由と不足しているBase必須条件を明示します。

## 14. Operational priority

この日次Workの最優先原則は次の通りです。

1. Baseが成立するなら不足addonを待たず完走する。
2. 見つからないsourceを推測で埋めない。
3. その時点の完成物を正式revisionとして一度公開する。
4. 遅着sourceは次revisionで安全に追加する。
5. 旧revisionを消さず、再現可能性と監査性を維持する。
6. ユーザーに細かな手順指示を要求せず、通常は日付だけで完走する。


### RaceReviewDB recommendation handoff

Canonical input:

`RRDB_recommendation_YYYYMMDD_PWA_handoff_v0_1.csv`

This is a sparse optional addon. Only RRDB-recommended horses appear.

Required columns:

`date,venue_code,race_no,race_key,horse_no,horse_name,recommendation_comment,recommendation_version`

Newspaper performs exact join only and stores the supplied prose under
`addons.rrdb_recommendation`. Do not recompute RRDB conditions, expose
internal signal IDs/strength JSON, or generate S/A grades.

Detailed contract:
`../../docs/RaceReviewDB_Newspaper_Handoff_v0_1.md`


#### PWA表示規約

RRDB推奨は独立した印列を新設しない。

- RaceNote印が既にある対象馬: その印を維持してモーダル化する。
- RaceNote印がない対象馬: `注` を表示してモーダル化する。
- RaceNote単馬短評がある場合: 消さずに同一モーダルへRRDB短評を併記する。
- RRDB内部のsignal ID / strength / S-A gradeはPWAへ表示しない。


### Edge Query consumer

日次Newspaper Baseと同じPACIを `jrdb_edgedb_query.py --profile STANDARD` に一度渡す。Analysisは既存のcanonical Parquet current bundleを世代IDとmanifest SHAで検証して利用する。adapterは `STANDARD` かつ `production_eligible=true` のsignalだけを `special_memos` に投影し、三つのidentity keyで完全一致mergeする。Edge Query/merge単独失敗時は `edge.state=ERROR` とaudit理由を残してBaseを維持する。旧matcher JSONLは互換入力に限定する。


## 15. EdgeDB v0.5 daily production rules

2026-10-09以降の日次通常新聞では、EdgeDB v0.5を正式なPWA addonとして扱います。

正規順序:

```text
PACI
-> Newspaper Base
-> canonical Analysis
-> STANDARD EdgeDB
-> EdgeDB v0.5 addon
-> remaining addons
-> audit / day artifact
-> Current Publish
-> JRDB PWA Pages
-> public verification
```

v0.5の表示契約:

- 馬単位: `horse.addons.edge_v05.candidate_ids`
- レース単位辞書: `edge_v05_candidates`
- 通常PWAでは既存mark群の直後、過去走の直前に独立Edge列を置く
- 該当馬だけ `○`、非該当馬は空欄
- `○` から詳細modalを開く
- 2026診断・複勝ROIは説明情報であり予想印・買い推奨へ変換しない
- 旧 `special_memos` は互換データとして残してよいが、旧「特注メモ」列は通常PWAへ出さない

現在の対応範囲は `EDGE_V05_PRODUCTION.md` を正本とし、未接続項目を推測で補完しません。特に結果SEDの馬場状態をpre-race goingとして流用せず、不完全履歴から初芝・初ダート・初ブリンカーを決め打ちしません。

日次artifactでは最低限、通常監査に加えて次を確認します。

```text
source_status.edge_v05.state
matched_runner_count
signal_count
missing_join_count
extra_join_count
```

`missing_join_count = 0`、`extra_join_count = 0` を通常条件とします。matched runner 0件だけでは直ちにERRORとしませんが、通常開催全体で完全0件なら入力・matcher・source statusを確認します。

公開完了はRelease更新ではなく、`JRDB PWA Pages` の `Run PWA focused tests / Prepare Pages artifact / Upload Pages artifact / Deploy to GitHub Pages` がすべてSUCCESSで、公開新聞を確認した時点です。

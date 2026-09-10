# JRDB Newspaper Daily Work Contract

Status: OPERATIONAL CONTRACT / 2026-09-11

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
- EdgeDB matcher output

独自指数は開発中で当面ファイルが存在しない運用を許容し、通常は `NOT_EXPECTED` として扱います。

RaceNoteは完成済みprediction outputのみをaddonとして利用し、RaceNote bundleやRaceNote内部実装をNewspaper Base/historyへ流用しません。

EdgeDBはEdge側matcherの照合結果をconsumer入力とし、Newspaper側でEdge条件を再実装・再判定しません。新規Newspaper packageでは表示対象を `special_memos` として保持し、旧 `edge_matches` は過去package互換に限定します。

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

Eval、RaceNote、keibailuka、EdgeDB、独自指数の欠損だけを理由にHard Stopしません。

## 6. Build and merge policy

標準処理は次の順です。

```text
PACI / neutral JRDB layer
  -> Newspaper Base / history
  -> available optional addons merge
  -> audit
  -> day package
  -> Drive canonical save
  -> current pointer update
  -> Current Publish
  -> Pages
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
my_index   NOT_EXPECTED
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
- history as-of / leakage
- schema validity
- source state / source coverage
- input SHA-256 where available
- source/module commit or version where available
- output SHA-256
- merge idempotence for same revision inputs

optional sourceの未着はaudit failureではなく、source stateとして記録します。

## 11. Publication semantics

ユーザーの標準指示にある「アップロード」は、特段の指定がなければ次までを含みます。

```text
1. day-package JSON生成
2. Google Drive canonical保存
3. revision/current metadata更新
4. Newspaper Current Publish
5. GitHub Pages反映
6. publication run / result確認
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
EdgeDB: READY
independent index: NOT_EXPECTED

Races / runners: 36R / NNN頭
Audit: PASS
Drive canonical: SAVED
Current Publish: SUCCESS
Pages: SUCCESS

Pending:
- keibailuka: target-date source not found
```

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

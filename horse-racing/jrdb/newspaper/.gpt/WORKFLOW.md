# JRDB Newspaper GPT workflow

1. `README.md` と `.gpt/CONTEXT.md` を確認する。
2. `.gpt/DAILY_WORK_CONTRACT.md` を日次通常運用の正本契約として確認する。
3. 新規専用Workスレッドでは `.gpt/WORK_THREAD_BOOTSTRAP.md` も確認する。
4. 親JRDBの `../README.md` / `../.gpt/CONTEXT.md` / `../.gpt/WORKFLOW.md` を確認する。
5. Newspaper design / schema / current implementationを確認する。
6. Common Reader / neutral JRDB history/access / external source contractを確認する。
7. NewspaperのJRDB Base/historyから `racenote_*` moduleを直接importしない。
8. 固定長offsetやjoin推測をconsumer側へ重複実装しない。新Raw fieldはneutral/Common Readerへ追加する。
9. JRDB Base生成とexternal addon mergeを分離する。
10. addon未取得をBase生成失敗とみなさず、source stateを残して処理を継続する。
11. mergeはnamespace ownershipとexact-key joinを守り、他source値を変更しない。
12. historical処理ではtarget date以降の結果を混入させない。
13. schema / key uniqueness / headcount / history as-of / merge idempotenceを検証する。
14. 日次生成JSON、JRDB Raw、PACI、秘密情報をGitへcommitしない。
15. 仕様変更時はdesign/schema/contextを必要範囲で同時更新し、Git `main` を正本とする。

## GitHub routing standard — 2026-09-10

処理開始時に「GitHub Actions実行環境が本当に必要か」を判定する。Issue駆動を標準経路にしない。

### A. Read / Audit

次はGitHub read/search/fetchから直接行う。

- latest main / file / commit / diff確認
- Issue / workflow / run / artifact metadata確認
- source SHA / output SHA / RESULT状態の監査
- repository code search

確認だけのIssueは作らない。

### B. Git Change

source / test / docs / schema / config / workflow / PWA JS-CSS-HTML等のUTF-8テキスト変更はGitHubへdirect commitする。`[gpt-git-update]` Issueは標準経路としない。

変更前に必ず:

```text
latest main
 -> path存在
 -> current content / blob SHA
 -> 必要差分
```

を確認する。同一目的の複数ファイルは、利用可能なら1 remote commitへまとめる。

### C. Pure Deterministic Execution

以下は入力が取得済みでsecret不要ならGPTローカルで正本moduleを実行する。

- `jrdb_newspaper_build.py`
- `jrdb_newspaper_day_build.py`
- `jrdb_newspaper_merge_external.py`
- `jrdb_newspaper_merge_edge.py`
- schema validation
- CSV / JSON join
- day-package生成
- SHA-256 / row count / key/headcount/as-of監査
- focused unit/regression test
- 既取得artifact/SQLite/CSV/JSONの比較・集計

GitHub上にmoduleがあることだけを理由にActionsへ送らない。

ローカル実行時は可能な限り次を成果物/manifest/auditへ残す。

- `source_commit`
- module/source file SHA
- input SHA-256
- runner/module version
- `generated_at`
- output SHA-256

### D. Actions-Native Execution

以下だけIssue / GitHub Actions経路を維持する。

- `JRDB_USER` / `JRDB_PASSWORD` 等Secretsを使うJRDB公式データ取得
- 認証付き外部取得でChat/connectorから代替できないもの
- Actions artifact chainそのものが正式入力/証跡の処理
- 長時間・大容量batch
- immutable freeze / settlement / publication / release
- run ID / artifact / Actions履歴を正式監査証跡として残すrun
- GitHub-hosted runner環境そのものを検証する処理
- GitHub Pages deployment

Pagesのsource変更はBでdirect commitし、そのpushでPages Actionsを起動する。Pagesを再配備するためだけに`[gpt-git-update]` Issueを作らない。

## Newspaper routine route

日次Workの詳細契約は `.gpt/DAILY_WORK_CONTRACT.md` を正本とする。

ユーザーが通常、

```text
MMDDの競馬新聞用JSONを作成し、アップロードしてください。
```

と依頼した場合の標準:

1. target date確定
2. current thread attachment -> File Library -> Drive canonical -> verified artifact の順で入力をresolve
3. 各sourceを `READY / NOT_FOUND / ERROR / NOT_EXPECTED` で管理
4. PACIが既に取得可能ならそのままCへ進む
5. PACI未取得かつ公式認証取得が必要ならDでJRDB Raw/PACI取得だけを実行
6. latest mainのNewspaper正本moduleを取得
7. Cで日次Base/history生成
8. 利用可能なEval / RaceNote prediction / keibailuka / Edge / independent indexをCでnamespace-safe merge
9. optional addonが未着でもBaseが成立する限り処理を継続
10. Cでschema / key / headcount / as-of / source coverage / SHA / idempotence監査
11. Cでday-package.json生成
12. immutable revisionとしてDrive canonicalへ保存
13. current pointerを新revisionへ更新
14. publishが必要なら既定Current Publish / Pages経路を使用
15. 各source stateと成果物、監査、publication状態を報告

PACI / Base identityが成立しない場合だけHard Stopを許容する。Eval / RaceNote / keibailuka / Edge / independent indexの欠損だけを理由にHard Stopしない。

## Partial completion and revision rule

optional sourceが未着でも、その時点で安全に生成できるday-packageを正式revisionとして保存・公開する。

同日再実行では既存JSONを直接手編集しない。

```text
previous revision verified inputs
+ newly arrived source
  -> clean rebuild / idempotent re-merge
  -> full audit
  -> next immutable revision
  -> current pointer update
  -> republish
```

旧revisionは削除・上書きしない。同一source versionを重複付与しない。前revisionでREADYだったsourceを欠落させない。

## External source handling

- Eval完成OCR CSV: deterministic exact-key merge対象
- keibailuka CSV/JSON: sparse source。exact matchのみmergeし、近似馬名を自動補正しない
- RaceNote prediction output: `addons.racenote_prediction` とrace-level RaceNote noteのみを所有
- independent index: `addons.my_index` を所有。未稼働中は `NOT_EXPECTED` を許容
- Edge Registry matcher output: Edge側の照合結果のみをconsumer入力とし、Newspaper側でEdge条件を再判定しない
- new Newspaper package: `special_memos` を現行Edge表示正本とする
- legacy package: `edge_matches` は後方互換fallbackに限定する

RaceNote prediction成果物の入力契約は別途正式化する。RaceNote本体bundleをNewspaper Base/historyへ流用しない。

## Source-state semantics

- `READY`: 対象日の正しいsourceを発見し、検証・merge完了
- `NOT_FOUND`: 対象日sourceが未生成・未着・未発見
- `ERROR`: source候補はあるが日付/schema/key/SHA/内容等の不整合で安全に採用不可
- `NOT_EXPECTED`: 現在そのsourceが未稼働・運用対象外

optional sourceの `NOT_FOUND / NOT_EXPECTED` はaudit failureではない。

optional sourceの `ERROR` も、そのsourceだけ安全に除外できるなら他sourceで日次処理を完走し、理由を報告する。

## Dependency boundary

RaceNote内にNewspaperでも必要な処理がある場合:

```text
RaceNote-specific implementation
  -> neutral JRDB moduleへ抽出
       -> RaceNote adapter
       -> Newspaper adapter
```

RaceNote固有のGPT-facing schema enrichment、Reader View、prediction handoffはNewspaper Base/historyへ持ち込まない。ただしpredictionの完成成果物は外部addonとしてmergeしてよい。

## Publication semantics

ユーザーの通常指示にある「アップロード」は、特段の指定がなければ次を含む。

```text
day-package JSON生成
-> Drive canonical保存
-> immutable revision/current metadata更新
-> Newspaper Current Publish
-> GitHub Pages反映
-> success確認
```

正式publication / PagesはDとして扱う。

## Actions Issue preflight — D only

Dを使う場合のみ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` と対象workflow parserを確認する。

Issue発行前に:

1. latest main
2. title prefix / required body keys
3. upstream success
4. artifact名実在
5. SHA実値
6. date / ID / race identity
7. freeze/manifest存在（必要時）
8. request JSONの機械的serialize

を全PASSさせ、Issueは1回だけ作成する。失敗時はfailed stepを確認し、blind rerunしない。

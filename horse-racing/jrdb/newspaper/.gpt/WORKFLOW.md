# JRDB Newspaper GPT workflow

1. `README.md` と `.gpt/CONTEXT.md` を確認する。
2. 親JRDBの `../README.md` / `../.gpt/CONTEXT.md` / `../.gpt/WORKFLOW.md` を確認する。
3. Newspaper design / schema / current implementationを確認する。
4. Common Reader / neutral JRDB history/access / external source contractを確認する。
5. NewspaperのJRDB Base/historyから `racenote_*` moduleを直接importしない。
6. 固定長offsetやjoin推測をconsumer側へ重複実装しない。新Raw fieldはneutral/Common Readerへ追加する。
7. JRDB Base生成とexternal addon mergeを分離する。
8. addon未取得をBase生成失敗とみなさずPENDING/nullで保持する。
9. mergeはnamespace ownershipとexact-key joinを守り、他source値を変更しない。
10. historical処理ではtarget date以降の結果を混入させない。
11. schema / key uniqueness / headcount / history as-of / merge idempotenceを検証する。
12. 日次生成JSON、JRDB Raw、PACI、秘密情報をGitへcommitしない。
13. 仕様変更時はdesign/schema/contextを必要範囲で同時更新し、Git `main` を正本とする。

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

ユーザーが

```text
MM/DDの競馬新聞用データを生成してください。
不足入力は添付またはLibraryから回収してください。
```

と依頼した場合の標準:

1. target date確定
2. 添付 / File Library / Drive / 既存artifactから入力をresolve
3. PACIが既に取得可能ならそのままCへ進む
4. PACI未取得かつ公式認証取得が必要ならDでJRDB Raw/PACI取得だけを実行
5. latest mainのNewspaper正本moduleを取得
6. Cで日次Base/history生成
7. 利用可能なEval / RaceNote prediction / keibailuka / Edge / independent indexをCでnamespace-safe merge
8. Cでschema / key / headcount / as-of / source coverage / SHA監査
9. Cでday-package.json生成
10. 必要ならDrive canonicalへ保存
11. publishが必要なら既定publish/Pages経路を使用
12. READY/PENDING/ERROR source stateと成果物を報告

同日再実行では同じsource versionを重複付与せず、差分sourceだけを安全に反映する。

## External source handling

- Eval完成OCR CSV: deterministic exact-key merge対象
- keibailuka CSV/JSON: sparse source。exact matchのみmergeし、近似馬名を自動補正しない
- RaceNote prediction output: `addons.racenote_prediction` とrace-level RaceNote noteのみを所有
- Edge Registry: `edge_matches` のみを所有

RaceNote prediction成果物の入力契約は別途正式化する。RaceNote本体bundleをNewspaper Base/historyへ流用しない。

## Dependency boundary

RaceNote内にNewspaperでも必要な処理がある場合:

```text
RaceNote-specific implementation
  -> neutral JRDB moduleへ抽出
       -> RaceNote adapter
       -> Newspaper adapter
```

RaceNote固有のGPT-facing schema enrichment、Reader View、prediction handoffはNewspaper Base/historyへ持ち込まない。ただしpredictionの完成成果物は外部addonとしてmergeしてよい。

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

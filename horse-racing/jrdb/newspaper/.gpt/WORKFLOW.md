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
12. Eval PWA提出CSVの分析列はEval側の判定済み出力として透過格納し、Newspaper/PWAで条件・status・コードを再判定しない。
13. historical処理ではtarget date以降の結果を混入させない。
14. schema / key uniqueness / headcount / history as-of / merge idempotenceを検証する。
15. 日次生成JSON、JRDB Raw、PACI、秘密情報をGitへcommitしない。
16. 仕様変更時はdesign/schema/contextを必要範囲で同時更新し、Git `main` を正本とする。

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

日次Workの正式契約は `.gpt/DAILY_WORK_CONTRACT.md`、request schemaは `../DAY_REQUEST_V2.md` を正本とします。

1. target dateとPACIのcanonical取得元を確認する。
2. 添付 → Library → Drive canonical → verified artifactの順で実物・SHA・日付を照合する。
3. PACI取得済みならC（deterministic）。認証取得が必要な場合のみDでJRDB Raw/PACIを取得する。
4. 最新mainの `jrdb_newspaper_day_build.py` でPACI-only Base/historyと日次race JSONを生成する。
5. Eval / RaceNote prediction / RRDB / イルカの独立addonをnamespace-safe・exact-keyでmergeする。未着addonはsource stateとして記録。
6. 新revisionの前に `jrdb_newspaper_retired_sources.py` で廃止sourceの非伝播を検証し、旧Currentやimmutable revisionは書き換えない。
7. schema、key、headcount、history as-of、race count、SHA/size/manifest、idempotenceを監査する。
8. verified day-packageをDrive canonicalへimmutable revisionとして保存し、current pointerを検証して更新する。
9. `JRDB Newspaper Current Publish` でReleaseを更新し、`JRDB PWA Pages` のfull-site deploy成功を確認する。
10. 個人・桃太郎の公開表示で日付・主要addon維持・旧EdgeDB/Training Edge非表示を確認し、provenanceと未検証事項を報告する。

EdgeDB STANDARD/v0.5、`special_memos`、Training Edge `my_index` を通常入力に追加しません。canonical Analysis ParquetはFact Lite等の独立経路で引き続き使用します。

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
- independent index: `addons.my_index` を所有。`独自指数_YYYYMMDD.csv` がverifiedなら`--my-index-csv`で全馬exact mergeし、numeric/nullを透過格納する。未着は`NOT_FOUND`、運用対象外だけ`NOT_EXPECTED`を許容
- Edge Registry matcher output: Edge側の照合結果のみをconsumer入力とし、Newspaper側でEdge条件を再判定しない
- new Newspaper package: `special_memos` を現行Edge表示正本とする
- legacy package: `edge_matches` は後方互換fallbackに限定する

RaceNote prediction成果物の入力契約は別途正式化する。RaceNote本体bundleをNewspaper Base/historyへ流用しない。

## 桃太郎・りょーた予想のレース短評取り込み（2026-10-10追加）

りょーたの「新聞提出用・前日予想」など、印の後に【見解】やレース別文章が付く原稿は、印だけではなく**レース単位の短評も正式入力**とする。短評を馬単位 `momotaro_predictions[].comment` に無理に複製しない。

- 原稿の対象日・場・レース番号ごとに印・馬番・馬名を正確に照合し、`momotaro_predictions` に投入する。
- 印の直下にあるレース全体の見解は原文を維持して `momotaro_race_comments` の `{date,venue_code,race_no,member:"ryota",comment}` として渡す。表示先は `race.notes.momotaro_comments.ryota`。
- 新馬戦・障害戦など見解のないレースは**原文に短評がないことを確認してから**コメントを省略する。空コメントを想像して作らない。
- 同日訂正が提供された場合は訂正版を優先し、以前の不一致・旧短評を混在させない。
- 発行前に「予想対象24R」「印行数」「原文で短評があるレース数」「提出コメント数」「短評本文の一致」を別々に監査する。コメント数0は原文に短評がある限りERROR。
- りょーたのレース自信度と馬単位短評・回顧コメントは別概念。自信度があるだけで `review_horse=true` にしたり、馬単位コメントを生成したりしない。注目馬一覧と印モーダルは馬単位の実コメントがある場合に限定する。
- 公開後に桃太郎projectionの `race.notes.momotaro_comments.ryota` をレース別に検証する。既存RaceNote/RRDB/🐬等を失わないことも監査する。
- 個人PWAのりょーた短評表示は桃太郎projectionとは別の表示契約であり、個人PWAにも表示されると断定せず実装・公開画面を確認する。

正規の統合は `[JRDB_NEWSPAPER_KENSHO_MERGE_REQUEST]` と `build_momotaro_newspaper_projection.py` を使用し、表示要件を満たすために既存モジュールを再実装しない。

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

## Retired-source gate

EdgeDB/Training Edgeの旧workflow/CLIはarchive上の監査資料であり、通常運用から起動しません。新revision/PWA projectionへ廃止sourceが残らないかを `jrdb_newspaper_retired_sources.py` と現行テストで監査します。旧JSONの後方互換・既存Releases・immutable revisionは維持します。

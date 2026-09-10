# 中央競馬予想 / 競馬新聞 日次生成Workスレッド 起動指示

このスレッドを **JRDB Newspaper 日次生成・公開専用Work** として運用してください。

## 1. 最初に確認する正本

作業開始時にGitHub `yukki0113/GPT` の **latest main** を確認し、少なくとも次を読んで現行仕様を取得してください。

```text
horse-racing/jrdb/newspaper/README.md
horse-racing/jrdb/newspaper/.gpt/CONTEXT.md
horse-racing/jrdb/newspaper/.gpt/WORKFLOW.md
horse-racing/jrdb/newspaper/.gpt/DAILY_WORK_CONTRACT.md
horse-racing/jrdb/newspaper/.gpt/REQUEST_CONTRACT.md
```

必要に応じて親JRDBのREADME / CONTEXT / WORKFLOW、Newspaper schema、現行builder / merger / publish workflowも確認してください。

このMarkdownの記述とGitHub latest mainが矛盾する場合は、**latest mainの正本仕様を優先**し、矛盾点を報告してください。

## 2. このWorkの最終目標

通常はユーザーから次の1文だけを受けて、日次処理を完遂できる状態を維持してください。

```text
MMDDの競馬新聞用JSONを作成し、アップロードしてください。
```

この「アップロード」は、特段の指定がない限り、単にJSONファイルを作るだけではなく、

```text
日次JSON生成
-> Google Drive canonical保存
-> immutable revision登録
-> current pointer更新
-> Newspaper Current Publish
-> GitHub Pages反映
-> 成功確認
```

までを意味します。

ユーザーに各sourceファイルを毎回列挙・再添付させる運用にはしないでください。利用可能な接続先・添付・Library・Drive・既存artifactを自律的に探索してください。

## 3. 日次処理対象source

### Base必須

- JRDB Raw / PACI

PACIを中心とするneutral JRDB layerからNewspaper Base / historyを生成します。

### Optional addons

- 独自指数 / independent index
- イルカブログ / keibailuka
- Eval
- RaceNote prediction output
- EdgeDB matcher output

独自指数は現在開発中のため、当面ファイルが存在しなくても正常です。その場合は `NOT_EXPECTED` としてください。

RaceNoteは完成済みprediction outputだけをaddonとして取り込み、RaceNote bundleやRaceNote内部ロジックをNewspaper Base/historyへ依存させないでください。

EdgeDBはEdge側のmatcher結果を入力とし、Newspaper側でEdge条件を再判定しないでください。新規packageは `special_memos` を正本表示フィールドとし、旧 `edge_matches` は過去package互換に限定します。

## 4. 入力探索順

対象日の各sourceは原則として次の順でresolveしてください。

```text
1. このWorkスレッドへの添付
2. File Library
3. Google Drive canonical storage
4. verified GitHub Actions artifact / frozen artifact
```

複数候補がある場合は日付、revision/version、canonical key、SHA/provenance等を確認して採用してください。

ファイル名や馬名が似ているという理由だけで推測採用・fuzzy joinしないでください。

## 5. source状態

各sourceを必ず次の4状態で管理・報告してください。

```text
READY
NOT_FOUND
ERROR
NOT_EXPECTED
```

意味:

- `READY`: 対象日の正しい入力を発見し、検証・merge完了
- `NOT_FOUND`: 対象日の入力が未生成・未着・未発見
- `ERROR`: 候補はあるが日付/schema/key/SHA/内容等の不整合で安全に採用不可
- `NOT_EXPECTED`: 現在そのsource自体が運用対象外・未稼働

optional addonが `NOT_FOUND` / `NOT_EXPECTED` でも処理を止めないでください。

optional addonが `ERROR` でも、そのsourceだけ安全に除外できるなら他sourceで日次生成を完走し、ERROR理由を報告してください。

## 6. Hard Stop条件

Hard StopはNewspaper Baseが安全に成立しない場合に限定してください。

代表例:

- PACI未取得で、公式取得も実行不能
- PACI破損
- target date / race identity / runner identity / headcountが確定不能
- Base canonical key重複等により一意性を保証不能

PACI未取得でもJRDB Secretsを使う公式取得が可能なら、Actions-Native routeでPACI取得を行い、その後はdeterministic buildへ戻ってください。

Eval、RaceNote、イルカブログ、EdgeDB、独自指数の欠損だけでHard Stopしないでください。

## 7. 標準生成フロー

```text
対象日確定
-> 入力resolve
-> PACI / neutral JRDBからBase/history生成
-> 利用可能optional addonをnamespace-safe exact merge
-> schema / key / headcount / as-of / coverage / SHA監査
-> day-package JSON生成
-> Drive canonical保存
-> current pointer更新
-> Current Publish
-> Pages反映
-> 最終状態報告
```

基本join keyは次です。

```text
date + venue_code + race_no + horse_no
```

source固有のより強い正式keyがある場合はそのcontractを使ってください。

近似馬名・推測補正による自動joinは禁止です。

historical rowは必ず `history_date < target_date` とし、対象レースの結果・最終オッズ等の未来情報を混入させないでください。

## 8. 不足sourceがあっても一度公開する

このWorkでは **partial completionを正常な正式publicationとして許容**します。

たとえば、

```text
PACI       READY
Eval       READY
RaceNote   READY
keibailuka NOT_FOUND
EdgeDB     READY
my_index   NOT_EXPECTED
```

であっても、その時点で作れる日次JSONを生成し、正式revisionとしてDrive保存・公開してください。

「イルカブログがまだないので待ちます」のように、optional source待ちで日次処理全体を保留しないでください。

## 9. revision管理

同日成果物は物理上書きせず、immutable revisionで管理してください。

```text
..._r1.json
..._r2.json
..._r3.json
```

新revision公開時も旧revisionは削除・変更しません。

`current.json` 等のcurrent pointerだけを最新revisionへ向けてください。

ユーザーが「アップロード分をUPDATE」と表現した場合も、内部では **新revision作成 + current切替** と解釈してください。

## 10. 遅着source

一度公開後、ユーザーがたとえば

```text
イルカブログ記載分がやっと取り込めました。09/12の競馬新聞を更新してください。
```

と依頼した場合、既存JSONへ直接追記・手編集しないでください。

```text
前revisionで使用したverified inputs
+ 新たに到着したsource
-> clean rebuild / idempotent re-merge
-> full audit
-> next revision
-> Drive保存
-> current切替
-> republish
```

としてください。

同一sourceを二重付与せず、前revisionのREADY sourceを落とさず、新sourceだけ安全に加えてください。

既存READY sourceが予期せず変化した場合は、その差分をERROR/警告として明示してください。

## 11. 必須監査

少なくとも次を確認してください。

```text
target date
venue / race_no identity
race count
runner headcount
canonical key uniqueness
exact-key merge coverage
history as-of / leakage
schema validity
source state / source coverage
input SHA-256 where available
source/module commit or version where available
output SHA-256
same-input merge idempotence
```

optional sourceの未着はaudit failureではありません。source stateとして残してください。

## 12. GitHub処理経路

2026-09-10以降の運用方針に従ってください。Issue駆動を標準へ戻さないでください。

```text
A Read / Audit
  GitHub read/search/fetchで直接

B Git Change
  UTF-8 source/test/docs/config/workflowはlatest main確認後にdirect commit

C Pure Deterministic Execution
  取得済みPACI/CSV/JSON/SQLite等に対するbuild/merge/validation/SHA/集計

D Actions-Native Execution
  JRDB Secrets、認証付き取得、長時間/大容量、artifact chain、immutable freeze、
  正式publication/audit、GitHub Pages deployment等
```

GitHub上にmoduleがあることだけを理由にActionsへ送らないでください。

## 13. 最終報告形式

ユーザーとの往復を細切れにせず、可能な限り1回の依頼で完遂してください。

完了時は概ね次の形で簡潔に報告してください。

```text
09/12 競馬新聞 r1 作成・公開完了

PACI: READY
Eval: READY
RaceNote: READY
keibailuka: NOT_FOUND
EdgeDB: READY
independent index: NOT_EXPECTED

36R / NNN頭
schema/key/headcount/as-of監査: PASS
Drive canonical: SAVED
Current Publish: SUCCESS
Pages: SUCCESS

未反映:
- keibailuka: 対象日source未発見
```

ERRORがある場合は、何が失敗し、なぜ採用せず、日次JSON自体はどこまで完走したかを明示してください。

Hard Stopの場合は、Baseを成立させられなかった理由だけを明確に報告してください。

## 14. 通常運用開始

上記確認が終わったら、このWorkスレッドでは以後、ユーザーから次の形式の短い依頼を受けて日次処理を実行してください。

```text
0912の競馬新聞用JSONを作成し、アップロードしてください。
```

形式的な確認質問は不要です。対象日と処理内容が解決できる限り、そのまま最後まで進めてください。

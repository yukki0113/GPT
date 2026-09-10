# JRDB Newspaper module

Status: V0.1 INITIAL ACCEPTANCE PASS / DAILY PACKAGE + EXTERNAL MERGE VALIDATED

このディレクトリは、JRDB PWA向け「自分用競馬新聞」の日次生成・外部source merge・配布契約を独立管理するためのmodule boundaryです。

## Design source of truth

- `../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- `../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`
- `../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- `../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- `.gpt/WORKFLOW.md`
- `.gpt/REQUEST_CONTRACT.md`
- `.gpt/DAILY_WORK_CONTRACT.md`
- `.gpt/WORK_THREAD_BOOTSTRAP.md`

日次Workの通常運用契約は `.gpt/DAILY_WORK_CONTRACT.md` を正本とし、新しい専用Workスレッドの起動には `.gpt/WORK_THREAD_BOOTSTRAP.md` を使用します。

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
        - independent index
        - Edge Registry
```

RaceNoteの予想結果・印・短評は外部addonとして `addons.racenote_prediction` とrace-level noteへmergeできます。RaceNote内部実装はNewspaper Base/historyの依存にしません。

## Implemented data pipeline

- `../src/jrdb_newspaper_build.py`: 1レースNewspaper Base生成
- `../src/jrdb_newspaper_day_build.py`: 1日分のmanifest + race JSON群生成
- `../src/jrdb_newspaper_merge_external.py`: 外部sourceのnamespace-safe merge + day-package生成
- `../src/audit_jrdb_newspaper_poc.py`: real-data PoC監査
- `../pwa/newspaper.html`: Newspaper PWA
- `../pwa/newspaper-day.js`: 1日パッケージ読込・OPFS保存・レース切替

Base/historyはCommon Reader / neutral JRDB accessから生成し、最大8走を保持します。初期表示3走、切替5走/8走。外部source欠損はBase失敗にせずnull/PENDINGで保持します。

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

- Eval merger: `addons.eval`
- RaceNote prediction merger: `addons.racenote_prediction` + race-level RaceNote note
- keibailuka merger: `addons.keibailuka`
- independent index merger: `addons.my_index`
- Edge matcher input: EdgeDB matcher output
- current Newspaper Edge display field: `special_memos`
- legacy Newspaper Edge compatibility field: `edge_matches`

基本join key:

```text
date + venue_code + race_no + horse_no
```

馬名は照合には使えますが、文字列の近似・推測による自動joinを標準経路にしません。

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
- Eval / RaceNote prediction / keibailuka / Edge / independent indexはoptional addonとして扱う
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
5. 利用可能なEval / RaceNote prediction / keibailuka / Edge / independent indexをmerge
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

# JRDB 開催終了後 Analysis / Mart 更新 Work 引継ぎ

更新日: 2026-09-11

## この Work スレッドの責務

この Work は、開催終了後の JRDB 基盤更新だけを担当する。

入力は原則としてユーザーの自然文だけでよい。

例:

```text
0905～0906についてAnalysis差分反映、Martの再発行をお願いします
```

ここから対象開催日を解決し、PACI + SED → Analysis v1.3 増分置換 → Stats Mart v1.1 対象年refresh → artifact回収 → Google Drive `20_mart` 発行まで完遂する。

PWA Fact Lite の再発行、RaceNote生成、Eval集計、イルカブログ処理はこの Work の責務外。

## 正本

Repository:

```text
yukki0113/GPT
```

JRDB root:

```text
horse-racing/jrdb/
```

開始時に必ず latest `main` を確認し、次を読む。

- `horse-racing/jrdb/README.md`
- `horse-racing/jrdb/.gpt/CONTEXT.md`
- `horse-racing/jrdb/.gpt/WORKFLOW.md`
- `horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md`
- `.gpt/ISSUE_REQUEST_CONTRACTS.md`

主要実装:

- `src/fetch_jrdb_paci.py`
- `src/fetch_jrdb_history.py`
- `src/update_jrdb_analysis_incremental.py`
- `src/refresh_jrdb_stats_mart_year.py`
- `.github/workflows/jrdb_post_race_refresh_issue.yml`

## データ正本と current artifact

Raw source of truth:

```text
JRDB PACI / SED ZIP
```

共有大容量artifact:

```text
Google Drive / JRDB / 20_mart
```

Work は Drive `20_mart` を毎回確認し、最新の compatible artifact をその場で resolve する。Gitへ変動する Drive file ID を固定しない。

Analysis current contract:

```text
Analysis Lite v1.3
```

必須:

- `win5_leg_no`
- `prev_result_key_1`
- `prev_race_key_1`
- `meta_analysis_ingest_batch`
- `ix_analysis_horse_history`

Stats Mart current contract:

```text
Stats Mart v1.1
```

対象table:

- `mart_sire_yearly`
- `mart_jockey_yearly`
- `mart_frame_yearly`

## 標準処理

### 1. ユーザー依頼から開催日を解決

例:

```text
0905～0906
```

現在年が2026なら:

```text
2026-09-05
2026-09-06
```

workflowへは `dates:` のカンマ区切りで渡す。

範囲内の非開催日を推測で含めない。必要なら JRA/JRDB の開催実績または current Analysis / Raw availability で確認する。

### 2. Drive `20_mart` の current pair を resolve

優先条件:

Analysis:

- v1.3
- 対象日以前までを含む最新artifact
- history indexあり
- integrity確認済み

Mart:

- v1.1
- current Analysis と互換
- 既存全期間を保持

候補が複数ある場合は file name だけで決めず、modified time / schema / row coverage / integrity を確認する。

### 3. Issue preflight

Title:

```text
[JRDB_POST_RACE_REFRESH] <request_id>
```

Body:

```text
request_id: <unique id>
dates: 2026-09-05,2026-09-06
analysis_drive_file_id: <resolved id>
analysis_source_filename: <resolved filename>
mart_drive_file_id: <resolved id>
mart_source_filename: <resolved filename>
```

Issue前に contract と workflow parser を確認する。

### 4. Actions 実行

Actionsは JRDB credentials を使用して各対象日の PACI / SED を取得する。

各日:

```text
PACI + SED
  -> update_jrdb_analysis_incremental.py
  -> target race_date DELETE + INSERT
  -> ingest SUCCESS
```

その後、対象年だけ:

```text
Analysis
  -> refresh_jrdb_stats_mart_year.py
  -> Stats Mart year partition replace
```

### 5. SUCCESS 判定

Issue commentに以下が必要。

```text
JRDB_POST_RACE_REFRESH_RESULT
status: success
run_id: ...
artifact_name: jrdb-post-race-refresh
```

加えて artifact が実在することを確認する。

### 6. artifact 回収・Drive再発行

artifact内の expected outputs:

- `jrdb_analysis_..._v1_3.sqlite.zip`
- `jrdb_stats_mart_..._v1_1.sqlite`
- `refresh_audit.json`
- `result.json`

`result.json` の SHA-256 と file size を確認してから `20_mart` へ upload する。

旧版は明示指示がない限り削除しない。

Drive upload後は再fetchして file name / size / parent folder を確認する。

## 検証条件

Analysis:

- row count > 0
- requested date 全件が存在
- requested date の latest ingest status = SUCCESS
- `race_key + horse_no` duplicate = 0
- `win5_leg_no` invalid = 0
- `ix_analysis_horse_history` preserved
- `PRAGMA integrity_check = ok`

Stats Mart:

- 対象年の sire/jockey/frame rows > 0
- 他年partitionを保持
- `PRAGMA integrity_check = ok`

PACI / SED:

- ZIP readable
- filename date一致
- required member存在

## 冪等性

同じ開催日を再実行してよい。

Analysis は対象日を transaction 内で DELETE → INSERT するため二重登録しない。

Stats Mart は対象年partitionを DELETE → aggregate INSERT するため二重集計しない。

したがって、更新済みか不明な場合も current artifact を起点に同じ日を安全に再適用できる。ただし failed reason 未確認の blind rerun はしない。

## 出力命名

workflow は更新後 Analysis の `MAX(race_date)` を data-through date とし、出力名へ含める。

例:

```text
jrdb_analysis_2016_2026YTD_20260906_v1_3.sqlite.zip
jrdb_stats_mart_2016_2026YTD_20260906_v1_1.sqlite
```

過去日だけを再処理し current source がさらに先まで進んでいる場合は、source の max race date を維持する。

## ユーザーへの最終報告

長いrunner logは返さず、次だけを簡潔に報告する。

- 対象開催日
- Analysis: before/after row count、data-through、integrity
- Mart: refresh年、sire/jockey/frame row count、integrity
- WIN5 invalid / duplicate の有無
- Actions run ID
- Analysis / Mart SHA-256
- Drive file ID / file name

異常がある場合は Drive publication せず、failed step と原因を報告する。

## 禁止事項

- Core SQLite を中間入力として要求しない
- PWAを自動publishしない
- Eval / イルカブログを同じ処理に混ぜない
- Raw / generated SQLite / credentials をGitへcommitしない
- Drive file IDをGitの恒久設定へ固定しない
- source artifact を検証せず上書きしない
- SUCCESS未確認のartifactを `20_mart` へ発行しない

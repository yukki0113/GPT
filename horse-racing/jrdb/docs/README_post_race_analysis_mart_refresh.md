# JRDB 開催終了後 Analysis / Stats Mart 更新 contract

## 目的

開催終了後の定型更新を、Work から日付だけ指定する運用へ寄せる。

ユーザー側の標準依頼例:

```text
0905～0906についてAnalysis差分反映、Martの再発行をお願いします
```

Work はこの自然文から対象開催日を解決し、Google Drive `20_mart` の現行 Analysis / Stats Mart を確認したうえで、Actions-native workflow を起動する。

## なぜ Actions-Native か

この処理は次を含むため `.gpt/WORKFLOW.md` の D. Actions-Native Execution とする。

- `JRDB_USER` / `JRDB_PASSWORD` を使う PACI / SED 取得
- 大容量 SQLite の更新・監査
- run ID / artifact / SHA-256 を残す正式な更新証跡

Google Drive への最終配置は Work の Google Drive アダプタで行う。GitHub Actions へ Google Drive の書込 credential は持たせない。

## Issue contract

Title prefix:

```text
[JRDB_POST_RACE_REFRESH]
```

Body は単純な `key: value` 形式。

Required:

```text
request_id: <unique id>
dates: YYYY-MM-DD,YYYY-MM-DD[, ...]
analysis_drive_file_id: <Drive file id>
analysis_source_filename: <current Analysis .sqlite or .sqlite.zip filename>
mart_drive_file_id: <Drive file id>
mart_source_filename: <current Stats Mart .sqlite or .sqlite.zip filename>
```

`dates` は実際の開催日だけを列挙する。範囲表現をそのまま workflow へ渡さず、Work が開催日リストへ解決する。

例:

```text
request_id: 20260911-0905-0906
dates: 2026-09-05,2026-09-06
analysis_drive_file_id: <resolved id>
analysis_source_filename: jrdb_analysis_..._v1_3_....sqlite.zip
mart_drive_file_id: <resolved id>
mart_source_filename: jrdb_stats_mart_..._v1_1.sqlite
```

## Workflow

`.github/workflows/jrdb_post_race_refresh_issue.yml`

処理順:

1. latest `main` checkout
2. request validation
3. current Analysis / Mart を Drive から取得
4. Analysis v1.3 / Mart v1.1 の schema・integrity・history index を確認
5. 各対象日の PACI / SED を JRDB から取得して ZIP validation
6. `update_jrdb_analysis_incremental.py` で各日を日付単位 replace/add
7. Analysis を監査
8. 対象年を `refresh_jrdb_stats_mart_year.py` で再集計・置換
9. Mart を監査
10. Analysis / Mart の SHA-256 と件数を固定
11. artifact を発行
12. Issue に RESULT をコメントして close

Analysis の更新は SQL UPSERT ではなく、対象 `race_date` の行を transaction 内で DELETE → INSERT する原子的な置換型増分更新。再実行しても同日が二重登録されない。

## Analysis v1.3 contract

必須:

- `fact_entry_result_lite.win5_leg_no` が存在
- `prev_result_key_1` / `prev_race_key_1` が存在
- `meta_analysis_ingest_batch` が存在
- `ix_analysis_horse_history` が維持される
- `PRAGMA integrity_check = ok`
- `win5_leg_no` は `NULL` または 1～5
- 対象日の最新 ingest batch が `SUCCESS`
- 対象日について `race_key + horse_no` 重複なし

WIN5 は PACI 内 BAC の値をそのまま Analysis へ投影する。開催中止等で日別 leg 1～5 が欠けること自体は fatal としない。

## Stats Mart v1.1 contract

対象日を含む年だけ再集計する。

```text
Analysis
  -> mart_sire_yearly
  -> mart_jockey_yearly
  -> mart_frame_yearly
```

既存の他年 partition は維持し、対象年だけ DELETE → aggregate INSERT する。

必須:

- 3 mart table が存在
- 対象年の Analysis row が存在
- refresh 後の各 mart row count > 0
- `PRAGMA integrity_check = ok`

WIN5 列追加は Stats Mart grain を変更しないため Mart schema v1.1 は据え置く。

## RESULT marker

成功時:

```text
JRDB_POST_RACE_REFRESH_RESULT
status: success
run_id: ...
artifact_name: jrdb-post-race-refresh
analysis_output_filename: ...sqlite.zip
mart_output_filename: ...sqlite
max_race_date: YYYY-MM-DD
analysis_rows: ...
analysis_sha256: ...
mart_sha256: ...
integrity_check: ok
```

失敗時:

```text
JRDB_POST_RACE_REFRESH_RESULT
status: failure
run_id: ...
```

失敗時は failed step / log を確認してから retry する。同一 request の blind rerun は行わない。

## Work の publication 責務

Actions SUCCESS 後、Work は以下を続けて実施する。

1. RESULT の `status: success` を確認
2. `run_id` / `artifact_name` を完全一致で取得
3. artifact を回収
4. `result.json` と SHA-256 を確認
5. Analysis ZIP と Mart SQLite を Google Drive `20_mart` へ upload
6. Drive から再 fetch して file name / size を確認
7. 旧 artifact は明示指示なしに削除しない
8. 最終報告で対象日・row count・Mart件数・SHA・Drive file ID を返す

PWA publication はこの contract の責務外。Analysis / Mart を更新しても PWA Fact Lite / OPFS を自動更新しない。

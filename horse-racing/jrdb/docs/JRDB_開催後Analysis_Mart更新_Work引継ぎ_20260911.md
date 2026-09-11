commit 793ab455dd0261c88fdb628241fa4af991dcd80b
Author: Codex <codex@openai.com>
Date:   Fri Sep 11 02:24:57 2026 -0400

    Extend post-race flow through Fact Lite publication

diff --git "a/horse-racing/jrdb/docs/JRDB_\351\226\213\345\202\254\345\276\214Analysis_Mart\346\233\264\346\226\260_Work\345\274\225\347\266\231\343\201\216_20260911.md" "b/horse-racing/jrdb/docs/JRDB_\351\226\213\345\202\254\345\276\214Analysis_Mart\346\233\264\346\226\260_Work\345\274\225\347\266\231\343\201\216_20260911.md"
index a10c7f6..6047e7c 100644
--- "a/horse-racing/jrdb/docs/JRDB_\351\226\213\345\202\254\345\276\214Analysis_Mart\346\233\264\346\226\260_Work\345\274\225\347\266\231\343\201\216_20260911.md"
+++ "b/horse-racing/jrdb/docs/JRDB_\351\226\213\345\202\254\345\276\214Analysis_Mart\346\233\264\346\226\260_Work\345\274\225\347\266\231\343\201\216_20260911.md"
@@ -14,9 +14,9 @@
 0905～0906についてAnalysis差分反映、Martの再発行をお願いします
 ```
 
-ここから対象開催日を解決し、PACI + SED → Analysis v1.3 増分置換 → Stats Mart v1.1 対象年refresh → artifact回収 → Google Drive `20_mart` 発行まで完遂する。
+ここから対象開催日を解決し、PACI + SED → Analysis v1.3 増分置換 → Stats Mart v1.1 対象年refresh → artifact回収 → Google Drive `20_mart` へAnalysis/Mart正本発行 → Fact Lite v0.3再生成・検証・GitHub Release / Pages配布まで完遂する。
 
-PWA Fact Lite の再発行、RaceNote生成、Eval集計、イルカブログ処理はこの Work の責務外。
+RaceNote生成、Eval集計、イルカブログ処理はこの Work の責務外。
 
 ## 正本
 
@@ -47,6 +47,7 @@ horse-racing/jrdb/
 - `src/update_jrdb_analysis_incremental.py`
 - `src/refresh_jrdb_stats_mart_year.py`
 - `.github/workflows/jrdb_post_race_refresh_issue.yml`
+- `.github/workflows/jrdb_pwa_fact_lite_publish.yml`
 
 ## データ正本と current artifact
 
@@ -185,7 +186,7 @@ artifact_name: jrdb-post-race-refresh
 
 加えて artifact が実在することを確認する。
 
-### 6. artifact 回収・Drive再発行
+### 6. artifact 回収・Drive正本再発行
 
 artifact内の expected outputs:
 
@@ -200,6 +201,20 @@ artifact内の expected outputs:
 
 Drive upload後は再fetchして file name / size / parent folder を確認する。
 
+### 7. Fact Lite再生成・検証・PWA配布
+
+AnalysisのDrive正本保存・再fetch確認後、保存済みAnalysisを入力に次のIssueを起票する。
+
+```text
+[JRDB_PWA_FACT_LITE_PUBLISH] <request_id>
+```
+
+bodyはJSONとし、`drive_file_id`、`source_filename`、`data_version` を渡す。`drive_file_id` は直前に正本保存したAnalysisのID、`data_version` はAnalysisのdata-through日を含む一意な版とする。
+
+ActionsはBAC race-name lookupを含めFact Lite v0.3を生成し、schema、row count、`win5_leg_no`、previous distance/class、race-name lookup、SHA-256、SQLite integrityを検証してから `jrdb-pwa-fact-lite-current` ReleaseとGitHub Pages `/data/` を更新する。PWAはmanifest SHA差分を検知し、端末OPFSのDBを安全に切替える。
+
+Fact Lite publishが失敗した場合、Analysis/Mart正本は維持するが、PWAを最新と報告してはならない。
+
 ## 検証条件
 
 Analysis:
@@ -258,13 +273,14 @@ jrdb_stats_mart_2016_2026YTD_20260906_v1_1.sqlite
 - Actions run ID
 - Analysis / Mart SHA-256
 - Drive file ID / file name
+- Fact Lite release / Pages deployment / SHA-256
 
 異常がある場合は Drive publication せず、failed step と原因を報告する。
 
 ## 禁止事項
 
 - Core SQLite を中間入力として要求しない
-- PWAを自動publishしない
+- Analysis正本保存前にFact Lite publishを起動しない
 - Eval / イルカブログを同じ処理に混ぜない
 - Raw / generated SQLite / credentials をGitへcommitしない
 - Drive file IDをGitの恒久設定へ固定しない

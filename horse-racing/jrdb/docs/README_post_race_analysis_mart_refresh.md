commit 793ab455dd0261c88fdb628241fa4af991dcd80b
Author: Codex <codex@openai.com>
Date:   Fri Sep 11 02:24:57 2026 -0400

    Extend post-race flow through Fact Lite publication

diff --git a/horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md b/horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md
index dffe421..d458f1a 100644
--- a/horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md
+++ b/horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md
@@ -10,7 +10,7 @@
 0905～0906についてAnalysis差分反映、Martの再発行をお願いします
 ```
 
-Work はこの自然文から対象開催日を解決し、Google Drive `20_mart` の現行 Analysis / Stats Mart を確認したうえで、Actions-native workflow を起動する。
+Work はこの自然文から対象開催日を解決し、Google Drive `20_mart` の現行 Analysis / Stats Mart を確認したうえで、Actions-native workflow を起動する。更新済みAnalysisをDrive正本へ保存・再検証した後、Fact Lite v0.3の再生成・検証・PWA配布も続けて行う。
 
 ## なぜ Actions-Native か
 
@@ -155,4 +155,14 @@ Actions SUCCESS 後、Work は以下を続けて実施する。
 7. 旧 artifact は明示指示なしに削除しない
 8. 最終報告で対象日・row count・Mart件数・SHA・Drive file ID を返す
 
-PWA publication はこの contract の責務外。Analysis / Mart を更新しても PWA Fact Lite / OPFS を自動更新しない。
+## Fact Lite / PWA publication
+
+Analysis/Mart refreshの成功後、Workは更新済みAnalysis ZIPをGoogle Drive `20_mart` へ正本保存し、file ID・filename・sizeを再fetch確認する。その確認済みAnalysisを入力に `[JRDB_PWA_FACT_LITE_PUBLISH]` Issueを起票する。
+
+JSON request:
+
+```json
+{"drive_file_id":"<saved Analysis id>","source_filename":"<saved Analysis filename>","data_version":"<unique data-through version>"}
+```
+
+Fact Lite publish workflowはAnalysisからFact Lite v0.3を再生成し、schema、identity/lookup、WIN5、SHA-256、size、integrityを検証する。成功時だけ `jrdb-pwa-fact-lite-current` ReleaseとGitHub Pages `/data/` manifestを更新し、PWAのOPFS同期対象を切替える。

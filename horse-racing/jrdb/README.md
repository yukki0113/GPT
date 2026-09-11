commit 793ab455dd0261c88fdb628241fa4af991dcd80b
Author: Codex <codex@openai.com>
Date:   Fri Sep 11 02:24:57 2026 -0400

    Extend post-race flow through Fact Lite publication

diff --git a/horse-racing/jrdb/README.md b/horse-racing/jrdb/README.md
index 110cd85..45bbb1b 100644
--- a/horse-racing/jrdb/README.md
+++ b/horse-racing/jrdb/README.md
@@ -161,7 +161,7 @@ The individual daily-kind layout (`BAC/KYI/SED/CYB/UKC`) remains supported for f
 
 Work は対象開催日を解決し、Drive `20_mart` の current Analysis / Mart を取得して `[JRDB_POST_RACE_REFRESH]` Issue を起票する。Actions は JRDB Secrets を用いて PACI / SED を取得し、Analysis v1.3 の対象日置換、対象年Stats Mart v1.1再集計、監査、artifact発行まで行う。SUCCESS後の `20_mart` への最終uploadは Work の Google Drive adapter が担当する。
 
-この経路では PWA Fact Lite を自動publishしない。Analysis / Martの更新とPWA publicationは独立する。
+Workの開催後更新では、Analysis/Mart artifactをDrive `20_mart` へ正本保存・再検証した後、同Analysisを入力にFact Lite v0.3を再生成・検証・publishする。成功時だけ `jrdb-pwa-fact-lite-current` ReleaseとGitHub Pages manifestを更新し、条件別集計PWAを最新化する。
 
 At year-end:
 

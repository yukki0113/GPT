# BRDB private horse-level going × relative acceptance v0.1 candidate — 2026-11-20

**RESEARCH ONLY / PRIVATE HORSE-LEVEL OUTPUT / NO RACENOTE OR PWA AUTHORISATION**

## Purpose

v0.6の父・母父・配合の馬場4状態観測と、M7のprivate近親条件別実績を `(horse_no, horse_id)` で完全結合する受入ランナー。公開ActionsにM7 private horse-level dataを載せない。

## Inputs

- SHA検証済みJRDB Analysis v1.4 annual Parquet + manifest
- 対象PACI
- private `m7_relatives_detail_candidate.json`

private近親入力は `brdb-m7-relatives-detail-v0.1-candidate`、`research_only=true`、`prediction_safe=false`、`historical_asof_status=AS_OF_UNVERIFIED`、対象日as-of一致、18頭完全一致、近親件数/条件セル/zeroセルのaggregate coverage一致をfail-closedで検証する。

2026-11-15 東京12Rのprivate source preflight実績: 18頭、75近親、375 scope cells、285 zero-start cells。母系root解決13頭と、実際に近親の条件別出走が1件以上ある11頭を混同しない。

## Outputs

1. `private_output`: v0.6 horse-level result。horse_id、各laneのprimary observation、cross-lane alignment、relative condition linksを含む。**Git/公開Artifactへ保存しない。**
2. `aggregate_output`: Git/監査へ出せるreceipt。horse identity/name/sire name/individual statisticsを含めず、件数・state/lane別リンク件数・安全フラグのみ。

近親v0.3は馬場状態別実績を持たないため、`PARENT_GOING_SIGNAL_WITH_RELATIVE_CONDITION_OBSERVATION` は平行観測に限定する。`relative_going_state_known=false`, `independent_support=false`, `causal_claim=false`, `distance_compensation_claim=false`, `suitability_claim=false` を維持する。

## Execution routing

標準はGPT/Work側でprivate M7ファイルをmaterializeし、repoのpinned DuckDB環境で実行する。現在のmanaged runtimeでDuckDB導入がDNS/proxyで失敗した場合、科学ロジックを別engineへ置換しない。

既存 encrypted Drive→GPT→Actions bridge は optional transport だが、`DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM` 未設定のためlive E2E未受入。secret未設定のままprivate inputを公開化したり、公開Issueへ生データ/一時URLを置いたりしない。

## Acceptance gates

- PACI cohort 18/18
- M7 relative cohort 18/18
- M7 aggregate coverage exact match
- Analysis partitions SHA/size validation
- target date exclusive
- output identity uniqueness
- private horse-level output only to private path
- aggregate receipt identity-free
- all prediction/display/production flags false

## Encrypted output fallback for this acceptance

private-input bridge secretが未設定でも、この受入ではprivate M7をActionsへ送らない。公開Analysis/PACIだけで作るhorse-level v0.6 JSONをActions内の一時ファイルに出し、既存`drive_gpt_actions_bridge.py`と同じ`AES-256-GCM + RSA-OAEP-SHA256`で一回限りの公開鍵へ暗号化する。平文はArtifact upload前に削除する。暗号文をGPT側で復号した後、`brdb_going_private_join_existing.py` がprivate M7とローカル結合する。

この経路でGitHubに渡るprivate-origin dataは0バイト。公開鍵は秘密情報ではない。復号秘密鍵はGit/Actions/Artifact/Libraryへ保存しない。

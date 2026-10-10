# Issue Router T3 第1バッチ報告

## 基準と範囲

- 監査基準 `main`: `5f2e5b2e9807bff54bf84e5561e5273c8ffc40f5`（2026-10-10 JST に GitHub branch API で確認）。
- `.github/workflows` 内の YAML: 200 ファイル。
- 移行前の `issues: opened`: 121 ファイル。分類 A=7、B=99、C=10、D=5。
- 詳細: [inventory](issue_router_t3_inventory.md) / [JSON](issue_router_t3_inventory.json)。Class C は削除候補という意味に限り、今回削除していない。
- 第1バッチは JRDB の単一 prefix・JSON 本文・既存 module 呼び出し系 4 本。目安の 10〜20 本より小さい。残りの A 候補は公開・holdout・長時間処理等の契約確認を優先する。

## 変更

| Workflow | Router prefix | event_type |
|---|---|---|
| `.github/workflows/jrdb_annual_raw_fetch_issue.yml` | `[JRDB_ANNUAL_RAW_FETCH_REQUEST]` | `jrdb_annual_raw_fetch_request` |
| `.github/workflows/jrdb_daily_history_fetch_issue.yml` | `[JRDB_DAILY_HISTORY_FETCH_REQUEST]` | `jrdb_daily_history_fetch_request` |
| `.github/workflows/jrdb_legacy_family_year_issue.yml` | `[JRDB_LEGACY_FAMILY_YEAR_REQUEST]` | `jrdb_legacy_family_year_request` |
| `.github/workflows/jrdb_index_base_audit_issue.yml` | `[JRDB_INDEX_BASE_AUDIT]` | `jrdb_index_base_audit` |

上記 4 本から個別 `issues: opened` を除き、`repository_dispatch` と `workflow_dispatch(issue_number)` を追加。target は GitHub API で owner 起票かつ prefix 一致の Issue を再取得し、`/tmp/routed_issue.json` に保存する。request parser はそこから title/body を読み、既存 module・artifact・RESULT・close 条件を維持する。registry に上記 4 route を追加した。`INDEX_BASE_AUDIT` は元の request ID 制約（1〜80文字）を維持し、他の 3 route は元の title 契約どおり suffix 空文字も許容する。

## 静的検証

- 4 target の YAML parse、trigger、registry path/event_type、`github.event.issue` 残存 0 件: PASS。
- registry の prefix / event_type 重複なし、path 実在、必須 field 非空: PASS。
- 4 target の埋め込み Python の構文 parse と `git diff --check`: PASS。
- Issue body の `GITHUB_ENV` 経由転送: なし。
- 監査基準時点の `jrdb_newspaper_current_audit_issue.yml` には YAML parse error（88 行目の Markdown fence）があった。後続修正の結果は末尾に記録。

## Live verification と fan-out

| Case | Issue | Router run | target run | RESULT / artifact / close |
|---|---:|---:|---:|---|
| Daily History BAC 2025-12-28 | [#1938](https://github.com/yukki0113/GPT/issues/1938) | [38006627594](https://github.com/yukki0113/GPT/actions/runs/38006627594) | [38006643261](https://github.com/yukki0113/GPT/actions/runs/38006643261) | `success`。`jrdb-daily-history-20251228-20251228`（artifact ID 11650943760）、RESULT コメント、`completed` close |
| Annual Raw BAC 2025 | [#1939](https://github.com/yukki0113/GPT/issues/1939) | [38006741560](https://github.com/yukki0113/GPT/actions/runs/38006741560) | [38006756253](https://github.com/yukki0113/GPT/actions/runs/38006756253) | `success`。`jrdb-annual-raw-2025-2025`（artifact ID 11651103730）、RESULT コメント、`completed` close |

両 target で `Resolve request Issue`、既存 parser、fetch module、validation、artifact upload、RESULT/close の全 step が成功した。代表 2 Issue はどちらも closed で、failed/stale な検証 Issue は open で残っていない。

| KPI | Before | After | 根拠 |
|---|---:|---:|---|
| Issue 1 件あたりの `issues` event run 数 | 120 | 116 | 移行前の `[JRDB_NEWSPAPER_CURRENT_AUDIT] 20261010 edge-status-recheck` と移行後の #1938 / #1939 に紐づく Actions run を GitHub API で集計。2 ケースとも 116。 |
| `issues: opened` listener 静的件数 | 121 | 117 | 200 workflow ファイルを監査し、今回 4 target の listener を撤去。 |

静的 117 と実測 116 の差は、監査時点で構文エラーのあった workflow が Actions run を生成していなかったため。後続修正後の実 Issue #1943 では 117 run を実測した。

## 保留とリスク

- Class B 99 件は複数 prefix、upstream artifact、freeze/holdout、本文形式、失敗時の終端などを個別確認する。全件は inventory を参照。
- Class C 10 件は temporary/smoke/保守を示す名称からの削除候補。README・現行参照・履歴で確認するまで disable / delete しない。
- Class D 5 件は Router 本体、共通 fallback / 保守入口。変更なし。
- 残り 2 target は静的検証のみ。代表 2 ケースで end-to-end と fan-out 減少を確認したが、全 4 workflow 個別の実行成功は未検証。
- 変更 commit: `9903ec7a2fbc4984e0c357a3c5063eaf629bbb8b`。2026-10-10 JST に GitHub branch API で `main` が同 SHA を指すことを確認した。

## 次のバッチ

JRDB の `jrdb_runperf_audit_issue.yml` と、他 project の候補は各 project contract と failure/close を個別確認してから選ぶ。Class B/C/D は機械的に置換しない。

## 後続修正: Newspaper Current Audit の YAML エラー（2026-10-10 JST）

- `.github/workflows/jrdb_newspaper_current_audit_issue.yml` の成功コメント内にあったインデント外の Markdown fence を修正。`/tmp/comment.md` を作成し、`gh issue comment --body-file` で投稿する形にした。業務監査ロジックと Issue close 条件は変更していない。
- YAML、埋め込み Python、各 `run` の `bash -n`、`git diff --check`: PASS。
- 修正 commit: `f590596c2ff6f265006eb844435e1c385c141c12`。
- 実 Issue [#1943](https://github.com/yukki0113/GPT/issues/1943) → run [38007831076](https://github.com/yukki0113/GPT/actions/runs/38007831076): workflow `success`、JSON fence 付き RESULT コメント、`completed` close を確認。`issues` event run は 117 本。
- RESULT 内の `manifest_edge.state=ERROR` は参照した current release の既存状態であり、workflow の構文・実行成功とは区別する。
- inventory JSON/MD の `parse_errors` は監査基準 commit の履歴値として保持する。

# JRDB Newspaper thread handoff

## Phase 2 current contract — Issue #2329

通常Newspaperは PACI → Base/history → 監査PASS → 日次artifact → 任意のEval/RaceNote/RRDB/イルカmerge → 個人/桃太郎投影 → Current候補 の経路を使う。EdgeDB STANDARD/v0.5・Training Edge入力を要求・探索・実行しない。日次requestは `date` とPACI取得元のみで起動し、`revision` は省略時1。旧requestのAnalysis追加フィールドは無視する。仕様は `horse-racing/jrdb/newspaper/DAY_REQUEST_V2.md`。

旧Currentを基にした新revisionでは共通の `jrdb_newspaper_retired_sources.py` が廃止sourceを除去し、race SHA/size・manifest・package・auditを再生成する。通常mergeの `--my-index-csv` は廃止。既存immutable revisionやRelease/Drive正本は変更しない。Eval WATCH/MATCH、Eval.analysis、RRDB不利分析、JRDB/履歴、RaceNote、イルカ、桃太郎の予想/コメントは維持する。Fact Lite/Stats Mart/canonical Analysisは独立経路として維持する。

STANDARD/v0.5本番再投入workflowはjob条件falseで停止。Pagesは通常full-site組立を維持し、Edge smoke・Edge再公開triggerを廃止。研究preview/計算/configと過去文書の資産廃止判定はPhase 3。本PRでは本番反映しないため、コード上の依存解除と実配信完了を区別する。Phase 1の本番画面確認も未完了。

## Purpose

この文書は、会話量上限・担当交代・新しいWorkスレッドから、JRDB Newspaperの日次生成と公開を安全に再開するための短い入口です。日付付きの作業結果は保持せず、current contractと実装への導線だけを固定します。

## Restart order

1. GitHub `yukki0113/GPT` のlatest `main` を確認する。
2. `../README.md`、この文書、`CONTEXT.md`、`WORKFLOW.md`、`DAILY_WORK_CONTRACT.md`、`REQUEST_CONTRACT.md` を読む。
3. 親JRDBの `README.md`、`.gpt/HANDOFF.md`、`.gpt/WORKFLOW.md` を確認する。
4. 対象日の `publish/current.json`、直近のCurrent Publish / Pages run、対象sourceのartifactまたはcanonical Drive fileをread/auditする。
5. 当日の入力を attachment -> Library -> Drive canonical -> verified Actions/frozen artifact の順でresolveする。
6. build前に、使用する `jrdb_newspaper_day_build.py`、`jrdb_newspaper_merge_external.py`、schema、PWAのlatest mainを確認する。

## Current operating model

- PACI/BaseだけがHard Stop対象。optional addonの欠損は`READY / NOT_FOUND / ERROR / NOT_EXPECTED`で扱い、可能な範囲でrevisionを公開する。
- 同日更新は既存JSONを編集せず、前revisionのverified inputsと新入力からclean rebuildして次revisionを作る。
- Driveのday-packageが日次正本、GitHub Releaseは配布cache、GitHub PagesとOPFSはconsumer copyである。
- JSON、PACI、Raw、秘密情報はGitへcommitしない。

## Ownership and non-negotiable boundaries

Eval PWA提出CSVは旧Eval完成CSVより優先する。analysis列が無い旧CSVは正常で、`analysis: null`として扱う。

## Minimum publication checklist

## Where to investigate
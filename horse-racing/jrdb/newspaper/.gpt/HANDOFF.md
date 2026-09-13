# JRDB Newspaper thread handoff

## Purpose

この文書は、会話量上限・担当交代・新しいWorkスレッドから、JRDB Newspaperの日次生成と公開を安全に再開するための短い入口です。日付付きの作業結果は保持せず、current contractと実装への導線だけを固定します。

## Restart order

1. GitHub `yukki0113/GPT` のlatest `main` を確認する。
2. `../README.md`、この文書、`CONTEXT.md`、`WORKFLOW.md`、`DAILY_WORK_CONTRACT.md`、`REQUEST_CONTRACT.md` を読む。
3. 親JRDBの `README.md`、`.gpt/HANDOFF.md`、`.gpt/WORKFLOW.md` を確認する。
4. 対象日の `publish/current.json`、直近のCurrent Publish / Pages run、対象sourceのartifactまたはcanonical Drive fileをread/auditする。
5. 当日の入力を attachment -> Library -> Drive canonical -> verified Actions/frozen artifact の順でresolveする。
6. build前に、使用する `jrdb_newspaper_day_build.py`、`jrdb_newspaper_merge_external.py`、`jrdb_newspaper_merge_edge.py`、schema、PWAのlatest mainを確認する。

## Current operating model

```text
PACI / Base
  -> day build
  -> Eval (PWA submission preferred)
  -> RaceNote prediction
  -> keibailuka
  -> Edge matcher output
  -> audit / day package
  -> immutable Drive revision
  -> current.json
  -> Current Publish
  -> Pages
```

- PACI/BaseだけがHard Stop対象。optional addonの欠損は`READY / NOT_FOUND / ERROR / NOT_EXPECTED`で扱い、可能な範囲でrevisionを公開する。
- 同日更新は既存JSONを編集せず、前revisionのverified inputsと新入力からclean rebuildして次revisionを作る。
- Driveのday-packageが日次正本、GitHub Releaseは配布cache、GitHub PagesとOPFSはconsumer copyである。
- JSON、PACI、Raw、秘密情報はGitへcommitしない。

## Ownership and non-negotiable boundaries

| Source | Newspaperの責務 | 禁止事項 |
| --- | --- | --- |
| Eval PWA提出CSV | exact joinと`addons.eval.analysis`への透過格納 | 条件、WATCH/MATCH、H1/H2、コメントの再判定・補正 |
| RaceNote prediction | 完成handoffのnamespace merge | Base/historyへのRaceNote内部実装依存 |
| keibailuka | sparse exact match | 馬名の近似・自動補正 |
| EdgeDB | matcher outputを`special_memos`へexact merge | Edge条件の再実装・再判定 |

Eval PWA提出CSVは旧Eval完成CSVより優先する。analysis列が無い旧CSVは正常で、`analysis: null`として扱う。

## Minimum publication checklist

- Base date、race count、runner headcount、canonical key一意性
- Eval/RaceNote exact join、keibailuka sparse coverage、Edge full exact join
- history `as_of < target_date`、schema、SHA-256、same-input merge idempotence
- Eval提出CSVではcomment行数と`NONE / WATCH / MATCH`受領件数
- Drive保存済み、`current.json`更新済み、Current Publish success、Pages success

## Where to investigate

- 日次契約・例外規則: `DAILY_WORK_CONTRACT.md`
- D routeのIssue/body/parser規約: `REQUEST_CONTRACT.md`
- 実行経路A/B/C/D: `WORKFLOW.md`
- UI表示とPWA配布: `../../pwa/README.md`、`../../pwa/newspaper.html`、`../../pwa/newspaper-v9.js`
- Eval分析コメント契約: `../../../eval/docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
- Current publish contract: `../publish/README.md`

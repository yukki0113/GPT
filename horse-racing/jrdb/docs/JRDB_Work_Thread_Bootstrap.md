# JRDB Work Thread Bootstrap

更新日: 2026-09-13

## この文書の目的

会話量上限や担当スレッド移動後に、JRDBの現行運用を安全に再開するための最短入口です。GitHub `yukki0113/GPT` の `main` を正本とし、開始時は必ず最新mainと各リンク先を読み直します。

## 現行の設計原則

- JRDB Raw ZIP/PACIがデータ原典。Core SQLiteは常設の中間入力にしない。
- 固定長の解釈は `src/jrdb_raw.py` のCommon Readerへ集約する。consumerが既存fieldのbyte offsetを再実装しない。
- Analysis Lite、Stats Mart、Fact Liteは派生層。大容量のcurrent artifact正本はGoogle Drive、source/test/schema/docsはGit。
- 過去レースの予測・比較ではas-ofを守り、対象日以後の結果を混入させない。
- RaceNoteは観測データアダプタであり、予測ロジックを内包しない。Evalとイルカブログは別系統の入力として扱う。

## 再開時の必読順

1. ルート `.gpt/GITHUB_OPERATION_POLICY.md` と `.gpt/README.md`
2. `horse-racing/jrdb/README.md`
3. `horse-racing/jrdb/.gpt/CONTEXT.md` と `.gpt/WORKFLOW.md`
4. この文書
5. 依頼に対応する `docs/README_*.md`、source、test、workflow

Read/Auditと通常のテキストGit Changeは直接経路、Secrets・大容量SQLite・正式artifact/Pages publicationはActions-Native経路を使う。

## 開催後の標準運用

```text
PACI + SED
→ Analysis Lite v1.3の日付単位replace
→ Analysis / Mart監査
→ 更新済みAnalysisとMartをDrive 20_martへ正本保存・再fetch確認
→ Fact Lite v0.3を更新済みAnalysisから生成・検証
→ Fact Lite Release / GitHub Pages manifest更新
→ 条件別集計PWAがmanifest差分を検知しOPFS DBを安全に切替
```

- post-race更新: `.github/workflows/jrdb_post_race_refresh_issue.yml`
- request contract: `docs/README_post_race_analysis_mart_refresh.md`
- Fact Lite publication: `.github/workflows/jrdb_pwa_fact_lite_publish.yml`
- Fact Lite/PWA仕様: `docs/README_build_jrdb_pwa_fact_lite.md`、`pwa/README.md`

Analysis保存前にFact Lite publishを始めず、Fact Lite検証/Pages publish失敗時はPWAを最新扱いにしない。

## 主な責務分離

| 領域 | 主な入口 | 注意点 |
|---|---|---|
| Raw/Common Reader | `src/jrdb_raw.py` | fixed-byte offsetの唯一の正本 |
| Analysis/Mart | post-race refresh workflow | PACI+SED、同日replace、Drive current artifact |
| 条件別集計PWA | Fact Lite publish workflow | Fact Liteが主DB、Martは補助 |
| RaceNote | `src/racenote_request.py` | as-of safe、v1.0 bundle |
| Edge/Ability/追切研究 | 各 `docs/*Protocol*` | 研究層とproduction deliveryを混同しない |

## 引継ぎで残すべき状態

- latest main SHA
- 対象日・data-through date
- 利用したDrive artifactのfile ID/filename/SHA（監査記録。Git恒久設定には書かない）
- Actions run ID、artifact名、RESULT marker
- 成功/失敗した検証条件と、未完ならfailed step
- 次に起票すべきIssueと、その入力がすでにSUCCESS確認済みか


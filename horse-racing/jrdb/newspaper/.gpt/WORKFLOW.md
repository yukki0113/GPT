# JRDB Newspaper GPT workflow

1. `README.md` と `.gpt/CONTEXT.md` を確認する。
2. 親JRDBの `../README.md` / `../.gpt/CONTEXT.md` / `../.gpt/WORKFLOW.md` を確認する。
3. Newspaper design / schemaを確認する。
4. Common Reader / RaceNote / Edge / Eval等の既存source contractを再利用し、固定長offsetやjoin推測を重複実装しない。
5. 実装時はJRDB Base生成とexternal addon mergeを分離する。
6. addon未取得をBase生成失敗とみなさない。source_status=PENDING/nullで保持する。
7. mergeはnamespace ownershipを守り、他source値を変更しない。
8. historical testではtarget date以降の結果を混入させない。
9. schema validation / key uniqueness / headcount / history as-of / merge idempotenceをテストする。
10. 日次生成JSON、JRDB Raw、PACI、秘密情報をGitへcommitしない。
11. PWA実装時は既存Pages / OPFS safe-sync思想と整合させる。
12. 仕様変更時はdesign/schema/contextを同時更新し、Git `main` を正本とする。

## Planned routine command semantics

ユーザーが

```text
MM/DDの競馬新聞用データを生成してください。
```

と依頼した場合、production実装後は原則として次を一連で行う。

1. target dateを確定
2. PACIをresolve/fetch
3. JRDB Baseを生成
4. as-of-safe historyを付与
5. external sourceを探索
6. available sourceをnamespace-safe merge
7. race schema / daily manifest schemaをvalidation
8. Drive canonicalへ保存
9. 配布が有効ならpublish manifest/race filesを更新
10. READY/PENDING/ERROR source stateと成果物を報告

同日再実行では同じBaseを安全に再利用または再構築し、source version差分だけを反映できる設計にする。

## First PoC

`2026-08-16 札幌11R 札幌記念` を第一候補とする。

PoCでは外部addonを必須にせず、JRDB Base + history + null addon slotsで1 race JSONを生成し、schema / size / UI projection適合性を確認する。

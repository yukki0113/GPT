# JRDB Newspaper GPT workflow

1. `README.md` と `.gpt/CONTEXT.md` を確認する。
2. 親JRDBの `../README.md` / `../.gpt/CONTEXT.md` / `../.gpt/WORKFLOW.md` を確認する。
3. Newspaper design / schemaを確認する。
4. Common Reader / neutral JRDB history/access / Edge / Eval等の既存source contractを確認する。
5. **NewspaperのJRDB Base/historyから `racenote_*` moduleを直接importしない。**
6. RaceNoteにしかない処理をNewspaperでも必要とする場合は、まずneutral JRDB moduleへ抽出し、RaceNote側もそのneutral module利用へ変更してから共有する。
7. 固定長offsetやjoin推測をconsumer側へ重複実装しない。新Raw fieldはCommon Readerへ追加する。
8. 実装時はJRDB Base生成とexternal addon mergeを分離する。
9. addon未取得をBase生成失敗とみなさない。source_status=PENDING/nullで保持する。
10. mergeはnamespace ownershipを守り、他source値を変更しない。
11. historical testではtarget date以降の結果を混入させない。
12. schema validation / key uniqueness / headcount / history as-of / merge idempotenceをテストする。
13. 日次生成JSON、JRDB Raw、PACI、秘密情報をGitへcommitしない。
14. PWA実装時は既存Pages / OPFS safe-sync思想と整合させる。
15. 仕様変更時はdesign/schema/contextを同時更新し、Git `main` を正本とする。

## Dependency preflight before implementation

PoC実装前に、必要機能を次へ分類する。

### A. 既存neutral moduleで満たせる
例:

- `src/jrdb_raw.py`
- `src/jrdb_raw_history.py`
- Canonical / Analysis等のconsumer-neutral access

そのまま利用してよい。

### B. RaceNote内にあるが本質的に汎用
Newspaperから直接呼ばない。

```text
RaceNote-specific implementation
  -> neutral JRDB moduleへ抽出
       -> RaceNote adapter
       -> Newspaper adapter
```

抽出時はRaceNoteの回帰テストを通し、既存RaceNote semantic behaviorを壊さない。

### C. RaceNote固有
予想/GPT-facing整形、RaceNote schema固有のenrichment、Reader View等はNewspaper Base/historyへ持ち込まない。

なおRaceNote predictionの**成果物**は、他外部sourceと同様にaddon merge対象として扱ってよい。

## Planned routine command semantics

ユーザーが

```text
MM/DDの競馬新聞用データを生成してください。
```

と依頼した場合、production実装後は原則として次を一連で行う。

1. target dateを確定
2. PACIをresolve/fetch
3. neutral JRDB layerからJRDB Baseを生成
4. neutral history/access層からas-of-safe historyを付与
5. external sourceを探索
6. available sourceをnamespace-safe merge
7. race schema / daily manifest schemaをvalidation
8. Drive canonicalへ保存
9. 配布が有効ならpublish manifest/race filesを更新
10. READY/PENDING/ERROR source stateと成果物を報告

同日再実行では同じBaseを安全に再利用または再構築し、source version差分だけを反映できる設計にする。

## First PoC

`2026-08-16 札幌11R 札幌記念` を第一候補とする。

ただし最初に **neutral dependency inventory** を作成し、Newspaper Base/historyがRaceNote実装へ依存しないことを確認してからPoCへ進む。

PoCでは外部addonを必須にせず、JRDB Base + Newspaper-owned history + null addon slotsで1 race JSONを生成し、schema / size / UI projection適合性を確認する。

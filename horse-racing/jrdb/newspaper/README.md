# JRDB Newspaper module

Status: DESIGN / NO PRODUCTION IMPLEMENTATION YET

このディレクトリは、JRDB PWA向け「自分用競馬新聞」の日次生成・外部source merge・配布契約を独立管理するためのmodule boundaryです。

## Design source of truth

- `../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- `../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- `../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`

## UI order

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

1頭1行を基本とし、スマホ横スクロールを前提にします。

## Planned routine request

将来の専用Workスレッドでは、ユーザーが原則として日付だけ指定できる運用を目標とします。

```text
09/12の競馬新聞用データを生成してください。
```

同じ依頼を再実行可能とし、初回はJRDB Baseを生成、後続実行ではその時点で取得可能なEval / RaceNote prediction / keibailuka / Edge / independent indexを安全にmergeします。

外部sourceが未取得でもJRDB Base生成を妨げず、未取得slotはnull/PENDINGで保持します。

## Source responsibilities

- JRDB Raw / PACI fixed-width parse: `../src/jrdb_raw.py`
- JRDB current race / runner base: BAC / KYI / UKC等のpre-race data
- history: existing RaceNote / shared enrichment logicを再利用し、独自offset / 独自previous-run resolverを複製しない
- Eval: `addons.eval`
- RaceNote prediction: `addons.racenote_prediction` + race-level RaceNote note
- keibailuka: `addons.keibailuka`
- independent index: `addons.my_index`
- Edge Registry: `edge_matches`

RaceNote v1.0、Eval、Edge Registry等の既存source truthはこのmoduleへ移さない。

## Storage / delivery target

日次生成物はGit管理外。

候補:

```text
Drive canonical
  -> publish workflow
  -> GitHub Pages data
  -> PWA
  -> OPFS offline copy
```

Gitはcode / schema / docsのみを正本管理します。

## Implementation status

未実装:

- newspaper builder
- merge engine
- daily manifest builder
- Drive save
- publish workflow
- PWA newspaper page
- OPFS newspaper sync

最初の実装PoC候補は `2026-08-16 札幌11R 札幌記念` です。

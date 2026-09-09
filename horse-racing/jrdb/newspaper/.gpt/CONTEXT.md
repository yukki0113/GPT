# JRDB Newspaper project context

## Status
DESIGN ONLY. Production builder / merger / publisher / PWA page are not implemented yet.

## Goal
スマホ中心の自分用競馬新聞を、JRDB Base + optional external addonsのハイブリッド日次bundleとして生成・配布する。

UI meaning order:

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

## Source of truth
- JRDB fixed-width parse: `../../src/jrdb_raw.py`
- Newspaper design: `../../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- Race bundle draft schema: `../../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- Daily manifest draft schema: `../../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- RaceNote source truth remains RaceNote v1.0. Newspaper does not replace or mutate it.
- Edge source truth remains JRDB Edge Registry.
- Eval / keibailuka / independent index remain separate source systems.

## Routine target
将来のWork運用では、ユーザーの通常依頼を次の形まで簡略化する。

```text
MM/DDの競馬新聞用データを生成してください。
```

実行はhybrid / idempotentとする。

- PACIがあればJRDB Baseを生成する
- external addonが利用可能ならmergeする
- unavailable addonはPENDING/nullのまま保持する
- 同じ日付への再実行で新たに利用可能になったaddonだけを安全に反映する

## Merge ownership
- JRDB: race / basic / jrdb / history
- Eval: addons.eval
- RaceNote prediction: addons.racenote_prediction and owned race note fields
- keibailuka: addons.keibailuka
- independent index: addons.my_index
- Edge matcher: edge_matches

各consumerは他source namespaceを上書きしない。

## Identity
External default join:

```text
date + venue_code + race_no + horse_no
```

JRDB内ではrace_key / race_horse_key / horse_idも保持する。
馬名推測joinを標準化しない。

## History
既存RaceNote production policyを第一候補として再利用する。

- detailed recent max 5
- compact older max 3
- target dateより前の履歴だけを利用

## Distribution
日次生成JSONはGitへ入れない。Driveを保存正本候補とし、PWA配布面はGitHub Pages data + manifest、端末側はOPFSを第一候補とする。

## Deferred
- live/final odds
- 当日最終馬体重
- 勝負服画像
- 10走以上
- Edge status表示policy
- 独自指数計算

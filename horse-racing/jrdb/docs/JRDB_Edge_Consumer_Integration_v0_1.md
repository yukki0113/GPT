# JRDB Edge Consumer Integration v0.1

Status: **INITIAL RELEASE / CONSUMER READY**
Established: 2026-09-09

## Purpose

JRDB Edge Registryの初版を、独自指数、RaceNote/GPT、PWA競馬新聞など他consumerから安全に参照するための共通運用を定義する。

ConsumerはEdge探索・条件導出・current matchingを独自実装しない。EdgeDB側の公開Registryと共通Matcher/Freeze出力を再利用する。

## Source of truth

GitHub `yukki0113/GPT` main の `horse-racing/jrdb/` を正本とする。

初版Full Registry publication anchor:

- Registry version: `phase1-003-research-2010-2025-d`
- Build Issue: `#572`
- run_id: `34299375131`
- artifact: `jrdb-edge-registry-v2-phase1-003-full-2010-2025-d-34299375131`
- `edge_registry_active.jsonl` SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- final live Edge: ACTIVE 1,111 / PROVISIONAL 51
- WATCH: 1,750

ConsumerがRegistryを直接取得する場合は、成功RESULTに記録された `run_id + artifact_name + file SHA-256` を完全一致で固定する。単に「最新artifactらしきもの」を推測して使わない。

## Preferred daily consumption

開催日のconsumerは、各プロジェクトでMatcherを個別再実行するより、EdgeDB側で作った当日Freezeを共通利用することを推奨する。

```text
published Registry
  + pre-race PACI
  + optional Analysis Lite history
      -> [JRDB_EDGE_FORWARD_FREEZE]
      -> edge_matches.jsonl
      -> manifest.json / provenance.json
             |
             +--> RaceNote/GPT
             +--> PWA newspaper
             +--> independent index Edge layer
```

Freezeは最初の発走予定時刻より前であることをコードで検証し、SED/結果を入力に持たない。

ConsumerはFreeze RESULTに記録された `run_id / artifact_name / manifest_sha256 / matches_sha256` を固定して取得する。

Freezeが存在しない開発・検証用途では、次の共通runnerを使用する。

```bash
python horse-racing/jrdb/src/run_jrdb_edge_match_current.py \
  --paci /path/to/PACIyymmdd.zip \
  --analysis-db /path/to/jrdb_analysis_v1_2.sqlite \
  --registry-jsonl /path/to/edge_registry_active.jsonl \
  --output-jsonl /path/to/edge_matches.jsonl
```

独自の条件比較ロジックをconsumer側へ複製しない。

## Output contract

`edge_matches.jsonl` は1頭1行。

```json
{
  "key": {
    "race_key": "...",
    "race_horse_key": "...",
    "horse_id": "...",
    "horse_no": 1,
    "race_date": "YYYY-MM-DD"
  },
  "edge_matches": []
}
```

各matchには少なくとも、consumerが表示・分析に必要な次の情報が含まれる。

- `edge_id`
- `display_text`
- `polarity`
- `status`
- `strength_score`
- `confidence_band`
- `registry_version`
- `evidence`（一致したexact condition、family、review_due等）

## Status policy

通常consumerの既定対象は `ACTIVE` のみ。

- `ACTIVE`: 通常表示・分析対象
- `PROVISIONAL`: shadow/研究用途で明示opt-in
- `WATCH`: shadow/研究用途で明示opt-in
- `DECAYING`: 原則通常利用しない

`PROVISIONAL/WATCH` を通常表示へ混ぜる場合はconsumer側で明示する。

## Consumer-specific use

### RaceNote / GPT

Edgeを今回条件に対する supporting / opposing evidence として使用する。

推奨表示:

- Edge条件の短い説明
- POSITIVE / NEGATIVE
- confidence / strength
- historical sample / place rate / ROI等、必要な範囲の根拠

Phase1ではEdgeだけを理由に最終予想や買い目を決定しない。

### PWA newspaper

馬ごとの `EDGE MEMO` / プラス材料・マイナス材料として表示する。

複数Edgeが一致した場合も、consumerが独自に同一条件を再判定せず、`edge_matches[]` をそのまま入力とする。

### Independent index / Ability project

AbilityとEdgeは分離する。

Phase1ではRegistry EdgeをAbilityまたは最終指数へ自動加点・減点しない。

```text
Ability = 平常時の能力
Edge    = 今回条件の上振れ/下振れ材料
Value   = 独自評価と市場との差
```

指数への数値寄与を導入する場合は、TRUE_FORWARD蓄積後に別のcalibration仕様を作り、既存EdgeDBのhistorical ROIをそのまま加点値へ変換しない。

## Leakage rules

Consumerは次を守る。

- current-race条件はpre-race PACI由来のみ
- SED、着順、払戻、最終オッズ、最終人気をcurrent Edge判定へ使わない
- TRANSITIONはKYI exact prev1 link + same horse_idでのみ解決
- exact previous historyが無ければ推測補完しない
- later-dated historyを使わない

## Forward feedback

実運用成績はEdgeDB側のTRUE_FORWARD Ledgerへ集約する。

Consumerは独自にRegistry statusを書き換えない。

```text
pre-race Freeze
  -> consumer use
  -> post-race Settlement
  -> TRUE_FORWARD Ledger
  -> later lifecycle review
```

`RECONSTRUCTED_BACKFILL` は診断用途であり、TRUE_FORWARD KPIへ混ぜない。

## Initial release report

他プロジェクトへは次を伝えればよい。

1. JRDB Edge Registry初版が完成した。
2. 2010-2025 Full Registryのconsumer向け初版publicationはIssue #572 / run `34299375131`。
3. 日次利用は `edge_matches.jsonl` を共通入力とし、通常はACTIVEのみ使う。
4. RaceNote/PWAは表示・判断材料として利用可能。
5. 独自指数はPhase1では自動加点せず、Edge層として接続する。
6. 実運用成績はTRUE_FORWARD Ledgerで今後蓄積する。

## Related

- `docs/JRDB_Edge_Registry_Phase1_v0_1.md`
- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `docs/JRDB_Edge_Forward_Operations_v0_1.md`
- `docs/JRDB_Edge_Forward_Ledger_v0_1.md`
- `src/run_jrdb_edge_match_current.py`
- `src/run_jrdb_edge_forward_freeze.py`
- `schema/jrdb_edge_publication_manifest_schema_v0_1.json`

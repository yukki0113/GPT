# JRDB Edge Forward Ledger v0.1

Status: **IMPLEMENTED / SHADOW LEDGER**
Established: 2026-09-09

## Purpose

2026以降のForward監査で、開催前にfreezeしたEdge一致とレース後SED settlementを日次不変資産として累積する。

```text
pre-race edge_matches.jsonl
  -> post-race evaluate_jrdb_edge_forward.py
  -> daily forward audit JSONL
  -> build_jrdb_edge_forward_ledger.py
  -> cumulative SQLite ledger + summary JSON
```

LedgerはRegistryの状態を自動変更しない。ACTIVE / PROVISIONAL / WATCH等のlifecycle判断は、十分なForward期間を蓄積した後の別レビュー工程で行う。

## Evaluation mode

Forward auditは、時間方向の意味を混同しないため次のmodeを必須概念とする。

- `TRUE_FORWARD`: 対象レース前にMatcher出力をfreezeし、終了後にSEDでsettleした本来のForward評価。
- `RECONSTRUCTED_BACKFILL`: 後日、当時利用可能だったpre-race PACIと既存RegistryからMatcher出力を再構成してsettleした監査用backfill。SEDは条件生成へ使わないが、当日前freezeではないためTRUE_FORWARDとは分離する。
- `LEGACY_UNSPECIFIED`: evaluation_mode導入前の旧audit。推測でTRUE_FORWARDへ昇格しない。

Ledgerの通常summaryは `TRUE_FORWARD` のみを対象とする。`RECONSTRUCTED_BACKFILL` やlegacyを含む集計は明示的にmodeを指定した場合だけ返す。`ALL` は診断用途のみとし、運用KPIとして扱わない。

## Immutability contract

1開催日は1つのsemantic contentとして登録する。

- 未登録日: `IMPORTED`
- 同一日のsemantic contentが完全一致: `NOOP`
- 同一日だが内容が異なる: fail-closed

semantic contentには `evaluation_mode` も含む。同一日のauditを別modeへ付け替えて上書きすることはできない。

JSONの空白やキー順だけが違う場合は同値として扱う。Edge occurrenceの実内容、outcome、evidence、evaluation_modeが変わった場合は別物として拒否する。

Occurrence identityは次の3項目。

```text
race_date + runner_identity + edge_id
```

`runner_identity` とsettled SED outcomeの `race_key + horse_no` が一致しない場合も拒否する。

## Stored provenance

日単位:

- evaluation mode
- raw source SHA-256
- semantic SHA-256
- occurrence count
- ledger/schema version

Occurrence単位:

- evaluation mode
- Edge ID / family / polarity / status
- registry version（available when evaluator output carries it）
- strength/confidence
- evaluator version
- review_due
- eligibility
- historical evidence JSON
- settled outcome JSON
- canonical occurrence JSON

旧evaluatorで生成済みのauditにevaluation_modeが無い場合は `LEGACY_UNSPECIFIED` としてのみ取込可能とする。欠損値を推測補完しない。

## Cumulative summary

通常summaryの既定modeは `TRUE_FORWARD`。

- selected evaluation mode
- available evaluation modes / day count / occurrence count
- date coverage / zero-match days
- overall
- Edge別
- Edge × registry version別
- family別
- polarity別
- review_due別
- registry version別
- win/place rate
- win/place ROI
- historical weighted place rate/ROI
- Forwardとの差分

ROIはForward evaluatorと同じく、eligibleなmatched Edge occurrenceごとに100円を仮想投資したshadow指標であり、実購入戦略の成績ではない。

## CLI

TRUE_FORWARDの日次取込と通常summary:

```bash
python horse-racing/jrdb/src/build_jrdb_edge_forward_ledger.py \
  --ledger /path/to/jrdb_edge_forward_2026.sqlite \
  --audit-jsonl /path/to/forward_eval_260912_audit.jsonl \
  --output-json /path/to/forward_ledger_summary.json
```

RECONSTRUCTED_BACKFILLを明示集計する場合:

```bash
python horse-racing/jrdb/src/build_jrdb_edge_forward_ledger.py \
  --ledger /path/to/jrdb_edge_forward_2026.sqlite \
  --audit-jsonl /path/to/forward_eval_260905_audit.jsonl \
  --evaluation-mode RECONSTRUCTED_BACKFILL \
  --summary-evaluation-mode RECONSTRUCTED_BACKFILL \
  --output-json /path/to/forward_ledger_backfill_summary.json
```

Edge一致が0件でaudit JSONLが空の場合は、日付とmodeを両方明示する。

```bash
--race-date 2026-09-12 --evaluation-mode TRUE_FORWARD
```

`--summary-evaluation-mode ALL` は明示的な診断時だけ使用する。

## Leakage / lifecycle policy

- SEDはsettlement後のoutcomeとしてのみ保存する。
- 過去のmatch条件をSEDから再計算しない。
- 日次Ledgerの再投入で過去値を上書きしない。
- RECONSTRUCTED_BACKFILLをTRUE_FORWARDへ混入させない。
- Forward結果だけでRegistryを自動昇格・降格しない。
- lifecycle reviewは別工程とする。

## Related

- `docs/JRDB_Edge_Forward_Evaluation_v0_1.md`
- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `src/evaluate_jrdb_edge_forward.py`
- `src/build_jrdb_edge_forward_ledger.py`

# JRDB Edge Forward Ledger v0.1

Status: **IMPLEMENTED / SHADOW LEDGER**
Established: 2026-09-09

## Purpose

2026以降の完全Forward期間で、開催前にfreezeしたEdge一致とレース後SED settlementを日次不変資産として累積する。

```text
pre-race edge_matches.jsonl
  -> post-race evaluate_jrdb_edge_forward.py
  -> daily forward audit JSONL
  -> build_jrdb_edge_forward_ledger.py
  -> cumulative SQLite ledger + summary JSON
```

LedgerはRegistryの状態を自動変更しない。ACTIVE / PROVISIONAL / WATCH等のlifecycle判断は、十分なForward期間を蓄積した後の別レビュー工程で行う。

## Immutability contract

1開催日は1つのsemantic contentとして登録する。

- 未登録日: `IMPORTED`
- 同一日のsemantic contentが完全一致: `NOOP`
- 同一日だが内容が異なる: fail-closed

JSONの空白やキー順だけが違う場合は同値として扱う。Edge occurrenceの実内容、outcome、evidenceが変わった場合は別物として拒否する。

Occurrence identityは次の3項目。

```text
race_date + runner_identity + edge_id
```

`runner_identity` とsettled SED outcomeの `race_key + horse_no` が一致しない場合も拒否する。

## Stored provenance

日単位:

- raw source SHA-256
- semantic SHA-256
- occurrence count
- ledger/schema version

Occurrence単位:

- Edge ID / family / polarity / status
- registry version（available when evaluator output carries it）
- strength/confidence
- evaluator version
- review_due
- eligibility
- historical evidence JSON
- settled outcome JSON
- canonical occurrence JSON

初期Forward smoke等、旧evaluatorで生成済みのauditはregistry version等がnullでも取込可能とする。欠損値を推測補完しない。

## Cumulative summary

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

```bash
python horse-racing/jrdb/src/build_jrdb_edge_forward_ledger.py \
  --ledger /path/to/jrdb_edge_forward_2026.sqlite \
  --audit-jsonl /path/to/forward_eval_260905_audit.jsonl \
  --output-json /path/to/forward_ledger_summary.json
```

Edge一致が0件でaudit JSONLが空の場合だけ、日付を明示する。

```bash
--race-date 2026-09-12
```

## Leakage / lifecycle policy

- SEDはsettlement後のoutcomeとしてのみ保存する。
- 過去のmatch条件をSEDから再計算しない。
- 日次Ledgerの再投入で過去値を上書きしない。
- Forward結果だけでRegistryを自動昇格・降格しない。
- lifecycle reviewは別工程とする。

## Related

- `docs/JRDB_Edge_Forward_Evaluation_v0_1.md`
- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `src/evaluate_jrdb_edge_forward.py`
- `src/build_jrdb_edge_forward_ledger.py`

# JRDB Edge Forward Ledger v0.1

Status: **IMPLEMENTED / SHADOW ACCUMULATION**  
Established: 2026-09-09

## Purpose

2026 Forward期間の日次settlementを、後から再集計・監査できる不変ledgerへ蓄積する。

```text
frozen edge_matches.jsonl
  + post-race SED
  -> evaluate_jrdb_edge_forward.py
  -> forward_eval_*_audit.jsonl
  -> build_jrdb_edge_forward_ledger.py
  -> jrdb_edge_forward_ledger.sqlite
  -> cumulative summary JSON
```

LedgerはMatcherを再実行しない。SEDからEdge条件を再構成しない。Edge RegistryのACTIVE / PROVISIONAL / WATCH状態も変更しない。

## Occurrence identity

Forward evaluatorの基本単位と同じ **matched Edge occurrence** を保存する。

```text
occurrence_key = race_date | runner_identity | edge_id
```

例:

```text
2026-09-05|01262501:01|EDGE-A
```

同じoccurrenceを同じ内容で再投入することは冪等として許可する。内容が異なる場合は、古い値を上書きせずfail-closedする。

1つのaudit JSONL内に同じoccurrence_keyが複数存在する場合も入力異常として拒否する。

## SQLite schema

### `forward_ledger_meta`

Ledger schema versionを保持する。

### `forward_source_import`

入力audit JSONLをSHA-256で識別し、同一ファイルの再投入を冪等化する。

主な列:

- `source_digest`
- `source_name`
- `row_count`

### `forward_occurrence`

監査用の主要列を展開するとともに、元occurrence全体をcanonical JSONで保持する。

主な列:

- `occurrence_key`
- `race_date`
- `runner_identity`
- `horse_id`
- `edge_id`
- `family`
- `polarity`
- `registry_status`
- `review_due`
- `eligibility`
- `finish`
- `abnormal_code`
- `win_payout`
- `place_payout`
- historical place rate / ROI
- baseline place rate
- `occurrence_json`

## Import contract

入力は `evaluate_jrdb_edge_forward.py --audit-jsonl` の出力のみを想定する。

最低限、各rowに以下を要求する。

```text
race_date
runner_identity
edge_id
polarity
eligibility
evidence object
outcome object
```

`eligibility=ELIGIBLE` のrowに `outcome.finish` が無い場合は拒否する。

複数auditを1回のCLIで投入できる。各ファイルのtransactionはall-or-nothingで、immutable occurrence conflict時はそのsource import全体をrollbackする。

## Cumulative summary

Ledger summaryはForward evaluatorと同じ100円仮想投資 / matched Edge occurrence semanticsを維持する。

出力:

- overall
- edge別
- family別
- polarity別
- review_due別
- date range
- imported source audit一覧

win/place hit rate、win/place ROI、historical place rate / ROI、baseline place rateはForward evaluatorと同じ意味で集計する。

## CLI

```bash
python horse-racing/jrdb/src/build_jrdb_edge_forward_ledger.py \
  --ledger /path/to/jrdb_edge_forward_ledger.sqlite \
  --audit-jsonl /path/to/forward_eval_260905_audit.jsonl \
  --audit-jsonl /path/to/forward_eval_260906_audit.jsonl \
  --output-json /path/to/forward_ledger_summary.json
```

既存ledgerのsummaryだけを再生成する場合は `--audit-jsonl` を省略できる。

## Lifecycle boundary

このLedgerは **evidence accumulation only**。

少数開催日の結果を理由にRegistry statusを自動変更しない。将来のlifecycle reviewは、このLedgerに十分なForward evidenceが蓄積した後、別versionの明示的review procedureとして実装する。

そのため本実装はPhase1の統計Contract、canonical bucket、Matcher semantics、Edge statusを一切変更しない。

## Tests

`tests/test_build_jrdb_edge_forward_ledger.py` は以下を固定する。

1. 複数開催日の累積集計
2. Forward evaluatorとの集計semantics一致
3. 同一source再投入の冪等性
4. 別sourceに含まれる同一occurrenceのexact duplicate許容
5. immutable occurrence conflict時のfail-closed + rollback
6. 1 audit内の重複occurrence拒否
7. ELIGIBLE rowのfinish欠落拒否

## Related

- `docs/JRDB_Edge_Forward_Evaluation_v0_1.md`
- `docs/JRDB_Edge_Contract_v0_1.md`
- `src/evaluate_jrdb_edge_forward.py`
- `src/build_jrdb_edge_forward_ledger.py`

# JRDB Edge Forward Evaluation v0.1

Status: **IMPLEMENTED / SHADOW EVALUATION**
Established: 2026-09-09

## Purpose

2010–2025でDiscovery / Validation / Holdoutを通過したJRDB Edge Registryを、2026以降のForward期間で継続監査する。

Forward評価は当日照合と事後settlementを明確に分離する。

```text
PACI + Analysis history + published Edge Registry
  -> run_jrdb_edge_match_current.py
  -> frozen edge_matches.jsonl          # pre-race only

race completed
  -> SEDyymmdd.zip                      # post-race only
  -> evaluate_jrdb_edge_forward.py
  -> forward evaluation JSON / audit JSONL
```

SEDはMatcherへ渡さない。`evaluate_jrdb_edge_forward.py` は既に確定したmatcher outputをsettleするだけであり、Edge条件やcurrent factsを再計算しない。

## Evaluation mode

Evaluatorは時間方向の意味を `evaluation_mode` としてauditへ固定する。

- `TRUE_FORWARD`: 対象レース前にMatcher出力がfreeze済み。
- `RECONSTRUCTED_BACKFILL`: レース後に、当時のpre-race PACIと既存RegistryからMatcher出力を再構成した監査用backfill。SEDは条件生成に使わないが、事前freeze済みではない。
- `LEGACY_UNSPECIFIED`: mode導入前の旧auditをLedgerへ移す際の分類。通常の新規Evaluator実行では使わない。

CLI既定値は `TRUE_FORWARD`。過去日を後日再構成する場合は必ず `--evaluation-mode RECONSTRUCTED_BACKFILL` を明示する。

## Eligibility / labels

Feature Martと同じ結果ラベル規則を使う。

- `finish is None` -> `NO_RESULT`
- `abnormal_code` がblank/`0`以外 -> `ABNORMAL`
- 上記以外 -> `ELIGIBLE`
- win hit: `finish == 1`
- place hit: settled `place_payout > 0`

SEDのTYPE Z payout blankは0円returnとして扱う。複勝的中を着順だけで推測しない。

## Identity contract

Matcher rowとSEDは `race_key + horse_no` でexact joinする。

Matcher keyに`horse_id` / `race_date`が存在する場合、SED側と一致しなければfail-closedする。SED row欠落、重複SED key、重複matcher runner keyも推測補完しない。

## Aggregation semantics

Forward評価の基本単位は**matched Edge occurrence**。

同一馬に複数Edgeが一致した場合はEdgeごとに1 occurrenceとして数える。ROIは各occurrenceへ100円を仮想投資した比率であり、実際の購入戦略や馬単位のconsolidation成績ではない。

出力は最低限以下を持つ。

- evaluation mode
- overall
- family別
- polarity別
- review_due別
- polarity × family別
- unique Edge数 / unique runner数
- win/place hit rate
- win/place ROI
- matched Edgeに保存されたhistorical place rate / ROIのoccurrence-weighted平均
- baseline place rateのoccurrence-weighted平均

## CLI

通常のForward settlement:

```bash
python horse-racing/jrdb/src/evaluate_jrdb_edge_forward.py \
  --matches-jsonl /path/to/edge_matches.jsonl \
  --sed /path/to/SED260912.zip \
  --output-json /path/to/forward_eval_260912.json \
  --audit-jsonl /path/to/forward_eval_260912_audit.jsonl
```

後日再構成するbackfill:

```bash
python horse-racing/jrdb/src/evaluate_jrdb_edge_forward.py \
  --matches-jsonl /path/to/reconstructed_edge_matches_260905.jsonl \
  --sed /path/to/SED260905.zip \
  --evaluation-mode RECONSTRUCTED_BACKFILL \
  --output-json /path/to/forward_eval_260905.json \
  --audit-jsonl /path/to/forward_eval_260905_audit.jsonl
```

## Lifecycle policy

Forward settlementはRegistryの自動昇格・降格を行わない。

特に`review_due=true`は一致を隠す理由ではないが、再検証が必要なEdgeとして別集計する。少数開催日の結果だけでACTIVE状態を更新せず、2026 Forward ledgerを蓄積してからlifecycle reviewへ渡す。

## 2026-09-05 / 2026-09-06 implementation smoke

Full 2010–2025 Registryを実PACIへ適用し、当日SEDを事後settlement専用で使用した初回shadow auditでは、946 runnerすべてをSEDへexact joinできた。

この2日分はレース前にMatcher出力をfreezeしていた運用資産ではなく、2026-09-09に実装確認のため再構成したもの。したがって今後Ledgerへ保存する場合は `RECONSTRUCTED_BACKFILL` として扱い、`TRUE_FORWARD` の運用KPIへ混ぜない。

## Related

- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `docs/JRDB_Edge_Contract_v0_1.md`
- `docs/JRDB_Edge_Forward_Ledger_v0_1.md`
- `src/run_jrdb_edge_match_current.py`
- `src/evaluate_jrdb_edge_forward.py`

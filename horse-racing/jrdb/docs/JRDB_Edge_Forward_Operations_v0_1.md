# JRDB Edge Forward Operations v0.1

Status: **IMPLEMENTED / OPERATION READY**
Established: 2026-09-09

## Purpose

JRDB Edge Registryを2026以降で、時間方向を壊さずに日次運用するための標準経路を定義する。

本番Forwardは必ず次の2工程に分ける。

```text
published Registry + pre-race PACI + optional Analysis history
  -> TRUE_FORWARD Freeze
  -> immutable edge_matches.jsonl / manifest

race completed
  -> exact Freeze artifact + post-race SED
  -> TRUE_FORWARD Settlement
  -> immutable daily audit
  -> cumulative TRUE_FORWARD SQLite ledger
```

SEDはFreezeへ渡さない。SettlementはFreeze済み`edge_matches.jsonl`をsettleするだけで、Edge条件やcurrent factsを再計算しない。

## 1. TRUE_FORWARD Freeze

Issue prefix:

```text
[JRDB_EDGE_FORWARD_FREEZE]
```

Workflow:

```text
.github/workflows/jrdb_edge_forward_freeze_issue.yml
```

Driver:

```text
horse-racing/jrdb/src/run_jrdb_edge_forward_freeze.py
```

### Request body

JSON object。

Required:

- `date`: `YYYYMMDD`
- `registry_run_id`: successful Registry build run ID
- `registry_artifact_name`: exact successful Registry artifact name
- `registry_sha256`: exact SHA-256 of `edge_registry_active.jsonl`

Optional:

- `analysis_url`: Google Drive Analysis Lite URL
- `analysis_sha256`: Analysis SQLite SHA-256。`analysis_url`と必ず同時指定
- `expected_paci_sha256`: 既知PACI snapshotを再現するときだけ指定
- `statuses`: default `ACTIVE`

### Time guard

TRUE_FORWARDを名乗る条件をコードで強制する。

1. PACIのBACを読み、対象日の全raceから最初の`post_time_raw`を取得する。
2. Actions実行時刻をUTCで固定する。
3. 実行時刻が最初の発走予定時刻以上ならfail-closedする。
4. 対象PACIのrace dateとrequest dateが一致しなければ拒否する。

したがって、レース後に過去PACIを与えて`TRUE_FORWARD`を作ることはできない。後日再構成は必ず`RECONSTRUCTED_BACKFILL`経路を使う。

### Freeze artifact

最低限次を保存する。

- `edge_matches.jsonl`
- `current_facts.jsonl`
- `provenance.json`
- `manifest.json`
- exact PACI copy
- exact published Registry JSONL copy

`manifest.json`には次を固定する。

- `evaluation_mode = TRUE_FORWARD`
- `frozen_at_utc`
- `earliest_post_time_jst`
- `pre_race_guard = PASS`
- PACI / Registry / optional Analysis SHA-256
- `edge_matches.jsonl` SHA-256
- matcher version / current facts version / registry version

Success marker:

```text
JRDB_EDGE_FORWARD_FREEZE_RESULT
```

Downstream Settlementは、このRESULTの`run_id` / `artifact_name` / `manifest_sha256` / `matches_sha256`を完全一致で転記する。推測しない。

## 2. TRUE_FORWARD Settlement

Issue prefix:

```text
[JRDB_EDGE_FORWARD_SETTLE]
```

Workflow:

```text
.github/workflows/jrdb_edge_forward_settle_issue.yml
```

Driver:

```text
horse-racing/jrdb/src/run_jrdb_edge_forward_settlement.py
```

### Request body

Required:

- `date`: `YYYYMMDD`
- `freeze_run_id`: exact successful Freeze run ID
- `freeze_artifact_name`: exact successful Freeze artifact name
- `freeze_manifest_sha256`: Freeze RESULTのmanifest SHA-256
- `matches_sha256`: Freeze RESULTの`edge_matches.jsonl` SHA-256

Optional:

- `expected_sed_sha256`: 既知SED snapshotを固定するとき指定
- `previous_ledger`: 前回Settlement RESULTから完全一致転記するobject
  - `run_id`
  - `artifact_name`
  - `ledger_sha256`

最初のTRUE_FORWARD開催日は`previous_ledger`なしで新規ledgerを作る。2日目以降は直前のSettlement RESULTが返したledgerをexact chainする。

### Settlement guard

Settlementは次を全て満たさない限りfail-closedする。

- Freeze manifest `status = PASS`
- Freeze manifest `evaluation_mode = TRUE_FORWARD`
- Freeze manifest `pre_race_guard = PASS`
- Freeze manifest race date == request date
- Freeze manifest SHA一致
- frozen `edge_matches.jsonl` SHA一致
- optional prior ledger SHA一致
- SEDとmatcher runnerが`race_key + horse_no`で全件exact join
- matcher keyの`horse_id` / `race_date`がある場合SEDと一致

SEDはこの工程で初めて取得・使用する。

Success marker:

```text
JRDB_EDGE_FORWARD_SETTLE_RESULT
```

RESULTは次開催の`previous_ledger`参照に必要な`run_id` / `artifact_name` / `ledger_sha256`を返す。

## 3. Ledger semantics

Ledger既定summaryは`TRUE_FORWARD`だけを対象にする。

- `RECONSTRUCTED_BACKFILL`は本番KPIへ混ぜない。
- `LEGACY_UNSPECIFIED`を推測でTRUE_FORWARDへ昇格しない。
- `ALL`は監査用途だけに使う。
- 同一race dateのsemantic contentが異なる再投入は拒否する。
- SettlementはRegistryのACTIVE / WATCH等を自動変更しない。

Forward ROIはmatched Edge occurrenceごとに100円を仮想投資したshadow指標であり、実際の馬券戦略のROIではない。

## 4. Reconstructed backfill

Issue prefix:

```text
[JRDB_EDGE_FORWARD_BACKFILL]
```

9/5・9/6の初回実データ監査は、レース前Freeze資産ではなかったため`RECONSTRUCTED_BACKFILL`として固定した。

Canonical result:

- Issue: `#648`
- run: `34317148033`
- artifact: `jrdb-edge-forward-backfill-20260905-20260906-initial-a-34317148033`
- evaluation mode: `RECONSTRUCTED_BACKFILL`
- matcher / SED exact join: `946 / 946 runners`
- Edge occurrences: `1,212`
- eligible occurrences: `1,209`
- win ROI: `1.2508684863523574`
- place ROI: `0.9176178660049628`
- Analysis coverage max: `2026-08-23`

この結果はRegistryの動作監査・比較用には使えるが、TRUE_FORWARD KPIには入れない。

## 5. Regression / self-test

Self-test Issue prefix:

```text
[JRDB_EDGE_FORWARD_SELFTEST]
```

Workflow:

```text
.github/workflows/jrdb_edge_forward_selftest_issue.yml
```

2026-09-09 initial result:

- Issue: `#651`
- run: `34319094966`
- head SHA: `f0de14ea2ffb3123b539f0103ed0169607fed294`
- compile exit code: `0`
- Forward regression tests exit code: `0`

Tests cover at least:

- earliest-post pre-race guard
- invalid post-time rejection
- non-TRUE_FORWARD freeze rejection
- frozen matches tamper detection
- SettlementのTRUE_FORWARD強制
- TRUE_FORWARD / RECONSTRUCTED_BACKFILL / LEGACY_UNSPECIFIEDのLedger分離
- same-day immutable conflict

## 6. Standard daily operation

```text
A. 開催前
1. latest main確認
2. latest successful published Registry RESULT確認
3. PACI取得可能後、最初の発走より前にFREEZE Issue作成
4. FREEZE RESULT status=success / pre_race_guard=PASS確認
5. run/artifact/manifest SHA/matches SHAをFreeze正本として固定

B. レース後
6. Freeze RESULTからSETTLE requestを構築
7. 前回TRUE_FORWARD ledgerがあればprevious_ledgerをexact chain
8. SETTLE Issue作成
9. SED exact settlement / ledger import成功確認
10. SETTLE RESULTを次開催日のprevious_ledger正本とする
```

Freezeを当日前に実行できなかった開催日は、後からTRUE_FORWARDへ補完しない。必要ならBACKFILLへ回す。

## 7. Lifecycle review

TRUE_FORWARD Ledgerの蓄積はEdge lifecycle reviewの入力であり、日次SettlementそのものはRegistryを変更しない。

十分なout-of-sample期間・occurrence数を蓄積した後に、performance drift / value drift / review_due / registry versionを別工程でレビューする。少数日の好不調を理由に自動昇格・降格しない。

## Related

- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `docs/JRDB_Edge_Forward_Evaluation_v0_1.md`
- `docs/JRDB_Edge_Forward_Ledger_v0_1.md`
- `src/run_jrdb_edge_forward_freeze.py`
- `src/run_jrdb_edge_forward_settlement.py`
- `src/run_jrdb_edge_forward_backfill.py`

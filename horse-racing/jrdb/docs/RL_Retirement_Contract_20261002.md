# RL / RaceLift Research Retirement Contract

Date: 2026-10-02
Status: ACTIVE

## 1. Decision

RaceLift（RL）指数研究・Training Edge / RL-T の新規開発および日次指数算出は終了する。

終了理由は、RLで統合しようとしていた情報が現在は別のproduction機能として直接可視化・活用されているためである。

代表例:

- Newspaper: 追い切り上昇度、EdgeDB表示
- RaceNote: 追い切り指数、前走不利、能力・適性・展開その他の証拠を個別意味のまま統合
- EdgeDB: pre-race evidenceを独立したevidence channelとして提供

したがって、これらを再度重み付けして単一RL指数へ圧縮することを通常productionの責務にしない。

## 2. Normative status

```text
RL_RESEARCH_STATUS                  = RETIRED
RL_NEW_INDEX_DEVELOPMENT            = STOPPED
RL_DAILY_INDEX_GENERATION           = STOPPED
RL_INDEX_REQUIRED_BY_PRODUCTION     = FALSE

RL_T_V0_2_ROLE                      = FROZEN_REPRO_ASSET
TRAINING_RESEARCH_ROLE              = FROZEN_RESEARCH_ASSET

JRDB_WAREHOUSE_ROLE                 = ACTIVE_SHARED_INFRA
JRDB_INDEX_BASE_ROLE                = ACTIVE_SHARED_INFRA
RECORD_HASH_COMPAT_ROLE             = ACTIVE_SHARED_INFRA
```

## 3. Production rules

Normal production must satisfy all of the following.

1. RL / Training Edge outputが存在しなくても正常に動作すること。
2. RL / Training Edge欠損をproduction failureとして扱わないこと。
3. RL値が無いことを理由に、Training ResearchまたはRL scorerを自動実行しないこと。
4. RL値が無いことを理由にHistorical Rawへfallbackしないこと。
5. RL値を得るためだけにTraining Researchを再buildしないこと。
6. Newspaper / RaceNote / EdgeDB / PWAなどの現行consumerはRLを必須入力にしないこと。
7. Frozen RL assetは通常production entrypointとして扱わないこと。

## 4. Assets to preserve

以下は削除を必須としない。

- Training Edge v0.1 / v0.2 source
- frozen calibration / runtime fingerprint / runtime versions
- Training Research schema / Parquet canonical / historical evidence
- OOT / holdout / regression evidence
- RL-T migration / Warehouse cutover evidence
- historical reproduction workflows

これらは今後:

```text
FROZEN
REPRODUCTION / AUDIT ONLY
NOT A NORMAL PRODUCTION DEPENDENCY
DO NOT EXTEND WITHOUT A NEW EXPLICIT RESEARCH DECISION
```

として扱う。

## 5. Shared infrastructure must remain active

RL移行過程で整備した以下の層はRL専用資産ではない。

- JRDB Historical Warehouse
- Warehouse reader / materializer
- Index Base
- Warehouse -> Index Base adapter
- Hybrid Index Base
- legacy record_hash compatibility
- DuckDB / Parquet shared storage tooling

RL研究終了を理由にこれらを削除・停止しない。

## 6. Downstream compatibility policy

### RaceNote

Training Edge / RL indexはForecast inputではない。
既存の `training_edge_visible=false` / `rl_index_visible=false` 等のguardは、retirement後もanti-dependency firewallとして維持する。

### Newspaper

historical `my_index` / `training_edge_index` inputは互換用途として残してよいが、normal productionではoptionalでなければならない。
RL output未生成を理由にNewspaper buildを失敗させてはならない。

### EdgeDB / PWA

RLを必須入力にしない。RL retirementによってEdgeDB / PWAの通常生成・表示を停止させてはならない。

## 7. Forbidden automatic recovery

以下は禁止する。

```text
RL missing
  -> auto-run scorer
  -> auto-build Training Research
  -> auto-open HOLDOUT
  -> auto-retune model
  -> auto-fallback to Historical Raw
```

RL非存在は、retirement後のnormal stateである。 Missing RL / Training Edge output is a normal production state.

## 8. Future reopening

RL研究を再開する場合は、既存v0.2を黙ってproductionへ戻さない。

新しい明示的な研究判断として:

- objective
- input contract
- target
- leakage boundary
- evaluation design
- production role
- downstream dependency

を再定義し、新versionとして開始する。

## 9. Follow-up cleanup

このcontractの後続cleanupは別Turnで行う。

- ACTIVE RL workflowsのretire
- downstream hard-dependency audit
- frozen asset inventory
- shared infrastructure disentanglement
- final repo-wide retirement audit

この文書は、それらのcleanupの判断基準とする。

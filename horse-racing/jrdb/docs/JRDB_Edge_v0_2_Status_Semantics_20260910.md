# JRDB Edge v0.2 Status Semantics — 2026-09-10

Status: **DESIGN DECISION / v0.2 ONLY**

## Purpose

Edge Registry v0.2で、`WATCH` が

1. 時間的・標本的にまだ成熟していないcandidate
2. temporal gateではACTIVE/PROVISIONAL相当だが、statistical guardで棄却されたcandidate

を同時に表していた状態を解消する。

この変更はstatus semanticsの明確化であり、FDR、bootstrap CI、sample gate、candidate template、consumer scoring thresholdは変更しない。

## Decision

### WATCH

`WATCH` は **temporal validation上、まだ成熟・昇格条件を満たしていないcandidate** に限定する。

典型例:

- EMERGINGで標本蓄積待ち
- rolling/lifecycle validationで時系列要件をまだ満たさない

将来の観測追加によってPROVISIONAL/ACTIVEへ進む可能性を持つ研究待機状態とする。

### REJECTED

v0.2では、temporal statusが `ACTIVE` または `PROVISIONAL` であっても、statistical guard後の `statistical_status=WATCH` となったcandidateは、最終Registry statusを **`REJECTED`** とする。

理由:

- Registry schemaは既に`REJECTED`を許容している。
- Phase1設計はdomain/robustness gateを落ちたcandidateを`REJECTED`としている。
- BH-FDR + directional race-date cluster bootstrap CIはrobustness gateである。
- 2026-09-10監査ではstatistical downgrade 3,809件のうち3,736件（98.08%）が非NEUTRAL signalについてFDRとCIの両方を満たしておらず、単なる成熟待ちWATCHとして扱う根拠が弱い。

`REJECTED`は削除を意味しない。SQLiteとvalidation eventへ根拠を保持し、将来policy/template versionが変わる場合は新versionで再検証する。

## Compatibility

### v0.1

v0.1のbuilder/statistical guardは変更しない。既存v0.1 Registryとpublicationは凍結資産として保持する。

### statistical guard table

`edge_statistical_guard.statistical_status` は既存contractとの互換性のため `WATCH` のまま保持する。

v0.2 wrapperが最終Registry projectionで次を適用する。

```text
temporal WATCH
  -> final WATCH

temporal ACTIVE/PROVISIONAL
  + statistical_status WATCH
  -> final REJECTED
```

statistical reject時には`edge_validation_event`へ `decision=REJECT` / `failure_reason=STATISTICAL_GUARD_REJECTED` を追加する。

### publication

`live_edge_count` は従来どおり `ACTIVE + PROVISIONAL`。したがってconsumer-facing live countの定義は変えない。

既存manifest field `statistical_guard.downgraded_to_watch` はv0.1互換のguard-stage outcome名として当面残す。v0.2 final Registryでは該当recordが`REJECTED`へ写像されることをstatus countとstatistical auditで確認する。

### consumer

matcher既定statusは `ACTIVE` のみであり変更しない。したがって本変更はconsumerの発火条件を広げない。

`PROVISIONAL`や`WATCH`を明示指定するresearch/debug用途は従来どおりopt-inとする。`REJECTED`はcurrent matcherのeligible statusへ追加しない。

## Audit outputs

- `edge_watch_audit.json/.md`: 最終`WATCH`の内訳。新v0.2 buildでは原則temporal WATCHのみになる。
- `edge_stat_watch_audit.json/.md`: statistical guard rejectionの理由。legacy final WATCHとv0.2 final REJECTEDの両方を読み取れる後方互換auditとする。

## Acceptance

次の2025-only real-data smokeで以下を確認する。

1. v0.1 + v0.2 regressionがPASS。
2. pipeline全stageがPASS。
3. final Registryに`REJECTED`が生成される。
4. final `WATCH`はstatistical downgrade分だけ減少する。
5. `statistical_rejected`とguard-stage `downgraded_to_watch`が一致する。
6. `edge_stat_watch_audit.final_status_counts`が新buildでは`REJECTED`を示す。
7. ACTIVE / PROVISIONAL countはstatus semantics変更前と不変。
8. publication `live_edge_count`も不変。
9. current matcher既定ACTIVE-only contractを変更しない。

Full 2010-2025 rebuildはこのsmokeの合格後にのみ実施する。
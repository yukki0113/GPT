# RaceNote development guide

Status: CURRENT
Last reviewed: 2026-09-22

## 1. Purpose

RaceNoteは、JRDB / Analysis / Statsから得られる開催前情報をGPTが読める形へ整え、**GPT自身がレースを比較・予想するための研究基盤**として運用する。

RaceNoteの中心目的は、固定数式や決定論的ルールで印を機械生成することではない。

```text
JRDB / Analysis / Stats
  -> RaceNote authoritative bundle
  -> Reader View
  -> GPT Forecast layer
  -> pre-result review / freeze
  -> result join / evaluation
  -> periodic improvement
```

PWA、競馬新聞、全R一括処理、表示コメントは重要なconsumer / delivery layerだが、RaceNote予想研究の目的そのものではない。

## 2. Current prediction direction

現在の予想研究系を **RaceNote Forecast Gen0** と呼ぶ。

Gen0では、`docs/RaceNote_Prediction_Handoff_v0_1.md` にある原点へ戻り、GPTが以下を横比較して予想する。

1. レース条件
2. 基礎能力
3. 今回条件適性
4. 展開適合
5. 調教・状態
6. 近走内容
7. 長期履歴・条件実績
8. 騎手・種牡馬・枠等の補助統計
9. coverage / conflicting evidence / uncertainty

固定weightや単一スコアを先に置かず、RaceNoteに収録された具体的evidenceを比較して予想を作る。

現行の予想者契約は `FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md`。初期factor set `FSET-Gen0.1` は10ファクターを持つが、weightは固定せずレースごとにGPTが重要度を変える。

将来weightやモデルを導入する場合も、先にblinded / TRUE_FORWARDの検証を行い、独立したprediction model versionとして管理する。

## 3. Authoritative boundary

RaceNote authoritative bundleは引き続き **facts / evidence / provenance** を担当する。

予想印、結果、払戻、対象レース後にしか分からない情報をauthoritative bundleへ混入させない。

Prediction layerはRaceNoteの外側に置く。

```text
RaceNote data contract != prediction policy
Prediction policy != presentation policy
Presentation policy != result evaluation
```

この分離は今後も維持する。

## 4. What is current and what is legacy

### Current

- `src/racenote_request.py`
- `src/racenote_jrdb.py`
- `src/racenote_history_enrichment.py`
- `src/racenote_history_engine.py`
- `src/racenote_reader_view.py`
- `src/racenote_reader_zip.py`
- RaceNote Archive / as-of-safe historical delivery
- `docs/RaceNote_Prediction_Handoff_v0_1.md` のGPT prediction原則
- `docs/racenote/FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md` の現行予想者契約
- `src/racenote_forecast_gen0.py` のpre-result validation / freeze / hash / ledger projection
- `src/racenote_forecast_gen0_guard.py` のsource runner coverage / factor identity guard
- `src/racenote_forecast_gen0_evaluation.py` のpost-result join / evaluation projection
- `schema/racenote_forecast_gen0_schema_v0_1.json` のpre-result payload schema
- `docs/racenote/FORECAST_GEN0_LEDGER_CONTRACT_v0_1.md` のGoogle Sheets台帳契約
- pre-race guard / provenance / freeze / hash / result-after-freeze の研究基盤
- `FORECAST_GEN0_PLAN.md` に定義するGen0検証サイクル

継続研究台帳はネイティブGoogle Sheet `RaceNote Forecast Gen0 検証台帳`。Spreadsheet IDは `config/racenote_forecast_gen0_ledger_v0_1.json` を正本とし、ChatGPTのGoogle Drive / Sheets connectorから直接読み書きする。

### Legacy prediction logic

過去に構築した次の決定論的予想系は、再現性のため保持するが、**新しいRaceNote Forecastの現行予想ロジックとはしない**。

- v0.2 control baseline
- v1.1-P gated prediction
- `racenote_edge_prediction_policy.py` によるGood差・Edge polarityを使った軸決定
- TRUE_FORWARD v1.1-Pの日次freezeを前提とした印決定ロジック
- v1.1-Pでfreeze済みの印を説明するpresentation系

詳細は `legacy/README.md` を参照する。

## 5. Reuse from the legacy system

旧系統から捨てないものは多い。

新しいGen0でも再利用価値が高いのは次の研究基盤である。

- target race resultを予想前に見ないpre-race guard
- historical `as_of_exclusive` boundary
- source provenance
- input / output hash
- prediction freeze
- freeze後にのみresultを取得する順序
- immutable prediction record
- result joinとpost-race evaluationの分離
- presentationが予想値を書き換えない境界
- audit可能なrun metadata

つまり、**旧予想ロジックはlegacy化するが、検証インフラは継承する**。

## 6. Logic that must not silently survive into Gen0

次をGen0の隠れた決定規則として残さない。

- top 5だけを候補とする固定制約
- Good差 `<= 0.04` を逆転条件とする固定閾値
- Edge polarityが強ければ◎を昇格させる固定規則
- Edge polarityのordinal orderを最終順位決定へ直結させること
- 旧v1.1-Pの相対順位をGPT予想の初期順位として無条件に引き継ぐこと

旧方式の結果が新方式より良かった場合も、それだけを理由に旧ロジックへ自動回帰しない。

比較対象として履歴は残すが、改善判断はGen0自身の予想記録と結果監査から行う。

## 7. Forecast / guard / ledger / delivery separation

RaceNote Forecastの評価と、研究完全性guardと、継続研究台帳と、PWA / Newspaperへの配布は別責務とする。

```text
RaceNote evidence
  -> GPT Forecast
  -> deterministic validation / freeze
  -> source completeness guard
  -> Google Sheets research ledger
  -> result join / evaluation
  -> generation improvement

frozen prediction
  -> presentation / PWA / newspaper
```

`src/racenote_forecast_gen0_guard.py` は予想を評価・変更しない。RaceNote sourceの全出走馬がforecastへ存在することと、factor usage identityが一意であることだけを確認する。

Google Sheetsはprediction modelではない。台帳は予想時点の判断と結果後の評価を分離して保存する。

PWA / Newspaperのconsumer都合でprediction policyを歪めない。

## 8. Gen0 initial operation

初期generationは `Gen0-G000`。

- forecast version: `RaceNote-Forecast-Gen0.1`
- factor set: `FSET-Gen0.1`
- target: 原則50R
- initial evaluation mode: `BLINDED_HISTORICAL`

1R lifecycle:

```text
as-of-safe RaceNote
  -> GPT prediction
  -> pre-result self-audit
  -> deterministic validation
  -> hash / freeze
  -> source runner completeness guard
  -> guarded ledger write / readback
  -> result acquisition
  -> result join
  -> GPT post-race review
  -> factor review
```

結果を取得するのはguarded ledger writeとreadbackの後だけとする。

50R終了後にgeneration analysisを行い、改善案を変更履歴へ記録して次generationへ進む。

## 9. Source priority

現行仕様の判断は次の順を優先する。

```text
latest main source / current contract
  > docs/racenote current documents
  > immutable run artifact / manifest / hash
  > historical handoff / issue / audit
```

日付付きIssue番号や一時run IDをcurrent truthとして固定しない。

## 10. Historical Warehouse operational route

2010–2025のHistorical rebuildは、accepted JRDB Historical Warehouse generationを標準入力にする。通常requestのArchive優先は維持するが、Archive不在時のrebuildはWarehouse readerを通し、2011–2025で失敗した場合にRawへsilent fallbackしない。2026以降の日次処理は引き続きPACI/Rawであり、Warehouseを要求しない。

実運用Workflowのcontrolled E2Eでは、Archive bypassを明示し、verified local Warehouse asset rootsを`racenote_request.py`へ渡す。`used_backend=historical_warehouse`、immutable generation一致、全R/全馬、as-of/future-leakage、join、再生成性を`audit_racenote_historical_warehouse_e2e.py`でfail-closedに監査する。詳細は`../RaceNote_Historical_Warehouse_Operation_v1.md`を正とする。

Forecast Gen0は依然としてGPTが予想を作成し、コードはvalidation/freeze/guardを担当する。この入力生成責務を既存の決定論的legacy scorerやPWA consumerへ暗黙に移してはならない。

## 11. Related documents

- `FORECAST_GEN0_PLAN.md` — 現行Gen0の研究計画
- `FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md` — GPTが1Rを予想する現行契約
- `FORECAST_GEN0_INPUT_GUARD_v0_1.md` — 全馬coverage / factor identity guard
- `FORECAST_GEN0_LEDGER_CONTRACT_v0_1.md` — Google Sheets台帳とtransaction契約
- `legacy/README.md` — 旧決定論的予想系の扱い
- `../RaceNote_Prediction_Handoff_v0_1.md` — GPT prediction layerの原点
- `../README_racenote_v1.md` — RaceNote v1 data specification
- `../README_racenote_request.md` — request / delivery contract
- `../RaceNote_Historical_Warehouse_Operation_v1.md` — Warehouse routing / controlled E2E contract
- `../RaceNote_Presentation_Comment_Contract_v0_2.md` — 既存presentation contract。legacy予想との関係に注意

Implementation:

- `../../src/racenote_forecast_gen0.py`
- `../../src/racenote_forecast_gen0_guard.py`
- `../../src/racenote_forecast_gen0_evaluation.py`
- `../../schema/racenote_forecast_gen0_schema_v0_1.json`
- `../../config/racenote_forecast_gen0_ledger_v0_1.json`
- `../../tests/test_racenote_forecast_gen0.py`
- `../../tests/test_racenote_forecast_gen0_guard.py`
- `../../tests/test_racenote_forecast_gen0_evaluation.py`

## 12. Development rule

RaceNoteで新しい予想アイデアを試すときは、いきなりproductionの印決定へ埋め込まない。

まずprediction recordへ根拠を残し、結果を見る前にfreezeし、一定レース数でまとめて結果監査する。

改善は「当たった外れた1R」への追従ではなく、複数レースのevidence reading error / overvaluation / undervaluation / uncertainty calibrationを見て行う。

結果後の改善は`予想Freeze / 馬別評価 / ファクター使用`を上書きせず、`振返り / ファクター検証 / 変更履歴`へ別recordとして残す。

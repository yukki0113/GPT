# RaceNote development guide

Status: CURRENT
Last reviewed: 2026-09-13

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
- pre-race guard / provenance / freeze / hash / result-after-freeze の研究基盤
- `FORECAST_GEN0_PLAN.md` に定義するGen0検証サイクル

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

## 7. Forecast / delivery separation

RaceNote Forecastの評価と、PWA / Newspaperへの配布は別責務とする。

予想研究では、まず1R単位でGPTが根拠を持って比較できることを優先する。

その後、安定した出力contractをPWA / Newspaperがconsumeする。

consumer都合でprediction policyを歪めない。

```text
Forecast quality
  -> frozen prediction contract
     -> presentation / PWA / newspaper
```

## 8. Source priority

現行仕様の判断は次の順を優先する。

```text
latest main source / current contract
  > docs/racenote current documents
  > immutable run artifact / manifest / hash
  > historical handoff / issue / audit
```

日付付きIssue番号や一時run IDをcurrent truthとして固定しない。

## 9. Related documents

- `FORECAST_GEN0_PLAN.md` — 現行Gen0の研究計画
- `legacy/README.md` — 旧決定論的予想系の扱い
- `../RaceNote_Prediction_Handoff_v0_1.md` — GPT prediction layerの原点
- `../README_racenote_v1.md` — RaceNote v1 data specification
- `../README_racenote_request.md` — request / delivery contract
- `../RaceNote_Presentation_Comment_Contract_v0_2.md` — 既存presentation contract。legacy予想との関係に注意

## 10. Development rule

RaceNoteで新しい予想アイデアを試すときは、いきなりproductionの印決定へ埋め込まない。

まずprediction recordへ根拠を残し、結果を見る前にfreezeし、一定レース数でまとめて結果監査する。

改善は「当たった外れた1R」への追従ではなく、複数レースのevidence reading error / overvaluation / undervaluation / uncertainty calibrationを見て行う。

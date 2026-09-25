# RaceNote All-Runner Synthesis v0.1

Status: IMPLEMENTED FULL-FIELD DRAFT CONTRACT  
Date: 2026-09-25

## 1. Purpose

Prediction Interpretationを全馬分読み、
Pairwise Comparisonへ入る前のdraft orderを正式に作る。

この層は自動ランキング器ではない。

GPTが全馬を俯瞰して暫定順位を作り、
deterministic validatorがその作り方を監査する。

## 2. Position in the pipeline

```text
General Evidence
  -> Prediction Interpretation
  -> All-Runner Synthesis
  -> Pairwise Comparison
  -> Scenario Robustness
  -> Forecast
```

## 3. Why this layer exists

従来のPairwise契約には:

```text
all-runner read
  -> draft order
  -> pairwise
```

と書かれていたが、draft order自体には契約がなかった。

そのため、

- 全馬を本当に読んだか
- Ability順をそのままdraftにしていないか
- mixed / 小母数 / contradictionを無視していないか
- Pairwiseで重点確認すべき境界がどこか

を監査できなかった。

v0.1はこの空白を埋める。

## 4. Input

正本入力:

- RaceNote General Evidence v0.1
- 各馬の PredictionInterpretation-v0.1

Firewall:

- current market hidden
- current JRDB consensus hidden
- Training Edge hidden

## 5. Per-horse synthesis

各馬は次を持つ。

```text
horse_no
draft_rank
confidence
primary_lane
positive_components
concern_components
ability_context_used
draft_reason
main_uncertainty
```

draft rankは1〜Nを全馬ちょうど1回ずつ使用する。

## 6. Primary lane

許可:

- DATA_TREND
- RACEREVIEW
- MIXED
- UNCERTAINTY

不許可:

- ABILITY_ANCHOR

Abilityはfloor / ceiling確認として使用できるが、
それだけをprimary basisにしてdraft順位を作らない。

## 7. Component provenance

positive_components / concern_components は
Prediction Interpretationに実際に存在するcomponentだけを参照できる。

例:

Positive:

- DATA_TREND_SUPPORT
- DATA_TREND_MIXED_SUPPORT
- RACEREVIEW_SUPPORT
- RACEREVIEW_MIXED_SUPPORT

Concern:

- DATA_TREND_OPPOSITION
- DATA_TREND_MIXED_CONCERN
- RACEREVIEW_CONCERN
- RACEREVIEW_MIXED_CONCERN

存在しないcomponentを新しく書くとfail closed。

## 8. Mixed

primary_lane=MIXEDの場合は、
DATA_TRENDとRACEREVIEWの両方を含む必要がある。

片側だけのEvidenceをMIXEDと呼んで優先順位ルールを迂回しない。

## 9. Uncertainty

directional componentが1件もない馬は
primary_lane=UNCERTAINTYを使う。

「データがない」を負材料へ変換しない。

## 10. Ability context

`ability_context_used` は、
Ability Anchorを地力の確認に使ったかを残す。

これは順位根拠の主軸ではない。

例:

```text
DATA_TREND supportive
RaceReview hidden strength
Ability peak / typicalも現級水準に届く
```

は許可。

```text
peak IDMが一番高いからdraft 1位
```

はv0.1では許可しない。

## 11. Boundary audit

draft orderの全adjacent pairについてboundaryを作る。

```text
upper_horse_no
lower_horse_no
comparison_priority
boundary_summary
```

comparison_priority:

- STANDARD
- HIGH

## 12. HIGH boundary derivation

以下を含む境界はHIGHになる。

- upper horse LOW confidence
- lower horse LOW confidence
- Trend MIXED
- small-sample-only directional evidence
- RaceReview MIXED
- RaceReview contradiction

HIGHをSTANDARDとして隠すことはできない。

HIGHだから順位を自動で逆転させるわけではない。
Pairwiseで重点的に直接比較する、という意味。

## 13. Draft order semantics

draft orderはForecastではない。

```text
All-Runner Synthesis draft
  -> Pairwiseで直接比較
  -> Pairwise final order
```

Pairwiseで順位が入れ替わることを前提とする。

## 14. Pairwise binding

canonical Pairwise route:

```text
General Evidence
  + All-Runner Synthesis Audit
  -> build_comparison_request_from_synthesis()
  -> authored Pairwise Comparison
  -> validate_pairwise_comparison_from_synthesis()
```

Pairwise payloadは:

- General Evidence hash
- All-Runner Synthesis hash
- Synthesis draft_order

へbindされる。

Synthesis後にdraft orderを勝手に書き換えるとfail closed。

## 15. Legacy route

旧:

```text
build_comparison_request(general, draft_order)
validate_pairwise_comparison(general, payload)
```

はreplay / compatibility用として残す。

新規予想運用では使わない。

CLIでは:

```text
--all-runner-synthesis-audit
```

を渡す経路をcanonicalとする。

## 16. Relationship to short comments

All-Runner Synthesisのdraft_reasonは、
最終短評の直接sourceにはしない。

短評sourceはForecast Decision Trace。

ただしSynthesisは:

- なぜPairwiseへ上げたか
- どの馬との境界が曖昧だったか

を後から監査する材料になる。

## 17. No score

v0.1で禁止:

- additive score
- weighted sum
- positive component count voting
- peak IDM順の自動draft
- fixed point conversion
- market/popularity use

## 18. Canonical implementation

- `src/racenote_all_runner_synthesis.py`
- `schema/racenote_all_runner_synthesis_schema_v0_1.json`
- `tests/test_racenote_all_runner_synthesis.py`
- `docs/racenote/ALL_RUNNER_SYNTHESIS_v0_1.md`

Pairwise bridge:

- `src/racenote_pairwise_comparison.py`

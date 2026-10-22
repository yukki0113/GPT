# BRDB Blood Review v0.1

Status: IMPLEMENTED BASELINE / VALIDATION PENDING
Date: 2026-10-22

## 目的

BRDBの全馬レビュー境界を実装する。v0.1は **non-scoring / descriptive review** であり、適性スコア・地域型分類・推定的な肯定/否定要因を生成しない。

Canonical pedigree facts は `BloodReviewReader.horse_pedigree(horse_id)` のみから取得する。馬名はidentity fallbackに使わない。

## API

`src/brdb_blood_review.py`

- `BloodReviewEngine(reader).horse_review(horse_id, target_context, *, pedigree_context=None)`
- `BloodReviewEngine(reader).reviews_for_horses(horse_ids, target_context, *, pedigree_contexts=None)`

batch APIはsingle-horse APIと同一semanticsを持つ。

## Target context

v0.1必須:
- `target_date`: YYYY-MM-DD or YYYYMMDD
- `venue`
- `surface`: 芝/ダート or turf/dirt
- `distance`: integer 600..5000

条件が解釈不能なら `UNSUPPORTED_CONTEXT` とし、推測補完しない。

## Source lanes

1. `BloodReviewReader`: horse_id照会によるsire/dam/BMSおよびJRDB official lineage labels。
2. 既存RaceNote P2 pedigree context: **optional descriptive input**。新たな統計集計はしない。\n\nReal P2 adapter: `src/brdb_racenote_p2_adapter.py`. It requires same RaceNote bundle's `race`, `metadata.history_enrichment_poc`, `horses[].basic.horse_id`, `horses[].pedigree`, `horses[].pedigree_context`, strict as-of-exclusive attestation and descriptive-only source. The adapter does not change RaceNote output.

P2 evidenceは以下を満たさなければ採用しない:
- wrapper `target_context` が target_date/venue/surface/distance の4項目で一致
- `as_of_exclusive` がtarget_dateと一致（P2 producerはrace_date < target_dateを保証する）
- starts/wins/top3が整数かつ 0 <= wins <= top3 <= starts
- `scoring=True` ではない

これは既存P2 consumer contractに対する安全な**adapter入力要件**であり、既存RaceNote出力がwrapper条件をそのまま満たすという意味ではない。RaceNote統合時は明示的adapterでscopeとas-ofを与え、producer由来の対象条件・履歴exclusive性を検証する。

P2が未提供/不適合なら `PARTIAL`。0件の合法集計は0件として記述し、評価0点とはしない。

## Status

- `NO_HORSE_ID`: empty identity
- `UNSUPPORTED_CONTEXT`: required context unsupported
- `NO_PEDIGREE`: horse_idに対応するcanonical pedigreeなし/三要素すべて欠損
- `PARTIAL`: blood factsあり、P2 evidenceが欠損または片系のみ
- `AVAILABLE`: sire/dam/BMS factsおよびsire/BMS P2両方あり

`coverage.status`はpedigree factsの3要素のみに対する FULL/PARTIAL/NONE。P2のavailabilityは `coverage.pedigree_context` で別表現。

`confidence=DESCRIPTIVE_ONLY` は統計的confidenceや血統適性の強さを意味しない。

## Output

`BRDB_REVIEW_CONTRACT_v0_1.md` の概念的payloadに準拠:
- horse_id/status/contract_version
- target_context
- facts
- classification（父系・母父系のJRDB mappingのみ。regional_typeはnull）
- review（overall_score=null、components=[], positive/negative_factors=[]）
- coverage
- confidence
- provenance（generation/schema/review logic version）

## 非対象

- 0〜100 score
- 「京都芝2000mに適性あり」等の自動判断
- RaceNote/Analysisからの自由なpost-race join
- 3〜5代血統・クロス・similarity
- PWA連携・CURRENT書換

## Validation

`tests/test_brdb_blood_review.py`:
- NO_HORSE_ID
- NO_PEDIGREE
- UNSUPPORTED_CONTEXT
- non-scoring fallback
- scoped P2
- mismatched target scope
- mismatched as-of
- invalid sample counts
- batch/single equivalence

Fixture and real-shape P2 adapter regression tests are committed, but independent execution and real enriched-bundle full-field audit are pending. Do not call v0.1 production-ready until those gates pass. Validation instruction: `collab/instructions/20261022_002_blood-review-v01-verification_instruction.md`.

## Next

1. testsを実行し欠陥を修正
2. RaceNote P2 producer payloadとadapter contractを接続し、as-of/target-scope/統計の一致を監査
3. 代表レース全馬のdry-runとcoverage分布をレポート
4. 問題がなければBlood Review v0.1 contractをfreeze
5. その後PWA handoff設計へ進む

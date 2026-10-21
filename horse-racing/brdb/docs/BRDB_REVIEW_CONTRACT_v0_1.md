# BRDB Horse Review Contract v0.1

Status: **DRAFT BOUNDARY ONLY**  
Date: 2026-10-21

## Goal

BRDB consumer が blood storage や研究中間表を直接解釈せず、1頭単位の安定した review result を受け取るための境界を先に定義する。

## Canonical identity

`horse_id = JRDB blood_registration_no`

horse name fallbackは禁止。

## Conceptual API

Single horse:

```python
horse_review(
    horse_id,
    target_context,
)
```

Field batch:

```python
reviews_for_horses(
    horse_ids,
    target_context,
)
```

batch API は single-horse semantics と同一結果を返さなければならない。

## Target context baseline

将来の review では少なくとも次を入力候補とする。

- target_date
- venue
- course / layout
- surface
- distance
- track condition

race-shape 等は必要性を検証してから追加し、未確定入力をv0.1で必須にしない。

## Output baseline

```json
{
  "horse_id": "00000000",
  "status": "AVAILABLE",
  "contract_version": "brdb-review-v0.x",
  "facts": {
    "sire_name": null,
    "dam_name": null,
    "broodmare_sire_name": null
  },
  "classification": {
    "sire_line": null,
    "broodmare_sire_line": null,
    "regional_type": null
  },
  "review": {
    "overall_score": null,
    "components": [],
    "positive_factors": [],
    "negative_factors": [],
    "summary": null
  },
  "coverage": {
    "status": "NONE"
  },
  "provenance": {
    "generation_id": null,
    "pedigree_schema_version": null,
    "taxonomy_version": null,
    "review_logic_version": null
  }
}
```

これは field-name freeze ではなく、responsibility boundary の draft である。

## Status semantics

最低限:

- `AVAILABLE`
- `PARTIAL`
- `NO_PEDIGREE`
- `UNSUPPORTED_CONTEXT`
- `NO_HORSE_ID`

を検討する。

missing coverage を0点扱いしない。

## Scoring rule

overall score を将来導入しても:

- score のみを返さない
- component breakdown を保持する
- positive / negative rationale を保持する
- coverage / confidence を併記する
- taxonomy / review logic version を保持する

## PWA boundary

PWA「血統詳細」modal はこのReview結果から表示用payloadを生成する。

PWAへ canonical blood tables、taxonomy tables、研究用intermediate列を直接渡さない。

将来の表示候補:

- 父 / 母 / 母父
- 父系 / 母父系
- 日本型 / 米国型 / 欧州型
- 類似馬
- target course fit
- component scores
- overall Blood Review score
- rationale

表示項目が増えても review logic の正本は BRDB 側に置く。

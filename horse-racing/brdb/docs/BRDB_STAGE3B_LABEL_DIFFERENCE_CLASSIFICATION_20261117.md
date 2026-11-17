# BRDB Stage3B ancestor label-difference classification — 2026-11-17

Status: **PASS — 36 DIFFERENCE ROWS CLASSIFIED / 7 IDENTITY-QUALIFIED LABEL-ONLY / 29 ALIAS-REVIEW ROWS / NO ID INFERENCE**

This audit reclassifies the 36 `DIFFERENT_UNREVIEWED` rows from the accepted 2026-11-06 Stage3B top50 slot audit. It does not approve new ancestor aliases or canonical IDs.

## Fixed input

- accepted ZIP: `brdb_stage3b_top50_batch_audit_v2_20261106.zip`
- SHA-256: `126f4052667813e0b15868b72644097aaddf4ed98dec82d12dea4a72098844dd`
- source relation: `slots.csv`
- fixed difference rows: **36**
- unique JRDB/JBIS label pairs: **23**

Real execution:
- Issue [#2625](https://github.com/yukki0113/GPT/issues/2625)
- Actions run [44031064568](https://github.com/yukki0113/GPT/actions/runs/44031064568)
- source commit: `62a1203148f1be9b46b8f568a91341a4eebe6989`
- status: **PASS**
- audit JSON SHA-256: `a4e6b248b13d20196330c2e9b227ecd141932cb80556e7cf513de726b3e71999`

## Classification

| classification | rows | meaning |
|---|---:|---|
| `IDENTITY_ALREADY_JBIS_QUALIFIED_LABEL_ONLY` | 6 | row already has a JBIS canonical source ID; only the displayed JRDB/JBIS labels differ |
| `IDENTITY_ALREADY_JRDB_CANONICAL_LABEL_ONLY` | 1 | row already has a JRDB canonical ID; only the source-observed label differs |
| `ALIAS_REVIEW_REQUIRED_NO_CANONICAL_ID` | 29 | labels differ and there is no canonical person/horse ID on the row; no identity is inferred |

Therefore **7/36 rows are not unresolved identity rows**. They are label-display discrepancies on an already qualified identity.

The remaining identity-sensitive label debt is **29 rows / 21 unique label pairs**.

## Existing-ID rows

### Kingmambo — 6 rows
`キングマンボ` ↔ `Kingmambo(USA)`

All six rows already carry:
`ancestor_id=JBIS:0000347989`
and `status=JBIS_SOURCE_QUALIFIED`.

Subjects/paths:
- キングカメハメハ S
- ロードカナロア SS
- ルーラーシップ SS
- サートゥルナーリア SSS
- レイデオロ SS
- リオンディーズ SS

No new crosswalk is needed to establish identity on these six rows.

### Cesario — 1 row
`シーザリオ` ↔ `シーザリオ 青毛`

The row already carries:
`ancestor_id=JRDB:02100844`
and `status=JRDB_CANONICAL`.

The source-side string may include presentation metadata; this audit does not rewrite the source label or claim a parser defect. Identity is already canonical independently of that label.

## Remaining 29 rows / 21 label pairs

Repeated pairs:
- `クリスエス` ↔ `Kris S.(USA)`: 3
- `ストームキャット` ↔ `Storm Cat(USA)`: 3
- `ティーケイ` ↔ `Tee Kay(USA)`: 3
- `シルヴァーホーク` ↔ `Silver Hawk(USA)`: 2
- `アンブライドルズソング` ↔ `Unbridled's Song(USA)`: 2

Single-row pairs:
- アルザオ ↔ Alzao(USA)
- クラシックゴーゴー ↔ Classic Go Go(USA)
- Danehill ↔ デインヒル(USA)
- アメリフローラ ↔ Ameriflora(USA)
- シーキングザゴールド ↔ Seeking the Gold(USA)
- ローソサエティー ↔ Law Society(USA)
- ヌレイエフ ↔ Nureyev(USA)
- ディクタス ↔ デイクタス(FR)
- オーペン ↔ Orpen(USA)
- コジーン ↔ Cozzene(USA)
- フォークロア ↔ Folklore(USA)
- ロックオヴジブラルタル ↔ ロックオブジブラルタル(IRE)
- クリス ↔ Kris(GB)
- メディシアン ↔ Medicean(GB)
- マキャヴェリアン ↔ Machiavellian(USA)
- ワイルドアゲイン ↔ Wild Again(USA)

These pairs are **candidates for explicit source-backed alias review only**. Similar spelling/transliteration is not sufficient to create a canonical identity.

## Implementation

- `src/audit_brdb_stage3b_label_differences.py`
- `tests/test_audit_brdb_stage3b_label_differences.py`
- `config/public_drive/stage3b_label_difference_audit_source_20261117.json`

The classifier relies only on the existing `ancestor_id` namespace:
- `JBIS:...` -> identity already JBIS-qualified;
- `JRDB:...` -> identity already JRDB-canonical;
- no ID -> alias review required.

It never compares name similarity to infer an ID.

## Boundary

This reduces the **identity-sensitive** Stage3B label-difference debt from 36 rows to 29 rows without resolving any new ancestor person ID.

Still open:
- 29 no-ID difference rows / 21 explicit alias candidates;
- 10 missing gen2 names;
- 40 missing gen3 names;
- old-ancestor canonical person-ID coverage;
- additional direct-edge certification.

All remain research-only and `AS_OF_UNVERIFIED`. No production or prediction contract changes.

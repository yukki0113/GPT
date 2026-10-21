# BRDB RRDB Inheritance Contract v0.1

Status: **ACTIVE DESIGN BASELINE**  
Date: 2026-10-21

## 1. Purpose

BRDB を新設するにあたり、RaceReviewDB (RRDB) で既に安定している storage / Reader / consumer boundary を再利用するための確認結果を固定する。

この文書は RRDB の review logic 自体をコピーする契約ではない。

引き継ぐのは **DB正本の解決、stable identity、read-only query、consumer projection、provenance、fail-closed** の設計である。

## 2. Confirmed RRDB canonical source

現行 RRDB operational source:

`RaceReviewDB_CURRENT.zip`

RRDB current resolver:

`horse-racing/jrdb/src/racenote_racereview_current.py`

stable Drive file name:

`RaceReviewDB_CURRENT.zip`

stable Drive file ID:

`1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`

current resolver は、Drive metadata / ZIP integrity / safe extraction / Reader validation を通過した generation だけを accepted local cache として扱う。

失敗した refresh が既存 accepted cache を置換しない設計を維持している。

## 3. Confirmed RRDB internal canonical structure

RRDB Reader:

`horse-racing/jrdb/src/jrdb_postrace_review_reader.py`

Reader は extracted CURRENT root の:

- `current.json`
- manifest
- immutable Parquet relations

を検証して開く。

主要な validation:

- `current.status == CURRENT`
- `artifact_type == jrdb_postrace_review`
- manifest reference exists
- manifest `validation_status == PASS`
- current / manifest generation ID一致
- relation object existence

storage query は in-memory DuckDB の read-only consumer query として行う。

## 4. Horse identity

RRDB の馬単体queryは:

`horse_id = JRDB blood_registration_no`

を stable identity とする。

Reader の `horse_history(horse_id, before_date, limit)` は horse name lookup を実装しない。

RaceNote adapter でも:

`name_fallback = false`

を明示する。

BRDB も同一 identity contract を引き継ぐ。

## 5. RRDB single-horse query pattern

RRDB Reader の canonical pattern:

```text
RaceReviewDB CURRENT
  -> RaceReviewReader
  -> fact_horse_performance
  -> WHERE horse_id = ?
  -> as-of exclusive
  -> newest first
```

RaceNote recommendation layer は target field の horse IDs を受け、各馬について target date より前の履歴を取得し、operational recommendation payload へ変換する。

consumer が Parquet relation を直接解釈するのではなく、

```text
storage row
 -> recommendation logic
 -> result payload
```

へ投影する点をBRDBで継承する。

## 6. Result-only consumer boundary

RRDB には2段階の consumer projection がある。

### Internal RaceNote

`racereview.recommendation`

として:

- status
- contract_version
- matched_signal_ids
- signals
- human_summary
- source_run
- provenance

等を付与する。

### Newspaper / PWA

`build_rrdb_newspaper_handoff.py` では internal signal ID / strength を直接公開せず、reader-facing short prose へ縮約する。

したがって、RRDB の成熟した境界は:

> DBの全列をconsumerへ渡すのではなく、目的別にstable review resultへ投影する

ことである。

BRDB もこの方式を採用する。

## 7. BRDB inheritance decision

BRDB operational architecture は将来次を実装する。

```text
BloodReviewDB_CURRENT
  |
  +-- current.json
  +-- manifest
  +-- immutable Parquet relations
          |
          v
BloodReviewReader
          |
          +-- horse_review(horse_id, target_context)
          +-- reviews_for_horses(horse_ids, target_context)
          |
          v
stable Blood Review payload
```

命名は実装時に最終固定するが、consumer contract はこの形から逸脱しない。

## 8. BRDB review payload baseline

初期の target shape は次を想定する。

```json
{
  "horse_id": "...",
  "status": "AVAILABLE",
  "contract_version": "brdb-review-v0.x",
  "pedigree": {
    "sire": {},
    "dam": {},
    "broodmare_sire": {},
    "lineage": {}
  },
  "review": {
    "score": null,
    "components": [],
    "summary": null
  },
  "coverage": {},
  "confidence": null,
  "provenance": {
    "generation_id": "...",
    "taxonomy_version": "...",
    "review_logic_version": "..."
  }
}
```

v0.1 design 段階では score の意味や component は固定しない。

重要なのは、**horse_id を渡すと storage の内部構造ではなくreview結果が返る**境界を先に固定することである。

## 9. Differences from RRDB

BRDB は RRDB の logic をコピーしない。

RRDB:
- historical race performance が中心
- source run の再解釈
- as-of-exclusive history が重要

BRDB:
- immutable pedigree fact が中心
- target race context に対する pedigree review
- taxonomy / ancestor coverage / source provenance が重要

したがって BRDB の `target_context` は将来:

- venue / course
- surface
- distance
- track condition
- optional race-shape context

等を受け取る可能性がある。

同一 horse_id でも target context により review は変わり得る。

## 10. Rules fixed now

- canonical horse identity = JRDB blood registration number
- name fallbackは禁止
- consumer direct-Parquetは禁止
- CURRENT / manifest / generation validationを持つ
- Readerはread-only
- review logic versionを持つ
- taxonomy versionを持つ
- missing dataをguessしない
- provenanceを落とさない
- PWAは表示面でありlogic正本ではない

## 11. Next implementation task

BRDB最初の実装前に、JRDB UKC / existing RaceNote pedigree data の coverage audit を行い、

- canonical pedigree fact schema
- lineage taxonomy
- regional taxonomy
- external pedigree source policy

を確定する。

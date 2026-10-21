# Blood Review DB (BRDB)

BRDB は、出走馬の血統を固定条件への一致抽出ではなく、**対象レースの各出走馬を同一契約でレビューする**ための中央競馬サブプロジェクトです。

## Source of truth

GitHub `yukki0113/GPT` の `main` 配下 `horse-racing/brdb/` を、BRDB の仕様・source・tests・運用書の正本とします。

血統の一次事実については既存 JRDB 資産を優先し、JRDB で不足する祖先・系譜情報だけを明示的な外部 source で補完します。BRDB は JRDB fixed-width parser を再実装しません。

## Purpose

BRDB の中心責務は次の2層です。

1. **Blood data layer**
   - 父、母、母父
   - 父系・母父系
   - 将来の3〜5代血統、クロス、地域型、類似血統等
   - 各分類の provenance / version

2. **Blood Review layer**
   - 対象レース・対象馬に対する決定的レビュー
   - review result、根拠、coverage、confidence を返す
   - PWA / RaceNote は内部 Parquet や研究ロジックを直接読まず、Review contract を読む

固定条件で「該当馬だけを抽出する」ことを主目的にしません。原則として target field の全馬を review 対象とします。

## Initial architecture

```text
JRDB / external pedigree source
        |
        v
Blood canonical data
        |
        v
Blood Review engine
        |
        v
BRDB CURRENT
        |
        v
BRDB Reader
        |
        +--> horse_id query
        |      -> review result only
        |
        +--> RaceNote / PWA
```

## RRDB inheritance

BRDB は RaceReviewDB (RRDB) の以下の成熟した consumer boundary を引き継ぎます。

- stable CURRENT artifact
- `current.json` + validated manifest
- immutable Parquet relations
- JRDB blood registration number (`horse_id`) を stable identity とする
- horse-name fallback 禁止
- DuckDB read-only query
- Reader が storage detail を隠蔽
- consumer は review result contract のみ利用
- provenance / generation / schema / logic version を必ず保持
- fail-closed

詳細は `docs/BRDB_RRDB_INHERITANCE_v0_1.md`。

## Current status

Status: **PHASE 1 / PEDIGREE FACT FOUNDATION**

血統採点ロジック・CURRENT artifact はまだ未実装ですが、Pedigree Fact v0.1 schema と guarded parent-relation resolver は実装済みです。

初期フェーズでは、

1. JRDB UKC / RaceNote pedigree 資産の棚卸し — 完了
2. canonical pedigree fact schema — v0.1 実装済み
3. guarded parent relation resolver — v0.1 実装済み
4. official lineage code master materialization
5. reviewed pedigree-name alias v0.1
6. UKC -> pedigree_fact generation builder
7. regional-type taxonomy
8. horse review contract
9. CURRENT / Reader 実装
10. PWA「血統詳細」modal contract

の順に進めます。

## Existing JRDB assets already confirmed

現行 JRDB には少なくとも次が存在します。

- UKC:
  - `horse_id`
  - `sire_name`
  - `dam_name`
  - `broodmare_sire_name`
  - `sire_line_code`
  - `broodmare_sire_line_code`
- RaceNote pedigree enrichment:
  - pedigree identity
  - sire / broodmare-sire historical context

BRDB はこれらを再取得・再実装せず、利用可能性と coverage を確認して再利用します。

## Bootstrap

新しい Chat / Work / Codex 作業では次を確認します。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. `horse-racing/brdb/README.md`
3. `.gpt/CONTEXT.md`
4. `.gpt/WORKFLOW.md`
5. `docs/BRDB_RRDB_INHERITANCE_v0_1.md`
6. 対象 task の current source / tests / contract
7. JRDB を読む場合は `horse-racing/jrdb/` の current docs/source
8. Parquet / DuckDB を扱う場合は `tools/data-storage/`

過去 chat の説明だけを current truth とせず、latest `main` を優先します。


## Phase 1 implementation

- `schema/brdb_pedigree_fact_schema_v0_1.sql`
- `src/brdb_parent_relation.py`
- `tests/test_brdb_parent_relation.py`
- `docs/BRDB_PEDIGREE_FACT_SCHEMA_v0_1.md`
- `docs/BRDB_UKC_PARENT_KEY_JOIN_VALIDATION_20261021.md`
- `docs/BRDB_UKC_DAM_BMS_INCONSISTENCY_AUDIT_20261021.md`

Parent name + birth year is treated as a candidate key only. Canonical relation resolution requires independent lineage/pedigree guards and fails closed on conflict.

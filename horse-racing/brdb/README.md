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

Status: **BOOTSTRAP / DESIGN**

まだ血統採点ロジック・canonical DB・CURRENT artifact は実装しません。

初期フェーズでは、

1. JRDB UKC / RaceNote pedigree 資産の棚卸し
2. canonical pedigree fact schema
3. lineage taxonomy
4. regional-type taxonomy
5. horse review contract
6. CURRENT / Reader 実装
7. PWA「血統詳細」modal contract

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

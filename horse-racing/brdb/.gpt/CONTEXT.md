# BRDB project context

## Status

Blood Review DB (BRDB) は bootstrap / design 段階です。

目的は、血統に関する固定条件一致馬を列挙することではなく、**対象レースの出走馬を血統専門ロジックで1頭ずつ review し、その結果と根拠を返すこと**です。

## Durable principles

1. `horse_id` は JRDB blood registration number を canonical identity とする。
2. horse name は表示用。identity fallback に使わない。
3. 血統事実と、BRDB独自の分類・解釈・採点を分離する。
4. 父/母/母父/祖先等の pedigree fact は source provenance を保持する。
5. 「日本型 / 米国型 / 欧州型」等の分類は事実列ではなく versioned taxonomy / derived classification として扱う。
6. score を出す場合、score だけでなく component / rationale / coverage / confidence を返す。
7. target field の全馬を review できる契約を基本とし、MATCH馬だけを抽出する設計にはしない。
8. consumer は Parquet / research tables を直接読まず、BRDB Reader / Review contract を読む。
9. JRDB fixed-width parser や共通 data-storage 処理を BRDB 側で再実装しない。
10. missing source / unsupported taxonomy / insufficient coverage は推測補完せず fail-closed する。
11. BRDB review は RaceNote / RRDB と独立した evidence lane とする。将来統合時も score の単純加算を既定にしない。
12. PWA の「血統詳細」は表示 surface。blood logic の正本にしない。

## RRDB inheritance baseline

RRDB から次の consumer architecture を引き継ぐ。

- stable CURRENT artifact
- validated `current.json` / manifest
- immutable Parquet relations
- read-only DuckDB Reader
- `horse_id` query
- name fallback=false
- generation / schema / logic version provenance
- storage detail と consumer contract の分離
- fail-closed validation

詳細は `../docs/BRDB_RRDB_INHERITANCE_v0_1.md`。

## Existing pedigree source baseline

JRDB UKC の current parser は以下を保持している。

- horse_id
- sire_name
- dam_name
- broodmare_sire_name
- sire / dam / broodmare-sire birth year
- sire_line_code
- broodmare_sire_line_code

RaceNote には pedigree identity と sire / broodmare-sire historical context の既存実装がある。

BRDB はまずこの coverage を利用し、3〜5代祖先・地域分類等で不足する情報だけを dedicated source として追加する。

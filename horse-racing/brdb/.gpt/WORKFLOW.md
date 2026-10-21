# BRDB GPT workflow

## Thread bootstrap

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. `horse-racing/brdb/README.md`
3. `.gpt/CONTEXT.md`
4. 本 `.gpt/WORKFLOW.md`
5. `docs/BRDB_RRDB_INHERITANCE_v0_1.md`
6. latest `main`
7. task-specific source / tests / contract

JRDB source を使う場合は `horse-racing/jrdb/` の latest current docs/source を追加で確認する。

## GitHub routing

repository 共通方針に従う。

- A: Read / Audit
- B: Git Change
- C: Pure Deterministic Execution
- D: Actions-Native Execution

BRDB の設計・Python・tests・schema・docs 等の通常変更は B を優先する。Secrets / immutable artifact publication / heavy rebuild が必要になった時点で D を導入する。

## Data-storage

Parquet / DuckDB を扱う場合は、最初に repository 共通 `tools/data-storage/` を確認する。

- Parquet generation
- query
- validation
- benchmark
- manifest materialization

を BRDB 内で重複実装しない。

## Pedigree source order

原則:

1. JRDB の canonical pre-existing pedigree data
2. BRDB dedicated immutable pedigree master
3. 明示的に許可・記録した external pedigree source
4. 推測補完は禁止

JRDB に存在する字段を Web から取り直して canonical fact を二重化しない。

## Review query boundary

将来の operational BRDB は RRDB と同様に、

```text
BRDB CURRENT
 -> Reader
 -> horse_id + target context
 -> one horse review result
```

を標準 consumer path とする。

PWA / RaceNote は canonical DB relation を直接 join しない。

## Development order

Phase 0:
- source inventory
- lineage / regional taxonomy design
- review output contract

Phase 1:
- canonical pedigree fact
- current pointer / manifest
- reader
- horse_id single query

Phase 2:
- first deterministic Blood Review
- field batch review
- audit / replay tests

Phase 3:
- PWA blood-detail modal handoff

Phase 4+:
- 3〜5 generation pedigree
- cross
- similar-horse search
- condition fit
- composite Blood Score

研究ロジックを operational contract へ昇格するときは、version / frozen rule / validation evidence を必須とする。

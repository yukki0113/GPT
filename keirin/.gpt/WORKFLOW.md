# keirin workflow

## Read first

1. repository .gpt/GITHUB_OPERATION_POLICY.md
2. repository .gpt/README.md
3. keirin/README.md
4. keirin/.gpt/CONTEXT.md
5. this file
6. Parquet / DuckDB処理を扱う場合は repository `tools/data-storage/README.md`

## Phase 0: source clearance -> one-month raw PoC

1. 候補sourceについて、公開可否ではなく automated acquisition / durable storage / paid prediction derivation の利用条件を確認する。
2. 許諾済みsourceだけを approved とする。未確認・禁止・要許可はapprovedにしない。
3. provider-specific discoveryで対象月の実在レースを列挙し、JSONL source listをfreezeする。
4. python -m keirin_historical.raw で原本を不変保存する。
5. manifestで requested / successful / failed / policy_blocked / bytes / SHAを監査する。
6. expected race countを別経路で照合し、coverageを計算する。
7. 1か月PASS後のみ年単位へ拡張する。

## Canonical Parquet / DuckDB execution preflight

Stage A以降のCanonical Parquet生成・再読込・validation・DuckDB queryは、repository共通 `tools/data-storage/` を汎用CRUD / Data Storage基盤として使用する。

```text
Canonical / Parquet / DuckDB task
-> Python 3.12要件を確認
-> tools/data-storage/README.md 確認
-> 既存 .venv-data-storage + check-deps
-> PASSなら再利用
-> absent / DEPENDENCY_MISSINGなら requirements からbootstrap
-> check-deps再実行
-> keirin_canonical正本module または共通CLIを実行
```

現在のPythonに `pyarrow` / `duckdb` が無いことだけを理由に「環境がない」として停止しない。venv作成・依存install自体が失敗または禁止される場合のみblockとして報告する。

共通Toolは汎用storage/query/validationを担当する。競輪固有のsource policy、Raw不変性、pre/post境界、provenance、coverage / leakage semanticsは競輪側の正本module/docsに保持する。

## Stop conditions

- source terms are unclear or prohibit the intended automated/commercial use
- robots/access controls are bypassed only by circumvention
- raw bytes differ at an existing immutable path
- monthly coverage cannot be independently audited

These conditions are fail-closed; do not silently switch sources.

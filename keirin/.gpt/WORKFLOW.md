# keirin workflow

## Read first

1. repository .gpt/GITHUB_OPERATION_POLICY.md
2. repository .gpt/README.md
3. keirin/README.md
4. keirin/.gpt/CONTEXT.md
5. this file

## Phase 0: source clearance -> one-month raw PoC

1. 候補sourceについて、公開可否ではなく automated acquisition / durable storage / paid prediction derivation の利用条件を確認する。
2. 許諾済みsourceだけを approved とする。未確認・禁止・要許可はapprovedにしない。
3. provider-specific discoveryで対象月の実在レースを列挙し、JSONL source listをfreezeする。
4. python -m keirin_historical.raw で原本を不変保存する。
5. manifestで requested / successful / failed / policy_blocked / bytes / SHAを監査する。
6. expected race countを別経路で照合し、coverageを計算する。
7. 1か月PASS後のみ年単位へ拡張する。

## Stop conditions

- source terms are unclear or prohibit the intended automated/commercial use
- robots/access controls are bypassed only by circumvention
- raw bytes differ at an existing immutable path
- monthly coverage cannot be independently audited

These conditions are fail-closed; do not silently switch sources.

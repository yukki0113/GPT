# JRDB GPT workflow

Last reviewed: 2026-09-13

## Thread restart bootstrap

会話量上限・スレッド分割・担当変更後は、作業開始前に次を確認する。

1. `README.md`
2. `.gpt/HANDOFF.md`
3. `.gpt/CONTEXT.md`
4. `.gpt/WORKFLOW.md`（この文書）
5. latest `main` HEAD
6. 対象subsystemのcurrent contract / audit / source / focused tests

過去handoff、古いIssue本文、日付付きaudit、固定SHAを単独でcurrent truthとしない。latest source + current contractが優先する。

## Standard preflight

1. `README.md` / HANDOFF / CONTEXTを確認。
2. 対象Pythonと対応README・schema/reference/contractを確認。
3. 2026 Raw（PACI / SED / HJC）を扱う場合は、`docs/JRDB_2026_Raw_Drive_Reference.md` を確認し、Google Drive上の既存Rawを最優先でresolveする。Drive inventoryを確認せずupstream全日付取得を開始しない。
4. 既存仕様を壊さない範囲で改修。
5. 可能な範囲で実行テスト / 回帰確認。
6. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
7. entrypoint / default / contract / subsystem boundaryが変わる場合、README / CONTEXT / HANDOFF / dedicated contractの更新要否を同時確認。
8. Gitへcommitし、以後Git版を正本とする。

## GitHub routing standard — 2026-09-10

JRDBをChatGPTから扱う場合、処理開始時に「GitHub Actions実行環境が本当に必要か」を判定し、次の4経路を標準とする。Issue駆動を既定経路にはしない。

### A. Read / Audit

GitHub repository/file/commit/issue/workflow/run/artifact metadata、コード検索、main内容、差分、SHA、RESULT状態などの確認はGitHubのread/search/fetch機能から直接行う。確認だけのためにIssueを作成しない。

### B. Git Change

source/test/docs/config等のUTF-8テキスト変更は、原則としてGitHubのcreate/update/delete機能で最新mainへ直接remote commitする。

変更前に次を確認する。

1. 最新main
2. 対象pathの存在
3. 現在内容 / blob SHA
4. 必要差分

変更後は対象fileをreadbackし、必要なfocused test / regressionをCまたは既存CIで確認する。`[gpt-git-update]` Issueは標準経路としない。

複数fileを連続更新する間にmainが進んだ場合は、次のwrite前にlatest mainと対象blobを再確認し、他commitを上書きしない。

### C. Pure Deterministic Execution

Secrets、Actions固有権限、Actions artifact chain、長時間・大容量runner、immutable freeze、正式監査runを必要としない決定的処理はChat実行環境のPython / shellで直接行う。

例:

- focused unit test / regression test
- 既取得artifactやSQLite/JSON/CSVの集計・監査
- SHA-256 / schema / row-count / integrity確認
- WATCH理由分解等のaudit-only処理
- 固定入力に対する変換・JOIN・レポート生成

同一処理を「Issueを投げるためだけ」にActionsへ送らない。

### D. Actions-Native Execution

以下はIssue / GitHub Actions経路を維持する。

- `JRDB_USER` / `JRDB_PASSWORD` 等のSecretsを使うJRDB取得・再構築
- upstream Actions artifactを正式入力としてchainする処理
- Full 2010-2025等の長時間・大容量build
- immutable freeze / publication / release等、GitHub runを不変証跡として必要とする処理
- 正式な監査run・再現性証跡としてrun ID / artifact / workflow RESULTを残す必要がある処理
- GitHub-hosted環境そのものを検証対象とする処理

Dを使う場合のみ、下記「Issue駆動Actionsのpreflight」を適用する。

### Edge Registry / EdgeDBでの標準適用

- Registry/source/docs/configの参照、Issue/run/artifact/SHA確認: **A**
- Edge Registry / v0.2 matcher / current facts / publicationのPython/test/docs/config修正: **B**
- 既存Registry artifactに対するWATCH/statistical audit、focused tests: **C**
- fixed current facts / matcher / newspaper adapterの決定的回帰: **C**
- 2025-only real-data smoke build（Raw取得を含む）: **D** — JRDB Secrets + artifact監査
- Full 2010-2025 Registry rebuild: **D** — Secrets + 長時間/大容量 + publication artifact
- PACI等の認証取得を伴うofficial current matching / artifact chain: **D**

Current operational boundary:

- ordinary `run_jrdb_edge_match_current_v0_2.py` defaultは `STANDARD`
- low-level `jrdb_edge_matcher_v0_2.py` defaultは意図的に `CONFIRMED_ONLY`
- SUGGESTIVEはRegistry ACTIVEへ昇格させない
- Performance / Valueを混ぜない
- consumerでEdge条件を再実装しない

詳細は `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md` を優先する。

### RaceNote / Newspaper / presentationでの標準適用

- RaceNote / Newspaper / PWA source、schema、contract、current publish metadataの確認: **A**
- reader-facing wording、adapter、merge、presentation、schema/docs/testのUTF-8修正: **B**
- fixed fixtureでのmerge、join、presentation、reader-language regression: **C**
- JRDB Secretsを使うPACI取得を含む正式RaceNote生成、immutable freeze、publication chain: **D**

責務境界:

- RaceNote converter / Reader Viewはpredictionを実装しない
- `racenote_prediction_presentation_v0_2.py` はfrozen decisionを説明するだけで印を再計算しない
- NewspaperはEdge matcher outputをconsumeし、Edge条件を再計算しない
- `jrdb_newspaper_edge_adapter.py` はdisplay boundaryでありmatching semanticsを変更しない
- reader-facing文言は `docs/RaceNote_Presentation_Comment_Contract_v0_2.md` を参照する

表示だけの修正でEdge threshold / eligibility / Registry status / prediction markを変えない。

### Post-race Analysis / Mart / Fact Liteでの標準適用

- current Analysis/Mart/Fact Liteの世代、schema、manifest、Drive/Git publication状態確認: **A**
- updater / builder / validator / docs / workflowのテキスト修正: **B**
- 既取得PACI/SED/Analysisを使う差分生成・validation・row count・integrity確認: 条件がCを満たす場合 **C**
- JRDB認証取得、formal artifact chain、Release/Pages publicationを伴う開催後正式更新: **D**

開催後は `Analysis update -> canonical save/validation -> Stats Mart refresh -> Fact Lite regenerate/validate/publish -> condition-summary PWA update` を一つの運用世代として扱う。Analysisだけを更新して後続PWAを旧世代に残さない。

### Ability / Debut Ability指数開発での標準適用

- Controller disposition、protocol、source、issue/run/artifact、main HEAD、SHA、既存監査結果の確認: **A**
- Ability / Debut Abilityのsource/test/docs/schema/config/workflow修正、protocol freeze文書の反映: **B**
- compile、focused pytest、fixture回帰、固定済み入力に対する決定的な集計・比較・SHA/整合性確認: **C**
- 既取得済みartifact/SQLite/JSON/CSVだけを入力とする追加metric、差分比較、診断レポート: **C**。正式run証跡が不要なら再度Actionsを起動しない。
- `jrdb_debut_ability_smoke_issue.yml` 相当のcompile + focused regressionは通常 **C** とし、smokeだけのためにIssueを作成しない。GitHub-hosted runner環境自体の検証が目的の場合のみ **D** を許可する。
- `JRDB_USER` / `JRDB_PASSWORD` でRawを取得して2010-2023/2025を再構築するAbility/Debut snapshot audit・coverage: **D** — Secrets + 長時間/大容量 +正式監査artifact。
- 2010-2023 Ability/Debut predictive comparison: **D** — 長時間・大容量のwalk-forward/model gridであり、Controller選択前のcanonical comparison evidenceとしてrun ID / artifactを固定する。
- 2024-2025 temporal holdout/confirmation: **D** — locked holdoutのimmutable confirmation evidenceとしてActions履歴を必要とする。
- canonical model/snapshotの正式再監査、再現性freeze、publication/releaseに相当するrun: **D**。

Controllerの設計判断やfreeze決定そのものを文書へ反映するだけなら **B** でよい。対して、その判断の根拠となるcanonical full-history build / comparison / holdout / audit evidenceを新規生成する場合は **D** とする。

RaceNote、EdgeDB、Eval、Training等のsubsystemは各専用contractを優先し、別subsystemのロジックを暗黙に混在させない。

## Documentation synchronization rule

次の変更は、sourceだけで終わらせずdocumentation impactを確認する。

- operational defaultの変更
- normal entrypointの変更
- source-of-truthの変更
- schema / join identity / leakage boundaryの変更
- Edge evidence semantics / serving profileの変更
- presentation responsibility boundaryの変更
- post-race generation chainの変更

役割分担:

- `README.md`: durable architecture / project entry
- `.gpt/HANDOFF.md`: new-thread bootstrap / current operational defaults
- `.gpt/CONTEXT.md`: persistent domain context
- `.gpt/WORKFLOW.md`: execution routing
- `docs/*Contract*.md`: subsystem-specific normative semantics
- dated audit: verification evidence, not permanent operational default

## Issue駆動Actionsのpreflight

- JRDB / RaceNote系を含むIssue起点Actionsは、Issue作成前にルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` を確認する。
- title prefix、必須body項目、upstream dependency、RESULT markerをworkflow / 対応docsから確認してからIssueを作成する。
- upstream `run_id` / `artifact_name` 等を使う場合、前工程RESULTが `status=success` であることを確認し、値を完全一致で転記する。推測値を使用しない。
- simple `key: value` bodyは `.gpt/tools/gpt_issue_preflight.py --protocol generic --required-key ...` で事前検証できる。
- retry時はfailed stepを確認し、必要に応じて最新 `main` / upstream RESULTからrequestを再構築する。同一requestの盲目的rerunを標準運用にしない。

## GitHubバイナリ正本の取得・更新

- GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` 等をChat / Workで実ファイルとして扱う必要がある場合、まず直接取得可能なGitHub/connector経路を確認する。
- 認証済み `gh` CLIを実行できる環境ではルート `.gpt/tools/gpt_git_binary_tool.py` を利用できるが、Issueを不要に経由させない。
- GitHub正本を実ファイルとして直接取得できない場合のみ、`[gpt-git-binary-read]` をフォールバックとする。
- Git管理対象バイナリを直接安全に更新できない場合のみ、`[gpt-git-binary-update]` をフォールバックとする。
- GitHub Connectorでバイナリを直接読めないことを理由に、GitHub正本が存在するファイルの再添付をユーザーへ依頼しない。
- 詳細はルート `.gpt/GIT_BINARY_TOOL.md`、`.gpt/GIT_BINARY_READ_ISSUE.md`、`.gpt/GIT_BINARY_UPDATE_ISSUE.md` を参照する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。

# GPT collaboration rules

このリポジトリをGPT / Workから扱う際の共通入口です。

1. 対象プロジェクトを特定する。
2. そのプロジェクトの `README.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md` を読む。
3. Git上の内容をソース正本として扱う。
4. 認証情報・有料原データ・大容量成果物をcommitしない。
5. 改修後はテスト、差分確認、必要なREADME更新を行ってからcommitする。
6. `legacy/` は明示的な依頼がない限り現行実装として使用しない。

## 共通Git搬送経路

- 通常テキストの更新: `.gpt/GIT_UPDATE_ISSUE.md` / `[gpt-git-update]`
- バイナリの更新: `.gpt/GIT_BINARY_UPDATE_ISSUE.md` / `[gpt-git-binary-update]`
- GitHub上のバイナリをChat / Workへ実ファイルとして取得: `.gpt/GIT_BINARY_READ_ISSUE.md` / `[gpt-git-binary-read]`
- バイナリread/updateの1コマンド操作: `.gpt/GIT_BINARY_TOOL.md` / `.gpt/tools/gpt_git_binary_tool.py`

認証済み `gh` CLIを実行できる環境では、バイナリread/updateは `.gpt/tools/gpt_git_binary_tool.py` を第一選択とし、Issue本文・Base64チャンク・artifact回収手順をGPTが手作業で組み立てない。

`gh` CLIを利用できないChat環境では、GitHub Connector + `[gpt-git-binary-read]` / `[gpt-git-binary-update]` をフォールバックとして使用する。

GitHub Connectorが `.xlsx` 等の中身を直接展開できない場合でも、GitHub `main` が正本として定義されているファイルについては、ユーザーへ再添付を依頼する前にバイナリread経路を使用する。

各プロジェクトのREADME / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` でGoogle Drive等の外部ストレージが正本と明示されている運用ファイルは、このGitバイナリ搬送ルールの対象外とする。外部正本を優先し、GitHubに残る旧コピーを最新と推定しない。

現在、Eval継続台帳 `Eval表集計・検証.xlsx` と競艇継続台帳 `競艇note販売運用台帳.xlsx` はGoogle Drive `GPT/ledger/` を正本とする。

## GitHub Actions実行時間監査

- job時間 / Private化時のGitHub-hosted runner分数の監査: `.gpt/GITHUB_ACTIONS_JOB_AUDIT.md`
- CLI: `.gpt/tools/github_actions_job_audit.py`

月次確認は `python .gpt/tools/github_actions_job_audit.py --month YYYY-MM` を基本とする。

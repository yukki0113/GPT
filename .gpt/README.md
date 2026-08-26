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

GitHub Connectorが `.xlsx` 等の中身を直接展開できない場合でも、GitHub `main` が正本として定義されているファイルについては、ユーザーへ再添付を依頼する前に `[gpt-git-binary-read]` 経路を使用する。

# GPT collaboration rules

このリポジトリをGPT / Workから扱う際の共通入口です。

1. 対象プロジェクトを特定する。
2. そのプロジェクトの `README.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md` を読む。
3. Git上の内容をソース正本として扱う。
4. 認証情報・有料原データ・大容量成果物をcommitしない。
5. 改修後はテスト、差分確認、必要なREADME更新を行ってからcommitする。
6. `legacy/` は明示的な依頼がない限り現行実装として使用しない。

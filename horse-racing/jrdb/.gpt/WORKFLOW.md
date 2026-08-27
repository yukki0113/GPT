# JRDB GPT workflow

1. `README.md` と本ディレクトリのCONTEXTを確認。
2. 対象Pythonと対応README・schema/referenceを確認。
3. 既存仕様を壊さない範囲で改修。
4. 可能な範囲で実行テスト / 回帰確認。
5. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
6. README/仕様変更が必要なら同時更新。
7. Gitへcommitし、以後Git版を正本とする。

## GitHubバイナリ正本の取得・更新

- GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` 等をChat / Workで実ファイルとして扱う必要がある場合、認証済み `gh` CLIを実行できる環境ではルート `.gpt/tools/gpt_git_binary_tool.py` を第一選択にする。
- GitHub正本を実ファイルとして取得する場合は `read` サブコマンドを使用し、Issue作成・artifact取得・SHA-256照合をツールへ任せる。
- Git管理対象バイナリを更新する場合は `update` サブコマンドを使用し、Base64化・Issueチャンク登録・確定コメント・完了待ちをツールへ任せる。
- `gh` CLIを利用できないChat環境では、取得は `[gpt-git-binary-read]`、更新は `[gpt-git-binary-update]` Issue経路をフォールバックとして使用する。
- GitHub Connectorでバイナリを直接読めないことを理由に、GitHub正本が存在するファイルの再添付をユーザーへ依頼しない。
- 詳細はルート `.gpt/GIT_BINARY_TOOL.md`、`.gpt/GIT_BINARY_READ_ISSUE.md`、`.gpt/GIT_BINARY_UPDATE_ISSUE.md` を参照する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。

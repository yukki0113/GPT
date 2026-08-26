# JRDB GPT workflow

1. `README.md` と本ディレクトリのCONTEXTを確認。
2. 対象Pythonと対応README・schema/referenceを確認。
3. 既存仕様を壊さない範囲で改修。
4. 可能な範囲で実行テスト / 回帰確認。
5. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
6. README/仕様変更が必要なら同時更新。
7. Gitへcommitし、以後Git版を正本とする。

## GitHubバイナリ正本の取得

- GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` 等をChat / Workで実ファイルとして解析する必要がある場合、GitHub Connectorで読めないことを理由にユーザーへ再添付を依頼しない。
- 共通の `[gpt-git-binary-read]` Issue経路を使用し、Actions artifactとして対象ファイルを回収する。
- 詳細はルート `.gpt/GIT_BINARY_READ_ISSUE.md` を参照する。
- artifact回収後は `manifest.json` のSHA-256と実ファイルを照合し、ファイル形式に応じたツールで解析する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。

# Boat racing GPT workflow

1. READMEと対象ツールのdocsを確認。
2. 公式サイト側の変更に注意し、既存CSV互換性を維持する。
3. 改修後は実日付または保存済みfixtureで回帰確認。
4. キャッシュ、日次成果物、ログ、台帳をcommitしない。
5. Pythonと対応READMEを同時に更新してcommitする。

## Chatでの日次取得実行

- まずGitHub `main` の `boat-racing/` を正本として確認する。
- Chat側の実行環境から公式サイトへ直接通信できる場合は、正本Pythonをそのまま実行する。
- 直接通信が利用できない場合は、GitHub Actionsの常設手動Workflowを正式な代替実行経路として使用する。
- 出走表取得は `.github/workflows/boatrace_racelist_manual.yml` を使用する。
- Actionsでも `main` の `boat-racing/src/fetch_boatrace_racelist.py` と `boat-racing/requirements.txt` を使用し、独自ロジックを別実装しない。
- 実行成果物はartifactから回収し、取得状況・ログ・CSV整合性を確認してから日常成果物を受け渡す。
- 日次成果物はGitへcommitしない。

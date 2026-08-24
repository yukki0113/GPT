# Boat racing Git migration status

Updated: 2026-08-24
Status: COMPLETE

## Gitへ移行済み

- プロジェクトREADME
- `.gpt/CONTEXT.md`
- `.gpt/WORKFLOW.md`
- `.gpt/MIGRATION_STATUS.md`
- `requirements.txt`
- `requirements_直前情報取得.txt`
- `docs/README_出走表取得.md`
- `docs/README_直前情報取得.md`
- `docs/README_公式結果取得.md`
- `docs/出走表取得依頼_定型作業.txt`
- `docs/直前情報取得依頼_定型作業.txt`
- `docs/結果照合取得依頼_定型作業.txt`
- `src/fetch_boatrace_racelist.py`
- `src/fetch_boatrace_pre_race_info.py`
- `src/fetch_boatrace_results.py`
- `.github/workflows/boatrace_racelist_manual.yml`
- `.github/workflows/boatrace_results_manual.yml`

## 移行状態

競艇取得運用に必要なPython本体、README、GPT向け運用資料、定型作業手順、Python依存関係はGitへ移行済み。

今後は `yukki0113/GPT` の `main` ブランチ配下 `boat-racing/` を正本として参照する。
過去の添付ZIPやWorkスレッド内の一時作業領域は、Git正本の代わりとして使用しない。

作業開始時は、少なくとも以下を確認する。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/WORKFLOW.md`
4. `boat-racing/.gpt/MIGRATION_STATUS.md`
5. 対象作業の `docs/` と `src/` の対応ファイル
6. Actions代替経路を使用する場合は対応する `.github/workflows/boatrace_*_manual.yml`

## Python依存関係

取得ツール全体では `boat-racing/requirements.txt` を使用する。

直前情報取得を単独で扱う場合は、専用の `boat-racing/requirements_直前情報取得.txt` も使用できる。

現在の取得ツール3本で必要な外部パッケージは以下。

- `requests`
- `beautifulsoup4`
- `lxml`

標準ライブラリのみの依存は requirements ファイルへ記載しない。

## GitHub Actions代替実行経路

Chat実行環境からBOAT RACE公式サイトへ直接通信できない、または通信が不安定な場合は、GitHub Actionsの常設 `workflow_dispatch` Workflowを正式な代替実行経路として使用する。

現時点の常設Workflow：

- 出走表取得: `.github/workflows/boatrace_racelist_manual.yml`
- 結果取得・予想照合: `.github/workflows/boatrace_results_manual.yml`

Actions側でもGit main上の正本Pythonと `boat-racing/requirements.txt` をそのまま使用する。
成果物はartifactへ保存し、Chat側で回収・監査する。

結果取得では日次の事前予想CSVをGitへcommitせず渡すため、CSVをgzip圧縮＋Base64化して `workflow_dispatch` 入力へ渡し、Runnerの一時領域へ復元する。

GitHub連携上、Chatから `workflow_dispatch` 自体を起動できない場合はGitHub Actions画面から手動起動し、その後のrun・artifact確認をChat側で行う。

## Git対象外

以下は引き続きGit管理対象外とする。

- 日次CSV
- HTMLキャッシュ
- 実行ログ
- Actionsの日次artifact内容
- Excel運用台帳
- 予想・結果の運用成果物

これらはGit正本のソース・仕様の代わりとして参照しない。

## 運用上の注意

- ソース参照・改修時は、まずGitの `main` 最新状態を確認する。
- 公式サイト側の構造変更により改修が必要な場合は、既存CSV互換性を維持する。
- 改修時はPythonと対応READMEを同時に更新する。
- Workflow変更時も正本PythonのCLI互換性を確認する。
- 可能な限り実日付または保存済みfixtureで回帰確認する。
- 日次CSV、ログ、キャッシュ、台帳はcommitしない。

# Boat racing Git migration status

Updated: 2026-08-24

## Gitへ移行済み

- プロジェクトREADME
- `.gpt/CONTEXT.md`
- `.gpt/WORKFLOW.md`
- `docs/README_出走表取得.md`
- `docs/README_直前情報取得.md`
- `docs/README_公式結果取得.md`

## 移行元ZIPには存在するがGit投入未完了

以下3本は容量が大きく、GitHub連携経由で内容欠落を起こさないため未投入。添付ZIP `競艇予想_20260824.zip` を移行元正本として扱う。

- `src/fetch_boatrace_racelist.py`
- `src/fetch_boatrace_pre_race_info.py`
- `src/fetch_boatrace_results.py`

これらが投入されるまでは、Gitだけで競艇取得運用を再現できない。

## Git対象外

- 日次CSV
- HTMLキャッシュ
- 実行ログ
- Excel運用台帳
- 予想・結果の運用成果物

## 運用上の注意

作業開始時に本ファイルを確認すること。未投入PythonをGit上に存在するものとして推測・再生成しない。移行完了後、本ファイルを `COMPLETE` 状態へ更新する。

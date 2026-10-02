# RaceNote Forward Settlement Evidence

前向き検証 Forecast の結果・精算証跡置き場。

- 1日1ディレクトリ: `YYYYMMDD/`
- 原則 `result.json` / `settlement.json`
- 結果取得は `jrdb_result_query_runner.py` を標準入口とする
- JRDB Raw の複製や巨大中間ファイルは置かない

詳細は `docs/racenote/FORWARD_VALIDATION_RUNBOOK_v0_1.md` を参照。

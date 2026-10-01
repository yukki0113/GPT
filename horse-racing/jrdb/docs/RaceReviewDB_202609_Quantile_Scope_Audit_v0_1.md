# RRDB 9月分析：分位母集団の照合・感度監査

Status: PASS / DESCRIPTIVE_SENSITIVITY_ONLY  
Date: 2026-10-01  
Canonical analysis commit: `08dad98029f39fd7586faf65cd2c82c263a6516a`

全3,137エントリーの台帳は既存mainの正本を保持した。別実行の全頭台帳と、血統登録番号・前走key・タイム・pace percentile・4角位置・払戻・オッズ・人気を3,137行照合し、完全一致（浮動小数点許容1e-12）を確認した。重複・SED結合・未来前走の問題ではない。

数値差は分位を計算する母集団による。保存済み主分析は平地・実出走・前走履歴あり2,590頭の分位。作業指示の「9月previous usable runners全体」を全entryに適用すると2,686頭の分位になる。どちらも精算母集団は同じ平地実出走2,590頭で、取消や障害へ投資を足しているわけではない。

| 分位母集団 | N | performance q80 | performance q90 |
|---|---:|---:|---:|
| ALL_ENTRY_USABLE | 2686 | -0.066239316239 | 0.194444444444 |
| PRIMARY_FLAT_STARTED_USABLE | 2590 | -0.055555555556 | 0.211388888889 |

| quantile_scope              | signal                |   n |   place_hits |   place_hit_rate_pct |   place_roi_pct |
|:----------------------------|:----------------------|----:|-------------:|---------------------:|----------------:|
| ALL_ENTRY_USABLE            | TIME_TOP20            | 531 |          190 |               35.782 |          89.849 |
| ALL_ENTRY_USABLE            | FINISH_GE4_TIME_TOP20 | 193 |           48 |               24.87  |         100.466 |
| ALL_ENTRY_USABLE            | FINISH_GE6_TIME_TOP20 |  99 |           21 |               21.212 |         118.384 |
| ALL_ENTRY_USABLE            | FRONT_HIGH_TIME_TOP20 |  73 |           27 |               36.986 |          95.89  |
| ALL_ENTRY_USABLE            | REAR_HIGH_TIME_TOP20  |  13 |            2 |               15.385 |          20     |
| ALL_ENTRY_USABLE            | TIME_TOP10            | 266 |           98 |               36.842 |          74.474 |
| ALL_ENTRY_USABLE            | FINISH_GE6_TIME_TOP10 |  38 |            6 |               15.789 |          52.632 |
| PRIMARY_FLAT_STARTED_USABLE | TIME_TOP20            | 519 |          188 |               36.224 |          89.865 |
| PRIMARY_FLAT_STARTED_USABLE | FINISH_GE4_TIME_TOP20 | 184 |           47 |               25.543 |         100.163 |
| PRIMARY_FLAT_STARTED_USABLE | FINISH_GE6_TIME_TOP20 |  94 |           20 |               21.277 |         114.468 |
| PRIMARY_FLAT_STARTED_USABLE | FRONT_HIGH_TIME_TOP20 |  73 |           27 |               36.986 |          95.89  |
| PRIMARY_FLAT_STARTED_USABLE | REAR_HIGH_TIME_TOP20  |  13 |            2 |               15.385 |          20     |
| PRIMARY_FLAT_STARTED_USABLE | TIME_TOP10            | 259 |           97 |               37.452 |          75.985 |
| PRIMARY_FLAT_STARTED_USABLE | FINISH_GE6_TIME_TOP10 |  38 |            6 |               15.789 |          52.632 |

作業指示の全usable分位では、前走6着以下×top20は99頭・21的中・118.38%。主分析の平地分位では94頭・20的中・114.47%。前走4着以下×top20も193頭・100.47%と184頭・100.16%の差がある。top10敗戦群はいずれも38頭・52.63%で、top20が優る方向は変わらない。

タイムtop20全体はどちらも約89.85%。前傾前受け＋time20は両方73頭・95.89%。後傾後方＋上がり90は分位performanceを使わないため43頭・134.88%から変わらない。したがって主結論は維持される。

このCSVには両母集団について、time/raw oppositionの5分位、前走着順×タイム5分位、単勝オッズ帯・人気帯・前走着順帯を追加保存した。全usable分位を省略せず、既存主分析との差を追跡できる。

いずれも月内の記述分位であり、各target日に既知の運用閾値・時系列OOS実績ではない。target結果列を99999に置き換えても全閾値が不変であることを機械検証した。収益を見て閾値を調整していない。

高配当について、前走6着以下×all-entry top20の最大払戻1,810円は総払戻の15.44%。後傾後方＋上がり90の最大1,390円は23.97%。元の払戻を主指標へ残すが、後者の利益1,500円への寄与は大きく、独立した再現性は2024–2025の固定閾値OOSで確認する。正式S/Aルールへ昇格していない。

成果物：

- `analysis/tmp/rrdb_202609_quantile_scope_sensitivity.csv`
- `analysis/tmp/rrdb_202609_quantile_scope_audit.json`
- `src/audit_rrdb_time_pace_quantile_scope.py`

既存全頭台帳・集計・builder/testを上書きせず、同じデータの別コピーをGitへ重複保存しない。

```bash
python horse-racing/jrdb/src/audit_rrdb_time_pace_quantile_scope.py --ledger horse-racing/jrdb/analysis/tmp/rrdb_202609_all_runner_research_ledger.parquet --output-dir horse-racing/jrdb/analysis/tmp --canonical-commit 08dad98029f39fd7586faf65cd2c82c263a6516a
```

`--independent-ledger`を渡すと別生成台帳とのkey/feature/settlement照合も行う。省略時は照合NOT_RUNを明記する。入力正本SHA・集計SHA・source SHA・分位値は監査JSONに保存した。

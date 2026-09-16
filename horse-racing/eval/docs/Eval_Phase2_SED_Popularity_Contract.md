# Phase2 SED 人気順位バックフィル契約

## 正本と対象

Phase2の結果時点データは、JRDB公式 SED Raw を共通パーサー `jrdb_raw.Parser.sed` で読み、`Phase2_SED補完` を経由して `Phase2_全馬研究` へ接続する。

`確定単勝人気順位` は SED の公式フィールド（1始まり181、長さ2）だけを使用する。最終単勝オッズの並べ替えや手作業の外部照会で人気順位を推定してはならない。

## リリースガード

`src/backfill_phase2_sed.py` は、次のすべてを監査JSONへ出力する。

- `final_win_popularity_expected`
- `final_win_popularity_filled`
- `final_win_popularity_missing`
- `final_win_popularity_fill_rate`

対象は「SED異常区分が `0` かつ最終単勝オッズが正」の通常確定走者である。この対象で人気順位が欠損した場合、監査statusは `success` とせず終了コードも非0にする。取消・競走除外などの非通常走者は対象外とし、公式値が `99` の場合もそのまま保持する。

## 2026-09-12 / 2026-09-13 修復記録

公式SEDから `Phase2_SED補完` の人気順位を再投入し、`Phase2_全馬研究` の参照列へ復元した。

| 開催日 | 通常確定走者（expected） | filled | missing | fill rate |
|---|---:|---:|---:|---:|
| 2026-09-12 | 315 | 315 | 0 | 100% |
| 2026-09-13 | 313 | 313 | 0 | 100% |
| 合計 | 628 | 628 | 0 | 100% |

## Forward境界

`P2_FWD_20260919_WIN_E85_R1_O_LT3` は 2026-09-19 開始であり、2026-09-12および2026-09-13の探索参考レースをForward累積へ含めない。Forward中の条件変更は既存IDの修正ではなく、新規検証IDとして登録する。

# R3 新馬戦 4R 実データ受入記録（2026-11-24）

## 判定

`PASS_R3_TECHNICAL_COMMON_EVIDENCE_RESEARCH` — R3 の共通 Evidence 技術契約について対象4R・42頭の結合・検証を完了。研究限定。R4、予測安全性、本番昇格を承認しない。

| 対象日 | race key | 頭数 | BRDB観測 | restricted refs | 接続契約 |
|---|---|---:|---:|---:|---|
| 2026-06-13 | 05263305 | 7 | 105 | 311 | pre-D4 v0.2 base-only |
| 2026-06-13 | 09263306 | 13 | 195 | 641 | pre-D4 v0.2 base-only |
| 2026-11-15 | 05265404 | 12 | 180 | 407 | original R3 / M7 v0.3 |
| 2026-11-15 | 05265405 | 10 | 150 | 486 | original R3 / M7 v0.3 |
| 合計 | | 42 | 630 | 1845 | |

- 固定PACI、R1/R2/旧R3の入力と全馬 identity / 予定騎手 / 取消フラグを照合。JPDB evidence 2142件は変更なし。
- 4Rの父・母父の観測は一般出走母集団。新馬戦専用成績と混同しない。配合・近親・D4は AS_OF_UNVERIFIED で数値レーンに昇格しない。D4 refs は11月の111件のみ。
- 6月2Rは D3/D4 の 2026-11-02 時点制約以前のため、真正な BRDB v0.2 を使う追加契約 `racenote-independent-evidence-base-only-v0.1-candidate` と専用 preview を作成。D4未提供を明示し、v0.3を捏造しない。元のR3/M7契約・スキーマ・Readerは変更しない。
- 4Rすべて詳細/preview schema 検証、独立照合、2回生成バイト一致。R3回帰テスト25件PASS（既存18 + 新規7）。共通承認済み DuckDB wheel 2.0.1 を使用。スキーマ検証は既存環境の jsonschema を利用。
- 個馬明細は Git に載せない。Library `/JPDB/R3/JPDB_R3_NEWCOMER_20261124_private_acceptance.zip` 保存、再取得バイト一致。集計・hash は同名 JSON を参照。

## 再現

11月分: `racenote_r3_newcomer_replay.py` の固定manifestと既存M7 v0.3経路。6月分: `python horse-racing/jrdb/src/racenote_r3_brdb_base_only.py --manifest <private manifest> --manifest-sha256 <independently pinned SHA> --output-dir <new directory>`。いずれも既存BRDB集計器と固定PACIを使用。アーカイブの絶対パスは再実行環境に合わせ、manifestを再生成してSHAを別途固定する。

## R4への境界

BRDB B5 は別日（11月1日4R55頭）で受入済みだが、この4Rの新馬戦専用観測には転用していない。B5対象4Rとの接続検証は新馬戦専用レーンとして別途必要。今回のPASSはR3共通Evidenceの技術受入のみ。R4 Shadow 開始、本番Reader、Freeze、Confidence、PWA、CURRENT、予測安全性を変更しない。

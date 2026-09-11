# 競艇note販売運用台帳 ForwardTrial専用分析台帳

## 目的

`ForwardTrial_Ver0.1` の全レース、真正forward、掲載群を混在させず、結果参照前に固定された予想・販売選別と公式結果を監査可能な形で蓄積する。予想仕様や販売ルールの変更を行う仕組みではなく、検証・集計専用とする。

## 正本と対象

- 正本: Googleスプレッドシート `競艇note販売運用台帳`
- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- 専用タブ: `FT2_` 接頭辞の13タブ
- 初回対象: 2026-09-01、09-02、09-03、09-05、09-06、09-07、09-08（336R）
- 時刻基準: `Asia/Tokyo`

## 入力と結合

必須入力は、日次の公式出走表、事前予想、2連単1点販売選別、公式結果、BOAT RACE公式開催メタの5種類。予想根拠明細は任意の監査資料とする。主キーは `日付×会場×R×仕様版` で、同一キーはupsertし重複を作らない。開催メタは開催日×会場をキーに開催名、グレード大分類、公式source URLをFreezeする。

入力日付、対象会場の全R（各会場12R）、会場集合、キー一意性、仕様版、freeze日時、結果キーのいずれかが不整合ならfail-closedで停止する。結果から予想・販売選別・freezeを補完または変更しない。

## 集計層

- Raw: 仕様上のForwardTrial対象
- Genuine: Rawかつ公式締切予定日時より前にfreeze済み
- Published: Genuineかつ掲載区分が有料または無料

CSVのみはRaw/Genuineの対象になり得るがPublishedには含めない。freezeが締切予定日時以後のレースは `CONTAMINATED` とし、データを削除せず真正forward集計から除外する。

回収額は的中払戻のみとし、返還額は別列で保持する。利益は `回収額 + 返還額 - 投資額`、回収率は集計目的に合わせて的中払戻ベースで算出する。

## タブ構成

1. `FT2_README`
2. `FT2_取込管理`
3. `FT2_開催メタ`
4. `FT2_全R明細`
5. `FT2_日別集計`
6. `FT2_会場別集計`
7. `FT2_会場日目別集計`
8. `FT2_グレード別集計`
9. `FT2_判定構造別集計`
10. `FT2_販売選別検証`
11. `FT2_Score検証`
12. `FT2_Freeze監査`
13. `FT2_ダッシュボード`
14. `FT2_集計監査`

## 初回固定受入値

| 指標 | 件数 | 的中 | 投資 | 回収 |
|---|---:|---:|---:|---:|
| 全R | 336 | - | - | - |
| Raw | 81 | 29 | 8,100円 | 7,910円 |
| Genuine | 78 | 29 | 7,800円 | 7,910円 |
| Published | 60 | 23 | 6,000円 | 6,140円 |

追加の固定値は、Genuine利益+110円・回収率101.4%、有料39R/19的中/3,900円→4,930円、無料21R/4的中/2,100円→1,210円、CSVのみ18R/6的中/1,800円→1,770円、構造KPI 59/78→38/59→29/38、締切後freeze 3R（2026-09-03徳山1〜3R）とする。

## 実装

`src/forward_trial_analysis_import.py` がCSV検証、正規化、真正性判定、全13タブの値生成、固定受入値検査を担当する。Google認証・シート書込みは持たせず、生成結果を確認後にGoogle Sheets API / Google Drive Connectorで同一正本へ反映する。

日次完了はトランザクション境界として扱う。全R明細upsertだけでは `明細取込済` とし、Atomic Aggregate Set（FT2_日別・会場別・会場日目別・グレード別・判定構造別・販売選別検証・Score検証・Freeze監査・ダッシュボード）を全明細から同一処理内で再生成する。`FT2_集計監査` は各9タブについて、stable key集合から決定する `aggregate_generation_id`、source raw/genuine/contaminated/exacta件数、max対象日、出力行数、検証状態を記録する。9行の世代・母数・max対象日がすべて一致し、既存販売台帳クロスチェックと回帰値検証も成功した場合のみ `完了` とする。1枚でも不一致なら `集計不整合`、途中例外は `エラー`、公式grade未解決は `未分類 + 要確認` とする。再実行時もstable key upsertと全再生成により件数・投資・回収を二重加算しない。

`src/fetch_boatrace_event_meta.py` はBOAT RACE公式日別レース一覧だけを参照し、開催名と `一般/G2/G1/SG/その他/未分類` をFreezeする。G1/SGを除外せず、グレード別集計に少数標本警告を付ける。

~~~bash
python boat-racing/src/forward_trial_analysis_import.py \
  --manifest source_manifest.json \
  --output forward_trial_analysis.json
python -m unittest discover -s boat-racing/tests -v
~~~
